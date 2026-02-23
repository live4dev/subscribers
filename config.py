import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
NOTIFICATION_CHAT_ID: int = int(os.getenv("NOTIFICATION_CHAT_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env файле")
if not NOTIFICATION_CHAT_ID:
    raise ValueError("NOTIFICATION_CHAT_ID не задан в .env файле")
