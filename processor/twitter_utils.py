# processor/twitter_utils.py

import os
import tweepy
import asyncio

# Load Twitter API credentials from environment variables
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

class TwitterPoster:
    def __init__(self):
        """
        Initialize the Twitter Poster.
        Sets up Tweepy clients for posting tweets and uploading media.
        """
        self.auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
        self.auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        self.api_v1 = tweepy.API(self.auth)

        self.client_v2 = tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_SECRET_KEY,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET
        )

    async def post(self, text, media_paths=None):
        """
        Post a tweet with optional media attachments.

        Args:
            text (str): The text content of the tweet.
            media_paths (list): List of local file paths to upload as media.
        """
        try:
            media_ids = []
            if media_paths:
                for path in media_paths:
                    media = self.api_v1.media_upload(path)
                    media_ids.append(media.media_id)
                print(f"[TwitterPoster] Uploaded media: {media_ids}")

            if media_ids:
                response = self.client_v2.create_tweet(text=text, media_ids=media_ids)
            else:
                response = self.client_v2.create_tweet(text=text)

            print(f"[TwitterPoster] Tweet posted: {response}")
        except Exception as e:
            print(f"[TwitterPoster] Error posting tweet: {e}")
