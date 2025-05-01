from collections import defaultdict
import asyncio
import os
import tweepy
import openai
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
from telethon.sessions import StringSession
import datetime
import shutil
import time
import json
import re
from difflib import SequenceMatcher

# Load API keys from environment variables
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING')

# OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_KEY ='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'
openai.api_key = OPENAI_API_KEY

# Authenticate with Twitter API v2 using Tweepy
client_v2 = tweepy.Client(bearer_token=BEARER_TOKEN,
                          consumer_key=API_KEY,
                          consumer_secret=API_SECRET_KEY,
                          access_token=ACCESS_TOKEN,
                          access_token_secret=ACCESS_TOKEN_SECRET)

# For v1.1 media upload
auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api_v1 = tweepy.API(auth)

# --- Make Telethon more resilient ---
client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=-1,  # unlimited retries
    auto_reconnect=True
)


# Global dictionaries and sets for grouping messages
grouped_media = defaultdict(list)  # grouped by grouped_id
group_processing = set()           # groups currently being processed

@client.on(events.NewMessage(chats=['@forklog','@unfolded','@unfolded_defi', '@decenter', '@tradeduckydemo', '@cryptoquant_official',"@cryptodaily","@glassnode",
                                     "@crypto02eth","@RBCCrypto","@crypto_headlines","@decryptnews","@incrypted"]))
async def handler(event):
    print("\n------------------------------STEP_0_event initiated------------------------------\n")
    message = event.message
    grouped_id = getattr(message, "grouped_id", None)
    print("\n------------------------------STEP_1_recieving_message------------------------------\n")
    if grouped_id:
        # Add message to its group
        print("\n------------------------------STEP_1_1_recieving_grouped_message------------------------------\n")
        grouped_media[grouped_id].append(message)
        if grouped_id not in group_processing:
            # grouped_id = f"single_{timestamp_str}" # EXPIEREMENTAL LINE TO NORMALIZE FOLDER NAMES
            group_processing.add(grouped_id)
            await process_group_id(grouped_id)
    else:
        # For a single message create a unique grouped_id
        print("\n------------------------------STEP_1_2_recieving_single_message------------------------------\n")
        # For a single message create a unique grouped_id
        timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        grouped_id = f"single_{timestamp_str}"
        grouped_media[grouped_id].append(message)
        if grouped_id not in group_processing:
            print("\n------------------------------STEP_1_2_2")
            group_processing.add(grouped_id)
            print("\n------------------------------STEP_1_2_3")
            await process_group_id(grouped_id)

async def process_group_id(grouped_id):
    messages = grouped_media[grouped_id]
    earliest_message = min(messages, key=lambda msg: msg.date)
    print(f"\n------------------------------STEP_2_0_processing group {grouped_id} with {len(messages)} messages------------------------------\n")

    # Create a directory for this tweet’s data
    dir_name = f"tweet_history/{grouped_id}" #group Id for multiple files is abitratry number while for sinlg messages its dates
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    media_paths = []
    text = earliest_message.text if earliest_message.text else ""

    # Download media files for all messages in the group
    for idx, msg in enumerate(messages):
        if msg.media:
            try:
                print(f"\n------------------------------STEP_2_1_Downloading media for message ID {msg.id}------------------------------\n")
                media = await msg.download_media()
                if media:
                    file_ext = os.path.splitext(media)[1]
                    new_filename = f"{grouped_id}_{idx}{file_ext}"
                    new_path = os.path.join(dir_name, new_filename)
                    shutil.move(media, new_path)
                    media_paths.append(new_path)
                    print(f"\n------------------------------STEP_2_2_Media downloaded and moved to: {new_path}------------------------------\n")
                else:
                    print("\n------------------------------STEP_2_2_Media download returned None i.e media==False ------------------------------\n")
            except Exception as e:
                print(f"\n------------------------------STEP_2_1_Error downloading media for message ID {msg.id}: {e}------------------------------\n")

    # Save the original text
    text_file_path = os.path.join(dir_name, "original_message.txt")
    with open(text_file_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n------------------------------STEP_3_0_Original tweet text saved to {text_file_path}\nORIGINAL MESSAGE TEXT: {text}------------------------------\n")

    # Process the group: generate tweet, analyze media/links, and post tweet
    await generate_and_post_tweet(text, media_paths, dir_name)
    print(f"\n------------------------------STEP_5_0_Tweet posted saved to {text_file_path}\nORIGINAL MESSAGE TEXT: {text}------------------------------\n")

    # Cleanup the processed group
    del grouped_media[grouped_id]
    group_processing.remove(grouped_id)

###############################
# URL and Media Analysis Helpers
###############################

def analyze_twitter_link(link):
    """
    Placeholder: Analyze a Twitter link.
    TODO: Replace with actual implementation.
    """
    return f"Analysis for Twitter link {link}: [Placeholder analysis output]"

def analyze_website(url):
    """
    Placeholder: Analyze a website link.
    TODO: Replace with actual implementation.
    """
    try:
        from scrape_and_download import scrape_and_download
        return scrape_and_download(url)
    except Exception as e:
        print(f"Error analyzing website {url}: {e}")
        return f"Error analyzing website {url}: {e}"

def analyze_image(image_path):
    """
    Analyze an image. If any Cyrillic (Russian) characters are detected in the result,
    prefix the analysis with 'RUSSSIAN:'.
    """
    import base64
    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    base64_image = encode_image(image_path)
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze an image for the iinformation that can be used in tweet post that descirbe this image. If any Cyrillic (Russian) characters are detected in the result prefix the analysis with 'RUSSSIAN:' "},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ],
                }
            ],
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        analysis = f"Error analyzing image: {e}"
    
    # If any Cyrillic letters are found, add the 'RUSSSIAN:' prefix.
    if re.search(r'[\u0400-\u04FF]', analysis):
        analysis = "RUSSSIAN: " + analysis

    filename = os.path.basename(image_path)
    print(f"\n-----------Analysis for media file {filename}: {analysis}")
    return analysis

