###############################
# Duplicate Tweet Prevention Helpers
###############################

import os
from pathlib import Path
import logging
import traceback
from models_openai import duplicate_checker
import json

# Get the logger for this module
logger = logging.getLogger(__name__)

def fetch_posted_tweet_history(history_dir=None, limit=25):
    """
    Fetch history from a specified directory using absolute paths.
    
    Args:
        history_dir (str or Path): Directory to search for posted messages. 
                                 If None, uses default POSTED_MESSAGES_DIR
        limit (int): Maximum number of recent messages to return
    
    Returns:
        list: List of message data dictionaries
    """
    # If no directory specified, use the default POSTED_MESSAGES_DIR
    if history_dir is None:
        # Get the workflow directory (parent of this file)
        workflow_dir = Path(__file__).parent
        history_dir = workflow_dir / "posted_messages"
    
    # Convert to Path object if string
    history_dir = Path(history_dir)
    
    logger.info(f"Fetching posted message history from {history_dir} (limit: {limit})")
    
    if not history_dir.exists():
        logger.warning(f"History directory '{history_dir}' does not exist")
        return []
    
    try:
        # Get directories sorted by modification time
        message_dirs = sorted(
            [d for d in history_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        history = []
        for message_dir in message_dirs:
            try:
                # Try to get tweet text
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
                
                # Get posting status if available
                posting_status = {}
                status_file = message_dir / "posting_status.json"
                if status_file.exists():
                    with open(status_file, "r", encoding="utf-8") as f:
                        posting_status = json.load(f)
                
                history.append({
                    "text": message_text,
                    "media_info": media_info,
                    "directory": str(message_dir),
                    "posting_status": posting_status
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

def media_file_equal(m1, m2, tolerance=0.01):
    """
    Compares two media file tuples (file_extension, file_size).
    """
    ext1, size1 = m1
    ext2, size2 = m2
    if ext1 != ext2:
        logger.info(f"Extension mismatch: {ext1} vs {ext2}")
        return False
    # Avoid division by zero and allow exact zero-size files.
    if size1 == 0 and size2 == 0:
        logger.info(f"Both files are zero size: {ext1}")
        return True
    # Check if the relative difference is within the tolerance.
    diff_ratio = abs(size1 - size2) / max(size1, size2)
    logger.info(f"Size comparison: {size1} vs {size2}, diff_ratio: {diff_ratio:.4f}, tolerance: {tolerance}")
    return diff_ratio <= tolerance

def media_list_equal(list1, list2, tolerance=0.01):
    """
    Compares two lists of media file tuples.
    """
    if len(list1) != len(list2):
        logger.info(f"List length mismatch: {len(list1)} vs {len(list2)}")
        return False
    
    # Sort both lists for consistent comparison
    sorted_list1 = sorted(list1)
    sorted_list2 = sorted(list2)
    
    logger.info(f"Comparing sorted lists: {len(sorted_list1)} vs {len(sorted_list2)} files")
    
    for i, (m1, m2) in enumerate(zip(sorted_list1, sorted_list2)):
        if not media_file_equal(m1, m2, tolerance):
            # Log the mismatch for debugging
            ext1, size1 = m1
            ext2, size2 = m2
            diff_ratio = abs(size1 - size2) / max(size1, size2) if max(size1, size2) > 0 else 0
            logger.info(f"Media mismatch at index {i}: {ext1}({size1}) vs {ext2}({size2}), diff_ratio: {diff_ratio:.4f}")
            return False
        else:
            logger.info(f"Media match at index {i}: {m1[0]}({m1[1]}) matches {m2[0]}({m2[1]})")
    
    logger.info("All media files match")
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
    logger.info(f"Checking media match with {len(normalized_current)} current files")
    logger.info(f"Current media: {current_media_str}")
    
    # Log current media files in detail
    for i, (ext, size) in enumerate(normalized_current):
        logger.info(f"Current media {i}: {ext} ({size} bytes)")
    
    for i, entry in enumerate(recent_entries):
        normalized_past = normalized_media_info(entry["media_info"])
        logger.info(f"Comparing with entry {i}: {len(normalized_past)} past files")
        logger.info(f"Past media: {format_media_info(entry['media_info'])}")
        
        # Log past media files in detail
        for j, (ext, size) in enumerate(normalized_past):
            logger.info(f"Past media {j}: {ext} ({size} bytes)")
        
        if media_list_equal(normalized_current, normalized_past, tolerance=0.01):
            # Enhanced logging - show exactly which tweet matched
            match_dir = os.path.basename(entry["directory"])
            match_text = entry["text"][:50] + "..." if len(entry["text"]) > 50 else entry["text"]
            logger.warning(f"DUPLICATE DETECTED (Media Match): Files match with tweet in: {match_dir}")
            logger.warning(f"Media match details: Current files: {len(normalized_current)}, Past files: {len(normalized_past)}")
            logger.warning(f"Matched tweet text begins with: '{match_text}'")
            return True
        else:
            logger.info(f"No media match with entry {i}")
            logger.info(f"Current: {len(normalized_current)} files, Past: {len(normalized_past)} files")
    
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
    
    # 1.3 Special case: Empty messages with same media (common for media-only posts)
    if not current_message or len(current_message.strip()) == 0:
        logger.info("Current message is empty - checking for empty messages with same media")
        for i, entry in enumerate(recent_entries):
            if not entry["text"] or len(entry["text"].strip()) == 0:
                # Both messages are empty, compare media
                normalized_past = normalized_media_info(entry["media_info"])
                if media_list_equal(normalized_current, normalized_past, tolerance=0.01):
                    match_dir = os.path.basename(entry["directory"])
                    logger.warning(f"DUPLICATE DETECTED (Empty Text + Media Match): Files match with tweet in: {match_dir}")
                    logger.warning(f"Both messages are empty with same media files")
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