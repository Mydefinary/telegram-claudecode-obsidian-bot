"""Evaluate saved Obsidian notes and manage Claude Code tips."""

import os
import re
from analyzer import _run_claude
from prompts import get_prompts
from config import LANGUAGE

_prompts = get_prompts()
EVAL_PROMPT = _prompts["eval"]

CLAUDE_MD_PATH = os.path.expanduser("~/.claude/CLAUDE.md")
COMMANDS_DIR = os.path.expanduser("~/.claude/commands")
TIPS_DIR = os.path.expanduser("~/.claude/tips")

# Mapping for bilingual parsing
_FIELD_MAP_KO = {
    "최신성": "freshness", "실용성": "practicality", "신뢰도": "reliability",
    "깊이": "depth", "개발자적합성": "relevance", "클코적용성": "claude_code",
    "종합등급": "grade", "한줄평": "summary",
    "클코팁": "tip", "팁설명": "tip_desc",
    "처리유형": "tip_action", "권장도": "tip_confidence",
    "유형근거": "tip_action_reason", "스킬명": "skill_name", "태그": "tags",
}
_FIELD_MAP_EN = {
    "Freshness": "freshness", "Practicality": "practicality", "Reliability": "reliability",
    "Depth": "depth", "DevRelevance": "relevance", "ClaudeCodeApplicability": "claude_code",
    "Grade": "grade", "OneLiner": "summary",
    "CCTip": "tip", "TipDesc": "tip_desc",
    "Action": "tip_action", "Confidence": "tip_confidence",
    "ActionReason": "tip_action_reason", "SkillName": "skill_name", "Tags": "tags",
}
_FIELD_MAP = {**_FIELD_MAP_KO, **_FIELD_MAP_EN}

_SCORE_FIELDS = {"freshness", "practicality", "reliability", "depth", "relevance", "claude_code", "tip_confidence"}
_NONE_VALUES = {"없음", "none", "None", ""}


def parse_eval_result(text: str) -> dict:
    """Parse evaluation result text into structured dict."""
    result = {
        "freshness": 0, "practicality": 0, "reliability": 0,
        "depth": 0, "relevance": 0, "claude_code": 0,
        "grade": "D", "summary": "", "tip": "", "tip_desc": "",
        "tip_action": "", "tip_confidence": 0, "tip_action_reason": "",
        "skill_name": "", "tags": [],
    }

    for line in text.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue

        key_part = line.split(":", 1)[0].strip()
        val_part = line.split(":", 1)[1].strip()

        field = _FIELD_MAP.get(key_part)
        if not field:
            continue

        if field in _SCORE_FIELDS:
            try:
                result[field] = int(re.search(r"\d", val_part).group())
            except (AttributeError, ValueError):
                pass
        elif field == "grade":
            result[field] = val_part[:1]
        elif field == "tags":
            if val_part not in _NONE_VALUES:
                result[field] = [t.strip() for t in val_part.split(",") if t.strip()]
        else:
            result[field] = val_part

    return result


async def evaluate_note(title: str, content: str, url: str = "") -> dict:
    """Evaluate a note."""
    note_text = f"Title: {title}\nURL: {url}\n\n{content}"
    if len(note_text) > 4000:
        note_text = note_text[:4000] + "\n...(truncated)"

    prompt = f"{EVAL_PROMPT}\n\n--- Note to evaluate ---\n{note_text}"
    raw = await _run_claude(prompt)
    return parse_eval_result(raw)


