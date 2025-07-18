from telethon.sync import TelegramClient
from telethon.sessions import StringSession



# Do I really need apiid and hash here?

session_string = input('Enter your session string: ')

with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
    print(f"{'Dialog Name':40} | {'Dialog ID'}")
    print('-' * 60)
    for dialog in client.iter_dialogs():
        print(f"{dialog.name:40} | {dialog.id}") 
