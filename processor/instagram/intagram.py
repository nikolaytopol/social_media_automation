import asyncio
import aiohttp
import os
from instagrapi import Client as InstaClient
from telethon import TelegramClient, events
from telethon.sessions import StringSession
# ---------------- Configuration ----------------
# Destination Instagram account credentials
INSTAGRAM_DEST_USERNAME = 'podzalupnaja_pizdoprojebina'
INSTAGRAM_DEST_PASSWORD = 'xuzde4-guQxak-gycqag'



# Telegram API keys and session string
TELEGRAM_API_ID='4589443'
TELEGRAM_API_HASH='9cbf638112eab9133ac99b1977f7aed9'
TELEGRAM_SESSION_STRING='1BJWap1wBu6dJdPMca8j6oE7mXck4k8AsilYvQL9hw0qL-mTl1A0s6KPhshUAvKNuDkZgpQ3TdianRaGVNKg5aK_N8H_r-Ab94R36lMdaHWBvzdNQwrA2u3BciJUIRaUNdiJJbOPDqqnaTJINSnQboR_cSz_XWib3J5ecl9ww-G6sszs9vWc3yuSXTCKXGLE6-D5yEEcxm_5nlT8lq0Zz-Cnhr8CtMWoBrKFhCQerD6cD_pJ1kidNXj0_nG3dFjv0XI4ejBRZYGU3gC-Wza0Se6YLI6rCDpJX7ufd3oVHWyJeYoyH1jGKCZhuTcX7VI0RoP-Szg0-dvI0q_H7BjkFRtNXkyR80-s='

# --- Make Telethon more resilient ---
client = TelegramClient(
    StringSession(TELEGRAM_SESSION_STRING),
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    connection_retries=-1,  # unlimited retries
    auto_reconnect=True
)
telegram_channel = "@angelsclothesshop"  # Optional: set to a channel username (e.g., "@mychannel")

# List of source Instagram account links to monitor
SOURCE_ACCOUNTS = [
    "https://www.instagram.com/main.kink/",
    "https://www.instagram.com/annamaylow/",
]

# Polling interval in seconds
POLL_INTERVAL = 60

# Dictionary to track last seen media IDs for each account:
# { username: { "posts": last_post_pk, "stories": last_story_pk } }
last_seen = {}

# ------------- HELPER FUNCTIONS -------------
def extract_username(url: str) -> str:
    """Extract the username from an Instagram URL."""
    return url.strip('/').split('/')[-1]

def download_media_from_source(insta_client: InstaClient, media_pk: int) -> str:
    """
    Downloads the media (post or story) by its primary key.
    Returns the local file path of the downloaded media.
    """
    media_info = insta_client.media_info(media_pk)
    if media_info.media_type == 1:  # Photo
        path = insta_client.photo_download(media_info.pk)
    elif media_info.media_type == 2:  # Video
        path = insta_client.video_download(media_info.pk)
    elif media_info.media_type == 8:  # Carousel – for simplicity, download f$irst item
        path = insta_client.photo_download(media_info.pk)
    else:
        path = None
    return path


async def post_to_telegram_channel(text, media_paths, channel_username):
    """
    Posts the given text (and optionally media) to the specified Telegram channel.
    The channel_username is the channel's username (e.g. "@mychannel").
    """
    try:
        if media_paths:
            await client.send_file(channel_username, media_paths, caption=text)
        else:
            await client.send_message(channel_username, text)
        print(f"Posted to Telegram channel: {channel_username}")
    except Exception as e:
        print(f"Error posting to Telegram channel {channel_username}: {e}")

async def post_to_telegram_channel(text: str, media_path: str, channel_username: str):
    """
    Posts the given text (and optionally media) to the specified Telegram channel.
    The channel_username is the channel's username (e.g. "@mychannel").
    """
    try:
        if media_path:
            await client.send_file(channel_username, media_path, caption=text)
        else:
            await client.send_message(channel_username, text)
        print(f"Posted to Telegram channel: {channel_username}")
    except Exception as e:
        print(f"Error posting to Telegram channel {channel_username}: {e}")

