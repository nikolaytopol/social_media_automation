from telethon.sync import TelegramClient
from telethon.sessions import StringSession


phone = input('Enter your phone number: ')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start(phone=phone)
    print('Session string:')
    print(client.session.save()) 
