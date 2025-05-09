import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_CHAT_ID: str = os.getenv("TELEGRAM_BOT_CHAT_ID")