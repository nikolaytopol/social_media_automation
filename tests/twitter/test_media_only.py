import os
import sys
import traceback
import datetime
import mimetypes
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

print("=== Twitter Media-Only Tweet Test ===")
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
    
    print("\n=== Testing Media-Only Tweet Posting ===")
    
    # Look for test images in the tests/twitter directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    test_images = []
    
    for file in os.listdir(test_dir):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            test_images.append(os.path.join(test_dir, file))
    
    if not test_images:
        print("❌ No test images found in tests/twitter directory")
        print("Please add some .jpg, .jpeg, .png, or .gif files to test with")
        sys.exit(1)
    
    print(f"Found {len(test_images)} test images: {[os.path.basename(img) for img in test_images]}")
    
    # Test with the first image
    test_image = test_images[0]
    print(f"\nUsing test image: {os.path.basename(test_image)}")
    
    # Check file info
    file_size = os.path.getsize(test_image)
    file_type = mimetypes.guess_type(test_image)[0]
    print(f"File size: {file_size} bytes")
    print(f"File type: {file_type}")
    
    if file_size > 5 * 1024 * 1024:  # 5MB limit
        print("⚠️  Warning: File is larger than 5MB")
    
    # Upload media using v1.1 API
    print("\n=== Uploading Media ===")
    try:
        with open(test_image, 'rb') as media_file:
            media = api_v1.media_upload(
                filename=os.path.basename(test_image),
                file=media_file
            )
            media_id = media.media_id
            print(f"✓ Media uploaded successfully!")
            print(f"  Media ID: {media_id}")
    except Exception as e:
        print(f"❌ Media upload failed: {e}")
        print(traceback.format_exc())
        sys.exit(1)
    
    # Post tweet with media only (no text)
    print("\n=== Posting Media-Only Tweet ===")
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"Posting media-only tweet (no text)")
    print(f"With media ID: {media_id}")
    
    try:
        response = client_v2.create_tweet(media_ids=[media_id])
        print(f"✓ Media-only tweet posted successfully!")
        print(f"  Tweet ID: {response.data['id']}")
        print(f"  Tweet URL: https://twitter.com/{me.data.username}/status/{response.data['id']}")
        print("\n✓ Media-only tweet test passed!")
    except Exception as e:
        print(f"❌ Media-only tweet posting failed: {e}")
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