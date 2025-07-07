import os
import sys
import traceback
import datetime
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

print("=== Twitter Text-Only Tweet Test ===")
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
    
    print("\n=== Testing Text-Only Tweet Posting ===")
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    test_message = f"🧪 Test: Text-only tweet from test script. Time: {now}"
    
    print(f"Posting tweet: {test_message}")
    response = client_v2.create_tweet(text=test_message)
    
    print(f"✓ Text-only tweet posted successfully!")
    print(f"  Tweet ID: {response.data['id']}")
    print(f"  Tweet URL: https://twitter.com/{me.data.username}/status/{response.data['id']}")
    
    print("\n✓ Text-only tweet test passed!")
    
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