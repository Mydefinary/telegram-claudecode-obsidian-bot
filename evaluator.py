"""저장된 옵시디언 노트를 평가하고, Claude Code 적용 가능한 내용은 글로벌 설정에 반영한다."""

import os
import re
from analyzer import _run_claude

CLAUDE_MD_PATH = os.path.expanduser("~/.claude/CLAUDE.md")
COMMANDS_DIR = os.path.expanduser("~/.claude/commands")
TIPS_DIR = os.path.expanduser("~/.claude/tips")

EVAL_PROMPT = """\
당신은 기술 콘텐츠 평가 전문가입니다. 아래 노트를 평가하세요.

## 평가 항목 (각 1-5점):

1. **최신성**: 2025-2026년 기준 최신 정보인가? (오래된 정보면 1점, 최신 트렌드면 5점)
2. **실용성**: 실무에 바로 적용 가능한 구체적 내용인가? (이론만이면 1점, 코드/설정/워크플로우 포함이면 5점)
3. **신뢰도**: 정보의 출처와 검증 수준이 높은가? (미검증/추측이면 1점, 공식 문서/저명 전문가면 5점)
4. **깊이**: 인사이트의 깊이가 있는가? (표면적 소개면 1점, 경험 기반 심화 분석이면 5점)
5. **개발자 적합성**: 개발자/PM/AI 산업 종사자에게 유용한가? (무관하면 1점, 핵심 실무면 5점)
6. **Claude Code 적용성**: Claude Code 사용 시 적용할 수 있는 팁/설정/워크플로우가 있는가? (없으면 1점, 바로 적용 가능하면 5점)

## 출력 형식 (반드시 이 형식을 따르세요):

최신성: N
실용성: N
신뢰도: N
깊이: N
개발자적합성: N
클코적용성: N
종합등급: A/B/C/D
한줄평: (이 노트의 가치를 한 문장으로)
클코팁: (Claude Code에 적용할 수 있는 구체적 팁이 있으면 작성. 없으면 "없음")
팁설명: (클코팁이 있을 경우, 이 팁이 무엇이고 왜 유용한지 1-2문장으로 설명. 없으면 "없음")
처리유형: (클코팁이 있을 경우 global/skill/풀/저장 중 하나. 없으면 "없음")
권장도: (처리유형에 대한 확신도 1-5. 5=강력 권장, 3=보통, 1=약한 권장. 없으면 0)
유형근거: (처리유형 판정 이유를 한 문장으로. 없으면 "없음")
스킬명: (클코팁이 있을 경우, 슬래시 커맨드로 만들 때의 이름. 영문 소문자+하이픈. 없으면 "없음")
태그: (클코팁이 있을 경우, 관련 기술 키워드를 쉼표로 구분. 3-7개. 없으면 "없음")

---
규칙:
- 점수는 반드시 1-5 사이 정수
- 종합등급: A(25점 이상), B(19-24점), C(13-18점), D(12점 이하) [총 30점 만점, 6항목]
- 클코팁은 Claude Code 사용자가 바로 실행할 수 있는 구체적이고 간결한 지침으로 작성
- 예: "CLAUDE.md에 멀티에이전트 기본 활용 지시 추가", "plan 모드에서 먼저 설계 후 개발 진행"
- 이미 널리 알려진 기본 기능(예: /help, /clear)은 팁으로 포함하지 마세요
- 처리유형 기준:
  - global: 모든 프로젝트에 항상 적용되는 범용 규칙/원칙 (예: 에이전트 운영 원칙, 코드 리뷰 기준)
  - skill: 필요할 때 호출하는 워크플로우/절차/프로세스 (예: TDD 파이프라인, QA 검증, 설계 리뷰)
  - 풀: 특정 기술/프레임워크/상황에 유용한 팁 → 팁 풀에 저장 후 /apply-tips로 프로젝트별 매칭 적용
  - 저장: 개발과 무관하거나 일반 지식 → 옵시디언에만 보관
- 권장도 기준: 5=해당 유형이 확실히 최적, 4=높은 확신, 3=보통, 2=애매함, 1=소극적 권장
- 스킬명은 영문 소문자와 하이픈만 사용 (예: qa-review, tdd-workflow)
- 태그는 영문 소문자와 하이픈만 사용. 공식 패키지명이나 널리 통용되는 약칭 사용 (예: python, react, async, multi-agent, claude-code, testing, git)
- 메타 코멘트나 분석 과정 설명 없이 결과만 출력
"""


