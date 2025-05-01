# processor/telegram_listener.py

import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio

# Load environment variables for Telegram credentials
API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')  # Reuse existing session

class TelegramListener:
    def __init__(self, channels, processor):
        """
        Initialize the Telegram listener.
        
        Args:
            channels (list): List of channel usernames to listen to (e.g., ['@mychannel'])
            processor (Processor): Reference to the parent Processor instance
        """
        self.channels = channels
        self.processor = processor
        self.client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    async def connect(self):
        """
        Connect to Telegram and authenticate the client.
        """
        await self.client.start()
        print("[TelegramListener] Connected to Telegram.")

    async def listen(self):
        """
        Start listening to new messages from specified channels.
        """
        @self.client.on(events.NewMessage(chats=self.channels))
        async def handler(event):
            await self.handle_new_message(event)

        print(f"[TelegramListener] Listening to channels: {self.channels}")
        await self.client.run_until_disconnected()

    async def handle_new_message(self, event):
        """
        Handle a new incoming Telegram message.
        Extract text and media, then forward to Processor.
        """
        message = event.message
        text = message.text or ""
        media_paths = []

        # Download media if available
        if message.media:
            try:
                media_path = await message.download_media()
                if media_path:
                    media_paths.append(media_path)
                    print(f"[TelegramListener] Downloaded media: {media_path}")
            except Exception as e:
                print(f"[TelegramListener] Failed to download media: {e}")

        await self.processor.handle_new_content(
            text=text,
            media_paths=media_paths,
            source_type="telegram",
            source_name=event.chat.username if event.chat else "unknown"
        )

    async def post_to_channel(self, text, media_paths, channel_username=None):
        """
        Post a message (and optionally media) to a Telegram channel.

        Args:
            text (str): Text content to post.
            media_paths (list): List of file paths to send.
            channel_username (str): Target channel (e.g., '@mychannel').
        """
        if not channel_username:
            print("[TelegramListener] No channel username provided for posting.")
            return

        try:
            if media_paths:
                await self.client.send_file(channel_username, media_paths, caption=text)
            else:
                await self.client.send_message(channel_username, text)
            print(f"[TelegramListener] Posted to Telegram channel: {channel_username}")
        except Exception as e:
            print(f"[TelegramListener] Failed to post to Telegram channel: {e}")
