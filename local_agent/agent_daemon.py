import asyncio
import json
import os
import time
import sqlite3
import uuid
from datetime import datetime, timedelta

from bot_message_sender import send_text, send_photo, send_document, delete_message
from bot_poll_sender import send_poll

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(BASE_DIR, "tasks")
DB_PATH = os.path.join(BASE_DIR, "storage.db")

os.makedirs(TASKS_DIR, exist_ok=True)

def save_sent_message(task_id, chat_id, message_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sent_messages (task_id, chat_id, message_id, sent_at, status)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, chat_id, message_id, datetime.now().isoformat(), 'sent'))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def update_message_status(chat_id, message_id, status):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            UPDATE sent_messages SET status = ? WHERE chat_id = ? AND message_id = ?
        """, (status, chat_id, message_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

async def run_daemon():
    print("Telegram agent daemon started. Scheduling active.\n")

    while True:
        try:
            tasks = [f for f in os.listdir(TASKS_DIR) if f.endswith(".json")]

            for fname in tasks:
                fpath = os.path.join(TASKS_DIR, fname)

                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        task = json.load(f)

                    send_at = task.get("send_at")
                    if send_at:
                        if datetime.now() < datetime.fromisoformat(send_at):
                            continue

                    task_id = fname.replace(".json", "") # Use filename as ID if not in task
                    recipients = task.get("recipients", [])
                    
                    # Log Task Name processing if needed (optional)

                    # ---------- MESSAGE ----------
                    if task["type"] == "message":
                        content = task.get("content", "")
                        file_path = task.get("file_path")
                        file_type = task.get("file_type")
                        expires_in = task.get("expires_in_hours")

                        for chat_id in recipients:
                            response = None
                            if file_path:
                                if file_type == "photo":
                                    response = send_photo(chat_id, file_path, content)
                                else:
                                    response = send_document(chat_id, file_path, content)
                            else:
                                response = send_text(chat_id, content)
                            
                            # Log to DB
                            if response and response.get("ok"):
                                msg_id = response["result"]["message_id"]
                                save_sent_message(task_id, chat_id, msg_id)

                                # Handle Expiration
                                if expires_in and float(expires_in) > 0:
                                    delete_time = datetime.now() + timedelta(hours=float(expires_in))
                                    
                                    del_task = {
                                        "type": "delete_message",
                                        "chat_id": chat_id,
                                        "message_id": msg_id,
                                        "send_at": delete_time.isoformat()
                                    }
                                    
                                    # Save deletion task
                                    del_fname = f"del_{uuid.uuid4()}.json"
                                    with open(os.path.join(TASKS_DIR, del_fname), "w") as df:
                                        json.dump(del_task, df)
                                    print(f"Scheduled deletion for msg {msg_id} at {delete_time}")

                    # ---------- QUIZ ----------
                    elif task["type"] == "poll":
                        q = task["content"]["question"]
                        options = task["content"]["options"]
                        correct = task["content"]["correct"]

                        for chat_id in recipients:
                            send_poll(chat_id, q, options, correct)
                            # Poll API in this repo doesn't return ID easily easily without modify bot_poll_sender
                            # Skipping poll ID tracking for now as per plan focus on messages or needs bot_poll_sender update? 
                            # The plan said "Undo/Delete". Ideally should work for polls too.
                            # But bot_poll_sender.py uses requests.post without return.
                            # For now, let's stick to text/media as per explicit "temporary message" request. 
                            # If user asks for poll undo, we'll need to update that file too.

                    # ---------- DELETE MESSAGE ----------
                    elif task["type"] == "delete_message":
                        cid = task.get("chat_id")
                        mid = task.get("message_id")
                        if cid and mid:
                            delete_message(cid, mid)
                            update_message_status(cid, mid, "deleted")
                            print(f"Deleted message {mid} in {cid}")

                    os.remove(fpath)
                    print(f"Processed task {fname}")

                except Exception as e:
                    print(f"Error processing {fname}: {e}")

            await asyncio.sleep(2)

        except KeyboardInterrupt:
            print("\nDaemon stopped.")
            break

if __name__ == "__main__":
    asyncio.run(run_daemon())