def analyze_audi(audio_path):
    """
    Placeholder: Analyze an audio file.
    TODO: Replace with actual implementation.
    """
    return f"Audio analysis for {os.path.basename(audio_path)} not implemented."

###############################
# Duplicate Tweet Prevention Helpers
###############################
import os
import re
# (Assuming OpenAI is already imported above)

def fetch_recent_tweet_history(history_dir="tweet_history", limit=15):
    """
    Scans the tweet_history folder for subdirectories that contain an 'original_message.txt' file.
    For each folder, it reads the original message and gathers associated media file details (file extension and file size)
    from any other files (excluding known text files).
    
    Returns a list of dictionaries. Each dictionary contains:
      - 'text': the content of original_message.txt
      - 'media_info': a list of dictionaries, one per associated media file.
    
    The list is sorted by the modification time of original_message.txt (most recent first)
    and only the latest 'limit' entries are returned.
    """
    tweet_entries = []
    if not os.path.exists(history_dir):
        return []
    
    # Iterate over each subdirectory in tweet_history.
    for folder in os.listdir(history_dir):
        folder_path = os.path.join(history_dir, folder)
        if os.path.isdir(folder_path):
            original_file = os.path.join(folder_path, "original_message.txt")
            if os.path.exists(original_file):
                try:
                    mtime = os.path.getmtime(original_file)
                    with open(original_file, "r", encoding="utf-8") as f:
                        text = f.read().strip()
                    
                    # Gather media info from any files that are not known text files.
                    media_info = []
                    for file in os.listdir(folder_path):
                        if file in ["original_message.txt", "tweet_text.txt", "full_input_to_gpt.txt"]:
                            continue
                        file_path = os.path.join(folder_path, file)
                        if os.path.isfile(file_path):
                            file_ext = os.path.splitext(file)[1]
                            file_size = os.path.getsize(file_path)
                            media_info.append({
                                "file_extension": file_ext,
                                "file_size": file_size
                            })
                    
                    tweet_entries.append((mtime, {"text": text, "media_info": media_info}))
                except Exception as e:
                    print(f"Error reading {original_file}: {e}")
    
    # Sort by modification time (most recent first)
    tweet_entries.sort(key=lambda x: x[0], reverse=True)
    
    # Return only the latest 'limit' entries (extract only the dictionary part)
    recent_tweets = [entry for mtime, entry in tweet_entries[1:limit+1]]
    return recent_tweets

def normalized_media_info(media_info):
    """
    Returns a sorted list of tuples (file_extension, file_size) for each media file.
    """
    if not media_info:
        return []
    normalized = [(item["file_extension"].lower(), item["file_size"]) for item in media_info]
    normalized.sort()
    return normalized

