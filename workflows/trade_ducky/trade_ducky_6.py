# Replace the current imports at the top of your file

# Standard library imports
import asyncio
import base64
import os
import datetime
import shutil
import time
import json
import re
import os
import traceback 
import sys
import threading
import subprocess
import mimetypes
from difflib import SequenceMatcher
from collections import defaultdict  # Add this line
from pathlib import Path
from dotenv import load_dotenv  # Add dotenv import
# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
print("Python path:", sys.path)
print("Current working directory:", os.getcwd())
print("Project root:", project_root)

from models_openai import tweet_generation, filter_model, duplicate_checker,analyze_image
from helpers import download_and_process_media,setup_error_handlers,cleanup_temporary_files
from scrape_and_download import scrape_and_download, extract_content_to_aggregated_file
# Ensure we're using the system's logging module 
import importlib.util
logging_spec = importlib.util.find_spec('logging')
logging = importlib.util.module_from_spec(logging_spec)
logging_spec.loader.exec_module(logging)

# After ensuring we have the correct logging module, import handlers
from logging.handlers import RotatingFileHandler

# Third-party imports
import tweepy
import openai
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
from telethon.sessions import StringSession

# At the very top of the file, after imports
import logging
from pathlib import Path

# Base directory constants
WORKFLOW_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = WORKFLOW_DIR.parent.parent  # Social_Media_CURSOR_2 root directory

# Workflow-specific directories
MESSAGE_HISTORY_DIR = WORKFLOW_DIR / "message_history"
POSTED_MESSAGES_DIR = WORKFLOW_DIR / "posted_messages"
LOGS_DIR = WORKFLOW_DIR / "logs"

