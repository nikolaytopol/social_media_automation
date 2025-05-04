# processor/workflows/history_repost_workflow.py
import os
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from processor.openai_utils import OpenAIUtils

class HistoryRepostWorkflow:
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
        self.start_date = config.get('start_date', None)
        
        if self.start_date and isinstance(self.start_date, str):
            # Convert string date to datetime object
            self.start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
        
        # Telegram client setup
        self.api_id = int(os.getenv('TELEGRAM_API_ID'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.session_string = os.getenv('TELEGRAM_SESSION_STRING')
        self.client = TelegramClient(
            StringSession(self.session_string),
            self.api_id,
            self.api_hash
        )
        
        # OpenAI for filtering and text modification
        self.openai_utils = OpenAIUtils()
        
        # State tracking
        self.running = False

    async def start(self):
        """Run the history reposting workflow."""
        self.running = True
        
        await self.client.start()
        print(f"[HistoryRepostWorkflow] Starting history repost for channels: {self.source_channels}")
        
        # Process each source channel
        for source in self.source_channels:
            if not self.running:
                break
            await self.process_channel_history(source)
            
        await self.client.disconnect()
        self.running = False
        print("[HistoryRepostWorkflow] Completed")
    
    async def stop(self):
        """Stop the workflow."""
        self.running = False
        await self.client.disconnect()
        print("[HistoryRepostWorkflow] Stopped")
    
    async def process_channel_history(self, channel_id):
        """Process all messages from a channel's history."""
        # Group messages by album
        grouped_messages = await self.gather_and_group_messages(channel_id)
        
        # Process each group
        for group_id, messages in grouped_messages:
            if not self.running:
                break
                
            # Get text from first message
            main_text = messages[0].message or ""
            
            # Check filter if configured
            if self.filter_prompt:
                passes = await self.openai_utils.filter_content(main_text, self.filter_prompt)
                if not passes:
                    print(f"[HistoryRepostWorkflow] Message filtered out: {main_text[:50]}...")
                    continue
                    
            # Modify text if configured
            if self.mod_prompt:
                new_text = await self.openai_utils.modify_content(main_text, self.mod_prompt)
            else:
                new_text = main_text
                
            # Download all media
            media_paths = []
            for msg in messages:
                if msg.media:
                    try:
                        path = await msg.download_media()
                        if path:
                            media_paths.append(path)
                    except Exception as e:
                        print(f"[HistoryRepostWorkflow] Error downloading media: {e}")
                        
            # Post to all target channels
            for target in self.target_channels:
                await self.post_to_channel(new_text, media_paths, target)
                
            # Clean up downloaded media
            for path in media_paths:
                if os.path.exists(path):
                    os.remove(path)
                    
            # Add a small delay between posts
            await asyncio.sleep(1)
    
    async def gather_and_group_messages(self, channel_id):
        """Fetch messages from a channel and group them by album."""
        all_msgs = []
        
        # Fetch messages, using start_date if provided
        if self.start_date:
            async for msg in self.client.iter_messages(channel_id, reverse=True, offset_date=self.start_date):
                all_msgs.append(msg)
        else:
            # Default to last 100 messages if no date specified
            async for msg in self.client.iter_messages(channel_id, limit=100, reverse=True):
                all_msgs.append(msg)
        
        # Group by grouped_id (for albums)
        groups = {}
        for m in all_msgs:
            g_id = m.grouped_id if m.grouped_id else m.id
            groups.setdefault(g_id, []).append(m)
        
        # Sort each group by date
        grouped_list = []
        for g_id, msgs in groups.items():
            msgs.sort(key=lambda x: x.date)
            grouped_list.append((g_id, msgs))
        
        # Sort the entire list by the earliest message in each group
        grouped_list.sort(key=lambda x: x[1][0].date)
        return grouped_list
    
    async def post_to_channel(self, text, media_paths, channel):
        """Post content to a Telegram channel."""
        try:
            if media_paths:
                await self.client.send_file(channel, media_paths, caption=text)
            else:
                await self.client.send_message(channel, text)
            print(f"[HistoryRepostWorkflow] Posted to channel: {channel}")
        except Exception as e:
            print(f"[HistoryRepostWorkflow] Error posting to channel {channel}: {e}")