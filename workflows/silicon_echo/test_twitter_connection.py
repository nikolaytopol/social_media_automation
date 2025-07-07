import os
import sys
import traceback
from dotenv import load_dotenv
import tweepy
import datetime

# Load environment variables from the correct .env file location
env_path = os.path.join('workflows', 'silicon_echo', '.env')
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

print("=== Twitter API Credentials Check ===")
print(f"Loading from: {env_path}")
print(f"API_KEY: {'✓ Set' if API_KEY else '❌ Missing'}")
print(f"API_SECRET_KEY: {'✓ Set' if API_SECRET_KEY else '❌ Missing'}")
print(f"ACCESS_TOKEN: {'✓ Set' if ACCESS_TOKEN else '❌ Missing'}")
print(f"ACCESS_TOKEN_SECRET: {'✓ Set' if ACCESS_TOKEN_SECRET else '❌ Missing'}")
print(f"BEARER_TOKEN: {'✓ Set' if BEARER_TOKEN else '❌ Missing'}")

if not all([API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]):
    print("\n❌ Missing one or more Twitter API credentials. Please check your .env file.")
    sys.exit(1)

try:
    print("\n=== Setting up OAuth 1.0a for v1.1 API ===")
    # Set up OAuth 1.0a for media upload (v1.1 API)
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api_v1 = tweepy.API(auth)
    print("✓ OAuth 1.0a setup completed")
    
    print("\n=== Setting up v2 Client ===")
    # Set up v2 Client for posting tweets
    client_v2 = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET_KEY,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
    print("✓ v2 Client setup completed")
    
    print("\n=== Testing Authentication ===")
    # Test 1: Try to verify user with v2 client
    try:
        me = client_v2.get_me()
        print(f"✓ v2 Client authenticated as: @{me.data.username}")
        print(f"  User ID: {me.data.id}")
    except Exception as e:
        print(f"❌ v2 Client authentication failed: {e}")
    
    # Test 2: Try to verify with v1.1 API
    try:
        me_v1 = api_v1.verify_credentials()
        print(f"✓ v1.1 API authenticated as: @{me_v1.screen_name}")
        print(f"  User ID: {me_v1.id}")
    except Exception as e:
        print(f"❌ v1.1 API authentication failed: {e}")
    
    print("\n=== Testing Tweet Posting ===")
    # Test 3: Try to post a text-only tweet using v2 endpoint
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    test_message = f"Test tweet from Tweepy v2 endpoint - testing OAuth 1.0a setup. Time: {now}"
    response = client_v2.create_tweet(text=test_message)
    print(f"✓ Text-only tweet posted successfully!")
    print(f"  Tweet ID: {response.data['id']}")
    print(f"  Tweet URL: https://twitter.com/user/status/{response.data['id']}")
    
    print("\n✓ All tests passed! Your Twitter API setup is working correctly.")
    
except tweepy.errors.Forbidden as e:
    print(f"\n❌ Forbidden error: {e}")
    if 'oauth1 app permissions' in str(e):
        print("\n🔧 SOLUTION - You need to regenerate your tokens:")
        print("1. Go to https://developer.x.com/en/portal/projects-and-apps")
        print("2. Select your app")
        print("3. Go to 'Keys and tokens' tab")
        print("4. Under 'Authentication Tokens', click 'Regenerate' for Access Token and Secret")
        print("5. Copy the new tokens to your .env file")
        print("6. Restart your application")
        print("\n⚠️  IMPORTANT: Old tokens won't work after changing app permissions!")
    elif 'not permitted to perform this action' in str(e):
        print("\n🔧 SOLUTION - Check your app permissions and account status:")
        print("1. Go to https://developer.x.com/en/portal/projects-and-apps")
        print("2. Select your app")
        print("3. Check that permissions are set to 'Read and write and Direct message'")
        print("4. Check that your Twitter account is not suspended or restricted")
        print("5. Verify your app is approved and active")
        print("6. Try posting manually to Twitter to ensure your account can post")
    elif 'duplicate content' in str(e):
        print("\n❌ Twitter rejected the tweet as duplicate content. Try changing the tweet text or adding a timestamp.")
    print(traceback.format_exc())
except tweepy.errors.Unauthorized as e:
    print(f"\n❌ Unauthorized error: {e}")
    print("\n🔧 SOLUTION:")
    print("1. Check your API keys and tokens in .env file")
    print("2. Ensure tokens are regenerated after changing app permissions")
    print("3. Verify your app is approved and active")
    print(traceback.format_exc())
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    print(traceback.format_exc()) 