# Ensure required directories exist
for directory in [MESSAGE_HISTORY_DIR, POSTED_MESSAGES_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Configure logging with absolute paths
logger = logging.getLogger("trade_ducky_bot")
logger.setLevel(logging.INFO)

log_file = LOGS_DIR / f"trade_ducky_{datetime.datetime.now().strftime('%Y%m%d')}.log"
file_handler = RotatingFileHandler(
    str(log_file),  # Convert Path to string for handler
    maxBytes=10*1024*1024,
    backupCount=5
)
console_handler = logging.StreamHandler()

# Create formatters with more detailed information
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Prevent logging from propagating to the root logger
logger.propagate = False

logger.info(f"Starting trade_ducky bot with logging to {log_file}")

# Load environment variables from .env file in workflow directory
WORKFLOW_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(WORKFLOW_DIR, '.env')
load_dotenv(dotenv_path=env_path)

# Load API keys from environment variables with default values
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

# Log the environment loading attempt
logger.info(f"Attempting to load environment variables from: {env_path}")
if os.path.exists(env_path):
    logger.info(".env file found")
else:
    logger.warning(".env file not found at expected location")

# Validate required API keys
if not all([API_KEY, API_SECRET_KEY, BEARER_TOKEN, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    logger.error("Missing required Twitter API credentials")
    raise ValueError("Missing required Twitter API credentials. Please check your .env file")

if not all([API_ID, API_HASH, SESSION_STRING]):
    logger.error("Missing required Telegram API credentials")
    raise ValueError("Missing required Telegram API credentials. Please check your .env file")

if not OPENAI_API_KEY:
    logger.error("Missing required OpenAI API key")
    raise ValueError("Missing required OpenAI API key. Please check your .env file")

# Authenticate with Twitter API v2 using Tweepy
try:
    logger.info("Authenticating with Twitter API")
    client_v2 = tweepy.Client(bearer_token=BEARER_TOKEN,
                              consumer_key=API_KEY,
                              consumer_secret=API_SECRET_KEY,
                              access_token=ACCESS_TOKEN,
                              access_token_secret=ACCESS_TOKEN_SECRET)

    # For v1.1 media upload
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api_v1 = tweepy.API(auth)
    logger.info("Twitter API authentication successful")
except Exception as e:
    logger.error(f"Error authenticating with Twitter API: {e}")
    logger.error(traceback.format_exc())
    # Continue without failing - we'll handle Twitter errors when posting

# --- Make Telethon more resilient ---
logger.info("Setting up Telegram client")
client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=-1,  # unlimited retries
    auto_reconnect=True
)

# Global dictionaries and sets for grouping messages
grouped_media = defaultdict(list)  # grouped by grouped_id
group_processing = set()           # groups currently being processed
# Add a dictionary to track when processing started for each group
group_processing_start_times = {}  # to track when processing started
# Set a timeout limit for group processing (in seconds)
GROUP_PROCESSING_TIMEOUT = 300  # 5 minutes

# Add a watchdog task that checks for stuck processes
async def watchdog_task():
    """Monitor for stuck processes and log/clean up if necessary"""
    while True:
        try:
            current_time = time.time()
            stuck_groups = []
            
            # Check for groups that have been processing for too long
            for group_id in list(group_processing_start_times.keys()):
                start_time = group_processing_start_times[group_id]
                if current_time - start_time > GROUP_PROCESSING_TIMEOUT:
                    logger.warning(f"Group {group_id} has been processing for over {GROUP_PROCESSING_TIMEOUT} seconds. Marking as stuck.")
                    stuck_groups.append(group_id)
            
            # Clean up stuck groups
            for group_id in stuck_groups:
                if group_id in group_processing:
                    group_processing.remove(group_id)
                if group_id in group_processing_start_times:
                    del group_processing_start_times[group_id]
                if group_id in grouped_media:
                    del grouped_media[group_id]
                logger.info(f"Cleaned up stuck group {group_id}")
            
            # Log a heartbeat message every minute
            logger.info("Watchdog heartbeat: Bot is running")
            logger.info(f"Currently processing {len(group_processing)} groups")
            logger.info("Listening for new messages...")
            
            await asyncio.sleep(360)  # Run every 6 minute
        except Exception as e:
            logger.error(f"Error in watchdog task: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(60)  # Keep running even if there's an error

# Add timeout to process_group_id
async def process_group_with_timeout(group_id):
    """Process a group with a timeout"""
    try:
        # Set when processing starts
        group_processing_start_times[group_id] = time.time()
        
        # Create a task with timeout
        task = asyncio.create_task(process_group_id(group_id))
        await asyncio.wait_for(task, timeout=GROUP_PROCESSING_TIMEOUT)
        
        # Cleanup after successful processing
        if group_id in group_processing_start_times:
            del group_processing_start_times[group_id]
            
    except asyncio.TimeoutError:
        logger.error(f"Processing group {group_id} timed out after {GROUP_PROCESSING_TIMEOUT} seconds")
        # Clean up resources
        if group_id in group_processing:
            group_processing.remove(group_id)
        if group_id in grouped_media:
            del grouped_media[group_id]
        if group_id in group_processing_start_times:
            del group_processing_start_times[group_id]
    except Exception as e:
        logger.error(f"Error processing group {group_id}: {e}")
        logger.error(traceback.format_exc())
        # Clean up resources
        if group_id in group_processing:
            group_processing.remove(group_id)
        if group_id in grouped_media:
            del grouped_media[group_id]
        if group_id in group_processing_start_times:
            del group_processing_start_times[group_id]

@client.on(events.NewMessage(chats=['@forklog','@unfolded','@unfolded_defi', '@decenter', '@tradeduckydemo', '@cryptoquant_official',"@cryptodaily","@glassnode",
                                     "@crypto02eth","@RBCCrypto","@crypto_headlines","@decryptnews","@incrypted","@whaletalks","https://t.me/+dyOYTmEkEwZhMWY0"]))
async def handler(event):
    logger.info(f"New message received from {event.chat.username if hasattr(event.chat, 'username') else 'unknown chat'}")
    
    try:
        message = event.message
        grouped_id = getattr(message, "grouped_id", None)
        
        if grouped_id:
            logger.info(f"Message is part of group {grouped_id}")
            # Add message to its group
            grouped_media[grouped_id].append(message)
            if grouped_id not in group_processing:
                group_processing.add(grouped_id)
                logger.info(f"Starting processing for group {grouped_id}")
                # Process with timeout protection
                asyncio.create_task(process_group_with_timeout(grouped_id))
        else:
            logger.info("Message is not part of a group")
            # For a single message create a unique grouped_id with timestamp first
            timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            message_id = str(message.id)  # Add this line
            grouped_id = f"{timestamp_str}_single_{message_id}"  # Date/time first, then "single"
            grouped_media[grouped_id].append(message)
            if grouped_id not in group_processing:
                group_processing.add(grouped_id)
                logger.info(f"Starting processing for single message with ID {grouped_id}")
                # Process with timeout protection - fixed syntax error here
                asyncio.create_task(process_group_with_timeout(grouped_id))
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        logger.error(traceback.format_exc())

async def process_group_id(grouped_id):
    try:
        logger.info(f"Processing group {grouped_id}")
        messages = grouped_media[grouped_id]
        earliest_message = min(messages, key=lambda msg: msg.date)
        logger.info(f"Processing group {grouped_id} with {len(messages)} messages")

        # Create directory using absolute path
        if isinstance(grouped_id, str) and "_single" in grouped_id:
            dir_name = f"{grouped_id}"
        else:
            timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            dir_name = f"{timestamp_str}_group_{grouped_id}"
            
        message_dir = MESSAGE_HISTORY_DIR / dir_name
        message_dir.mkdir(exist_ok=True)
        logger.info(f"Created directory {message_dir}")

        media_paths = []
        text = earliest_message.text if earliest_message.text else ""

        # Download media files
        for idx, msg in enumerate(messages):
            if msg.media:
                media_path = await download_and_process_media(msg, message_dir, idx)
                if media_path:
                    media_paths.append(media_path)
            else:
                logger.info(f"Message ID {msg.id} has no media")
                
        # Save original text
        text_file_path = message_dir / "original_message.txt"
        with open(text_file_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Original message text saved to {text_file_path}")
        logger.debug(f"Original message text: {text}")

        # Process the group: generate tweet, analyze media/links, and post tweet
        await generate_and_post_tweet(text, media_paths, str(message_dir))
        logger.info(f"Tweet generation and posting completed for group {grouped_id}")

        # Cleanup the processed group
        del grouped_media[grouped_id]
        group_processing.remove(grouped_id)
        logger.info(f"Group {grouped_id} processing completed and cleaned up")
        
    except Exception as e:
        logger.error(f"Error processing group {grouped_id}: {e}")
        logger.error(traceback.format_exc())
        # Clean up even if there's an error
        if grouped_id in grouped_media:
            del grouped_media[grouped_id]
        if grouped_id in group_processing:
            group_processing.remove(grouped_id)

###############################
# URL and Media Analysis Helpers
###############################

def analyze_website(url, download_folder=None):
    logger.info(f"Analyzing website: {url}")
    try:
        if download_folder:
            result = scrape_and_download(url, download_folder=download_folder)
        else:
            result = scrape_and_download(url)
        logger.info(f"Website analysis completed for {url}")
        return result
    except Exception as e:
        logger.error(f"Error analyzing website {url}: {e}")
        logger.error(traceback.format_exc())
        return f"Error analyzing website {url}: {e}"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

###############################
# Duplicate Tweet Prevention Helpers
###############################

def fetch_posted_tweet_history(limit=25):
    """
    Fetch history from posted_messages directory using absolute paths.
    """
    logger.info(f"Fetching posted message history (limit: {limit})")
    
    if not POSTED_MESSAGES_DIR.exists():
        logger.warning(f"Posted messages directory '{POSTED_MESSAGES_DIR}' does not exist")
        return []
    
    try:
        # Get directories sorted by modification time
        message_dirs = sorted(
            [d for d in POSTED_MESSAGES_DIR.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        history = []
        for message_dir in message_dirs:
            try:
                tweet_text_file = message_dir / "tweet_text.txt"
                if not tweet_text_file.exists():
                    continue
                
                with open(tweet_text_file, "r", encoding="utf-8") as f:
                    message_text = f.read().strip()
                
                # Get media info
                media_info = []
                for file_path in message_dir.glob('*'):
                    if file_path.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.mp4'):
                        media_info.append({
                            "file_extension": file_path.suffix,
                            "file_size": file_path.stat().st_size
                        })
                
                history.append({
                    "text": message_text,
                    "media_info": media_info,
                    "directory": str(message_dir)
                })
                
            except Exception as e:
                logger.error(f"Error processing directory {message_dir}: {e}")
                continue
        
        return history
        
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return []

def normalized_media_info(media_info):
    """
    Returns a sorted list of tuples (file_extension, file_size) for each media file.
    """
    if not media_info:
        return []
    normalized = [(item["file_extension"].lower(), item["file_size"]) for item in media_info]
    normalized.sort()
    return normalized

def media_file_equal(m1, m2, tolerance=0.05):
    """
    Compares two media file tuples (file_extension, file_size).
    """
    ext1, size1 = m1
    ext2, size2 = m2
    if ext1 != ext2:
        return False
    # Avoid division by zero and allow exact zero-size files.
    if size1 == 0 and size2 == 0:
        return True
    # Check if the relative difference is within the tolerance.
    diff_ratio = abs(size1 - size2) / max(size1, size2)
    return diff_ratio <= tolerance

def media_list_equal(list1, list2, tolerance=0.05):
    """
    Compares two lists of media file tuples.
    """
    if len(list1) != len(list2):
        return False
    for m1, m2 in zip(list1, list2):
        if not media_file_equal(m1, m2, tolerance):
            return False
    return True

def format_media_info(media_info):
    """
    Given a list of media file info dictionaries, returns a string summarizing the details.
    """
    if not media_info:
        return "No media files."
    
    formatted_items = []
    for item in media_info:
        formatted_items.append(
            f"(Extension: {item['file_extension']}, Size: {item['file_size']} bytes)"
        )
    return ", ".join(formatted_items)

async def is_duplicate_tweet(current_message, current_media_info, dir_path):
    """
    Comprehensive duplicate check combining both non-AI and AI-based methods.
    
    Args:
        current_message (str): The message to check
        current_media_info (list): List of media file information
        dir_path (Path): Directory path for saving model decisions
        
    Returns:
        bool: True if duplicate detected, False otherwise
    """
    logger.info("Starting comprehensive duplicate check")
    
    # Get only successfully posted tweets
    recent_entries = fetch_posted_tweet_history(limit=25)
    if not recent_entries:
        logger.info("No posted entries to compare against")
        return False

    # Debug logging - show what we're comparing
    current_media_str = format_media_info(current_media_info)
    logger.debug(f"Current message (first 50 chars): {current_message[:50] if current_message else ''}")
    logger.debug(f"Current media: {current_media_str}")
    
    # 1. Quick checks first (non-AI based)
    
    # 1.1 Media match check
    normalized_current = normalized_media_info(current_media_info)
    for i, entry in enumerate(recent_entries):
        normalized_past = normalized_media_info(entry["media_info"])
        if media_list_equal(normalized_current, normalized_past, tolerance=0.01):
            # Enhanced logging - show exactly which tweet matched
            match_dir = os.path.basename(entry["directory"])
            match_text = entry["text"][:50] + "..." if len(entry["text"]) > 50 else entry["text"]
            logger.warning(f"DUPLICATE DETECTED (Media Match): Files match with tweet in: {match_dir}")
            logger.warning(f"Media match details: Current files: {len(normalized_current)}, Past files: {len(normalized_past)}")
            logger.warning(f"Matched tweet text begins with: '{match_text}'")
            return True
    
    # 1.2 Text-based exact matches
    for i, entry in enumerate(recent_entries):
        past_text = entry["text"].strip()
        # Only check substantial messages
        if len(current_message) > 20 and len(past_text) > 20:
            # Exact match check
            if current_message.strip() == past_text:
                match_dir = os.path.basename(entry["directory"])
                logger.warning(f"DUPLICATE DETECTED (Exact Text): Match found in: {match_dir}")
                logger.warning(f"Current text: '{current_message[:50]}...'")
                logger.warning(f"Matched text: '{past_text[:50]}...'")
                return True
            
            # Beginning of message match (for very similar messages)
            if (current_message[:30].lower() == past_text[:30].lower() and 
                abs(len(past_text) - len(current_message)) < 10):
                match_dir = os.path.basename(entry["directory"])
                logger.warning(f"DUPLICATE DETECTED: Text beginning matches with tweet in: {match_dir}")
                logger.warning(f"First 30 chars match: '{current_message[:30]}'")
                return True
    
    # 2. AI-based semantic check
    try:
        # Prepare prompt for duplicate checking
        duplicate_prompt = (
            "Compare the new message with past messages and determine if it's a duplicate.\n"
            "Consider both content similarity and meaning.\n"
            "NEW MESSAGE:\n-------------------\n"
            f"{current_message}\n"
            "-------------------\n\n"
            "PAST MESSAGES:\n"
        )
        
        for i, entry in enumerate(recent_entries, start=1):
            duplicate_prompt += f"[{i}] {entry['text'][:100]}{'...' if len(entry['text']) > 100 else ''}\n\n"
        
        is_duplicate = await duplicate_checker(
            current_message=current_message,
            current_media_info=current_media_info,
            recent_entries=recent_entries,
            prompt_text=duplicate_prompt,
            model="gpt-4o-2024-11-20",
            system_content="You are a duplicate content detector. If content is not duplicate, respond with 'No'. If duplicate, respond with 'Yes, similar to message #X' where X is the message number.",
            temperature=0.0,
            max_tokens=50,
            save_decision=True,
            directory_prefix=str(dir_path)
        )
        
        if is_duplicate:
            logger.warning("DUPLICATE DETECTED (AI Analysis): Semantic similarity found")
            return True
            
    except Exception as e:
        logger.error(f"Error in AI-based duplicate check: {e}")
        logger.error(traceback.format_exc())
        logger.warning("AI check failed - relying on non-AI checks only")
    
    logger.info("No duplicates found - message appears to be unique")
    return False

###############################
# New Function: Post to Telegram Channel
###############################

async def post_to_telegram_channel(text, media_paths, channel_username):
    """
    Posts the given text (and optionally media) to the specified Telegram channel.
    """
    logger.info(f"Posting to Telegram channel: {channel_username}")
    try:
        if media_paths:
            await client.send_file(channel_username, media_paths, caption=text)
        else:
            await client.send_message(channel_username, text)
        logger.info(f"Successfully posted to Telegram channel: {channel_username}")
    except Exception as e:
        logger.error(f"Error posting to Telegram channel {channel_username}: {e}")
        logger.error(traceback.format_exc())

###############################
# New Function: Post to Twitter
###############################

async def post_to_twitter(text, media_paths=None):
    """Post a tweet with media to Twitter with better error handling"""
    try:
        logger.info(f"Posting to Twitter: {text[:50]}... with {len(media_paths) if media_paths else 0} media items")
        
        # Check credentials
        if not all([API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
            logger.error("Twitter credentials missing. Cannot post to Twitter.")
            return None
        
        # Check media paths
        if media_paths and not all(os.path.exists(path) for path in media_paths):
            invalid_paths = [path for path in media_paths if not os.path.exists(path)]
            logger.error(f"Some media paths don't exist: {invalid_paths}")
            # Continue with valid paths only
            media_paths = [path for path in media_paths if os.path.exists(path)]
        
        # Upload media
        media_ids = []
        if media_paths:
            for media_path in media_paths:
                try:
                    # Log file info for debugging
                    file_size = os.path.getsize(media_path)
                    file_type = mimetypes.guess_type(media_path)[0]
                    logger.info(f"Uploading media: {os.path.basename(media_path)}, size: {file_size}, type: {file_type}")
                    
                    # Using tweepy's v1 API for media uploads
                    with open(media_path, 'rb') as media_file:
                        # Add explicit mime type and more verbose logging
                        media = api_v1.media_upload(
                            filename=os.path.basename(media_path),
                            file=media_file,
                        )
                        media_ids.append(media.media_id)
                    logger.info(f"Media uploaded successfully with ID: {media.media_id}")
                except Exception as e:
                    logger.error(f"Error uploading media {media_path}: {e}")
                    logger.error(traceback.format_exc())
                    # Continue with other media files
        
        # Post the tweet
        if media_ids:
            logger.info(f"Posting tweet with {len(media_ids)} media attachments")
            response = client_v2.create_tweet(text=text, media_ids=media_ids)
        else:
            logger.info("Posting text-only tweet")
            response = client_v2.create_tweet(text=text)
        
        tweet_id = response.data['id']
        logger.info(f"Tweet posted successfully with ID: {tweet_id}")
        return tweet_id
    
    except tweepy.errors.BadRequest as e:
        logger.error(f"Twitter BadRequest error: {e}")
        error_detail = getattr(e, 'api_errors', [{}])[0].get('message', str(e))
        logger.error(f"Error details: {error_detail}")
        return None
    except tweepy.errors.Unauthorized as e:
        logger.error(f"Twitter authentication error: {e}")
        logger.error("Check your Twitter API credentials")
        return None
    except tweepy.errors.TooManyRequests as e:
        logger.error(f"Twitter rate limit exceeded: {e}")
        reset_time = e.response.headers.get('x-rate-limit-reset', 'unknown')
        logger.error(f"Rate limit resets at: {reset_time}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error posting to Twitter: {e}")
        logger.error(traceback.format_exc())
        return None

###############################
# Main Function: Generate and Post Tweet
###############################

async def generate_and_post_tweet(text, media_paths, dir_name):
    """
    Aggregates data, generates tweet content with GPT, checks for duplicate content,
    and then posts the tweet (and optionally posts to Telegram).
    """
    dir_path = Path(dir_name)  # Convert to Path object for consistent handling
    logger.info(f"Beginning generation and posting of the tweet from directory: {dir_path}")
    logger.debug(f"Original message: {text}")
    logger.debug(f"Media paths: {media_paths}")

    # 1. First extract content to aggregated file
    aggregated_content = await extract_content_to_aggregated_file(text, media_paths, str(dir_path))
    
    # 2. Check for duplicates using unified approach
    try:
        # Build a list of current media file details in the same format as expected.
        current_media_details = []
        for media in media_paths:
            file_ext = os.path.splitext(media)[1]
            file_size = os.path.getsize(media)
            current_media_details.append({
                "file_extension": file_ext,
                "file_size": file_size
            })
        
        is_duplicate = await is_duplicate_tweet(
            current_message=text,
            current_media_info=current_media_details,
            dir_path=dir_path
        )
        
        if is_duplicate:
            logger.warning("Tweet is similar to a recent message. Skipping posting to avoid duplicates.")
            return
            
    except Exception as e:
        logger.error(f"Error checking for duplicate tweets: {e}")
        logger.error(traceback.format_exc())
        # Continue with posting even if duplicate check fails

    # 3. Filter for unwanted content
    logger.info("Filtering tweet for unwanted content")
    filter_prompt = (
        "Is the following content PURELY promotional without valuable information? Note that content with BOTH promotional elements (like platform links) AND valuable market analysis should be classified as NOT promotional. "
        "If the content is purely promotional with no value, respond with 'Yes, Promotional: [explanation]'\n"
        "If the content contains valuable information (even with some promotional elements), respond with 'No'.\n\n"
        "IMPORTANT GUIDELINES:\n"
        f"1. Content from our monitored channels ({', '.join(all_channels)}) should NOT be considered promotional\n"
        "2. The following combinations are NOT promotional:\n"
        "   - Market analysis + trading platform links (Bybit, OKX, etc.)\n"
        "   - Price predictions + affiliate/referral links\n"
        "   - Technical analysis + Telegram group invites\n"
        "   - Trading insights + sign-up links\n"
        "   - Price targets + platform recommendations\n"
        "   - Market updates + community group links\n"
        "3. Content is ONLY promotional if it:\n"
        "   - Contains ONLY links/calls to action with NO analysis\n"
        "   - Is pure advertising with no market insights\n"
        "   - Has NO valuable information, just promotions\n"
        "4. ALWAYS classify as NOT promotional if content includes:\n"
        "   - Specific price levels and analysis\n"
        "   - Technical indicators or chart analysis\n"
        "   - Market predictions with reasoning\n"
        "   - Trading strategies or insights\n"
        "   Even if these are accompanied by platform links or group invites\n"
        "5. The presence of links alone is NOT enough to classify as promotional\n"
        "6. When in doubt, if there's ANY valuable analysis, classify as NOT promotional\n\n"
        f"Content: {aggregated_content}"
    )

    filter_result = "yes"  # Default to yes to be safe
    logger.debug(f"Filter prompt first 200 chars: {filter_prompt[:200]}...")
    filter_result = await filter_model(  # Don't forget the await keyword!
        tweet_text=aggregated_content,  # Use aggregated_content here too
        prompt_text=filter_prompt,
        model="gpt-4o-2024-11-20",
        system_content="You are a filter system for identifying content not suitable for posting. If the content is promotional, respond with 'Yes, Promotional: [brief explanation]'.Otherwise, respond with 'No'.",
        temperature=0.0,
        top_p=1.0,
        max_tokens=50,  # Increased to allow for explanation
        presence_penalty=0.0,
        frequency_penalty=0.0,
        timeout=30,
        save_decision=True,
        directory_prefix=str(dir_path)
    )

    if filter_result == "yes":
        logger.warning("Tweet identified as promotional or Russian. Skipping posting...")
        return

    # 4. Generate tweet content
    logger.info("Generating tweet content using OpenAI")
    logger.info(f"All twitter channels: {all_channels}")
    prompt_text = (
        "Rewrite the following content as an engaging Twitter post. "
        "Note that the text is from the Original Message section, with helpful details in image analysis sections.\n\n"
        "IMPORTANT RULES:\n"
        f"1. REMOVE all Telegram channel mentions ({', '.join(all_channels)})\n"
        "2. KEEP essential information about the subject (TRON, Ethereum, USDT, etc.)\n"
        "3. REMOVE dashboard links but KEEP the insight from the data\n"
        "4. Add relevant emojis for engagement\n\n"
        "Content: {content}"
    )
    
    tweet_text = ""
    tweet_text = await tweet_generation(
        content=aggregated_content,
        prompt_text=prompt_text,
        model="gpt-4o-2024-11-20",
        system_content="You are a Twitter blogger creating concise, engaging tweets. Be cool and not overly excited.",
        temperature=0.7,
        top_p=1.0,
        max_tokens=900,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        timeout=60,
        save_decision=True,
        directory_prefix=str(dir_path)
    )

    # Save the generated tweet text
    try:
        tweet_text_file = os.path.join(dir_name, "tweet_text.txt")
        with open(tweet_text_file, "w", encoding="utf-8") as f:
            f.write(tweet_text)
        logger.info(f"Tweet text saved to {tweet_text_file}")
    except Exception as e:
        logger.error(f"Error saving tweet text: {e}")
        logger.error(traceback.format_exc())

    # 5. Post the tweet if it passed all checks
    if filter_result == "no":
        logger.info("Tweet passed all checks. Proceeding to post.")
        
        # Upload media if available.
        media_ids = []
        for path in media_paths:
            try:
                media = api_v1.media_upload(path)
                media_ids.append(media.media_id)
                logger.info(f"Media uploaded: {media.media_id}")
            except Exception as e:
                logger.error(f"Error uploading media: {e}")
                logger.error(traceback.format_exc())
        
        # Post the tweet
        tweet_id = None
        posting_status = {
            "telegram_posted": False,
            "twitter_posted": False,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

        try:
            if media_ids:
                response = client_v2.create_tweet(text=tweet_text, media_ids=media_ids)
                tweet_id = response.data['id']
                logger.info(f"Tweet with media posted successfully: {tweet_id}")
                posting_status["twitter_posted"] = True
                posting_status["twitter_id"] = tweet_id
            else:
                response = client_v2.create_tweet(text=tweet_text)
                tweet_id = response.data['id']
                logger.info(f"Tweet posted successfully: {tweet_id}")
                posting_status["twitter_posted"] = True
                posting_status["twitter_id"] = tweet_id
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            logger.error(traceback.format_exc())
            posting_status["twitter_error"] = str(e)

        # Telegram posting attempt
        telegram_channel = "@tradeducky" # e.g., "@mychannel"
        if telegram_channel:
            try:
                await post_to_telegram_channel(tweet_text, media_paths, telegram_channel)
                logger.info("Successfully posted to Telegram channel")
                posting_status["telegram_posted"] = True
            except Exception as e:
                logger.error(f"Error posting to Telegram channel: {e}")
                logger.error(traceback.format_exc())
                posting_status["telegram_error"] = str(e)

        # If either platform was successful, save files and status
        if posting_status["telegram_posted"] or posting_status["twitter_posted"]:
            try:
                # Create the posted messages directory if it doesn't exist
                if not os.path.exists(POSTED_MESSAGES_DIR):
                    os.makedirs(POSTED_MESSAGES_DIR)
                
                # Extract the original directory name without the path
                dir_basename = os.path.basename(dir_name)
                
                # Create destination directory with tweet ID if available
                if posting_status.get("twitter_id"):
                    dest_dir = os.path.join(POSTED_MESSAGES_DIR, f"{dir_basename}_tid_{posting_status['twitter_id']}")
                else:
                    dest_dir = os.path.join(POSTED_MESSAGES_DIR, dir_basename)
                    
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                
                # Save posting status first
                status_file = os.path.join(dest_dir, "posting_status.json")
                with open(status_file, "w", encoding="utf-8") as f:
                    json.dump(posting_status, f, indent=2)
                
                # Copy all other files
                for filename in os.listdir(dir_name):
                    src_file = os.path.join(dir_name, filename)
                    if os.path.isfile(src_file):
                        shutil.copy2(src_file, os.path.join(dest_dir, filename))
                
                logger.info(f"Message data and status copied to posted directory: {dest_dir}")
            except Exception as e:
                logger.error(f"Error copying message data to posted directory: {e}")
                logger.error(traceback.format_exc())
    else:
        logger.warning("Tweet is either promotional or contains Russian content. It will not be posted.")

###############################
# New Function: Setup Monitored Channels
###############################

async def setup_monitored_channels(client, channels_list):
    """
    Test each channel and return only the valid ones that can be resolved
    """
    valid_channels = []
    for channel in channels_list:
        try:
            # Attempt to resolve the channel
            logger.info(f"Testing channel: {channel}")
            await client.get_input_entity(channel)
            valid_channels.append(channel)
            logger.info(f"Successfully verified channel: {channel}")
        except ValueError as e:
            # This happens when the username doesn't exist
            logger.error(f"Invalid channel {channel}: {e}")
        except Exception as e:
            # Other errors (network, etc)
            logger.error(f"Error verifying channel {channel}: {e}")
    
    if not valid_channels:
        logger.critical("No valid channels to monitor! Check your channel list.")
    
    logger.info(f"Monitoring {len(valid_channels)}/{len(channels_list)} channels: {valid_channels}")
    return valid_channels

async def main_runner():
    """
    Continuously run the Telegram client. If disconnected or certain exceptions occur,
    wait a bit and then restart.
    """
    # Start the watchdog task
    asyncio.create_task(watchdog_task())

    # Use the global all_channels list (no need to redefine it here)
    global all_channels
    
    # Define channels to monitor
    all_channels = [
        '@forklog', '@unfolded', '@unfolded_defi', '@decenter', 
        '@tradeduckydemo', '@cryptoquant_official', '@cryptodaily', '@glassnode',
        '@crypto02eth', '@RBCCrypto', '@crypto_headlines', '@decryptnews', '@incrypted','@whaletalks','https://t.me/+dyOYTmEkEwZhMWY0'
    ]
    
    while True:
        try:
            logger.info("Starting Telegram client")
            async with client:
                logger.info("Client started. Attempting to connect...")
                if not await client.is_user_authorized():
                    logger.error('Client is not authorized')
                    break
                else:
                    logger.info("Client is authorized")
                
                # Verify and filter channel list
                valid_channels = await setup_monitored_channels(client, all_channels)
                
                if not valid_channels:
                    logger.critical("No valid channels to monitor. Exiting.")
                    break
                
                # Remove current handlers
                client.remove_event_handler(handler)
                
                # Add handler with valid channels
                client.add_event_handler(
                    handler,
                    events.NewMessage(chats=valid_channels)
                )
                
                logger.info(f"Successfully registered handler for {len(valid_channels)} channels")
                
                # Log "Listening for messages" periodically
                while True:
                    try:
                        logger.info("Listening for messages...")
                        await asyncio.sleep(300)  # Log every 5 minutes
                    except Exception as e:
                        logger.error(f"Error in listening heartbeat: {e}")
                        break
                
                asyncio.create_task(cleanup_temporary_files())
                await client.run_until_disconnected()
                logger.warning("Client disconnected")
        except (ConnectionResetError, OSError) as e:
            logger.error(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Main runner was cancelled. Shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            logger.error("Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()  # allows running the loop within Jupyter if needed
        logger.info("Starting main runner")
        # Setup error handlers and cleanup task
        setup_error_handlers()
        asyncio.run(main_runner())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user. Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error in main program: {e}")
        logger.critical(traceback.format_exc())