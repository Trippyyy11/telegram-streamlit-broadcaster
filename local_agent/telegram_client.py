from telethon import TelegramClient
from telethon.sessions import StringSession
import os

API_ID = int(input("Enter your Telegram API ID: "))
API_HASH = input("Enter your Telegram API HASH: ")

SESSION_FILE = "session.txt"

def get_client():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            session_str = f.read()
        return TelegramClient(StringSession(session_str), API_ID, API_HASH)
    else:
        return TelegramClient(StringSession(), API_ID, API_HASH)


async def login_and_save(client):
    await client.start()
    with open(SESSION_FILE, "w") as f:
        f.write(client.session.save())
