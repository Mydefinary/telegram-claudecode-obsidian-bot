import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "E:/옵시디언/호아1")
OBSIDIAN_FOLDER = "텔레그램"  # Obsidian 내 저장 폴더
