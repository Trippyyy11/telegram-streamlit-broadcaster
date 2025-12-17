import asyncio
import json
import os
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN") or "PASTE_YOUR_BOT_TOKEN"

async def send_quiz(task_file):
    with open(task_file, "r", encoding="utf-8") as f:
        task = json.load(f)

    bot = Bot(token=BOT_TOKEN)

    quiz = task["content"]

    for chat_id in task["recipients"]:
        await bot.send_poll(
            chat_id=chat_id,
            question=quiz["question"],
            options=quiz["options"],
            type="quiz",
            correct_option_id=quiz["correct"],
            is_anonymous=False
        )
        print(f"Quiz sent to {chat_id}")

    os.remove(task_file)

if __name__ == "__main__":
    import sys
    asyncio.run(send_quiz(sys.argv[1]))
