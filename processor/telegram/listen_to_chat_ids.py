import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Replace these with your actual credentials or set them as environment variables
API_ID = os.getenv('TELEGRAM_API_ID')        # e.g., '123456'
API_HASH = os.getenv('TELEGRAM_API_HASH')      # e.g., 'abcdef1234567890abcdef1234567890'
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')  # Your session string

# Create the Telegram client using your session string
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage())
async def handler(event):
    # Get the chat where the message was sent
    chat = await event.get_chat()
    # Get the message text; if there's no text (e.g., for media messages), this might be None
    message_text = event.message.message  
    print(f"New message in chat id: {chat.id}")
    print(f"Message content: {message_text}")

async def main():
    print("Client started. Listening for messages...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
