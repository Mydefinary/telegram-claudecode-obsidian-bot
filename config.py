import os
import shutil
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Obsidian
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
OBSIDIAN_FOLDER = os.getenv("OBSIDIAN_FOLDER", "텔레그램")

# Processing
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
LANGUAGE = os.getenv("LANGUAGE", "ko")  # ko, en

# Analysis engine: "claude-cli", "anthropic", "openai"
ANALYSIS_ENGINE = os.getenv("ANALYSIS_ENGINE", "claude-cli")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Claude CLI path (auto-detect if not set)
CLAUDE_CMD = os.getenv("CLAUDE_CMD", "")
if not CLAUDE_CMD:
    CLAUDE_CMD = shutil.which("claude") or "claude"
