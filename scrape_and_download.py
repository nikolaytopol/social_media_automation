import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString, Comment, Tag
import logging
from models_openai import analyze_image
import traceback
# Get the logger for this module
logger = logging.getLogger(__name__)


def sanitize_filename(filename):
    """
    Removes invalid characters from the filename for most operating systems.
    """
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)

def download_file(url, download_folder="downloaded_media"):
    """
    Downloads a file from `url` into the specified download folder.
    Returns the local path to the downloaded file or None if failed.
    Only used for files scraped from the web, NOT for Telegram message media.
    """
    # Always create a 'downloaded_media' subfolder for scraped files
    if download_folder:
        media_folder = os.path.join(download_folder, "downloaded_media")
    else:
        media_folder = download_folder

    # Create the folder if it doesn't exist
    if not os.path.exists(media_folder):
        os.makedirs(media_folder)

    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename:
        filename = "index.html"

    filename = sanitize_filename(filename)
    file_path = os.path.join(media_folder, filename)

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        # Double-check file exists and is not empty
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        else:
            logger.error(f"Downloaded file {file_path} does not exist or is empty.")
            return None
    except Exception as e:
        logger.error(f"Could not download {url}. Error: {e}")
        return None

def looks_like_style_or_junk(text):
    """
    Heuristic check to see if the text looks like CSS or purely technical data:
      - contains lots of curly braces { } or semicolons ;
      - or starts with `[data-`, `.cls-`, etc.
      - or is dominated by non-letter characters.
    Adjust these checks based on real-world usage.
    """
    # Quick check: if text includes CSS/JS symbols in large amounts
    if len(text) < 8:
        return True  # very short, likely not real content

    # Count curly braces, semicolons
    braces = text.count('{') + text.count('}')
    semicolons = text.count(';')
    # If over half the text is braces/semicolons, likely CSS or junk.
    if (braces + semicolons) > (0.5 * len(text)):
        return True

    # If it starts with data-rk, .cls-, or has large numeric blocks => likely style or junk
    if text.strip().startswith('[data-') or text.strip().startswith('.cls-'):
        return True

    # If many lines appear to be selectors or variables, skip
    if re.search(r"--[a-zA-Z0-9-]+:", text):
        return True

    # If the proportion of letters to total chars is very small, skip
    letters = sum(c.isalpha() for c in text)
    if letters < 0.2 * len(text):
        return True

    return False

