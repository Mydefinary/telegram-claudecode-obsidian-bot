import os
import logging
import shutil
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# ── Logging ──
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 파일 핸들러: 5MB 회전, 최대 5개 백업
_file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "bot.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(_log_formatter)
_file_handler.setLevel(logging.DEBUG)

# 에러 전용 파일 핸들러
_error_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "error.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_error_handler.setFormatter(_log_formatter)
_error_handler.setLevel(logging.ERROR)

# 콘솔 핸들러
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)
_console_handler.setLevel(logging.INFO)

# 루트 로거 설정
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG)
_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_error_handler)
_root_logger.addHandler(_console_handler)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Obsidian
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
OBSIDIAN_FOLDER = os.getenv("OBSIDIAN_FOLDER", "텔레그램")

# Processing
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10MB default
LANGUAGE = os.getenv("LANGUAGE", "ko")  # ko, en

# Security: 허용된 텔레그램 사용자 ID (쉼표 구분, 비어있으면 모든 사용자 허용)
_allowed_ids_raw = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {int(x.strip()) for x in _allowed_ids_raw.split(",") if x.strip()}

# Message merge (연속 메시지 자동 병합)
MESSAGE_MERGE_ENABLED = os.getenv("MESSAGE_MERGE_ENABLED", "true").lower() == "true"
MESSAGE_MERGE_WAIT = int(os.getenv("MESSAGE_MERGE_WAIT", "5"))

# Analysis engine: "claude-cli", "anthropic", "openai"
ANALYSIS_ENGINE = os.getenv("ANALYSIS_ENGINE", "claude-cli")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Gemini (YouTube fallback)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# GitHub API (optional, for richer repo metadata)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Claude CLI path (auto-detect if not set)
CLAUDE_CMD = os.getenv("CLAUDE_CMD", "")
if not CLAUDE_CMD:
    CLAUDE_CMD = shutil.which("claude") or "claude"
