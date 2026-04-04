# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
pip install -r requirements.txt          # Install dependencies
python bot.py                            # Run the bot
docker compose up -d                     # Or run via Docker
```

## Testing & Linting

```bash
pip install pytest pytest-asyncio        # Dev dependencies (not in requirements.txt)
pytest tests/ -v                         # Run all tests
pytest tests/test_analyzer.py -v         # Run a single test file
python -m py_compile bot.py              # Lint a single file (CI uses this for all .py files)
```

CI (.github/workflows/ci.yml) runs py_compile on all .py files + pytest on Python 3.11 and 3.13.

## Architecture

The bot follows a linear pipeline: **Telegram input → scraping → AI analysis → dedup → Obsidian save → evaluation → tip processing**.

### Core Pipeline

- **bot.py** — Telegram handlers, async queue processor with `asyncio.Semaphore(MAX_CONCURRENT)`. Entry point for all message types (URL, text, image, .txt file). Manages tip callback routing via `pending_tips` dict with UUID keys.
- **scraper.py** — URL extraction (regex) + httpx/BeautifulSoup page fetch. Strips nav/footer/script, truncates to 6000 chars.
- **analyzer.py** — Multi-engine abstraction. `analyze_link()`, `analyze_text()`, `analyze_image()` dispatch to Claude CLI (`claude -p -` via stdin pipe, 180s timeout), Anthropic API, or OpenAI API based on `ANALYSIS_ENGINE` config. Also handles dedup: `check_duplicate_content()` compares title + 500-char preview against existing notes, AI returns new/skip/merge verdict.
- **obsidian_writer.py** — Saves markdown notes with YAML frontmatter. Filename collision handling (`_1`, `_2` suffix). Original content preserved in collapsible `> [!quote]-` callouts (max 5000 chars). Image pipeline: download → copy to `/attachments/img_TIMESTAMP.jpg` → embed as `![[...]]`.
- **evaluator.py** — 6-criteria scoring (freshness/practicality/reliability/depth/dev-relevance/claude-code-applicability, 5pts each = 30 total, grades A-D). Extracts Claude Code tips and routes them via Telegram inline buttons to: `~/.claude/CLAUDE.md` (global), `~/.claude/commands/` (skill), `~/.claude/tips/` (pool with tags), or skip.

### Supporting Modules

- **kakao_parser.py** — Auto-detects KakaoTalk export format via date header regex. Groups URL+description into single posts, skips media (사진/동영상/파일).
- **config.py** — Loads `.env` via python-dotenv. Auto-detects Claude CLI path with `shutil.which("claude")`.
- **prompts/{ko,en}.py** — Bilingual prompt templates loaded by `LANGUAGE` config. Includes fail/meta pattern regexes for output validation and cleanup.

### Key Patterns

- **Encoding fallback**: .txt uploads try UTF-8 → CP949 → EUC-KR → Latin-1 in sequence.
- **Dedup merge**: When AI returns "보강/supplement", new info appends to existing note under `### 추가 정보`.
- **Tip callback flow**: evaluator extracts tip → bot stores in `pending_tips[uuid]` → user clicks inline button → `callback_data="action:uuid"` → routes to global/skill/pool/skip handler.
- **Bilingual field parsing**: evaluator maps Korean field names (최신성, 실용성, etc.) to English keys for structured processing.

## Environment Variables

Required: `TELEGRAM_BOT_TOKEN`, `OBSIDIAN_VAULT_PATH`

Engine selection via `ANALYSIS_ENGINE`: `claude-cli` (default), `anthropic`, `openai`. Each engine requires its own API key except claude-cli which uses the authenticated CLI.

See `.env.example` for all options.
