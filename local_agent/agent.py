import sys
import json
import asyncio
from telegram_client import get_client, login_and_save

async def send_messages(task_file):
    with open(task_file, "r", encoding="utf-8") as f:
        task = json.load(f)

    recipients = task.get("recipients", [])
    message = task.get("message")

    if not recipients or not message:
        print("No recipients or message found in task.json")
        return

    client = get_client()
    await login_and_save(client)

    for recipient in recipients:
        try:
            await client.send_message(recipient, message)
            print(f"Sent to {recipient}")
            await asyncio.sleep(3)  # basic rate-limit protection
        except Exception as e:
            print(f"Failed to send to {recipient}: {e}")

    await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py task.json")
        sys.exit(1)

    asyncio.run(send_messages(sys.argv[1]))
