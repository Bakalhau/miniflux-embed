import requests
import os
import re
import time
from miniflux import Client
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

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
        icon_url = root.find(".//image/url").text
        return icon_url
    else:
        print(f"Error accessing the feed: {response.status_code}")
        return None

# Function to send embed to Discord
def send_embed_to_discord(unread_entries):
    for entry in unread_entries:

        feed_url = entry["feed"]["feed_url"]

        icon_url = get_icon_url(feed_url)

        # Extract image URL from 'content'
        image_url = extract_image(entry["content"])

        if image_url is None:
            image_url = "https://i.imgur.com/5zcBLRc.png"
        
        # Create the embed payload
        embed = {
            "embeds": [
                {
                    "title": entry["title"],
                    "url": entry["url"],
                    "color": 16742912,
                    "author": {
                        "name": entry["author"],
                        "url": entry["feed"]["site_url"],
                        "icon_url": icon_url
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
        time.sleep(20)
        
        # Check if the send was successful
        if response.status_code == 204:
            print(f"Article '{entry['title']}' sent successfully to Discord!")
        else:
            print(f"Failed to send '{entry['title']}'. Status code: {response.status_code}")
    

# Fetch all unread entries from Miniflux
unread_entries = client.get_entries(status="unread")["entries"]

# Mark user entries as read in Miniflux
client.mark_user_entries_as_read(MINIFLUX_USER_ID)

# Send each entry as an embed to Discord
send_embed_to_discord(unread_entries)
