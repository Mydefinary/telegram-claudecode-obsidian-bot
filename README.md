# telegram-claudecode-obsidian-bot

A Telegram bot that analyzes links, messages, images, and files with AI, then saves them as structured Obsidian notes.

[![CI](https://github.com/Mydefinary/telegram-claudecode-obsidian-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Mydefinary/telegram-claudecode-obsidian-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[한국어 README](README_ko.md)

## Demo

> Screenshots and demo GIF coming soon. See [Usage](#usage) for details.
<!--
TODO: Add screenshots
- Telegram conversation showing URL analysis
- Generated Obsidian note with evaluation
- Tip processing inline buttons
-->

## Features

- **URL Analysis** -- Scrapes web pages + AI analysis to generate Obsidian notes (supports YouTube, Instagram, Threads, and other social media)
- **Text Analysis** -- AI organizes text into structured notes
- **Image Analysis** -- AI reads and analyzes images; originals are attached to the vault
- **Batch File Processing** -- Upload `.txt` files for queue-based parallel processing (3 concurrent by default)
- **KakaoTalk Chat Parsing** -- Auto-detects KakaoTalk chat export format and parses messages individually
- **Content Deduplication** -- Compares against existing notes to determine new/duplicate/supplement status
- **Original Content Preservation** -- Stores raw source content in collapsible Obsidian callouts alongside the analysis
- **6-Criteria Note Evaluation** -- Freshness, Practicality, Reliability, Depth, Developer Relevance, Claude Code Applicability (30 points, A-D grades)
- **Claude Code Tips Extraction** -- When tips are found, choose via Telegram inline buttons: Apply Globally / Create Skill / Save to Pool / Skip
- **Tip Pool + Tag Matching** -- Saved tips can be applied to projects via `/apply-tips` with tag-based matching
- **Multi-language Output** -- Supports Korean and English output
- **Multiple AI Engines** -- Choose between Claude Code CLI, Anthropic API, or OpenAI API

## Architecture

```
Telegram Message/File
    |
    v
[bot.py] Telegram Handler + Queue Processing
    |
    v
[scraper.py] Web Scraping (if URL)
    |
    v
[analyzer.py] AI Analysis (Claude CLI / Anthropic API / OpenAI API)
    |
    v
[obsidian_writer.py] Save to Obsidian Vault (with original content)
    |
    v
[evaluator.py] 6-Criteria Evaluation + Claude Code Tips Extraction
    |
    v
[Telegram Inline Buttons] Tip Processing
    |
    +--[Apply Globally]---> ~/.claude/CLAUDE.md
    +--[Create Skill]-----> ~/.claude/commands/{name}.md
    +--[Save to Pool]-----> ~/.claude/tips/{date}_{seq}.md (with tags)
    +--[Skip]-------------> Kept in Obsidian only
```

## Quick Start

### Prerequisites

- Python 3.10+
- One of the following AI engines:
  - [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (default)
  - Anthropic API key
  - OpenAI API key

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/telegram-obsidian-bot.git
cd telegram-obsidian-bot
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

See [Configuration](#configuration-1) for all available variables.

### Run

```bash
python bot.py
```

### Docker

```bash
docker compose up -d
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token from [BotFather](https://t.me/BotFather) |
| `OBSIDIAN_VAULT_PATH` | Yes | - | Absolute path to your Obsidian vault |
| `ANALYSIS_ENGINE` | No | `claude-cli` | AI engine: `claude-cli`, `anthropic`, or `openai` |
| `LANGUAGE` | No | `ko` | Output language: `ko` or `en` |
| `MAX_CONCURRENT` | No | `3` | Max concurrent analysis tasks |
| `OBSIDIAN_FOLDER` | No | `텔레그램` | Subfolder name within the vault for saved notes |
| `ANTHROPIC_API_KEY` | If engine is `anthropic` | - | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Anthropic model name |
| `OPENAI_API_KEY` | If engine is `openai` | - | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model name |
| `CLAUDE_CMD` | No | Auto-detected | Path to Claude CLI executable |

## Usage

1. Start a conversation with your bot on Telegram (`/start`)
2. Send any of the following:
   - **URL** -- Analyzes the web page and generates a note
   - **Text** -- Organizes the content into a structured note
   - **Image** -- Analyzes the image and generates a note (original attached)
   - **`.txt` file** -- Splits into items and processes in parallel (auto-detects KakaoTalk export format)
3. The bot saves a markdown note to your Obsidian vault's configured folder
4. If a Claude Code tip is detected, you get 4 inline buttons:
   - **Apply Globally** -- Appends to `~/.claude/CLAUDE.md`
   - **Create Skill** -- Creates a slash command in `~/.claude/commands/`
   - **Save to Pool** -- Saves to `~/.claude/tips/` with tags for later matching
   - **Skip** -- Keeps the tip in the Obsidian note only
5. Run `/apply-tips` in any project to get tag-matched tip recommendations from the pool

## Evaluation Criteria

Each note is automatically evaluated on 6 criteria (1-5 points each, 30 points total):

| Criterion | Description | 1 point | 5 points |
|---|---|---|---|
| Freshness | Is this current information? | Outdated | Cutting-edge |
| Practicality | Can it be applied immediately? | Theory only | Includes code/workflow |
| Reliability | How credible is the source? | Unverified/speculation | Official docs/expert |
| Depth | Level of insight | Surface-level intro | Deep, experience-based analysis |
| Dev Relevance | Useful for developers? | Irrelevant | Core practice |
| Claude Code Applicability | Applicable to Claude Code? | None | Immediately applicable |

**Grades:** **A** (25+) / **B** (19-24) / **C** (13-18) / **D** (12 or below)

## Project Structure

```
telegram-obsidian-bot/
├── bot.py                  # Main bot: Telegram handlers + queue processing
├── analyzer.py             # AI analysis engine (Claude CLI / Anthropic / OpenAI)
├── scraper.py              # Web scraping (httpx + BeautifulSoup)
├── obsidian_writer.py      # Obsidian markdown writer + original preservation + image copy
├── evaluator.py            # 6-criteria evaluation + Claude Code tips + tip pool/skill creation
├── kakao_parser.py         # KakaoTalk chat export parser
├── config.py               # Configuration (tokens, vault path, engine selection)
├── prompts/                # Multi-language prompt templates
│   ├── __init__.py
│   ├── ko.py               # Korean prompts
│   └── en.py               # English prompts
├── tests/                  # Tests
│   ├── __init__.py
│   └── conftest.py
├── fix_existing_notes.py   # Batch cleanup of existing note frontmatter
├── backfill_originals.py   # Backfill original content into existing notes
├── backfill_tags.py        # Backfill tags into existing tip files
├── Dockerfile              # Docker image build
├── docker-compose.yml      # Docker Compose configuration
├── start.bat               # Windows startup script
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── README_ko.md            # Korean README
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.13 |
| Telegram | python-telegram-bot |
| Web Scraping | httpx + BeautifulSoup4 |
| AI Engines | Claude Code CLI / Anthropic API / OpenAI API (configurable) |
| Environment | python-dotenv |
| Note Storage | Direct markdown file creation in Obsidian vault |
| Container | Docker + Docker Compose |

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).
