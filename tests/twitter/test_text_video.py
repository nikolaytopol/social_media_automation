import os
import sys
import traceback
import datetime
import mimetypes
import time
from dotenv import load_dotenv
import tweepy

# Load environment variables from the correct .env file location
env_path = os.path.join('workflows', 'silicon_echo', '.env')
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

print("=== Twitter Text + Video Tweet Test ===")
print(f"Loading from: {env_path}")
print(f"API_KEY: {'✓ Set' if API_KEY else '❌ Missing'}")
print(f"API_SECRET_KEY: {'✓ Set' if API_SECRET_KEY else '❌ Missing'}")
print(f"ACCESS_TOKEN: {'✓ Set' if ACCESS_TOKEN else '❌ Missing'}")
print(f"ACCESS_TOKEN_SECRET: {'✓ Set' if ACCESS_TOKEN_SECRET else '❌ Missing'}")
print(f"BEARER_TOKEN: {'✓ Set' if BEARER_TOKEN else '❌ Missing'}")

if not all([API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]):
    print("\n❌ Missing one or more Twitter API credentials.")
    sys.exit(1)

try:
    print("\n=== Setting up OAuth 1.0a for v1.1 API ===")
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api_v1 = tweepy.API(auth)
    print("✓ OAuth 1.0a setup completed")
    
    print("\n=== Setting up v2 Client ===")
    client_v2 = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET_KEY,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
    print("✓ v2 Client setup completed")
    
    print("\n=== Testing Authentication ===")
    try:
        me = client_v2.get_me()
        print(f"✓ v2 Client authenticated as: @{me.data.username}")
        print(f"  User ID: {me.data.id}")
    except Exception as e:
        print(f"❌ v2 Client authentication failed: {e}")
        sys.exit(1)
    
    try:
        me_v1 = api_v1.verify_credentials()
        print(f"✓ v1.1 API authenticated as: @{me_v1.screen_name}")
        print(f"  User ID: {me_v1.id}")
    except Exception as e:
        print(f"❌ v1.1 API authentication failed: {e}")
        sys.exit(1)
    
    print("\n=== Testing Video Upload and Tweet Posting ===")
    
    # Look for test videos in the tests/twitter directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    video_extensions = ['.mp4', '.mov', '.avi', '.m4v']
    test_videos = []
    
    for file in os.listdir(test_dir):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            test_videos.append(os.path.join(test_dir, file))
    
    if not test_videos:
        print("❌ No test videos found in tests/twitter directory")
        print("Please add some .mp4, .mov, .avi, or .m4v files to test with")
        print("Note: Twitter has strict video requirements:")
        print("- Maximum file size: 512MB")
        print("- Maximum duration: 2 minutes 20 seconds")
        print("- Supported formats: MP4, MOV, AVI, M4V")
        sys.exit(1)
    
    print(f"Found {len(test_videos)} test videos: {[os.path.basename(vid) for vid in test_videos]}")
    
    # Test with the first video
    test_video = test_videos[0]
    print(f"\nUsing test video: {os.path.basename(test_video)}")
    
    # Check file info
    file_size = os.path.getsize(test_video)
    file_type = mimetypes.guess_type(test_video)[0]
    print(f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
    print(f"File type: {file_type}")
    
    if file_size > 512 * 1024 * 1024:  # 512MB limit
        print("❌ Error: Video file is larger than 512MB (Twitter limit)")
        sys.exit(1)
    elif file_size > 100 * 1024 * 1024:  # 100MB warning
        print("⚠️  Warning: Video file is larger than 100MB, upload may take a while")
    
    # Import the timeout function from twitter.py to test it
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from twitter import wait_for_video_processing, VIDEO_PROCESSING_TIMEOUT
    
    print(f"\nVideo processing timeout configured: {VIDEO_PROCESSING_TIMEOUT} seconds")
    
    # Upload video using v1.1 API with chunked upload
    print("\n=== Uploading Video ===")
    try:
        with open(test_video, 'rb') as video_file:
            print("Starting video upload (this may take a while for large files)...")
            media = api_v1.media_upload(
                filename=os.path.basename(test_video),
                file=video_file,
                media_category='tweet_video'
            )
            media_id = media.media_id
            print(f"✓ Video uploaded successfully!")
            print(f"  Media ID: {media_id}")
    except Exception as e:
        print(f"❌ Video upload failed: {e}")
        print(traceback.format_exc())
        sys.exit(1)
    
    # Wait for video processing using the new timeout function
    print("\n=== Waiting for Video Processing ===")
    start_time = time.time()
    
    # Create a simple logger for testing
    import logging
    test_logger = logging.getLogger("test_video_processing")
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    test_logger.addHandler(handler)
    
    # Test with configured timeout
    result = wait_for_video_processing(api_v1, media_id, test_logger)
    end_time = time.time()
    
    print(f"\nVideo processing test completed in {end_time - start_time:.1f} seconds")
    print(f"Result: {'✓ Success' if result else '❌ Failed/Timeout'}")
    
    if not result:
        print("❌ Video processing failed or timed out. Cannot post tweet with video.")
        sys.exit(1)
    
    # Post tweet with video
    print("\n=== Posting Tweet with Video ===")
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    test_message = f"🧪 Test: Tweet with video from test script. Time: {now}"
    
    print(f"Posting tweet: {test_message}")
    print(f"With video media ID: {media_id}")
    
    try:
        response = client_v2.create_tweet(text=test_message, media_ids=[media_id])
        print(f"✓ Tweet with video posted successfully!")
        print(f"  Tweet ID: {response.data['id']}")
        print(f"  Tweet URL: https://twitter.com/{me.data.username}/status/{response.data['id']}")
        print("\n✓ Text + Video tweet test passed!")
    except Exception as e:
        print(f"❌ Tweet posting failed: {e}")
        print(traceback.format_exc())
        sys.exit(1)
    
except tweepy.errors.Forbidden as e:
    print(f"\n❌ Forbidden error: {e}")
    if 'oauth1 app permissions' in str(e):
        print("\n🔧 SOLUTION - Regenerate your tokens after changing app permissions")
    elif 'not permitted to perform this action' in str(e):
        print("\n🔧 SOLUTION - Check app permissions and account status")
    print(traceback.format_exc())
except tweepy.errors.Unauthorized as e:
    print(f"\n❌ Unauthorized error: {e}")
    print(traceback.format_exc())
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    print(traceback.format_exc()) 