def parse_eval_result(text: str) -> dict:
    """평가 결과를 파싱한다."""
    result = {
        "freshness": 0,
        "practicality": 0,
        "reliability": 0,
        "depth": 0,
        "relevance": 0,
        "claude_code": 0,
        "grade": "D",
        "summary": "",
        "tip": "",
        "tip_desc": "",
        "tip_action": "",
        "tip_confidence": 0,
        "tip_action_reason": "",
        "skill_name": "",
        "tags": [],
    }

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("최신성:"):
            try:
                result["freshness"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("실용성:"):
            try:
                result["practicality"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("신뢰도:"):
            try:
                result["reliability"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("깊이:"):
            try:
                result["depth"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("개발자적합성:"):
            try:
                result["relevance"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("클코적용성:"):
            try:
                result["claude_code"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("종합등급:"):
            result["grade"] = line.split(":", 1)[1].strip()[:1]
        elif line.startswith("한줄평:"):
            result["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("클코팁:"):
            result["tip"] = line.split(":", 1)[1].strip()
        elif line.startswith("팁설명:"):
            result["tip_desc"] = line.split(":", 1)[1].strip()
        elif line.startswith("처리유형:"):
            result["tip_action"] = line.split(":", 1)[1].strip()
        elif line.startswith("권장도:"):
            try:
                result["tip_confidence"] = int(re.search(r"\d", line).group())
            except:
                pass
        elif line.startswith("유형근거:"):
            result["tip_action_reason"] = line.split(":", 1)[1].strip()
        elif line.startswith("스킬명:"):
            result["skill_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("태그:"):
            raw_tags = line.split(":", 1)[1].strip()
            if raw_tags and raw_tags != "없음":
                result["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]

    return result


async def evaluate_note(title: str, content: str, url: str = "") -> dict:
    """노트를 평가한다."""
    note_text = f"제목: {title}\nURL: {url}\n\n{content}"
    # 너무 긴 내용은 앞부분만
    if len(note_text) > 4000:
        note_text = note_text[:4000] + "\n...(truncated)"

    prompt = f"{EVAL_PROMPT}\n\n--- 평가 대상 노트 ---\n{note_text}"
    raw = await _run_claude(prompt)
    return parse_eval_result(raw)


def format_eval_tags(result: dict) -> str:
    """평가 결과를 옵시디언 노트에 추가할 텍스트로 포맷한다."""
    total = (result['freshness'] + result['practicality'] + result['reliability']
             + result['depth'] + result['relevance'] + result['claude_code'])
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
    """Claude Code 팁을 글로벌 CLAUDE.md에 추가한다. 중복 방지."""
    if not tip or tip == "없음":
        return False

    # 기존 내용 읽기
    content = ""
    if os.path.exists(CLAUDE_MD_PATH):
        with open(CLAUDE_MD_PATH, "r", encoding="utf-8") as f:
            content = f.read()

    # 중복 체크 (동일 팁이 이미 있으면 스킵)
    if tip in content:
        return False

    # 섹션이 없으면 추가
    section_header = "## Claude Code 팁 (자동 수집)"
    if section_header not in content:
        content += f"\n\n{section_header}\n"

    # 팁 추가
    content += f"- {tip} (출처: {source_title})\n"

    with open(CLAUDE_MD_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    return True


def save_tip_to_pool(tip: str, tip_desc: str, source_title: str, skill_name: str = "", tags: list[str] = None):
    """팁을 풀에 저장한다. 나중에 /apply-tips로 프로젝트에 매칭.
    Returns: 생성된 파일 경로 또는 False
    """
    if not tip or tip == "없음":
        return False

    os.makedirs(TIPS_DIR, exist_ok=True)

    # 중복 체크
    for f in os.listdir(TIPS_DIR):
        if not f.endswith(".md"):
            continue
        try:
            with open(os.path.join(TIPS_DIR, f), "r", encoding="utf-8") as fh:
                if tip in fh.read():
                    return False
        except Exception:
            continue

    # 파일명: 날짜_순번.md
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
    if tip_desc and tip_desc != "없음":
        lines.extend(["", "## 설명", tip_desc])
    if skill_name and skill_name != "없음":
        lines.extend(["", "## 관련 스킬명", skill_name])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def create_skill(skill_name: str, tip: str, tip_desc: str, source_title: str):
    """Claude Code 슬래시 커맨드(스킬)를 생성한다.
    Returns: 생성된 파일 경로 또는 False
    """
    if not skill_name or skill_name == "없음":
        return False

    os.makedirs(COMMANDS_DIR, exist_ok=True)

    safe_name = skill_name.strip().replace(" ", "-").lower()
    filepath = os.path.join(COMMANDS_DIR, f"{safe_name}.md")

    # 이미 존재하면 스킵
    if os.path.exists(filepath):
        return False

    # 스킬 프롬프트 구성
    lines = [tip]
    if tip_desc and tip_desc != "없음":
        lines.append(f"\n## 배경\n{tip_desc}")
    lines.append(f"\n---\n> 출처: {source_title}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def update_note_with_eval(filepath: str, eval_text: str):
    """옵시디언 노트 파일 끝에 평가 결과를 추가한다."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 이미 평가가 있으면 스킵
    if "## 평가" in content:
        return

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(eval_text)
