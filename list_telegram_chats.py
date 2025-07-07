from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 7178098  # <-- Replace with your API ID
api_hash = 'e5a435bec5c99532f1e019c3738eab8c'  # <-- Replace with your API Hash

session_string = input('Enter your session string: ')

with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
    print(f"{'Dialog Name':40} | {'Dialog ID'}")
    print('-' * 60)
    for dialog in client.iter_dialogs():
        print(f"{dialog.name:40} | {dialog.id}") 