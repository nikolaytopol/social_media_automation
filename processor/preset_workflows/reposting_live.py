import os
import time
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from processor.openai_utils import OpenAIUtils
from processor.deepseek_utils import DeepSeekUtils

# ------------------------------------------------------------------------
# 1) TELEGRAM CLIENT SETUP WITH AUTO-RECONNECT OPTIONS
# ------------------------------------------------------------------------
API_ID = os.getenv('TELEGRAM_API_ID') or "your_api_id_here"
API_HASH = os.getenv('TELEGRAM_API_HASH') or "your_api_hash_here"
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING') or "your_session_string_here"

# Source channels: numeric IDs from which to listen for new messages
source_channels = [-1002454067712, -1002167975984]

# Target channel: where messages will be reposted
target_channel = -1002634663671
client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=-1,
    auto_reconnect=True
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RepostingLive')

# ------------------------------------------------------------------------
# 2) SAFE SEND WRAPPERS
# ------------------------------------------------------------------------
async def safe_send_message(target, text):
    if not client.is_connected():
        logger.info("Client not connected. Reconnecting...")
        await client.connect()
    for attempt in range(3):
        try:
            return await client.send_message(target, text)
        except ConnectionError as ce:
            logger.error(f"Error sending message (attempt {attempt+1}): {ce}")
            await client.connect()
            await asyncio.sleep(1)
    raise Exception("Unable to send message after several retries.")

async def safe_send_file(target, file, caption=None, allow_cache=False):
    if not client.is_connected():
        logger.info("Client not connected. Reconnecting...")
        await client.connect()
    for attempt in range(3):
        try:
            return await client.send_file(target, file, caption=caption, allow_cache=allow_cache)
        except ConnectionError as ce:
            logger.error(f"Error sending file (attempt {attempt+1}): {ce}")
            await client.connect()
            await asyncio.sleep(1)
    raise Exception("Unable to send file after several retries.")

# ------------------------------------------------------------------------
# 3) FILTERING FUNCTION
# ------------------------------------------------------------------------
async def passes_filter(message_text: str) -> bool:
    """
    Uses OpenAI to determine if the given message text meets your posting standards.
    The prompt is designed so that various acceptable formats pass.
    """
    filter_prompt = (
        "We consider a message acceptable if it meets ANY of the following conditions:\n"
        "1. It contains personal details (e.g., age, height, weight, chest size) along with pricing information and a manager/admin contact.\n"
        "2. It contains promotional content, discounts, or special offers (e.g., percentage discounts, special deals).\n"
        "3. It is very brief or consists mainly of emojis (minimal text) or even has no text at all.\n"
        "4. It mentions or promotes any channel, admin, or manager.\n\n"
        "Does the following content satisfy any of these posting standards? Answer 'yes' if acceptable, 'no' if not.\n\n"
        f"Message: {message_text}"
    )
    try:
        response = OpenAIUtils.chat_completion(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a filter system for identifying content that is acceptable to post. "
                        "Answer 'yes' if the message meets ANY of the conditions described. Otherwise, answer 'no'."
                    )
                },
                {"role": "user", "content": filter_prompt}
            ],
            max_tokens=10,
            temperature=0
        )
        filter_result = response.choices[0].message.content.strip().lower()
        logger.info(f"[Filter] Message text: {message_text[:50]}... => {filter_result}")
        return (filter_result == "yes")
    except Exception as e:
        logger.error(f"Error during filtering: {e}")
        return False

# ------------------------------------------------------------------------
# 4) TWEET TEXT GENERATION FUNCTION
# ------------------------------------------------------------------------
async def generate_tweet_content(original_text: str) -> str:
    """
    Uses OpenAI to generate a modified version of the text:
      - Change manager's name to '@ANeliteagency'
      - Increase each price appropriately, convert all prices from CZK to EUR (rounded up).
      - Remove quotes or extraneous symbols at the beginning.
      - Remove additional links and unnecessary commentary.
    """
    prompt_text = (
        "Rewrite the following advertisement in English with the following modifications:\n"
        "1) Change the manager's name to '@ANeliteagency'.\n"
        "2) Convert price to EUR and USD "
        "Note that outcall is always 50 EUR more than incall, etc.\n"
        "3) Remove any quotes around the message and any extraneous symbols at the beginning.\n"
        "4) Remove additional links from the message.\n"
        "5) Do not add any unnecessary commentary (for example, do not include phrases like 'Prices increased by 3000-4000 CZK').\n\n"
        f"Original text: {original_text}"
    )
    try:
        response = OpenAIUtils.chat_completion(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Twitter blogger creating concise, engaging posts. Keep it fun but not overly excited."
                },
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=900,
            temperature=0
        )
        tweet_text = response.choices[0].message.content.strip()
        logger.info(f"[Generate] Modified text: {tweet_text[:50]}...")
        return tweet_text
    except Exception as e:
        logger.error(f"Error generating text with OpenAI GPT: {e}")
        return original_text  # Fallback to original text on error