def format_eval_tags(result: dict) -> str:
    """Format evaluation result as Obsidian note section."""
    total = (result['freshness'] + result['practicality'] + result['reliability']
             + result['depth'] + result['relevance'] + result['claude_code'])

    if LANGUAGE == "en":
        return (
            f"\n\n---\n"
            f"## Evaluation\n"
            f"- Freshness: {'⭐' * result['freshness']}{'☆' * (5 - result['freshness'])} ({result['freshness']}/5)\n"
            f"- Practicality: {'⭐' * result['practicality']}{'☆' * (5 - result['practicality'])} ({result['practicality']}/5)\n"
            f"- Reliability: {'⭐' * result['reliability']}{'☆' * (5 - result['reliability'])} ({result['reliability']}/5)\n"
            f"- Depth: {'⭐' * result['depth']}{'☆' * (5 - result['depth'])} ({result['depth']}/5)\n"
            f"- Dev Relevance: {'⭐' * result['relevance']}{'☆' * (5 - result['relevance'])} ({result['relevance']}/5)\n"
            f"- Claude Code: {'⭐' * result['claude_code']}{'☆' * (5 - result['claude_code'])} ({result['claude_code']}/5)\n"
            f"- Grade: **{result['grade']}** ({total}/30)\n"
            f"- Summary: {result['summary']}\n"
        )

    return (
        f"\n\n---\n"
        f"## 평가\n"
        f"- 최신성: {'⭐' * result['freshness']}{'☆' * (5 - result['freshness'])} ({result['freshness']}/5)\n"
        f"- 실용성: {'⭐' * result['practicality']}{'☆' * (5 - result['practicality'])} ({result['practicality']}/5)\n"
        f"- 신뢰도: {'⭐' * result['reliability']}{'☆' * (5 - result['reliability'])} ({result['reliability']}/5)\n"
        f"- 깊이: {'⭐' * result['depth']}{'☆' * (5 - result['depth'])} ({result['depth']}/5)\n"
        f"- 개발자 적합성: {'⭐' * result['relevance']}{'☆' * (5 - result['relevance'])} ({result['relevance']}/5)\n"
        f"- Claude Code 적용성: {'⭐' * result['claude_code']}{'☆' * (5 - result['claude_code'])} ({result['claude_code']}/5)\n"
        f"- 종합등급: **{result['grade']}** ({total}/30)\n"
        f"- 한줄평: {result['summary']}\n"
    )


def append_to_claude_md(tip: str, source_title: str):
    """Append Claude Code tip to global CLAUDE.md. Dedup check included."""
    if not tip or tip in _NONE_VALUES:
        return False

    content = ""
    if os.path.exists(CLAUDE_MD_PATH):
        with open(CLAUDE_MD_PATH, "r", encoding="utf-8") as f:
            content = f.read()

    if tip in content:
        return False

    section_header = "## Claude Code 팁 (자동 수집)"
    if section_header not in content:
        content += f"\n\n{section_header}\n"

    content += f"- {tip} (출처: {source_title})\n"

    with open(CLAUDE_MD_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    return True


def save_tip_to_pool(tip: str, tip_desc: str, source_title: str, skill_name: str = "", tags: list[str] = None):
    """Save tip to pool for later /apply-tips matching.
    Returns: file path or False
    """
    if not tip or tip in _NONE_VALUES:
        return False

    os.makedirs(TIPS_DIR, exist_ok=True)

    for f in os.listdir(TIPS_DIR):
        if not f.endswith(".md"):
            continue
        try:
            with open(os.path.join(TIPS_DIR, f), "r", encoding="utf-8") as fh:
                if tip in fh.read():
                    return False
        except Exception:
            continue

    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    existing = [f for f in os.listdir(TIPS_DIR) if f.startswith(date_str) and f.endswith(".md")]
    seq = len(existing) + 1
    filename = f"{date_str}_{seq:02d}.md"
    filepath = os.path.join(TIPS_DIR, filename)

    tags_str = ", ".join(tags) if tags else ""
    lines = [
        "---",
        f'source: "{source_title}"',
        f'date: "{datetime.now().strftime("%Y-%m-%d")}"',
        f'tags: [{tags_str}]',
        "applied: []",
        "declined: []",
        "---",
        "",
        "## 팁",
        tip,
    ]
    if tip_desc and tip_desc not in _NONE_VALUES:
        lines.extend(["", "## 설명", tip_desc])
    if skill_name and skill_name not in _NONE_VALUES:
        lines.extend(["", "## 관련 스킬명", skill_name])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def create_skill(skill_name: str, tip: str, tip_desc: str, source_title: str):
    """Create a Claude Code slash command (skill).
    Returns: file path or False
    """
    if not skill_name or skill_name in _NONE_VALUES:
        return False

    os.makedirs(COMMANDS_DIR, exist_ok=True)

    safe_name = skill_name.strip().replace(" ", "-").lower()
    filepath = os.path.join(COMMANDS_DIR, f"{safe_name}.md")

    if os.path.exists(filepath):
        return False

    lines = [tip]
    if tip_desc and tip_desc not in _NONE_VALUES:
        lines.append(f"\n## Background\n{tip_desc}")
    lines.append(f"\n---\n> Source: {source_title}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def update_note_with_eval(filepath: str, eval_text: str):
    """Append evaluation result to the end of an Obsidian note file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if "## 평가" in content or "## Evaluation" in content:
        return

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(eval_text)
