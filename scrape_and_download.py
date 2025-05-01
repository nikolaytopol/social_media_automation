import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString, Comment, Tag

def sanitize_filename(filename):
    """
    Removes invalid characters from the filename for most operating systems.
    """
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)

def download_file(url, download_folder="downloaded_media"):
    """
    Downloads a file from `url` into the specified download folder.
    Returns the local path to the downloaded file or None if failed.
    """
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename:
        filename = "index.html"

    filename = sanitize_filename(filename)
    file_path = os.path.join(download_folder, filename)

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return file_path
    except Exception as e:
        print(f"Could not download {url}. Error: {e}")
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

def scrape_and_download(url):
    """
    Scrapes the page at `url` for text, images, and video elements.
    Ignores obviously technical or styling-related text blocks.
    Downloads media files and returns a combined representation
    of text + placeholders showing media positions.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
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
                        downloaded = download_file(abs_src)
                        if downloaded:
                            elements_in_order.append(("image", downloaded))
                        else:
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
                        downloaded = download_file(abs_src)
                        if downloaded:
                            elements_in_order.append(("video", downloaded))
                        else:
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

if __name__ == "__main__":
    test_url = "https://decrypt.co/298869/7-breakout-crypto-games-2024"
    result_text = scrape_and_download(test_url)
    with open("scraped_output.txt", "w", encoding="utf-8") as f:
        f.write(result_text)

    print("Scraping complete! Output saved to 'scraped_output.txt'.")
