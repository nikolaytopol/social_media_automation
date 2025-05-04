# processor/workflows/live_repost_workflow.py
import os
import asyncio
import time
import logging
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from processor.openai_utils import OpenAIUtils
from processor.deepseek_utils import DeepSeekUtils

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('LiveRepostWorkflow')

class LiveRepostWorkflow:
    def __init__(self, config):
        """
        Initialize with configuration from workflow_manager.
        
        Args:
            config (dict): Configuration with sources, destinations, 
                          filter_prompt, mod_prompt, etc.
        """
        self.config = config
        self.source_channels = [src['name'] for src in config['sources'] if src['type'] == 'telegram']
        self.target_channels = [dest['name'] for dest in config['destinations'] if dest['type'] == 'telegram']
        self.filter_prompt = config.get('filter_prompt', '')
        self.mod_prompt = config.get('mod_prompt', '')
        self.duplicate_check = config.get('duplicate_check', False)
        self.preserve_files = config.get('preserve_files', False)
        
        # Create media directory if it doesn't exist
        self.media_dir = os.path.join(os.getcwd(), 'data', 'media')
        os.makedirs(self.media_dir, exist_ok=True)
        
        # Telegram client setup with error handling
        try:
            api_id_str = os.getenv('TELEGRAM_API_ID')
            if not api_id_str:
                logger.error("TELEGRAM_API_ID environment variable is missing!")
                raise ValueError("TELEGRAM_API_ID environment variable is required")
            
            self.api_id = int(api_id_str)
            self.api_hash = os.getenv('TELEGRAM_API_HASH')
            if not self.api_hash:
                logger.error("TELEGRAM_API_HASH environment variable is missing!")
                raise ValueError("TELEGRAM_API_HASH environment variable is required")
            
            self.session_string = os.getenv('TELEGRAM_SESSION_STRING')
            if not self.session_string:
                logger.error("TELEGRAM_SESSION_STRING environment variable is missing!")
                raise ValueError("TELEGRAM_SESSION_STRING environment variable is required")
            
            self.client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash,
                connection_retries=-1,
                auto_reconnect=True
            )
        except Exception as e:
            logger.error(f"Error setting up Telegram client: {e}")
            raise
        
        # Initialize AI provider based on configuration
        ai_provider_config = config.get('ai_provider', {'name': 'openai'})
        ai_provider_name = ai_provider_config.get('name', 'openai').lower()
        ai_model = ai_provider_config.get('model', None)
        
        try:
            if ai_provider_name == 'deepseek':
                self.ai_utils = DeepSeekUtils()
                logger.info(f"Using DeepSeek for AI processing with model: {ai_model}")
            else:
                # Default to OpenAI
                self.ai_utils = OpenAIUtils()
                logger.info(f"Using OpenAI for AI processing with model: {ai_model}")
        except Exception as e:
            logger.error(f"Error initializing AI provider: {e}")
            raise
        
        # State tracking
        self.running = False
        self.processed_messages = set()  # For duplicate checking

    async def start(self):
        """Start the live reposting workflow."""
        try:
            self.running = True
            
            @self.client.on(events.NewMessage(chats=self.source_channels))
            async def on_new_message(event):
                if not self.running:
                    return
                await self.handle_new_message(event)
                
            @self.client.on(events.Album(chats=self.source_channels))
            async def on_new_album(event):
                if not self.running:
                    return
                await self.handle_new_album(event)
                
            # Connect and run
            await self.client.start()
            logger.info(f"Started monitoring channels: {self.source_channels}")
            
            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in workflow: {e}")
            self.running = False
    
    async def stop(self):
        """Stop the workflow."""
        self.running = False
        if self.client.is_connected():
            await self.client.disconnect()
        logger.info("Workflow stopped")
    
    async def handle_new_message(self, event):
        """Process a single new message."""
        try:
            # Skip if part of an album (will be handled by album handler)
            if event.message.grouped_id:
                return
                
            message_id = event.message.id
            chat_id = event.chat_id
            message_key = f"{chat_id}_{message_id}"
            
            # Skip if already processed (for duplicate checking)
            if self.duplicate_check and message_key in self.processed_messages:
                logger.info(f"Skipping duplicate message {message_key}")
                return
                
            message_text = event.message.message or ""
            logger.info(f"Processing message: {message_text[:100]}")
            
            # Add debugging for filter prompt
            if self.filter_prompt:
                logger.info(f"Using filter: {self.filter_prompt[:50]}...")
                try:
                    passes = await self.ai_utils.filter_content(message_text, self.filter_prompt)
                    logger.info(f"Filter result: {passes}")
                    if not passes:
                        logger.info(f"Message filtered out: {message_text[:50]}...")
                        return
                    logger.info("Message passed filter ✓")
                except Exception as e:
                    logger.error(f"Filter error: {e}, allowing message to pass")
                    # On error, continue processing
                    
            # Modify text if configured
            if self.mod_prompt:
                logger.info(f"Modifying text with prompt: {self.mod_prompt[:50]}...")
                new_text = await self.ai_utils.modify_content(message_text, self.mod_prompt)
                logger.info(f"Original: {message_text[:50]}... -> Modified: {new_text[:50]}...")
            else:
                new_text = message_text
                
            # Process media if any
            media_paths = []
            if event.message.media:
                try:
                    timestamp = int(time.time())
                    media_path = await event.message.download_media(
                        file=os.path.join(self.media_dir, f"{timestamp}_{event.message.id}")
                    )
                    if media_path:
                        logger.info(f"Downloaded media to: {media_path}")
                        media_paths.append(media_path)
                except Exception as e:
                    logger.error(f"Error downloading media: {e}")
                    
            # Post to all target channels
            success = False
            for target in self.target_channels:
                result = await self.post_to_channel(new_text, media_paths, target)
                if result:
                    success = True
                    
            # Mark as processed for duplicate checking
            if success and self.duplicate_check:
                self.processed_messages.add(message_key)
                
            # Clean up downloaded media if not preserving
            if not self.preserve_files:
                for path in media_paths:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            logger.info(f"Cleaned up media file: {path}")
                        except Exception as e:
                            logger.error(f"Error removing media file {path}: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def handle_new_album(self, event):
        """Process an album of messages."""
        try:
            if not event.messages:
                return
                
            album_id = event.messages[0].grouped_id
            chat_id = event.chat_id
            album_key = f"{chat_id}_{album_id}"
            
            # Skip if already processed (for duplicate checking)
            if self.duplicate_check and album_key in self.processed_messages:
                logger.info(f"Skipping duplicate album {album_key}")
                return
                
            # Use text from first message
            main_text = event.messages[0].message or ""
            logger.info(f"Processing new album with text: {main_text[:50]}...")
            
            # Check filter if configured
            if self.filter_prompt:
                logger.info(f"Applying filter to album with prompt: {self.filter_prompt[:50]}...")
                passes = await self.ai_utils.filter_content(main_text, self.filter_prompt)
                if not passes:
                    logger.info(f"Album filtered out: {main_text[:50]}...")
                    return
                logger.info("Album passed filter")
                    
            # Modify text if configured
            if self.mod_prompt:
                logger.info(f"Modifying album text with prompt: {self.mod_prompt[:50]}...")
                new_text = await self.ai_utils.modify_content(main_text, self.mod_prompt)
                logger.info(f"Original: {main_text[:50]}... -> Modified: {new_text[:50]}...")
            else:
                new_text = main_text
                
            # Download all media
            media_paths = []
            timestamp = int(time.time())
            
            for idx, msg in enumerate(event.messages):
                if msg.media:
                    try:
                        media_path = await msg.download_media(
                            file=os.path.join(self.media_dir, f"{timestamp}_{album_id}_{idx}")
                        )
                        if media_path:
                            logger.info(f"Downloaded album media to: {media_path}")
                            media_paths.append(media_path)
                    except Exception as e:
                        logger.error(f"Error downloading album media: {e}")
                        
            # Post to all target channels
            success = False
            for target in self.target_channels:
                result = await self.post_to_channel(new_text, media_paths, target)
                if result:
                    success = True
                    
            # Mark as processed for duplicate checking
            if success and self.duplicate_check:
                self.processed_messages.add(album_key)
                
            # Clean up downloaded media if not preserving
            if not self.preserve_files:
                for path in media_paths:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            logger.info(f"Cleaned up album media file: {path}")
                        except Exception as e:
                            logger.error(f"Error removing media file {path}: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing album: {e}")
    
    async def post_to_channel(self, text, media_paths, channel):
        """Post content to a Telegram channel."""
        try:
            if media_paths:
                # Send as a single message or as an album
                if len(media_paths) == 1:
                    await self.client.send_file(
                        channel, 
                        media_paths[0], 
                        caption=text,
                        parse_mode='md'
                    )
                else:
                    # For multiple files, send as an album
                    await self.client.send_file(
                        channel, 
                        media_paths, 
                        caption=text,
                        parse_mode='md'
                    )
            else:
                await self.client.send_message(
                    channel, 
                    text,
                    parse_mode='md'
                )
                
            logger.info(f"Successfully posted to channel: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Error posting to channel {channel}: {e}")
            return False