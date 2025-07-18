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
import glob

# First add the project root directory to Python path (before imports)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Now you can import from the root directory
from scrape_and_download import scrape_and_download, extract_content_to_aggregated_file,analyze_website
from models_openai import tweet_generation, filter_model, duplicate_checker,analyze_image 
from helpers import download_and_process_media,setup_error_handlers,cleanup_temporary_files
from telegram import setup_monitored_channels,post_to_telegram_channel
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
from duplicate_checker import fetch_posted_tweet_history,is_duplicate_tweet
from twitter import post_to_twitter

# Base directory constants
WORKFLOW_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = WORKFLOW_DIR.parent.parent  # Social_Media_CURSOR_2 root directory

# Workflow-specific directories
MESSAGE_HISTORY_DIR = WORKFLOW_DIR / "message_history"
POSTED_MESSAGES_DIR = WORKFLOW_DIR / "posted_messages"
LOGS_DIR = WORKFLOW_DIR / "logs"
BOT_NAME="silicon_echo_bot"

# Ensure required directories exist
for directory in [MESSAGE_HISTORY_DIR, POSTED_MESSAGES_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Configure logging with absolute paths
logger = logging.getLogger(BOT_NAME)
logger.setLevel(logging.INFO)

log_file = LOGS_DIR / f"{BOT_NAME}_{datetime.datetime.now().strftime('%Y%m%d')}.log"
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

logger.info(f"Starting {BOT_NAME} bot with logging to {log_file}")

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

# At the top of the file, after imports, define channels in one place
CHANNELS_TO_MONITOR = [
    '@exploitex', '@habr_com', '@forklogAI', '@Bell_tech', 
    '@seeallochnaya', '@techcrunchru', '@llm_under_hood',-1002794375706
]

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

@client.on(events.NewMessage(chats=CHANNELS_TO_MONITOR))
async def handler(event):
    logger.info(f"New message received from {event.chat.username if hasattr(event.chat, 'username') else 'unknown chat'}")
    
    # Add debugging to see message content
    message_text = event.message.text if event.message.text else ""
    message_preview = message_text[:15] + "..." if len(message_text) > 15 else message_text
    logger.info(f"Message preview (first 15 chars): '{message_preview}'")
    logger.info(f"Message has media: {event.message.media is not None}")
    logger.info(f"Message text length: {len(message_text)}")
    
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

        # Add debugging for text content
        logger.info(f"Processing message text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        logger.info(f"Text length: {len(text)}")
        logger.info(f"Text is empty: {not text or len(text.strip()) == 0}")

        # Download media files
        for idx, msg in enumerate(messages):
            if msg.media:
                try:
                    logger.info(f"Current working directory: {os.getcwd()}")
                    logger.info(f"Intended download directory: {message_dir}")
                    logger.info(f"Downloading media for message ID {msg.id}")
                    # Save media directly to the message_dir
                    media = await msg.download_media(file=str(message_dir))
                    logger.info(f"download_media returned: {media}")
                    if media and os.path.exists(media):
                        file_ext = os.path.splitext(media)[1]
                        msg_time = msg.date.strftime("%H%M%S")
                        new_filename = f"{msg_time}_{idx}{file_ext}"
                        new_path = message_dir / new_filename
                        shutil.move(media, str(new_path))
                        media_paths.append(str(new_path))
                        logger.info(f"Media downloaded and moved to: {new_path}")
                    else:
                        logger.error(f"Media file not found after download: {media}")
                except Exception as e:
                    logger.error(f"Error downloading media: {e}")
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
# Main Function: Generate and Post Tweet
###############################

async def generate_and_post_tweet(text, media_paths, dir_name):
    """
    Aggregates data, generates tweet content with GPT, checks for duplicate content,
    and then posts the tweet (and optionally posts to Telegram).

    The function should work as follows:
    1. Check for duplicates using unified approach (Optionally need it will need to set the folder with messages - and messages lookback )
    2. Filter for unwanted content (It will require to set filtering prompt )
    2. Aggegate content before generating tweet content using OpenAI
    3. Generate tweet content using OpenAI
    4. Post the tweet if it passed all checks to all social networks and acount which were specified for posting ()
    7. Save the posting status
    """
    dir_path = Path(dir_name)  # Convert to Path object for consistent handling
    logger.info(f"Beginning generation and posting of the tweet from directory: {dir_path}")
    logger.debug(f"Original message: {text}")
    logger.info(f"Media paths: {media_paths}")

    logger.info(f"Beginning to extract content to aggregated file")
    # 1. First extract content to aggregated file
    aggregated_content = await extract_content_to_aggregated_file(text, media_paths, str(dir_path),analyze_urls=False)
    logger.info(f"Content extracted to aggregated file")

    logger.info(f"Beginning to check for duplicates")
    # 2. Check for duplicates using unified approach
    try:
        # Build a list of current media file details in the same format as expected.
        current_media_details = []
        for media in media_paths:
            # Check if file exists before getting size
            if os.path.exists(media):
                file_ext = os.path.splitext(media)[1]
                file_size = os.path.getsize(media)
                current_media_details.append({
                    "file_extension": file_ext,
                    "file_size": file_size
                })
            else:
                logger.warning(f"Media file not found during duplicate check: {media}")
                # Still add entry with 0 size to avoid breaking the check
                file_ext = os.path.splitext(media)[1]
                current_media_details.append({
                    "file_extension": file_ext,
                    "file_size": 0
                })
        
        is_duplicate = await is_duplicate_tweet(
            current_message=text,
            current_media_info=current_media_details,
            dir_path=dir_path
        )
        
        if is_duplicate:
            logger.warning("Tweet is similar to a recent message. Skipping posting to avoid duplicates.")
            # Save duplicate check decision
            try:
                duplicate_decision = {
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "is_duplicate": True,
                    "reason": "Tweet is similar to a recent message",
                    "current_message_preview": text[:100] + "..." if len(text) > 100 else text,
                    "media_count": len(current_media_details)
                }
                decision_file = os.path.join(dir_name, "duplicate_check_decision.json")
                with open(decision_file, "w", encoding="utf-8") as f:
                    json.dump(duplicate_decision, f, indent=2)
                logger.info(f"Duplicate check decision saved to {decision_file}")
            except Exception as e:
                logger.error(f"Error saving duplicate check decision: {e}")
            return
        else:
            # Save success decision when no duplicates found
            try:
                success_decision = {
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "is_duplicate": False,
                    "reason": "No duplicates found - message appears to be unique",
                    "current_message_preview": text[:100] + "..." if len(text) > 100 else text,
                    "media_count": len(current_media_details)
                }
                decision_file = os.path.join(dir_name, "duplicate_check_decision.json")
                with open(decision_file, "w", encoding="utf-8") as f:
                    json.dump(success_decision, f, indent=2)
                logger.info(f"Duplicate check decision saved to {decision_file}")
            except Exception as e:
                logger.error(f"Error saving duplicate check success decision: {e}")
            
    except Exception as e:
        logger.error(f"Error checking for duplicate tweets: {e}")
        logger.error(traceback.format_exc())
        # Save error decision
        try:
            error_decision = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "is_duplicate": False,
                "error": str(e),
                "error_type": "duplicate_check_failed"
            }
            decision_file = os.path.join(dir_name, "duplicate_check_decision.json")
            with open(decision_file, "w", encoding="utf-8") as f:
                json.dump(error_decision, f, indent=2)
            logger.info(f"Duplicate check error decision saved to {decision_file}")
        except Exception as save_error:
            logger.error(f"Error saving duplicate check error decision: {save_error}")
        # Continue with posting even if duplicate check fails

    # 3. Filter for unwanted content
    logger.info("Filtering tweet for unwanted content")
    filter_prompt = (
        "Is the following content PURELY promotional without valuable information? Note that content with BOTH promotional elements (like platform links) AND valuable market analysis should be classified as NOT promotional. "
        "If the content is purely promotional with no value, respond with 'Yes, Promotional: [explanation]'\n"
        "If the content contains valuable information (even with some promotional elements), respond with 'No'.\n\n"
        "IMPORTANT GUIDELINES:\n"
        f"1. Content from our monitored channels ({', '.join(str(ch) for ch in CHANNELS_TO_MONITOR)}) should NOT be considered promotional\n"
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
        logger.warning("Tweet identified as promotional. Skipping posting...")
        return

    # 4. Generate tweet content
    logger.info("Generating tweet content using OpenAI")
    logger.info(f"All twitter channels: {CHANNELS_TO_MONITOR}")
    prompt_text = (
        "Rewrite the following content as an engaging Twitter post. "
        "Note that the text is from the Original Message section, with helpful details in image analysis sections.\n\n"
        "IMPORTANT RULES:\n"
        f"1. REMOVE all Telegram channel mentions ({', '.join(str(ch) for ch in CHANNELS_TO_MONITOR)})\n"
        "2. KEEP essential information about the subject\n"
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

        # Post the tweet using the modularized function
        tweet_result = post_to_twitter(
            text=tweet_text,
            media_paths=media_paths,
            client_v2=client_v2,
            api_v1=api_v1,
            logger=logger
        )
        posting_status = {
            "telegram_posted": False,
            "twitter_posted": False,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        
        # Handle the new return format from post_to_twitter
        if isinstance(tweet_result, dict) and "error" in tweet_result:
            # Error occurred
            posting_status["twitter_error"] = tweet_result["error"]
            posting_status["twitter_error_type"] = tweet_result["error_type"]
            if "reset_time" in tweet_result:
                posting_status["twitter_rate_limit_reset"] = tweet_result["reset_time"]
                # Add human-readable date
                try:
                    ts = int(tweet_result["reset_time"])
                    posting_status["twitter_rate_limit_reset_utc"] = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S UTC')
                except Exception as e:
                    posting_status["twitter_rate_limit_reset_utc"] = f"Invalid timestamp: {tweet_result['reset_time']}"
        elif isinstance(tweet_result, str):
            # Success - tweet_id returned as string
            posting_status["twitter_posted"] = True
            posting_status["twitter_id"] = tweet_result
        elif tweet_result is None:
            # Fallback for old return format
            posting_status["twitter_error"] = "Failed to post tweet. See logs for details."
            posting_status["twitter_error_type"] = "unknown"
        else:
            # Unexpected return type
            posting_status["twitter_error"] = f"Unexpected return type from post_to_twitter: {type(tweet_result)}"
            posting_status["twitter_error_type"] = "unexpected_return_type"

        # Telegram posting attempt
        telegram_channel = "@silicon_echo" # e.g., "@mychannel"
        if telegram_channel:
            try:
                valid_channels = await setup_monitored_channels(client, CHANNELS_TO_MONITOR, logger=logger)
                await post_to_telegram_channel(tweet_text, media_paths, telegram_channel, client, logger=logger)
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



async def main_runner():
    """
    Continuously run the Telegram client. If disconnected or certain exceptions occur,
    wait a bit and then restart.
    """
    # Start the watchdog task
    asyncio.create_task(watchdog_task())
    
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
                valid_channels = await setup_monitored_channels(client, CHANNELS_TO_MONITOR, logger=logger)
                
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