import os
import mimetypes
import logging
import traceback
import tweepy
import time

# Configuration options for video processing
VIDEO_PROCESSING_TIMEOUT = 300  # 5 minutes timeout for video processing
SKIP_VIDEO_PROCESSING = False   # Set to True to skip video processing entirely

# You may need to import your logger and API clients from your main workflow or pass them as arguments

def post_to_twitter(text, media_paths=None, client_v2=None, api_v1=None, logger=None):
    """
    Post a tweet with optional media using pre-configured clients.
    
    Args:
        text (str): The tweet text
        media_paths (list): List of file paths to media (optional)
        client_v2: Pre-configured Tweepy v2 Client (required)
        api_v1: Pre-configured Tweepy v1.1 API (required for media upload)
        logger: Logger instance
    Returns:
        tweet_id (str) if successful, None otherwise
    """
    if logger is None:
        logger = logging.getLogger("twitter_post")
    
    try:
        logger.info(f"Posting to Twitter: {text[:50]}... with {len(media_paths) if media_paths else 0} media items")
        
        # Check if video processing is disabled
        if SKIP_VIDEO_PROCESSING:
            logger.warning("⚠️  Video processing is disabled - videos will be skipped")
        
        # Validate required clients
        if client_v2 is None:
            logger.error("client_v2 (Tweepy v2 Client) is required for posting tweets.")
            return None
        
        if api_v1 is None:
            logger.error("api_v1 (Tweepy v1.1 API) is required for media upload.")
            return None
        
        # Upload media using OAuth 1.0a (v1.1 API)
        media_ids = []
        if media_paths:
            # Supported media types for free tier
            supported_image_types = ['.jpg', '.jpeg', '.png', '.gif']
            supported_video_types = ['.mp4', '.mov', '.avi', '.m4v']
            supported_types = supported_image_types + supported_video_types
            
            for media_path in media_paths:
                try:
                    # Check if file exists
                    if not os.path.exists(media_path):
                        logger.warning(f"Media file does not exist: {media_path}")
                        continue
                    
                    # Check file extension
                    file_ext = os.path.splitext(media_path)[1].lower()
                    if file_ext not in supported_types:
                        logger.warning(f"Unsupported media type {file_ext} for file: {media_path}")
                        continue
                    
                    # Skip videos if processing is disabled
                    if SKIP_VIDEO_PROCESSING and file_ext in supported_video_types:
                        logger.warning(f"Skipping video file due to SKIP_VIDEO_PROCESSING setting: {os.path.basename(media_path)}")
                        continue
                    
                    # Log file info for debugging
                    file_size = os.path.getsize(media_path)
                    file_type = mimetypes.guess_type(media_path)[0]
                    logger.info(f"Uploading media: {os.path.basename(media_path)}, size: {file_size}, type: {file_type}")
                    
                    # Upload media using OAuth 1.0a (v1.1 API)
                    with open(media_path, 'rb') as media_file:
                        if file_ext in supported_video_types:
                            # For videos, use chunked upload
                            logger.info(f"Starting video upload for: {os.path.basename(media_path)}")
                            media = api_v1.media_upload(
                                filename=os.path.basename(media_path),
                                file=media_file,
                                media_category='tweet_video'
                            )
                        else:
                            # For images, use simple upload
                            logger.info(f"Starting image upload for: {os.path.basename(media_path)}")
                            media = api_v1.media_upload(
                                filename=os.path.basename(media_path),
                                file=media_file
                            )
                        
                        media_ids.append(media.media_id)
                        logger.info(f"Media uploaded successfully with ID: {media.media_id}")
                        
                        # For videos, wait for processing with timeout
                        if file_ext in supported_video_types:
                            logger.info(f"Starting video processing wait for media ID: {media.media_id}")
                            processing_success = wait_for_video_processing(api_v1, media.media_id, logger)
                            if not processing_success:
                                logger.error(f"Video processing failed or timed out for media ID: {media.media_id}")
                                media_ids.remove(media.media_id)
                            
                except tweepy.errors.Forbidden as e:
                    logger.error(f"Forbidden error uploading media {media_path}: {e}")
                    if 'oauth1 app permissions' in str(e):
                        logger.error("Your Twitter app is not configured with the appropriate OAuth1 permissions.")
                        logger.error("Please ensure your app has 'Read and write and Direct message' permissions and regenerate your tokens.")
                    logger.error(traceback.format_exc())
                except Exception as e:
                    logger.error(f"Error uploading media {media_path}: {e}")
                    logger.error(traceback.format_exc())
        
        # Post the tweet using v2 endpoint
        try:
            if media_ids:
                logger.info(f"Posting tweet with {len(media_ids)} media attachments")
                response = client_v2.create_tweet(text=text, media_ids=media_ids)
            else:
                logger.info("Posting text-only tweet")
                response = client_v2.create_tweet(text=text)
            
            tweet_id = response.data['id']
            logger.info(f"Tweet posted successfully with ID: {tweet_id}")
            return tweet_id
            
        except tweepy.errors.Forbidden as e:
            logger.error(f"Twitter Forbidden error: {e}")
            if 'oauth1 app permissions' in str(e):
                logger.error("Your Twitter app is not configured with the appropriate OAuth1 permissions.")
                logger.error("Please ensure your app has 'Read and write and Direct message' permissions and regenerate your tokens.")
            logger.error(traceback.format_exc())
            return {"error": str(e), "error_type": "forbidden"}
        except tweepy.errors.Unauthorized as e:
            logger.error(f"Twitter authentication error: {e}")
            logger.error("Check your Twitter API credentials and ensure tokens are regenerated after permission changes.")
            return {"error": str(e), "error_type": "unauthorized"}
        except tweepy.errors.TooManyRequests as e:
            logger.error(f"Twitter rate limit exceeded: {e}")
            reset_time = e.response.headers.get('x-rate-limit-reset', 'unknown')
            logger.error(f"Rate limit resets at: {reset_time}")
            return {"error": str(e), "error_type": "rate_limit", "reset_time": reset_time}
        except Exception as e:
            logger.error(f"Unexpected error posting to Twitter: {e}")
            logger.error(traceback.format_exc())
            return {"error": str(e), "error_type": "unexpected"}
            
    except Exception as e:
        logger.error(f"Unexpected error in post_to_twitter: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e), "error_type": "general"}

def wait_for_video_processing(api_v1, media_id, logger, max_wait_time=None, check_interval=5):
    """
    Wait for video processing to complete with timeout and detailed logging.
    
    Args:
        api_v1: Tweepy v1.1 API client
        media_id: Media ID to check
        logger: Logger instance
        max_wait_time: Maximum time to wait in seconds (uses VIDEO_PROCESSING_TIMEOUT if None)
        check_interval: Time between status checks in seconds (default: 5)
    
    Returns:
        bool: True if processing completed successfully, False otherwise
    """
    if max_wait_time is None:
        max_wait_time = VIDEO_PROCESSING_TIMEOUT
    
    logger.info(f"Starting video processing wait for media ID: {media_id}")
    logger.info(f"Max wait time: {max_wait_time} seconds, Check interval: {check_interval} seconds")
    
    start_time = time.time()
    wait_time = 0
    check_count = 0
    
    while wait_time < max_wait_time:
        try:
            check_count += 1
            logger.debug(f"Check #{check_count}: Checking status for media ID: {media_id}")
            
            status = api_v1.get_media_upload_status(media_id)
            
            # Log the full status for debugging
            logger.debug(f"Media status: {status}")
            
            if status.processing_info is None:
                logger.info(f"✓ Video processing completed successfully for media ID: {media_id}")
                logger.info(f"Total processing time: {wait_time:.1f} seconds")
                return True
                
            elif status.processing_info['state'] == 'failed':
                error_info = status.processing_info.get('error', {})
                logger.error(f"❌ Video processing failed for media ID: {media_id}")
                logger.error(f"Error details: {error_info}")
                logger.error(f"Processing info: {status.processing_info}")
                return False
                
            elif status.processing_info['state'] == 'succeeded':
                logger.info(f"✓ Video processing succeeded for media ID: {media_id}")
                logger.info(f"Total processing time: {wait_time:.1f} seconds")
                return True
                
            elif status.processing_info['state'] == 'pending':
                progress = status.processing_info.get('progress_percent', 0)
                logger.info(f"⏳ Video processing pending: {progress}% complete (media ID: {media_id})")
                
            elif status.processing_info['state'] == 'in_progress':
                progress = status.processing_info.get('progress_percent', 0)
                logger.info(f"⏳ Video processing in progress: {progress}% complete (media ID: {media_id})")
                
            else:
                logger.warning(f"Unknown processing state: {status.processing_info['state']} for media ID: {media_id}")
                # If we get an unknown state, check if it might be a success state
                if 'succeeded' in str(status.processing_info['state']).lower():
                    logger.info(f"✓ Video processing appears to be completed (state: {status.processing_info['state']})")
                    logger.info(f"Total processing time: {wait_time:.1f} seconds")
                    return True
            
            # Sleep before next check
            time.sleep(check_interval)
            wait_time += check_interval
            
            # Log progress every 30 seconds
            if check_count % 6 == 0:  # Every 6 checks (30 seconds)
                logger.info(f"Still waiting for video processing... ({wait_time:.0f}s elapsed)")
            
        except tweepy.errors.TweepyException as e:
            logger.error(f"Twitter API error checking video status for media ID {media_id}: {e}")
            logger.error(traceback.format_exc())
            time.sleep(check_interval)
            wait_time += check_interval
            
        except Exception as e:
            logger.error(f"Unexpected error checking video status for media ID {media_id}: {e}")
            logger.error(traceback.format_exc())
            time.sleep(check_interval)
            wait_time += check_interval
    
    # Timeout reached
    logger.error(f"❌ Video processing timed out after {max_wait_time} seconds for media ID: {media_id}")
    logger.error(f"Total checks performed: {check_count}")
    logger.error(f"Total time waited: {wait_time:.1f} seconds")
    return False
