import discord
import os
import dotenv
import json
import time
import asyncio

dotenv.load_dotenv()

IMAGE_SUSPICIOUSNESS = 0.3
SUSPICIOUSNESS_THRESHOLD = 1.0
FORGIVENESS_TIME = 120 # Two minutes
SUSPICIOUS_MESSAGES_THRESHOLD = 5 # If a user sends this many suspicious messages within the forgiveness time, they will be kicked.
IGNORE_LONGTIME_USERS = True # If true, users who have been in the server for a long time will be ignored.
LONGTIME_USER_THRESHOLD = 7 # If IGNORE_LONGTIME_USERS is true, users who have been in the server for this many days will be ignored.

log_channel = None

keywords = {}
with open("keywords.json", "r") as file:
    keywords = json.load(file)

user_suspicious_messages = {}
# When a message is flagged as suspicious, it will be added to this dictionary.
# If a user sends too many such messages in a short timespan, they will be kicked.
# After a certain amount of time, the messages will decay and eventually disappear.

def log(text):
    print(text)
    if log_channel:
        asyncio.create_task(log_channel.send(text))

def get_suspiciousness(message):
    score = 0
    content = message.content.lower()
    content = content.replace("’", "'")
    for keyword, weight in keywords.items():
        if keyword.lower() in content:
            score += weight
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            score += IMAGE_SUSPICIOUSNESS
    return score

def is_suspicious(message):
    return get_suspiciousness(message) >= SUSPICIOUSNESS_THRESHOLD

def set_log_channel(channel):
    global log_channel
    if channel is None:
        log_channel = None
        if os.path.exists("log_channel_id.txt"):
            os.remove("log_channel_id.txt")
        return
    log_channel = channel
    with open("log_channel_id.txt", "w") as file:
        file.write(str(channel.id))

def load_log_channel():
    global log_channel
    if os.path.exists("log_channel_id.txt"):
        with open("log_channel_id.txt", "r") as file:
            channel_id = int(file.read().strip())
            if channel_id is None: return
            log_channel = client.get_channel(channel_id)
            if log_channel:
                log(f"Loaded log channel: {log_channel.name} (ID: {log_channel.id})")
            else:
                log("Failed to load log channel. Channel not found.")

async def update_user_suspicion(user):
    now = time.time()
    if user not in user_suspicious_messages:
        return
    # Remove old entries
    user_suspicious_messages[user] = [message for message in user_suspicious_messages[user] if now - message.created_at.timestamp() < FORGIVENESS_TIME]
    count = len(user_suspicious_messages[user])
    if count >= SUSPICIOUS_MESSAGES_THRESHOLD:
        try:
            await send_to_the_shadow_realm(user)
            del user_suspicious_messages[user]
        except Exception as e:
            log(f"Failed to punish user {user}: {e}")

async def send_to_the_shadow_realm(user):
    await user.kick(reason="Suspected of sending scam messages. Please contact the moderators if you believe this was a mistake.")
    for message in user_suspicious_messages[user]:
        print(f"Deleting message {message.id} from user {user} in channel {message.channel}")
        try:
            await message.delete()
        except Exception as e:
            log(f"Failed to delete message {message.id} from user {user}: {e}")
    log(f"**User {user} has been kicked on suspicion of sending scam messages.**")

def is_trustworthy(member):
    if not IGNORE_LONGTIME_USERS: return False
    now = time.time()
    been_in_server_time = now - member.joined_at.timestamp()
    if been_in_server_time >= LONGTIME_USER_THRESHOLD * 24 * 60 * 60:
        return True
    return False

def get_help_text():
    return """**Commands:**
`!help` - Show this help message.
`!suspiciousness` - Test the suspiciousness of your message.
`!loghere` - Set the current channel as the log channel.
`!stoplogging` - Stop logging to Discord. 
"""

class Bot(discord.Client):
    async def on_ready(self):
        load_log_channel()
        log(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith("!help"):
            await message.channel.send(get_help_text())
        if message.content.startswith("!suspiciousness"):
            await self.test_suspiciousness(message)
        if message.content.startswith("!loghere"):
            set_log_channel(message.channel)
            await message.channel.send("This channel is now set for logging.")
        if message.content.startswith("!stoplogging"):
            set_log_channel(None)
            await message.channel.send("Logging to Discord has been stopped.")
        if is_suspicious(message):
            log(f"Flagged message {message.id} from {message.author} as suspicious with score {get_suspiciousness(message):.2f}")
            author = message.author
            if is_trustworthy(author):
                log(f"User {author} is considered trustworthy. Ignoring suspicious message.")
                return
            if author not in user_suspicious_messages:
                user_suspicious_messages[author] = []
            user_suspicious_messages[author].append(message)
            await update_user_suspicion(author)

    async def test_suspiciousness(self, message):
        score = get_suspiciousness(message)
        suspicious_text = "SUSPICIOUS" if is_suspicious(message) else "not suspicious"
        await message.channel.send(f"Suspiciousness score: **{score:.2f}** *[{suspicious_text}]*")
        log(f"Calculated suspiciousness for message {message.id} with score {score:.2f} [{suspicious_text}]")

intents = discord.Intents.default()
intents.message_content = True

client = Bot(intents=intents)
client.run(os.getenv('TOKEN'))