from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Define your API ID and API Hash here
api_id = 7178098  # <-- Replace with your API ID
api_hash = 'e5a435bec5c99532f1e019c3738eab8c'  # <-- Replace with your API Hash

phone = input('Enter your phone number: ')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start(phone=phone)
    print('Session string:')
    print(client.session.save()) 