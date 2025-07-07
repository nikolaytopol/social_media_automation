import os
import sys
import shutil
import glob
import asyncio
import datetime
import logging
import traceback

# Get the logger for this module
logger = logging.getLogger(__name__)

# Make sure BASE_DIR is defined somewhere in your project, or add:
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def fetch_recent_tweet_history(history_dir="message_history", limit=15):
    """
    Scans the message_history folder for subdirectories that contain an 'original_message.txt' file.
    """
    logger.info(f"Fetching recent tweet history (limit: {limit})")
    tweet_entries = []
    if not os.path.exists(history_dir):
        logger.warning(f"History directory {history_dir} does not exist")
        return []
    
    # Iterate over each subdirectory in message_history.
    for folder in os.listdir(history_dir):
        folder_path = os.path.join(history_dir, folder)
        if os.path.isdir(folder_path):
            original_file = os.path.join(folder_path, "original_message.txt")
            if os.path.exists(original_file):
                try:
                    mtime = os.path.getmtime(original_file)
                    with open(original_file, "r", encoding="utf-8") as f:
                        text = f.read().strip()
                    
                    # Gather media info from any files that are not known text files.
                    media_info = []
                    for file in os.listdir(folder_path):
                        if file in ["original_message.txt", "tweet_text.txt", "full_input_to_gpt.txt"]:
                            continue
                        file_path = os.path.join(folder_path, file)
                        if os.path.isfile(file_path):
                            file_ext = os.path.splitext(file)[1]
                            file_size = os.path.getsize(file_path)
                            media_info.append({
                                "file_extension": file_ext,
                                "file_size": file_size
                            })
                    
                    tweet_entries.append((mtime, {"text": text, "media_info": media_info}))
                except Exception as e:
                    logger.error(f"Error reading {original_file}: {e}")
                    logger.error(traceback.format_exc())
    
    # Sort by modification time (most recent first)
    tweet_entries.sort(key=lambda x: x[0], reverse=True)
    
    # Return only the latest 'limit' entries (extract only the dictionary part)
    recent_tweets = [entry for mtime, entry in tweet_entries[1:limit+1]]
    logger.info(f"Found {len(recent_tweets)} recent tweets")
    return recent_tweets


def analyze_twitter_link(link):
    """
    Placeholder: Analyze a Twitter link.
    TODO: Replace with actual implementation.
    """
    logger.info(f"Analyzing Twitter link: {link}")
    return f"Analysis for Twitter link {link}: [Placeholder analysis output]"

def analyze_audi(audio_path):
    """
    Placeholder: Analyze an audio file.
    TODO: Replace with actual implementation.
    """
    logger.info(f"Analyzing audio: {audio_path}")
    return f"Audio analysis for {os.path.basename(audio_path)} not implemented."


async def download_and_process_media(msg, message_dir, idx):
    try:
        logger.info(f"Downloading media for message ID {msg.id}")
        media = await msg.download_media()
        if media:
            file_ext = os.path.splitext(media)[1]
            msg_time = msg.date.strftime("%H%M%S")
            new_filename = f"{msg_time}_{idx}{file_ext}"
            new_path = message_dir / new_filename
            shutil.move(media, str(new_path))
            logger.info(f"Media downloaded and moved to: {new_path}")
            return str(new_path)
        else:
            logger.warning(f"Media download returned None for message ID {msg.id}")
            return None
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None

async def cleanup_temporary_files():
    """Periodically clean up temporary files in root directory"""
    while True:
        try:
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=1)
            for file in os.listdir(BASE_DIR):
                file_path = os.path.join(BASE_DIR, file)
                if os.path.isfile(file_path):
                    if file.startswith('tmp') or file.endswith('.temp'):
                        file_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
                        if file_time < cutoff:
                            try:
                                os.remove(file_path)
                                logger.info(f"Cleaned up old temporary file: {file_path}")
                            except Exception as e:
                                logger.error(f"Failed to clean up file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
        await asyncio.sleep(3600)

def setup_error_handlers():
    def log_exception(exctype, value, tb):
        logger.error("Uncaught exception:", exc_info=(exctype, value, tb))
        cleanup_on_error()
    sys.excepthook = log_exception

def cleanup_on_error():
    try:
        temp_pattern = os.path.join(BASE_DIR, "tmp*")
        for temp_file in glob.glob(temp_pattern):
            try:
                os.remove(temp_file)
                logger.info(f"Cleaned up temporary file during error handling: {temp_file}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file {temp_file}: {e}")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")