import os
import re
import time
import random
import requests
import subprocess
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from miniflux import Client
from dotenv import load_dotenv
from categories import CATEGORY_COLORS, CATEGORY_ICONS
from error_images import NOT_FOUND_IMAGES
from pathlib import Path
from calendar import month_name


load_dotenv()

ARCHIVE_MODE = os.getenv("ARCHIVE_MODE")

# Miniflux configuration
MINIFLUX_URL = os.getenv("MINIFLUX_URL")
MINIFLUX_API_KEY = os.getenv("MINIFLUX_API_KEY")
MINIFLUX_USER_ID = os.getenv("MINIFLUX_USER_ID")

# Discord Webhook configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

client = Client(MINIFLUX_URL, api_key=MINIFLUX_API_KEY)

def extract_image(content):
    # Regular expression to find the image URL in the 'content' field
    match = re.search(r'<img src="([^"]+)"', content)
    return match.group(1) if match else None

def get_icon_url(feed_url):
    # Make a GET request to retrieve the RSS feed content
    response = requests.get(feed_url)
    
    if response.status_code == 200:
        # Parse the XML
        root = ET.fromstring(response.content)
        
        # Find the <url> tag within <image>
        icon_url = root.find(".//image/url")
        
        # Check if the icon_element exists and has text, else return None
        if icon_url is not None and icon_url.text:
            return icon_url.text
        else:
            return None
    else:
        print(f"Error accessing the feed: {response.status_code}")
        return None

def download_with_ktoolbox(post_url):
    """
    Use KToolBox to download all files from a post into the default directory.
    """
    try:
        # Command to run KToolBox
        command = ["ktoolbox", "download-post", post_url, "-"]
        subprocess.run(command, check=True)
        print(f"Files from {post_url} downloaded successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error using KToolBox for {post_url}: {e}")

def move_downloaded_folder(post_title, base_path):
    """
    Move the most recently downloaded folder to the correct path and rename it.
    """
    download_dir = Path.cwd()  # Current working directory
    recent_folder = max(download_dir.glob("*"), key=os.path.getctime)  # Find the newest folder

    if recent_folder.is_dir():
        target_folder = base_path / post_title
        shutil.move(str(recent_folder), str(target_folder))
        print(f"Moved folder to {target_folder}")
    else:
        print("No folder found to move.")

def archive_post(entry):
    if not ARCHIVE_MODE:
        return

    # Extract necessary details
    author = entry["author"] or "Unknown Author"
    category = entry.get("category", {}).get("title", "Uncategorized")
    author_with_category = f"{author} - {category}"

    try:
        # Parse the publication date with ISO 8601 support
        published_at = datetime.fromisoformat(entry["published_at"])
    except ValueError as e:
        print(f"Error parsing date: {e}")
        return

    year = str(published_at.year)
    month = month_name[published_at.month]  # Get the full month name (e.g., "August")
    day_and_time = published_at.strftime("%d-%H-%M-%S")
    post_title = f"{day_and_time} - {entry['title']}"

    # Create base path with the updated structure
    base_path = Path("Archive") / author_with_category / year / month

    # Create directories
    base_path.mkdir(parents=True, exist_ok=True)

    # Use KToolBox to download the post's content
    post_url = entry["url"]
    download_with_ktoolbox(post_url)

    # Move the downloaded folder to the appropriate location
    move_downloaded_folder(post_title, base_path)

def send_embed_to_discord(unread_entries):
    for entry in unread_entries:
        feed_url = entry["feed"]["feed_url"]

        icon_url = get_icon_url(feed_url)
        
        # Extract image URL from 'content'
        image_url = extract_image(entry["content"])
        if image_url is None:
            image_url = random.choice(NOT_FOUND_IMAGES)

        archive_post(entry)
        
        # Determine the embed color based on the entry category
        category = entry["feed"].get("category", {}).get("title", "Uncategorized")
        embed_color = CATEGORY_COLORS.get(category, 16777215)  # White as default if category not found
        
        # Determine the category-specific icon or use the default icon
        category_icon = CATEGORY_ICONS.get(category, "https://i.imgur.com/Nyh7tRG.png")

        if icon_url is None:
            icon_url = category_icon

        # Create the embed payload
        embed = {
            "embeds": [
                {
                    "title": entry["title"],
                    "url": entry["url"],
                    "color": embed_color,
                    "author": {
                        "name": entry["author"],
                        "url": entry["feed"]["site_url"],
                        "icon_url": icon_url  # Set category-specific icon
                    },
                    "footer": {
                        "text": category,
                        "icon_url": category_icon
                    },
                    "timestamp": entry["published_at"],
                    "image": {
                        "url": image_url
                    }
                }
            ],
            "attachments": []
        }

        # Send the embed to the Discord webhook
        response = requests.post(DISCORD_WEBHOOK_URL, json=embed)
        time.sleep(5)
        
        # Check if the send was successful
        if response.status_code == 204:
            print(f"Article '{entry['title']}' sent successfully to Discord!")
        else:
            print(f"Failed to send '{entry['title']}'. Status code: {response.status_code}")

# Fetch all unread entries from Miniflux
unread_entries = client.get_entries(status="unread")["entries"]

if unread_entries == []:
    print("No new articles found.")

# Mark user entries as read in Miniflux
client.mark_user_entries_as_read(MINIFLUX_USER_ID)

# Send each entry as an embed to Discord
send_embed_to_discord(unread_entries)
