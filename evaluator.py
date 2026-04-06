"""Evaluate saved Obsidian notes and manage Claude Code tips."""

import os
import re
import logging
from analyzer import _run_claude
from prompts import get_prompts
from config import LANGUAGE

logger = logging.getLogger(__name__)

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
    logger.info(f"노트 평가 시작: {title}")
    note_text = f"Title: {title}\nURL: {url}\n\n{content}"
    if len(note_text) > 4000:
        note_text = note_text[:4000] + "\n...(truncated)"

    prompt = f"{EVAL_PROMPT}\n\n--- Note to evaluate ---\n{note_text}"
    raw = await _run_claude(prompt, allowed_tools="")
    result = parse_eval_result(raw)
    logger.info(f"노트 평가 완료: {title} -> 등급 {result['grade']}")
    return result


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
        logger.debug(f"중복 팁 스킵 (global): {tip[:50]}")
        return False

    section_header = "## Claude Code 팁 (자동 수집)"
    if section_header not in content:
        content += f"\n\n{section_header}\n"

    content += f"- {tip} (출처: {source_title})\n"

    try:
        with open(CLAUDE_MD_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Global 팁 추가: {tip[:50]}")
    except Exception as e:
        logger.error(f"CLAUDE.md 쓰기 실패: {e}", exc_info=True)
        return False

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
        except Exception as e:
            logger.warning(f"팁 중복 체크 시 파일 읽기 실패: {f} - {e}")
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

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info(f"팁 풀 저장: {filepath}")
    except Exception as e:
        logger.error(f"팁 풀 저장 실패: {e}", exc_info=True)
        return False

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
        logger.debug(f"중복 스킬 스킵: {safe_name}")
        return False

    lines = [tip]
    if tip_desc and tip_desc not in _NONE_VALUES:
        lines.append(f"\n## Background\n{tip_desc}")
    lines.append(f"\n---\n> Source: {source_title}")

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info(f"스킬 생성: /{safe_name} -> {filepath}")
    except Exception as e:
        logger.error(f"스킬 파일 생성 실패: {e}", exc_info=True)
        return False

    return filepath


def update_note_with_eval(filepath: str, eval_text: str):
    """Append evaluation result to the end of an Obsidian note file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if "## 평가" in content or "## Evaluation" in content:
            return

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(eval_text)
    except Exception as e:
        logger.error(f"평가 결과 저장 실패: {filepath} - {e}", exc_info=True)


def save_content_to_pool(title: str, content: str, source_url: str = "", tags: list[str] = None) -> str | bool:
    """분석 내용 자체를 팁 풀에 type:content로 저장한다.
    Returns: 저장된 파일 경로 또는 False (중복)
    """
    from datetime import datetime

    os.makedirs(TIPS_DIR, exist_ok=True)

    # 중복 체크: 동일 title의 content 파일이 이미 있는지
    for f in os.listdir(TIPS_DIR):
        if not f.endswith("_content.md"):
            continue
        try:
            with open(os.path.join(TIPS_DIR, f), "r", encoding="utf-8") as fp:
                existing = fp.read()
            if f'source: "{title}"' in existing:
                return False
        except Exception as e:
            logger.warning(f"내용 풀 중복 체크 실패: {f} - {e}")

    # 내용 2000자 제한
    truncated = content[:2000] + "\n...(truncated)" if len(content) > 2000 else content

    # 파일명 생성
    today = datetime.now().strftime("%Y%m%d")
    seq = 1
    while os.path.exists(os.path.join(TIPS_DIR, f"{today}_{seq:02d}_content.md")):
        seq += 1
    filename = f"{today}_{seq:02d}_content.md"
    filepath = os.path.join(TIPS_DIR, filename)

    # 태그 포맷
    tags_str = ", ".join(tags) if tags else ""

    file_content = (
        f"---\n"
        f'source: "{title}"\n'
        f'date: "{datetime.now().strftime("%Y-%m-%d")}"\n'
        f'type: "content"\n'
        f"tags: [{tags_str}]\n"
        f'url: "{source_url}"\n'
        f"applied: []\n"
        f"declined: []\n"
        f"---\n\n"
        f"## 핵심 내용\n"
        f"{truncated}\n"
    )
    if source_url:
        file_content += f"\n## 출처\n{source_url}\n"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(file_content)
        logger.info(f"내용 풀 저장: {filename} ({len(truncated)}자)")
        return filepath
    except Exception as e:
        logger.error(f"내용 풀 저장 실패: {filename} - {e}")
        return False


async def summarize_content_for_knowledge(title: str, content: str) -> str:
    """내용이 2000자 초과면 AI로 요약, 이하면 그대로 반환."""
    if len(content) <= 2000:
        return content

    from analyzer import _run_claude

    prompt = (
        "아래 분석 내용을 핵심만 추려 1500자 이내로 요약해줘. "
        "구체적인 수치, 도구명, 코드 패턴은 보존하고, 반복이나 부연은 제거해.\n\n"
        f"<content>\n{content[:4000]}\n</content>"
    )
    try:
        result = await _run_claude(prompt, allowed_tools="")
        return result[:2000]
    except Exception as e:
        logger.error(f"내용 요약 실패: {title} - {e}")
        return content[:2000] + "\n...(truncated)"


def append_content_to_claude_md(title: str, summary: str, source_url: str = "") -> bool:
    """분석 내용을 글로벌 CLAUDE.md의 '지식 반영' 섹션에 추가한다."""
    try:
        with open(CLAUDE_MD_PATH, "r", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""

    # 중복 체크
    if title in existing:
        return False

    # 요약을 5줄 이내로 축약
    lines = [l for l in summary.strip().split("\n") if l.strip()]
    short_summary = "\n".join(lines[:5])
    if len(lines) > 5:
        short_summary += "\n  ..."

    # 지식 반영 섹션 구성
    entry = f"- **{title}**: {short_summary}"
    if source_url:
        entry += f"\n  > 출처: {source_url}"

    section_header = "## 지식 반영 (자동 수집)"

    if section_header in existing:
        # 기존 섹션에 추가
        existing = existing.replace(section_header, f"{section_header}\n{entry}", 1)
    else:
        # 새 섹션 추가 (파일 끝)
        existing = existing.rstrip() + f"\n\n{section_header}\n{entry}\n"

    try:
        with open(CLAUDE_MD_PATH, "w", encoding="utf-8") as f:
            f.write(existing)
        logger.info(f"CLAUDE.md 지식 반영: {title}")
        return True
    except Exception as e:
        logger.error(f"CLAUDE.md 지식 반영 실패: {title} - {e}")
        return False
