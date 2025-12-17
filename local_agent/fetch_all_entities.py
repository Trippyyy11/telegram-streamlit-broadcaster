import asyncio
import json
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = 35246931
API_HASH = "c14ab433b85e2250ec4ce4691a881443"

OUTPUT_FILE = "telegram_entities.json"

async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()

    entities = []

    print("\nFetching all Telegram groups, channels, and contacts...\n")

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        entity_type = (
            "group" if dialog.is_group else
            "channel" if dialog.is_channel else
            "contact"
        )

        username = getattr(entity, "username", None)

        print(
            f"NAME: {dialog.name} | "
            f"ID: {dialog.id} | "
            f"TYPE: {entity_type}"
        )

        entities.append({
            "name": dialog.name,
            "id": dialog.id,
            "username": username,
            "type": entity_type
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2)

    print(f"\nSaved {len(entities)} entities to {OUTPUT_FILE}\n")

    await client.disconnect()

asyncio.run(main())
