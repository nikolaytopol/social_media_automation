import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Replace these with your actual API credentials
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')


with TelegramClient(StringSession(), API_ID , API_HASH) as client:
    print("Your session string is:")
    print(client.session.save())


SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')