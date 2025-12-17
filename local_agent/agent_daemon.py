import asyncio
import json
import os
import time
from datetime import datetime

from bot_message_sender import send_text, send_photo, send_document
from bot_poll_sender import send_poll

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(BASE_DIR, "tasks")

os.makedirs(TASKS_DIR, exist_ok=True)

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

                    recipients = task["recipients"]

                    # ---------- MESSAGE ----------
                    if task["type"] == "message":
                        text = task.get("content", "")
                        file_path = task.get("file_path")
                        file_type = task.get("file_type")

                        for chat_id in recipients:
                            if file_path:
                                if file_type == "photo":
                                    send_photo(chat_id, file_path, text)
                                else:
                                    send_document(chat_id, file_path, text)
                            else:
                                send_text(chat_id, text)

                    # ---------- QUIZ ----------
                    elif task["type"] == "poll":
                        q = task["content"]["question"]
                        options = task["content"]["options"]
                        correct = task["content"]["correct"]

                        for chat_id in recipients:
                            send_poll(chat_id, q, options, correct)

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