def media_file_equal(m1, m2, tolerance=0.05):
    """
    Compares two media file tuples (file_extension, file_size).
    Returns True if the file extensions are the same (case-insensitive) and the file sizes differ by no more than the tolerance (default 5%).
    """
    ext1, size1 = m1
    ext2, size2 = m2
    if ext1 != ext2:
        return False
    # Avoid division by zero and allow exact zero-size files.
    if size1 == 0 and size2 == 0:
        return True
    # Check if the relative difference is within the tolerance.
    diff_ratio = abs(size1 - size2) / max(size1, size2)
    return diff_ratio <= tolerance

def media_list_equal(list1, list2, tolerance=0.05):
    """
    Compares two lists of media file tuples.
    Returns True if both lists have the same length and each corresponding media file is equal
    based on file extension and file size within the given tolerance.
    """
    if len(list1) != len(list2):
        return False
    for m1, m2 in zip(list1, list2):
        if not media_file_equal(m1, m2, tolerance):
            return False
    return True

def format_media_info(media_info):
    """
    Given a list of media file info dictionaries, returns a string summarizing the details.
    For example: "(Extension: .jpg, Size: 12345 bytes), (Extension: .mp4, Size: 456789 bytes)"
    """
    if not media_info:
        return "No media files."
    
    formatted_items = []
    for item in media_info:
        formatted_items.append(
            f"(Extension: {item['file_extension']}, Size: {item['file_size']} bytes)"
        )
    return ", ".join(formatted_items)

def is_duplicate_tweet(current_message, current_media_info):
    """
    Compares the current original message (and its associated media file details)
    with each of the last 15 original messages stored in tweet_history.
    
    First, it checks if the normalized media info (file type and file size) of the current message
    exactly matches that of any past message (using a tolerance for size differences).
    If so, the new message is considered a duplicate immediately.
    
    Otherwise, it constructs a single prompt that includes the text and formatted media details
    of the new message as well as the details of all 15 past messages. It then calls ChatGPT one time
    to decide whether the new message is semantically similar to any of the past messages.
    If ChatGPT returns "Yes", this function returns True.
    """
    recent_entries = fetch_recent_tweet_history(limit=7)
    if not recent_entries:
        # No previous history to compare against.
        return False

    current_media_str = format_media_info(current_media_info)
    normalized_current = normalized_media_info(current_media_info)
    
    # Check for any exact (or nearly exact) media match first.
    for entry in recent_entries:
        normalized_past = normalized_media_info(entry["media_info"])
        if media_list_equal(normalized_current, normalized_past, tolerance=0.01):
            print("Media files match (file type and size within tolerance) with a past entry; marking as duplicate without ChatGPT comparison.")
            return True

    # Construct a single prompt that includes the new message and all past 15 messages.
    prompt = "You are an assistant that compares messages for duplication.\n\n"
    prompt += "New Message:\n"
    prompt += f"Text: {current_message}\n"
    prompt += f"Media: {current_media_str}\n\n"
    prompt += "Past 15 Messages:\n"
    for i, entry in enumerate(recent_entries, start=1):
        past_text = entry["text"]
        past_media_str = format_media_info(entry["media_info"])
        prompt += f"Message {i}:\n"
        prompt += f"Text: {past_text}\n"
        prompt += f"Media: {past_media_str}\n\n"
    prompt += (
        "Based on the above, determine if the new message is semantically similar to any of the past messages. "
        "Consider whether they convey essentially the same meaning, have similar text lengths, and display similar associated media details "
        "(in terms of file type and file size). Answer only with 'Yes' if the new message is a duplicate, or 'No' otherwise. And also give me the text of the message that you think was similar pretexting it with 'DUBLICATE FOUND MESSGAGE' IN THE END followed by the message"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": "You are an assistant that compares messages for duplication."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0  # to favor deterministic output
        )
        print('Response :',response.choices[0].message)
        answer = response.choices[0].message.content.strip().lower()
        print(f"ChatGPT overall comparison result: {answer}")
        if "yes" in answer:
            return True
    except Exception as e:
        print(f"Error comparing messages using ChatGPT: {e}")
    
    return False

###############################
# New Function: Post to Telegram Channel
###############################

async def post_to_telegram_channel(text, media_paths, channel_username):
    """
    Posts the given text (and optionally media) to the specified Telegram channel.
    The channel_username is the channel's username (e.g. "@mychannel").
    """
    try:
        if media_paths:
            await client.send_file(channel_username, media_paths, caption=text)
        else:
            await client.send_message(channel_username, text)
        print(f"Posted to Telegram channel: {channel_username}")
    except Exception as e:
        print(f"Error posting to Telegram channel {channel_username}: {e}")

###############################
# Main Function: Generate and Post Tweet
###############################

