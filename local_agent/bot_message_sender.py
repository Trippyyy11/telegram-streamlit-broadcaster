import requests
import os

BOT_TOKEN = "8256718800:AAGGLyn_aSxg3aVruamFOL6mb0ZrVo3mhbU"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_text(chat_id, text):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def send_photo(chat_id, file_path, caption=None):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print(f"Photo file missing or empty: {file_path}")
        return

    with open(file_path, "rb") as photo:
        response = requests.post(
            f"{BASE_URL}/sendPhoto",
            data={
                "chat_id": chat_id,
                "caption": caption or ""
            },
            files={
                "photo": photo
            },
            timeout=60
        )

    print("PHOTO RESPONSE:", response.text)

def send_document(chat_id, file_path, caption=None):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print(f"Document file missing or empty: {file_path}")
        return

    with open(file_path, "rb") as doc:
        response = requests.post(
            f"{BASE_URL}/sendDocument",
            data={
                "chat_id": chat_id,
                "caption": caption or ""
            },
            files={
                "document": doc
            },
            timeout=60
        )

    print("DOC RESPONSE:", response.text)
