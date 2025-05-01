import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# Replace these with your actual credentials or set them as environment variables.
API_ID = os.getenv('TELEGRAM_API_ID')            # e.g., '123456'
API_HASH = os.getenv('TELEGRAM_API_HASH')          # e.g., 'abcdef1234567890abcdef1234567890'
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')  # Your session string

# Create the client using your session string.
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def list_all_dialogs():
    print("Listing all dialogs (channels, groups, and chats):")
    async for dialog in client.iter_dialogs():
        # For channels, you may check the entity type.
        entity_type = type(dialog.entity).__name__
        print(f"Name: {dialog.name}, ID: {dialog.id}, Type: {entity_type}")

async def fetch_historical_messages(chat_id, limit=100):
    print(f"\nFetching the last {limit} messages from chat id: {chat_id}")
    messages = await client.get_messages(chat_id, limit=limit)
    for message in messages:
        print(f"Message ID: {message.id} | Content: {message.text}")

async def main():
    # First, list all dialogs so you can identify the chat id of the channel you're interested in.
    await list_all_dialogs()
    
    # Once you've identified the chat ID of a channel (even if it isn't currently active),
    # you can fetch historical messages from that channel.
    #
    # For example, replace CHAT_ID with the actual id (it can be a numeric id or even a username, e.g., '@channelusername')
    CHAT_ID = input("\nEnter the chat id (or username like @channelusername) to fetch historical messages: ")
    
    # Optionally, convert to int if needed. For usernames, keep it as a string.
    try:
        CHAT_ID = int(CHAT_ID)
    except ValueError:
        pass  # If it's not an int, it might be a username.
    
    await fetch_historical_messages(CHAT_ID, limit=100)

with client:
    client.loop.run_until_complete(main())