async def generate_and_post_tweet(text, media_paths, dir_name):
    """
    Aggregates data, generates tweet content with GPT, checks for duplicate content,
    filters out promotional or where Russian language in in the media file description but posts in russina are ok you identify the posts by the prefix 'RUSSSIAN' posts in the imge descirpions, and then posts the tweet (and optionally posts to Telegram).
    """

    print(f"\n------------------------------STEP_4_0_Beginning generation and posting of the tweet------------------------------\nORIGINAL MESSAGE TEXT: {text}\nMEDIA PATHS : {media_paths}\n DIRECTORY : {dir_name}")


    # 1. Write aggregated data into a full-input file.
    print(f"\n------------------------------STEP_4_1_Creating full_input_to_gpt.txt file and saving it to the {dir_name}------------------------------\n")
    full_input_path = os.path.join(dir_name, "full_input_to_gpt.txt")
    with open(full_input_path, "w", encoding="utf-8") as full_input_file:
        # Append the original message.
        original_message_file = os.path.join(dir_name, "original_message.txt")
        if os.path.exists(original_message_file):
            with open(original_message_file, "r", encoding="utf-8") as orig_file:
                original_content = orig_file.read()
            full_input_file.write("----- Original Message -----\n")
            full_input_file.write(original_content)
            full_input_file.write("\n----- End of Original Message -----\n\n")
        else:
            full_input_file.write("Original message file not found.\n\n")
            original_content = text

        # 2. Process attached media files.
        print(f'\nMEDIA PATHS: {media_paths}')
        if media_paths:
            import mimetypes
            for media in media_paths:
                mime_type, _ = mimetypes.guess_type(media)
                if mime_type:
                    if mime_type.startswith("image/"):
                        media_analysis = analyze_image(media)
                    elif mime_type.startswith("audio/"):
                        media_analysis = analyze_audi(media)
                    else:
                        media_analysis = (f"Media file {os.path.basename(media)} of type '{mime_type}' "
                                          f"is attached and will be reposted with the processed text.")
                else:
                    media_analysis = (f"Media file {os.path.basename(media)} (unknown type) "
                                      f"is attached and will be reposted with the processed text.")
                print(f"----------MEDIA ANALYSIS: {media_analysis}")
                full_input_file.write(f"\n----- Analysis for media file: {os.path.basename(media)} -----\n")
                full_input_file.write(media_analysis)
                full_input_file.write(f"\n----- End of analysis for media file: {os.path.basename(media)} -----\n")
        else:
            full_input_file.write("\nNo media files attached.\n")
        
        # 3. Find and process URLs in the original message.
        urls = re.findall(r'(https?://\S+)', original_content)
        ignored_substrings = [
            "t.me",             # e.g. Telegram links
            "bybit.com/register",
            "okx.com/join",
            "t.co"
        ]
        if urls:
            for url in urls:
                if any(ignore in url.lower() for ignore in ignored_substrings):
                    print(f"Ignoring URL: {url}")
                    continue
                try:
                    if "twitter.com" in url.lower():
                        link_analysis = analyze_twitter_link(url)
                    else:
                        link_analysis = analyze_website(url)
                    full_input_file.write(f"\n----- Analysis for link: {url} -----\n")
                    full_input_file.write(link_analysis)
                    full_input_file.write(f"\n----- End of analysis for link: {url} -----\n")
                except Exception as e:
                    print(f"Error analyzing URL {url}: {e}")
                    continue
        else:
            full_input_file.write("\nNo URLs found in the original message.\n")
            
    print(f"\n------------------------------STEP_4_1_Creating full_input_to_gpt.txt file and saving it to the {dir_name}------------------------------\n")
    # Read the aggregated content.
    with open(full_input_path, "r", encoding="utf-8") as f:
        aggregated_content = f.read()
    
    print("AGGREGATED CONTENT:", aggregated_content)
    print("TEXT:", text, "\nMEDIA PATHS:", media_paths, "\nDIR NAME:", dir_name)

    # 4. Generate tweet content using OpenAI.
    prompt_text = (
        "Rewrite the following content to make it suitable for a Twitter post. "
        "Note that the text given to you is the Original Message.However details that might help in the creating of the tweet can be found in sections that decribed images or urls "
        "Ensure it sounds authentic and engaging, adding relevant emojis and removing brand or promotional elements "
        "such as '@forklog', '@decenter', '@tradeducky', '@cryptoquant_official'. "
        "Translate to English if necessary. If no content is provided, suggest a tweet that complements the attached media. "
        "Avoid putting quotation marks around tweet text or mentioning technical aspects.\n\n"
        f"Content: {text}"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-2024-11-20",  # or another model as needed
            messages=[
                {"role": "system", "content": "You are a Twitter blogger creating concise, engaging tweets. Be cool and not overly excited."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=900 # What max toke number influences it
        )
        tweet_text = response.choices[0].message.content.strip()
        print(f"Generated tweet content: {tweet_text}")
    except Exception as e:
        print(f"Error generating text with OpenAI GPT: {e}")
        tweet_text = ""

    # Save the generated tweet text.
    tweet_text_file = os.path.join(dir_name, "tweet_text.txt")
    with open(tweet_text_file, "w", encoding="utf-8") as f:
        f.write(tweet_text)
    print(f"Tweet text saved to {tweet_text_file}")

    ###############################
    # 5. Filter out unwanted posts:
    #    (a) Use OpenAI’s filter with an updated prompt to also check for Russian content.
    #    (b) Additionally, perform a manual check below.
    ###############################
    filter_prompt = (
        "Is the following tweet promotional or does it contain prefix 'RUSSSIAN'? "
        "If the tweet is promotional or contains the Russian prefix text (i.e. any Cyrillic characters), respond with 'Yes'. Otherwise, respond with 'No'.\n\n"
        "Also if post contain any trnalsation or event link and time of some event post probable the tweet is a promo"
        f"Tweet: {tweet_text}"
    )
    try:
        filter_response = openai.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": "You are a filter system for identifying content not suitable for posting on this Twitter account."},
                {"role": "user", "content": filter_prompt}
            ],
            max_tokens=10
        )
        filter_result = filter_response.choices[0].message.content.strip().lower()
        print(f"Filter response: {filter_result}")
    except Exception as e:
        print(f"Error filtering tweet with OpenAI GPT: {e}")
        filter_result = "yes"  # default to 'yes' to avoid posting problematic content

    # Log the classification for later review.
    classification_log = {
        "tweet_text": tweet_text,
        "filter_result": filter_result,
        "actual_posted": (filter_result == "no"),
        "manual_feedback": None
    }
    feedback_file = "classification_feedback.json"
    try:
        with open(feedback_file, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(classification_log, ensure_ascii=False) + "\n")
        print(f"Classification log saved: {classification_log}")
    except Exception as e:
        print(f"Error saving classification log: {e}")


    # 6. Check for duplicate tweets.
    # Build a list of current media file details in the same format as expected.
    current_media_details = []
    for media in media_paths:
        file_ext = os.path.splitext(media)[1]
        file_size = os.path.getsize(media)
        current_media_details.append({
            "file_extension": file_ext,
            "file_size": file_size
        })
    
    if is_duplicate_tweet(text, current_media_details):
        print("Tweet is similar to one of the last 15 messages. Skipping posting to avoid duplicates.")
        return

    # 7. Post the tweet only if it passed the filter.
    if filter_result == "no":
        print("Tweet passed filtering. Proceeding to post.")
        # Upload media if available.
        media_ids = []
        for path in media_paths:
            try:
                media = api_v1.media_upload(path)
                media_ids.append(media.media_id)
                print(f"Media uploaded: {media.media_id}")
            except Exception as e:
                print(f"Error uploading media: {e}")
        try:
            if media_ids:
                response = client_v2.create_tweet(text=tweet_text, media_ids=media_ids)
                print(f"Tweet with media posted: {response}")
            else:
                response = client_v2.create_tweet(text=tweet_text)
                print(f"Tweet posted: {response}")
        except Exception as e:
            print(f"Error posting tweet: {e}")


        # Optionally, also post to a Telegram channel.
        # For example, to post to a channel with username '@mychannel', uncomment the next line:
        # --- Repost to Telegram Channel ---
        telegram_channel = "@tradeducky" # e.g., "@mychannel"
        if telegram_channel:
            await post_to_telegram_channel(tweet_text, media_paths, telegram_channel)
        else:
            print("No Telegram channel username defined in environment variables.")
    else:
        print("Tweet is either promotional or contains Russian content. It will not be posted.")

async def main_runner():
    """
    Continuously run the Telegram client. If disconnected or certain exceptions occur,
    wait a bit and then restart.
    """
    while True:
        try:
            async with client:
                print("Client started. Listening for new messages...")
                if not await client.is_user_authorized():
                    print('Client is not authorized')
                await client.run_until_disconnected()
        except (ConnectionResetError, OSError) as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # allows running the loop within Jupyter if needed
    asyncio.run(main_runner())