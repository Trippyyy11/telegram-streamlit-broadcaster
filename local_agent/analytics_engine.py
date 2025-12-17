from telethon import TelegramClient
from telethon.tl.types import Message
import sqlite3
import asyncio
import os
import json
from datetime import datetime
from telegram_client import get_client

# Define Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "storage.db")

async def update_stats():
    print("Starting Analytics Sync...")
    
    # 1. Connect to DB
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 2. Fetch Sent Messages that are not deleted
    # We only care about messages composed by us (status='sent')
    # Optimally, we filter recent ones or check all. For MVP, check all non-deleted.
    cur.execute("SELECT id, chat_id, message_id FROM sent_messages WHERE status = 'sent'")
    rows = cur.fetchall()
    
    if not rows:
        print("No sent messages to track.")
        conn.close()
        return

    # Group by chat_id to batch requests
    chat_map = {}
    for db_id, chat_id, msg_id in rows:
        if chat_id not in chat_map:
            chat_map[chat_id] = []
        chat_map[chat_id].append((db_id, msg_id))

    # 3. Connect Telegram Client
    client = get_client()
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("Client not authorized. Cannot fetch stats.")
            return

        # Cache Warming: Fetch dialogs so Telethon knows about the entities
        print("Warming up entity cache...")
        await client.get_dialogs(limit=100) 

        print(f"Processing {len(chat_map)} chats...")
        
        for chat_id, items in chat_map.items():
            msg_ids = [m[1] for m in items]
            
            try:
                # Telethon get_messages allows bulk fetching
                messages = await client.get_messages(chat_id, ids=msg_ids)
                
                for msg in messages:
                    if not msg: continue
                    if not isinstance(msg, Message): continue
                    
                    # Extract Metrics
                    # Note: views/forwards are often None for private chats, but present for Channels
                    views = getattr(msg, 'views', 0) or 0
                    forwards = getattr(msg, 'forwards', 0) or 0
                    
                    # Reactions
                    reaction_count = 0
                    if msg.reactions and msg.reactions.results:
                        reaction_count = sum(r.count for r in msg.reactions.results)

                    # Replies / Comments
                    replies_count = 0
                    if msg.replies:
                        replies_count = msg.replies.replies or 0

                    # Find DB ID
                    db_id = next((i[0] for i in items if i[1] == msg.id), None)
                    
                    if db_id:
                        cur.execute("""
                            UPDATE sent_messages 
                            SET views = ?, forwards = ?, reactions = ?, replies = ?, last_updated = ?
                            WHERE id = ?
                        """, (views, forwards, reaction_count, replies_count, datetime.now().isoformat(), db_id))
                        print(f"Updated Msg {msg.id}: {views} views, {replies_count} replies")

                conn.commit()
                # Rate limit safety
                await asyncio.sleep(1) 
                
            except Exception as e:
                print(f"Failed to fetch for chat {chat_id}: {e}")

    except Exception as e:
        print(f"Client Error: {e}")
    finally:
        await client.disconnect()
        conn.close()
    
    print("Analytics Sync Complete.")

if __name__ == "__main__":
    asyncio.run(update_stats())
