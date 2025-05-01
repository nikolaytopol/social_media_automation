import os
import asyncio
import openai
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime
# ------------------------------------------------------------------------
# 1) TELEGRAM CLIENT SETUP
# ------------------------------------------------------------------------
API_ID = os.getenv('TELEGRAM_API_ID') or "your_api_id_here"
API_HASH = os.getenv('TELEGRAM_API_HASH') or "your_api_hash_here"
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING') or "your_session_string_here"

# Source channels: messages will be gathered from these numeric IDs
source_channels = [-1002454067712, -1002167975984]

# Target channel: where messages will be reposted
target_channel =-1002634663671

# Initialize the Telegram client
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# ------------------------------------------------------------------------
# 2) FILTERING FUNCTION
# ------------------------------------------------------------------------
async def passes_filter(message_text: str) -> bool:
    """
    Calls OpenAI to determine if the given message text meets your posting standards.
    This prompt is designed so that the three example messages you provided will pass.
    You can adjust the logic or wording further as needed.
    """
    filter_prompt = (
    "We consider a message acceptable if it meets ANY of the following conditions:\n"
    "1. It contains personal details (e.g., age, height, weight, chest size) along with pricing information and a manager/admin contact.\n"
    "2. It contains promotional content, discounts, or special offers (e.g., percentage discounts, special deals).\n"
    "3. It is very brief or consists mainly of emojis (minimal text) or even has no text at all.\n"
    "4. It mentions or promotes any channel, admin, or manager.\n\n"
    "Does the following content satisfy these posting standards? Answer 'yes' if acceptable, 'no' if not.\n\n"
    f"Message: {message_text}"
    )   

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a filter system for identifying content that is acceptable to post. "
                        "Answer 'yes' if the message meets ANY of the conditions described by the user. Otherwise, 'no'."
                    )
                },
                {"role": "user", "content": filter_prompt}
            ],
            max_tokens=10,
            temperature=0  # More deterministic
        )
        filter_result = response.choices[0].message.content.strip().lower()
        print(f"[Filter] Message text: {message_text[:50]}... => {filter_result}")
        return (filter_result == "yes")
    except Exception as e:
        print(f"Error during filtering: {e}")
        # If there's an error, you might choose to default to False or True.
        return False


# ------------------------------------------------------------------------
# 3) TWEET TEXT GENERATION (MODIFICATION) FUNCTION
# ------------------------------------------------------------------------
async def generate_tweet_content(original_text: str) -> str:
    """
    Calls OpenAI to generate a modified version of the text:
    - Replaces the manager name with '@ANeliteagency'
    - Increases any promotion prices by 3000-4000 CZK
    """
    prompt_text = (
    "Rewrite the following advertisement in English with the following modifications:\n"
    "1) Change the manager's name to '@ANeliteagency'.\n"
    "3) Convert all price values from CZK to EUR, rounding up to the nearest whole number.\n"
    "4) Remove any quates around the messagee.\n"
    "5) Remove additional link from the message\n"
    "6) Do not add any unnecessary commentary (for example, do not include phrases like 'Prices increased by 3000-4000 CZK').\n\n"
    f"Original text: {original_text}"
)
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Twitter blogger creating concise, engaging posts. Keep it fun but not overly excited."
                },
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=900,
            temperature=0
        )
        tweet_text = response.choices[0].message.content.strip()
        print(f"[Generate] Modified text: {tweet_text[:50]}...")
        return tweet_text
    except Exception as e:
        print(f"Error generating text with OpenAI GPT: {e}")
        return original_text  # Fallback: just return the original text if there's an error


# ------------------------------------------------------------------------
# 4) MESSAGE GATHERING & GROUPING (ALBUMS)
# ------------------------------------------------------------------------
async def gather_and_group_messages(channel_id, limit=None):
    """
    Fetches messages from a single source channel and groups them by grouped_id
    so that albums (multiple photos in one post) can be reposted together.
    
    :param channel_id: The ID (or username) of the source channel.
    :param limit: Optionally limit how many messages to fetch.
    :return: A list of (group_id, [messages]) tuples, sorted by earliest message date in each group.
    """
    print(f"Gathering messages from channel {channel_id}...")
    all_msgs = []
    from datetime import datetime

    start_date = datetime(2025,4, 16) # Replace with your desired start date

    # Fetch messages from the channel
    async for msg in client.iter_messages(channel_id, reverse=True, offset_date=start_date):
        all_msgs.append(msg)

    # Group by grouped_id. If there's no grouped_id, use the message's own id to treat it as a single group.
    groups = {}
    for m in all_msgs:
        g_id = m.grouped_id if m.grouped_id else m.id
        groups.setdefault(g_id, []).append(m)

    # Convert to a list of (group_id, [msgs]) and sort each group by date
    grouped_list = []
    for g_id, msgs in groups.items():
        msgs.sort(key=lambda x: x.date)  # oldest to newest
        grouped_list.append((g_id, msgs))

    # Sort the entire list by the earliest message in each group
    grouped_list.sort(key=lambda x: x[1][0].date)
    return grouped_list


# ------------------------------------------------------------------------
# 5) MAIN PROCESSING: FILTER, MODIFY TEXT, AND REPOST
# ------------------------------------------------------------------------
async def process_messages_from_channel(channel_id):
    """
    1. Gather & group messages by album.
    2. For each group:
       - Combine or select text from the earliest message (you can customize this).
       - Check if it passes filter.
       - If yes, generate the modified tweet text.
       - Repost the entire album as one post with that caption.
    """
    grouped_list = await gather_and_group_messages(channel_id)
    for group_id, msgs in grouped_list:
        # Combine text from all messages or just take the earliest text
        # For simplicity, let's take the earliest message's text
        main_text = msgs[0].message or ""

        # 1) Filter
        if await passes_filter(main_text):
            # 2) Modify text
            new_text = await generate_tweet_content(main_text)

            # 3) Collect media from all messages in this group
            media_files = []
            for m in msgs:
                if m.media:
                    try:
                        downloaded_path = await m.download_media()
                        if downloaded_path:
                            media_files.append(downloaded_path)
                    except Exception as e:
                        print(f"Error downloading media for message {m.id}: {e}")

            # 4) Repost
            try:
                if media_files:
                    # Send as an album if multiple files
                    if len(media_files) > 1:
                        await client.send_file(
                            target_channel,
                            file=media_files,
                            caption=new_text,
                            allow_cache=False
                        )
                        print(f"Reposted album of {len(media_files)} files to {target_channel}")
                    else:
                        # Single media
                        await client.send_file(
                            target_channel,
                            file=media_files[0],
                            caption=new_text,
                            allow_cache=False
                        )
                        print(f"Reposted single media to {target_channel}")
                else:
                    # No media => just send text
                    await client.send_message(target_channel, new_text)
                    print(f"Reposted text-only message to {target_channel}")
            except Exception as e:
                print(f"Failed to repost group {group_id} to {target_channel}: {e}")
            finally:
                # Clean up downloaded files
                for f in media_files:
                    if os.path.exists(f):
                        os.remove(f)
        else:
            print(f"[Filter Fail] Group {group_id} was skipped.")


async def main():
    print("Starting the message processing and reposting process...")
    for source in source_channels:
        await process_messages_from_channel(source)
    print("Processing completed.")


# ------------------------------------------------------------------------
# 6) RUN SCRIPT
# ------------------------------------------------------------------------
with client:
    client.loop.run_until_complete(main())
