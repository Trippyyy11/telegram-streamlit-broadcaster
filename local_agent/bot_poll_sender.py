
import requests

BOT_TOKEN = "8256718800:AAGGLyn_aSxg3aVruamFOL6mb0ZrVo3mhbU"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_poll(chat_id, question, options, correct):
    payload = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_id": correct,
        "is_anonymous": True
    }

    requests.post(f"{BASE_URL}/sendPoll", json=payload)
