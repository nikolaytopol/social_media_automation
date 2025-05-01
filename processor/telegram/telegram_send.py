from collections import defaultdict
import asyncio
import os
import datetime
import shutil
from telethon import TelegramClient, events
from telethon.sessions import StringSession



# Example usage
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=-1,  # unlimited retries
    auto_reconnect=True
)

channels = ['@tradeduckydemo']
output_folder = "tweet_history"


async def post_to_telegram_channel(text, media_paths, channel_username):
    """
    Posts the given text (and optionally media) to the specified Telegram channel.
    The channel_username is the channel's username (e.g. "@mychannel").
    """
    try:
        if media_paths:
            await client.send_file(channel_username, media_paths, caption=text)
        else:
            await client.send_message(channel_username, text)
        print(f"Posted to Telegram channel: {channel_username}")
    except Exception as e:
        print(f"Error posting to Telegram channel {channel_username}: {e}")