from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get credentials with validation
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
session_string = os.getenv("TELEGRAM_SESSION_STRING")

# Validate credentials
if not api_id or not api_hash:
    print("ERROR: Telegram API credentials not found in environment variables.")
    print("Please make sure TELEGRAM_API_ID and TELEGRAM_API_HASH are set in your .env file.")
    exit(1)

if not session_string:
    print("WARNING: TELEGRAM_SESSION_STRING not found. New session will be created.")
    # For new session creation, uncomment the following line:
    # session_string = ""

# Convert api_id to integer (required by Telethon)
api_id = int(api_id)

client = TelegramClient(StringSession(session_string), api_id, api_hash)

async def test_connection():
    await client.start()
    me = await client.get_me()
    print(f"Connected as: {me.first_name} ({me.username})")
    await client.disconnect()

# Run the test
import asyncio
asyncio.run(test_connection())