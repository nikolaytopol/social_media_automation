# processor/instagram_utils.py

import asyncio
from instagrapi import Client as InstaClient

class InstagramReader:
    def __init__(self, source_accounts, destination_accounts, telegram_poster=None):
        """
        Initialize Instagram Reader.

        Args:
            source_accounts (list): List of Instagram source usernames.
            destination_accounts (list): List of destination account credentials (dicts with 'username' and 'password').
            telegram_poster (optional): TelegramPoster instance to repost to Telegram.
        """
        self.source_accounts = source_accounts
        self.destination_accounts = destination_accounts
        self.destination_clients = []
        self.telegram_poster = telegram_poster
        self.poll_interval = 60  # Default polling every 60 seconds
        self.last_seen = {}  # {username: {"posts": last_post_pk, "stories": last_story_pk}}

    async def login_all(self):
        """
        Login to all destination Instagram accounts.
        """
        for creds in self.destination_accounts:
            client = InstaClient()
            client.login(creds['username'], creds['password'])
            self.destination_clients.append(client)
        print(f"[InstagramReader] Logged into {len(self.destination_clients)} Instagram destination accounts.")

    async def start_polling(self):
        """
        Start polling the source accounts.
        """
        await self.login_all()
        while True:
            await self.poll_sources_once()
            await asyncio.sleep(self.poll_interval)

    async def poll_sources_once(self):
        """
        Check for new posts and stories from all source accounts.
        """
        for source_username in self.source_accounts:
            try:
                await asyncio.gather(
                    self.process_source_posts(source_username),
                    self.process_source_stories(source_username)
                )
            except Exception as e:
                print(f"[InstagramReader] Error processing {source_username}: {e}")

    async def process_source_posts(self, username):
        """
        Fetch and repost new posts from a source account.
        """
        if username not in self.last_seen:
            self.last_seen[username] = {"posts": 0, "stories": 0}

        temp_client = InstaClient()
        await asyncio.to_thread(temp_client.login_anonymous)

        user_id = await asyncio.to_thread(temp_client.user_id_from_username, username)
        medias = await asyncio.to_thread(temp_client.user_medias, user_id, 10)
        new_medias = [media for media in medias if media.pk > self.last_seen[username]["posts"]]
        if new_medias:
            self.last_seen[username]["posts"] = max(media.pk for media in new_medias)

        for media in new_medias:
            print(f"[InstagramReader] New post from {username}: {media.pk}")
            media_path = await asyncio.to_thread(self.download_media, temp_client, media.pk)
            if media_path:
                caption_text = f"Reposted from {username}"
                await self.repost_to_destinations(media, media_path, caption_text)
            else:
                print(f"[InstagramReader] Failed to download media {media.pk}")

    async def process_source_stories(self, username):
        """
        Fetch and repost new stories from a source account.
        """
        if username not in self.last_seen:
            self.last_seen[username] = {"posts": 0, "stories": 0}

        temp_client = InstaClient()
        await asyncio.to_thread(temp_client.login_anonymous)

        user_id = await asyncio.to_thread(temp_client.user_id_from_username, username)
        stories = await asyncio.to_thread(temp_client.user_stories, user_id)
        new_stories = [story for story in stories if story.pk > self.last_seen[username]["stories"]]
        if new_stories:
            self.last_seen[username]["stories"] = max(story.pk for story in new_stories)

        for story in new_stories:
            print(f"[InstagramReader] New story from {username}: {story.pk}")
            media_path = await asyncio.to_thread(self.download_media, temp_client, story.pk)
            if media_path:
                await self.repost_story_to_destinations(media_path)
            else:
                print(f"[InstagramReader] Failed to download story {story.pk}")

    async def download_media(self, client, media_pk):
        """
        Download a media file.
        """
        media_info = await asyncio.to_thread(client.media_info, media_pk)
        if media_info.media_type == 1:
            return await asyncio.to_thread(client.photo_download, media_info.pk)
        elif media_info.media_type == 2:
            return await asyncio.to_thread(client.video_download, media_info.pk)
        elif media_info.media_type == 8:
            return await asyncio.to_thread(client.photo_download, media_info.pk)
        return None

    async def repost_to_destinations(self, media, media_path, caption_text):
        """
        Upload media as a post to all destination Instagram accounts.
        """
        for client in self.destination_clients:
            if media.media_type == 1:
                await asyncio.to_thread(client.photo_upload, media_path, caption_text)
            elif media.media_type == 2:
                await asyncio.to_thread(client.video_upload, media_path, caption_text)
            print(f"[InstagramReader] Reposted media {media.pk} to one destination.")

        if self.telegram_poster:
            await self.telegram_poster.post_to_telegram_channel(caption_text, media_path)

    async def repost_story_to_destinations(self, media_path):
        """
        Upload media as a story to all destination Instagram accounts.
        """
        for client in self.destination_clients:
            await asyncio.to_thread(client.story_upload, media_path)
            print(f"[InstagramReader] Reposted story to one destination.")

        if self.telegram_poster:
            await self.telegram_poster.post_to_telegram_channel("Instagram Story reposted", media_path)
