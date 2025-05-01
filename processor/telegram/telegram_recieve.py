from collections import defaultdict
import asyncio
import os
import datetime
import shutil
from telethon import TelegramClient, events
from telethon.sessions import StringSession

def setup_telegram_bot(client, channels, output_folder):
    # Global dictionaries and sets for grouping messages
    grouped_media = defaultdict(list)  # grouped by grouped_id
    group_processing = set()           # groups currently being processed
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent tasks

    @client.on(events.NewMessage(chats=channels))
    async def handler(event):
        try:
            print("Handler triggered!")
            print(f"Message received from chat: {event.chat_id}")
            message = event.message
            grouped_id = getattr(message, "grouped_id", None)
            print(f"Current group_processing: {group_processing}")
            print(f"Current grouped_media keys: {list(grouped_media.keys())}")

            if grouped_id:
                # Add message to its group

                print("Receiving grouped message...")
                grouped_media[grouped_id].append(message)
                if grouped_id not in group_processing:
                    group_processing.add(grouped_id)
                    asyncio.create_task(process_group_id(grouped_id))
            else:
                # For a single message, create a unique grouped_id
                print("Receiving single message...")
                timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                grouped_id = f"single_{timestamp_str}"
                grouped_media[grouped_id].append(message)
                if grouped_id not in group_processing:
                    group_processing.add(grouped_id)
                    asyncio.create_task(process_group_id(grouped_id))
        except Exception as e:
            print(f"Error in handler: {e}")

    # @client.on(events.NewMessage)
    # async def debug_handler(event):
    #     try:
    #         print(f"Debug Handler: Message received from chat: {event.chat_id}")
    #         print(f"Debug Handler: Message content: {event.message.text}")
    #     except Exception as e:
    #         print(f"Error in debug handler: {e}")
        
    async def process_group_id(grouped_id):
        async with semaphore:
            try:
                messages = grouped_media[grouped_id]
                earliest_message = min(messages, key=lambda msg: msg.date)
                print(f"Processing group {grouped_id} with {len(messages)} messages...")

                # Extract text and generate a base prefix for filenames and folder names
                text = earliest_message.text if earliest_message.text else ""
                timestamp_str = earliest_message.date.strftime("%Y%m%d_%H%M%S")
                message_preview = text[:6].replace(" ", "_") if text else "no_text"

                # Count the number of media files in the group
                media_count = sum(1 for msg in messages if msg.media)
                is_single = media_count == 1

                # Generate the folder name based on whether it's a single or grouped message
                folder_name = f"{timestamp_str}_{message_preview}_{'single' if is_single else 'grouped'}"

                # Create the directory for this group's data
                dir_name = os.path.join(output_folder, folder_name)
                if not os.path.exists(dir_name):
                    os.makedirs(dir_name)

                media_paths = []
                base_filename = f"{timestamp_str}_{message_preview}"

                # Download media files for all messages in the group
                for idx, msg in enumerate(messages):
                    if msg.media:
                        try:
                            print(f"Downloading media for message ID {msg.id}...")
                            media = await msg.download_media()
                            await asyncio.sleep(1)
                            if media:
                                file_ext = os.path.splitext(media)[1]
                                new_filename = f"{base_filename}_{'single' if is_single else 'grouped'}_{idx}{file_ext}"
                                new_path = os.path.join(dir_name, new_filename)
                                shutil.move(media, new_path)
                                media_paths.append(new_path)
                                print(f"Media downloaded and moved to: {new_path}")
                            else:
                                print("Media download returned None.")
                        except Exception as e:
                            print(f"Error downloading media for message ID {msg.id}: {e}")

                # Save the original text
                text_file_path = os.path.join(dir_name, f"{base_filename}_original_message.txt")
                with open(text_file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"Original message text saved to {text_file_path}")

            except Exception as e:
                print(f"Error in process_group_id for group {grouped_id}: {e}")
            finally:
                # Cleanup the processed group
                if grouped_id in grouped_media:
                    del grouped_media[grouped_id]
                if grouped_id in group_processing:
                    group_processing.remove(grouped_id)
                print(f"Group {grouped_id} processing completed. Cleanup done.")

    return handler

# Example usage
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=-1,  # unlimited retries
    auto_reconnect=True
)

channels = ['@tradeduckydemo']
output_folder = "tweet_history"

"""Starts listening to the list of channels and outputs everything to the designated folder"""
handler = setup_telegram_bot(client, channels, output_folder)

async def main_runner():
    while True:
        try:
            async with client:
                print("Client started. Listening for new messages...")
                await client.run_until_disconnected()
        except (ConnectionResetError, OSError) as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

print(f"Listening to channels: {channels}")
print("Telegram client is now running and listening for messages...")
client.start()
print("Client started successfully!")
client.run_until_disconnected()