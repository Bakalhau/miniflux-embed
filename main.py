import os
import re
import time
import random
from datetime import datetime
from miniflux import Client
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from categories import CATEGORY_COLORS, CATEGORY_ICONS
from error_images import NOT_FOUND_IMAGES
from pathlib import Path
from calendar import month_name
import subprocess

load_dotenv()

ARCHIVE_MODE = os.getenv("ARCHIVE_MODE") == "true"

# Miniflux configuration
MINIFLUX_URL = os.getenv("MINIFLUX_URL")
MINIFLUX_API_KEY = os.getenv("MINIFLUX_API_KEY")
MINIFLUX_USER_ID = os.getenv("MINIFLUX_USER_ID")

# Discord Webhook configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

client = Client(MINIFLUX_URL, api_key=MINIFLUX_API_KEY)

def extract_image(content):
    match = re.search(r'<img src="([^"]+)"', content)
    return match.group(1) if match else None

def get_icon_url(feed_url):
    """
    Retrieve the icon URL from the RSS feed metadata.
    """
    try:
        response = requests.get(feed_url)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            icon_url = root.find(".//image/url")
            return icon_url.text if icon_url is not None and icon_url.text else None
        else:
            print(f"Error accessing feed: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error retrieving icon URL: {e}")
        return None

def archive_post(entry):
    if not ARCHIVE_MODE:
        return

    author = entry.get("author", "Unknown Author")
    category = entry["feed"].get("category", {}).get("title", "Uncategorized")
    author_with_category = f"{author} - {category}"

    try:
        published_at = datetime.fromisoformat(entry["published_at"])
    except ValueError as e:
        print(f"Error parsing date: {e}")
        return

    year = str(published_at.year)
    month = month_name[published_at.month]
    day_and_time = published_at.strftime("%d-%H-%M-%S")
    post_title = f"{day_and_time} - {entry['title']}"

    base_path = Path("Archive") / author_with_category / year / month / post_title
    base_path.mkdir(parents=True, exist_ok=True)

    post_url = entry["url"]
    try:
        command = ["gallery-dl", "-D", str(base_path), post_url]
        subprocess.run(command, check=True)
        print(f"Files downloaded successfully to {base_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error using gallery-dl for {post_url}: {e}")

def send_embed_to_discord(unread_entries):
    for entry in unread_entries:
        feed_url = entry["feed"]["feed_url"]
        icon_url = get_icon_url(feed_url)

        image_url = extract_image(entry["content"]) or random.choice(NOT_FOUND_IMAGES)
        archive_post(entry)

        category = entry["feed"].get("category", {}).get("title", "Uncategorized")
        embed_color = CATEGORY_COLORS.get(category, 16777215)  # Default to white
        category_icon = CATEGORY_ICONS.get(category, "https://i.imgur.com/Nyh7tRG.png")

        if icon_url is None:
            icon_url = category_icon

        embed = {
            "embeds": [
                {
                    "title": entry["title"],
                    "url": entry["url"],
                    "color": embed_color,
                    "author": {
                        "name": entry["author"],
                        "url": entry["feed"]["site_url"],
                        "icon_url": icon_url
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

        response = requests.post(DISCORD_WEBHOOK_URL, json=embed)
        time.sleep(5)

        if response.status_code == 204:
            print(f"Article '{entry['title']}' sent successfully to Discord!")
        else:
            print(f"Failed to send '{entry['title']}'. Status code: {response.status_code}")

# Fetch unread entries from Miniflux
unread_entries = client.get_entries(status="unread")["entries"]

if not unread_entries:
    print("No new articles found.")
else:
    client.mark_user_entries_as_read(MINIFLUX_USER_ID)
    send_embed_to_discord(unread_entries)