# ------------------------------------------------------------------------
# 5) REAL-TIME EVENT HANDLERS
# ------------------------------------------------------------------------
@client.on(events.NewMessage(chats=source_channels))
async def new_message_handler(event):
    # Skip if the message is part of an album (handled by album_handler)
    if event.message.grouped_id:
        return

    message_text = event.message.message or ""
    logger.info(f"New single message from chat {event.chat_id}: {message_text[:50]}...")
    if await passes_filter(message_text):
        new_text = await generate_tweet_content(message_text)
        try:
            if event.message.media:
                media_path = await event.message.download_media()
                logger.info(f"Downloaded media for message id {event.message.id}: {media_path}")
                await safe_send_file(target_channel, media_path, caption=new_text, allow_cache=False)
                logger.info(f"Reposted message id {event.message.id} with media to {target_channel}")
                if media_path and os.path.exists(media_path):
                    os.remove(media_path)
            else:
                await safe_send_message(target_channel, new_text)
                logger.info(f"Reposted text message id {event.message.id} to {target_channel}")
        except Exception as e:
            logger.error(f"Error reposting message id {event.message.id}: {e}")
    else:
        logger.info(f"Message id {event.message.id} did not pass filter. Skipped.")

@client.on(events.Album(chats=source_channels))
async def album_handler(event):
    if not event.messages:
        return
    # Use the text from the first message in the album
    main_text = event.messages[0].message or ""
    logger.info(f"New album received from chat {event.chat_id}: {len(event.messages)} items. Base text: {main_text[:50]}...")
    if await passes_filter(main_text):
        new_text = await generate_tweet_content(main_text)
        media_files = []
        for msg in event.messages:
            if msg.media:
                try:
                    path = await msg.download_media()
                    if path:
                        media_files.append(path)
                except Exception as e:
                    logger.error(f"Error downloading media for message {msg.id}: {e}")
        try:
            if media_files:
                await safe_send_file(target_channel, file=media_files, caption=new_text, allow_cache=False)
                logger.info(f"Reposted album with {len(media_files)} files to {target_channel}")
            else:
                await safe_send_message(target_channel, new_text)
                logger.info(f"Reposted album text to {target_channel}")
        except Exception as e:
            logger.error(f"Error reposting album: {e}")
        finally:
            for f in media_files:
                if os.path.exists(f):
                    os.remove(f)
    else:
        logger.info("Album did not pass filter. Skipped.")

# ------------------------------------------------------------------------
# 6) WORKFLOW CLASS
# ------------------------------------------------------------------------
class TelegramRepostingWorkflow:
    """Telegram channel reposting workflow."""
    
    # These class attributes are required for the WorkflowRegistry to detect this class
    workflow_type = "live"
    workflow_info = {
        "id": "telegram_reposting",
        "name": "Telegram Channel Reposting",
        "description": "Repost content from one Telegram channel to another in real-time with AI filtering",
        "author": "Admin",
        "version": "1.0",
        "required_fields": [
            {"name": "source_channels", "type": "string", "label": "Source Channels"},
            {"name": "target_channels", "type": "string", "label": "Target Channels"}
        ],
        "optional_fields": [
            {"name": "filter_prompt", "type": "text", "label": "Filter Prompt", "required": False},
            {"name": "mod_prompt", "type": "text", "label": "Modification Prompt", "required": False},
            {"name": "duplicate_check", "type": "boolean", "label": "Check for Duplicates", "default": False}
        ]
    }
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        
    async def start(self):
        """Start the workflow."""
        logger.info("Starting Telegram Reposting Workflow...")
        # Your existing start method here

# ------------------------------------------------------------------------
# 7) RUN THE CLIENT (LISTEN INDEFINITELY)
# ------------------------------------------------------------------------
def main():
    logger.info("Listening for new messages from source channels...")
    while True:
        try:
            with client:
                client.loop.run_until_complete(client.run_until_disconnected())
        except Exception as e:
            logger.error("Client disconnected with error:", e)
            logger.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    main()
