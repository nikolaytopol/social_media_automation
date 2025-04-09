# processor/reposting_live.py
import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config.settings import API_ID, API_HASH, SESSION_STRING, SOURCE_CHANNELS, TARGET_CHANNEL
from processor.openai_utils import passes_filter, generate_tweet_content

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, auto_reconnect=True, connection_retries=-1)

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def new_message_handler(event):
    if event.message.grouped_id:
        return  # Album messages handled elsewhere
    message_text = event.message.message or ""
    if await passes_filter(message_text):
        new_text = await generate_tweet_content(message_text)
        if event.message.media:
            media_path = await event.message.download_media()
            await client.send_file(TARGET_CHANNEL, media_path, caption=new_text)
            os.remove(media_path)
        else:
            await client.send_message(TARGET_CHANNEL, new_text)

@client.on(events.Album(chats=SOURCE_CHANNELS))
async def album_handler(event):
    if not event.messages:
        return
    main_text = event.messages[0].message or ""
    if await passes_filter(main_text):
        new_text = await generate_tweet_content(main_text)
        media_files = []
        for msg in event.messages:
            if msg.media:
                path = await msg.download_media()
                if path:
                    media_files.append(path)
        await client.send_file(TARGET_CHANNEL, file=media_files, caption=new_text)
        for f in media_files:
            os.remove(f)

def main():
    client.run_until_disconnected()

if __name__ == '__main__':
    main()