# ------------- INSTAGRAM PROCESSING FUNCTIONS -------------
async def process_source_posts(source_url: str, insta_client: InstaClient):
    """Polls for new posts from a source account and reposts them."""
    username = extract_username(source_url)
    if username not in last_seen:
        last_seen[username] = {"posts": 0, "stories": 0}

    # Get the user ID (wrapped in asyncio.to_thread since it’s a blocking call)
    user_id = await asyncio.to_thread(insta_client.user_id_from_username, username)
    medias = await asyncio.to_thread(insta_client.user_medias, user_id, 10)  # Get latest 10 posts
    
    # Filter new posts based on media primary key
    new_medias = [media for media in medias if media.pk > last_seen[username]["posts"]]
    if new_medias:
        last_seen[username]["posts"] = max(media.pk for media in new_medias)
    
    for media in new_medias:
        print(f"[Posts] New media from {username}: {media.pk}")
        media_path = await asyncio.to_thread(download_media_from_source, insta_client, media.pk)
        if media_path:
            caption_text = f"Reposted from {username}"
            # Repost to destination Instagram account based on media type
            if media.media_type == 1:  # Photo
                await asyncio.to_thread(dest_client.photo_upload, media_path, caption_text)
            elif media.media_type == 2:  # Video
                await asyncio.to_thread(dest_client.video_upload, media_path, caption_text)
            print(f"Reposted media {media.pk} to Instagram")

          
            # Optionally, also post to a Telegram channel if defined
            if telegram_channel:
                await post_to_telegram_channel(caption_text, media_path, telegram_channel)
        else:
            print(f"Failed to download media {media.pk}")

async def process_source_stories(source_url: str, insta_client: InstaClient):
    """Polls for new stories from a source account and reposts them."""
    username = extract_username(source_url)
    if username not in last_seen:
        last_seen[username] = {"posts": 0, "stories": 0}

    user_id = await asyncio.to_thread(insta_client.user_id_from_username, username)
    stories = await asyncio.to_thread(insta_client.user_stories, user_id)
    
    new_stories = [story for story in stories if story.pk > last_seen[username]["stories"]]
    if new_stories:
        last_seen[username]["stories"] = max(story.pk for story in new_stories)
    
    for story in new_stories:
        print(f"[Stories] New story from {username}: {story.pk}")
        media_path = await asyncio.to_thread(download_media_from_source, insta_client, story.pk)
        if media_path:
            # Upload as an Instagram story (mind Instagram’s dimension restrictions)
            await asyncio.to_thread(dest_client.story_upload, media_path)
            print(f"Reposted story {story.pk} to Instagram")

            caption_text = f"Story from {username}"
            
            if telegram_channel:
                await post_to_telegram_channel(caption_text, media_path, telegram_channel)
        else:
            print(f"Failed to download story {story.pk}")

async def poll_sources():
    """Main polling loop that checks each source account for new posts and stories."""
    while True:
        for source in SOURCE_ACCOUNTS:
            try:
                # Process posts and stories concurrently for each source account
                await asyncio.gather(
                    process_source_posts(source, dest_client),
                    process_source_stories(source, dest_client)
                )
            except Exception as e:
                print(f"Error processing {source}: {e}")
        await asyncio.sleep(POLL_INTERVAL)

# ------------- MAIN EXECUTION -------------
if __name__ == "__main__":
    # Create and login to the destination Instagram client
    dest_client = InstaClient()
    dest_client.login(INSTAGRAM_DEST_USERNAME, INSTAGRAM_DEST_PASSWORD)
    
    print("Logged into Instagram. Starting to poll for new posts and stories...")
    
    # Start the Telegram client (in an async context)
    async def main():
        async with client:
            await poll_sources()
    
    asyncio.run(main())