def scrape_and_download(url, download_folder="downloaded_media"):
    """
    Scrapes the page at `url` for text, images, and video elements.
    Downloads media files (scraped from the web) into 'downloaded_media' subfolder of the given download_folder.
    Returns a combined representation of text + placeholders showing media positions.
    Only for external/scraped files, NOT for Telegram message media.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            # For 403 errors, extract title from URL and return that
            path_parts = urlparse(url).path.split('/')
            title = next((part for part in reversed(path_parts) if part), '')
            title = title.replace('-', ' ').title()
            return f"Article title (403 protected): {title}"
        print(f"Failed to fetch URL {url}: {e}")
        return ""
    except Exception as e:
        print(f"Failed to fetch URL {url}: {e}")
        return ""

    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove <script>, <style>, and comment nodes entirely:
    for s in soup(["script", "style"]):
        s.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # This list will hold tuples of (type, content).
    elements_in_order = []

    def traverse(node):
        """
        Recursively traverse the DOM, in document order.
        If text -> store if it doesn't look like junk.
        If <img> or <video> -> download + store path placeholder.
        Else -> dive into children.
        """
        for child in node.children:
            if isinstance(child, NavigableString):
                text = child.strip()
                if text and not looks_like_style_or_junk(text):
                    elements_in_order.append(("text", text))
            elif isinstance(child, Tag):
                # Images
                if child.name == "img":
                    src = child.get("src")
                    if src:
                        abs_src = urljoin(url, src)
                        downloaded = download_file(abs_src, download_folder=download_folder)
                        if downloaded and os.path.exists(downloaded):
                            elements_in_order.append(("image", downloaded))
                        else:
                            logger.warning(f"Image not downloaded or missing: {abs_src}")
                            elements_in_order.append(("image", abs_src))
                # Videos
                elif child.name == "video":
                    video_src = child.get("src")
                    if not video_src:
                        # check <source> tags
                        source_tag = child.find("source")
                        if source_tag:
                            video_src = source_tag.get("src")
                    if video_src:
                        abs_src = urljoin(url, video_src)
                        downloaded = download_file(abs_src, download_folder=download_folder)
                        if downloaded and os.path.exists(downloaded):
                            elements_in_order.append(("video", downloaded))
                        else:
                            logger.warning(f"Video not downloaded or missing: {abs_src}")
                            elements_in_order.append(("video", abs_src))
                else:
                    # Recursively dive in
                    traverse(child)

    body = soup.body if soup.body else soup
    traverse(body)

    # Now format them in a text output with placeholders
    output_lines = []
    media_count = {"image": 0, "video": 0}

    for elem_type, content in elements_in_order:
        if elem_type == "text":
            output_lines.append(content)
        elif elem_type == "image":
            media_count["image"] += 1
            output_lines.append(f"[IMAGE_{media_count['image']}: {content}]")
        elif elem_type == "video":
            media_count["video"] += 1
            output_lines.append(f"[VIDEO_{media_count['video']}: {content}]")

    return "\n".join(output_lines)
###############################
# New Function: Extract Content to Aggregated File
###############################

async def extract_content_to_aggregated_file(text, media_paths, dir_name,analyze_urls=False):
    """
    Extract and combine content from original message, media files, and URLs into a single aggregated file.
    
    Args:
        text (str): The original message text
        media_paths (list): List of paths to media files
        dir_name (str): Directory where the tweet data is stored
    Returns:
        str: The aggregated content as a string
        
    This function:
    1. Creates a "full_input_to_gpt.txt" file in the specified directory
    2. Adds the original message text
    3. Analyzes and adds descriptions of any media files (images, audio)
    4. Finds and analyzes URLs in the original message (ignoring certain promotional URLs)
    5. Returns the complete aggregated content for further processing
    """
    logger.info(f"Creating full_input_to_gpt.txt file in {dir_name}")
    full_input_path = os.path.join(dir_name, "full_input_to_gpt.txt")
    
    try:
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

            # Process attached media files.
            logger.info(f"Processing {len(media_paths)} media files")
            if media_paths:
                import mimetypes
                for media in media_paths:
                    mime_type, _ = mimetypes.guess_type(media)
                    media_analysis = "Media analysis unavailable"
                    
                    try:
                        if mime_type:
                            if mime_type.startswith("image/"):
                                media_analysis = await analyze_image(media)
                            elif mime_type.startswith("audio/"):
                                media_analysis = analyze_audi(media)
                            else:
                                media_analysis = (f"Media file {os.path.basename(media)} of type '{mime_type}' "
                                                f"is attached and will be reposted with the processed text.")
                        else:
                            media_analysis = (f"Media file {os.path.basename(media)} (unknown type) "
                                            f"is attached and will be reposted with the processed text.")
                    except Exception as e:
                        logger.error(f"Error analyzing media {media}: {e}")
                        logger.error(traceback.format_exc())
                        media_analysis = f"Error analyzing media: {e}"
                    
                    # Safely log the media analysis with null check
                    if media_analysis:
                        logger.info(f"Media analysis for {os.path.basename(media)}: {media_analysis[:100]}...")
                    else:
                        logger.warning(f"No analysis available for media: {os.path.basename(media)}")
                    
                    full_input_file.write(f"\n----- Analysis for media file: {os.path.basename(media)} -----\n")
                    full_input_file.write(media_analysis)
                    full_input_file.write(f"\n----- End of analysis for media file: {os.path.basename(media)} -----\n")
            else:
                full_input_file.write("\nNo media files attached.\n")
            
            # Find and process URLs in the original message.
            urls = re.findall(r'(https?://\S+)', original_content)
            ignored_substrings = [
                "t.me",             # e.g. Telegram links
                "bybit.com/register",
                "okx.com/join",
                "t.co"
            ]
            
            logger.info(f"Processing {len(urls)} URLs")
            if urls and analyze_urls:
                for url in urls:
                    if any(ignore in url.lower() for ignore in ignored_substrings):
                        logger.info(f"Ignoring URL: {url}")
                        continue
                    try:
                        if "twitter.com" in url.lower():
                            link_analysis = analyze_twitter_link(url)
                        else:
                            link_analysis = analyze_website(url, download_folder=dir_name)
                        full_input_file.write(f"\n----- Analysis for link: {url} -----\n")
                        full_input_file.write(link_analysis)
                        full_input_file.write(f"\n----- End of analysis for link: {url} -----\n")
                    except Exception as e:
                        logger.error(f"Error analyzing URL {url}: {e}")
                        logger.error(traceback.format_exc())
                        continue
            else:
                full_input_file.write("\nNo URLs found in the original message.\n")
        
        logger.info(f"Full input file created at {full_input_path}")
        
        # Read the aggregated content
        with open(full_input_path, "r", encoding="utf-8") as f:
            aggregated_content = f.read()
        logger.debug(f"Aggregated content: {aggregated_content[:500]}...")  # First 500 chars
        return aggregated_content
        
    except Exception as e:
        logger.error(f"Error creating or reading full input file: {e}")
        logger.error(traceback.format_exc())
        return text  # Return original text if there was an error

def analyze_website(url, download_folder=None):
    """
    Analyze a website link and save media to the specified download_folder if provided.
    """
    logger.info(f"Analyzing website: {url}")
    try:
        if download_folder:
            result = scrape_and_download(url, download_folder=download_folder)
        else:
            result = scrape_and_download(url)
        logger.info(f"Website analysis completed for {url}")
        return result
    except Exception as e:
        logger.error(f"Error analyzing website {url}: {e}")
        logger.error(traceback.format_exc())
        return f"Error analyzing website {url}: {e}"
    
    
if __name__ == "__main__":
    test_url = "https://decrypt.co/298869/7-breakout-crypto-games-2024"
    result_text = scrape_and_download(test_url)
    with open("scraped_output.txt", "w", encoding="utf-8") as f:
        f.write(result_text)

    print("Scraping complete! Output saved to 'scraped_output.txt'.")
