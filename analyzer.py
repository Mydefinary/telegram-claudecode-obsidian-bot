import asyncio
import re
import os


LINK_ANALYSIS_PROMPT = """\
당신은 콘텐츠 분석가입니다. 아래 웹페이지 내용을 분석하여 옵시디언 마크다운 노트를 작성하세요.

## 출력 형식 (반드시 이 형식을 따르세요):

제목: (내용을 한눈에 파악할 수 있는 구체적 제목, 15자 이내)

### 한줄 요약
(핵심 내용을 한 문장으로)

### 주요 내용
(핵심 포인트를 불릿으로 3-7개)

### 키워드
(관련 키워드를 쉼표로 구분, 5개 이내)

### 인사이트
(이 콘텐츠에서 얻을 수 있는 핵심 인사이트 1-2문장)

---
규칙:
- 한국어로 작성
- 간결하고 핵심만
- 옵시디언 태그 형식으로 키워드 제공 (예: #AI #개발)
- 분석 과정 설명이나 메타 코멘트 절대 포함하지 마세요 (예: "분석 결과를 작성합니다", "충분한 정보를 확보했습니다" 등)
- 오직 분석 결과만 출력하세요
"""

TEXT_ANALYSIS_PROMPT = """\
당신은 메모 정리 전문가입니다. 아래 텍스트를 분석하여 옵시디언 마크다운 노트로 정리하세요.

## 출력 형식:

제목: (내용을 한눈에 파악할 수 있는 구체적 제목, 15자 이내)

### 요약
(핵심 내용 정리)

### 키워드
(관련 태그, 옵시디언 형식 #태그)

---
규칙:
- 한국어로 작성
- 간결하고 핵심만
- 분석 과정 설명이나 메타 코멘트 절대 포함하지 마세요
- 오직 분석 결과만 출력하세요
"""


CLAUDE_CMD = r"C:\Users\hoa\AppData\Roaming\npm\claude.cmd"

# 분석 실패를 감지하는 패턴들
FAIL_PATTERNS = [
    "권한이 필요합니다",
    "승인해주시겠어요",
    "콘텐츠를 가져올 수 없",
    "접근이 차단",
    "403",
    "로그인이 필요",
    "본문을 직접 복사",
    "URL을 알고 계시면",
    "어떤 방법이 편하신가요",
    "분석할 웹페이지 URL이나 내용을 제공",
    "분석해야 하는지 알려주",
    "콘텐츠를 제공해",
]

# 분석 결과에서 제거할 메타 코멘트 패턴
META_PATTERNS = [
    r"이제 충분한 정보를 확보했습니다\.?\s*분석 결과를 작성합니다\.?",
    r"분석 결과를 작성하겠습니다\.?",
    r"분석을 시작하겠습니다\.?",
    r"다음과 같이 분석했습니다\.?",
    r"아래와 같이 정리했습니다\.?",
    r"WebFetch.*?가져와.*?\n",
    r"WebSearch.*?검색.*?\n",
]


def is_analysis_failed(text: str) -> bool:
    """분석 결과가 실패/불완전한지 판별한다."""
    if not text or len(text.strip()) < 30:
        return True
    for pattern in FAIL_PATTERNS:
        if pattern in text:
            return True
    return False


def clean_analysis(text: str) -> str:
    """분석 결과에서 메타 코멘트를 제거한다."""
    for pattern in META_PATTERNS:
        text = re.sub(pattern, "", text)
    # 연속 빈 줄 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


DEDUP_PROMPT = """\
당신은 콘텐츠 중복 판별 전문가입니다.

아래에 [새 콘텐츠]와 [기존 노트 목록]이 있습니다.
새 콘텐츠가 기존 노트 중 하나와 주제/내용이 실질적으로 겹치는지 판별하세요.

## 출력 형식 (반드시 따르세요):

판정: 신규/중복/보강
유사노트: (유사한 기존 노트 파일명. 없으면 "없음")
추가정보: (기존 노트에 없는 새로운 핵심 정보만 간결하게. 없으면 "없음")

---
규칙:
- 신규: 기존 노트와 겹치는 내용이 없음 → 새 노트로 저장
- 중복: 기존 노트와 거의 동일한 내용 → 저장하지 않음
- 보강: 같은 주제지만 기존 노트에 없는 중요한 정보가 있음 → 기존 노트에 추가
- URL이 다르더라도 내용이 같으면 중복
- 메타 코멘트 없이 결과만 출력
"""


async def check_duplicate_content(new_title: str, new_content: str, existing_notes: list[dict]) -> dict:
    """새 콘텐츠가 기존 노트와 중복되는지 확인한다.
    Returns: {"action": "new"/"skip"/"merge", "similar_file": str, "new_info": str}
    """
    if not existing_notes:
        return {"action": "new", "similar_file": "", "new_info": ""}

    # 기존 노트 목록을 텍스트로 구성 (가벼운 요약만)
    notes_text = ""
    for n in existing_notes:
        notes_text += f"- 파일: {n['filename']}\n  제목: {n['title']}\n  미리보기: {n['preview'][:150]}\n\n"

    # 너무 길면 잘라냄
    if len(notes_text) > 3000:
        notes_text = notes_text[:3000] + "\n...(truncated)"

    new_preview = new_content[:500] if len(new_content) > 500 else new_content

    prompt = (
        f"{DEDUP_PROMPT}\n\n"
        f"[새 콘텐츠]\n제목: {new_title}\n내용:\n{new_preview}\n\n"
        f"[기존 노트 목록]\n{notes_text}"
    )

    raw = await _run_claude(prompt)

    result = {"action": "new", "similar_file": "", "new_info": ""}

    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("판정:"):
            verdict = line.split(":", 1)[1].strip()
            if "중복" in verdict:
                result["action"] = "skip"
            elif "보강" in verdict:
                result["action"] = "merge"
            else:
                result["action"] = "new"
        elif line.startswith("유사노트:"):
            val = line.split(":", 1)[1].strip()
            if val != "없음":
                result["similar_file"] = val
        elif line.startswith("추가정보:"):
            val = line.split(":", 1)[1].strip()
            if val != "없음":
                result["new_info"] = val

    return result


def extract_title_from_analysis(text: str) -> str:
    """분석 결과에서 '제목: ...' 행을 추출하고 본문에서 제거한다."""
    match = re.search(r"^제목:\s*(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def remove_title_line(text: str) -> str:
    """분석 결과에서 '제목: ...' 행을 제거한다."""
    return re.sub(r"^제목:\s*.+\n*", "", text, count=1, flags=re.MULTILINE).strip()


async def _run_claude(prompt: str) -> str:
    """Claude Code CLI를 호출하여 분석 결과를 반환한다."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_CMD, "-p", "-",
        "--allowedTools", "WebFetch,WebSearch,Read",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(input=prompt.encode("utf-8")),
        timeout=180,
    )

    if proc.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Claude CLI 오류: {error_msg}")

    result = stdout.decode("utf-8", errors="replace").strip()
    return clean_analysis(result)


async def analyze_link(url: str, title: str, content: str) -> dict:
    """웹페이지 내용을 Claude Code로 분석한다.
    Returns: {"title": str, "content": str, "failed": bool}
    """
    if content and len(content.strip()) > 100:
        prompt = (
            f"{LINK_ANALYSIS_PROMPT}\n\n"
            f"URL: {url}\n제목: {title}\n\n본문:\n{content}"
        )
    else:
        prompt = (
            f"{LINK_ANALYSIS_PROMPT}\n\n"
            f"다음 URL의 콘텐츠를 WebFetch 도구로 직접 가져와서 분석해주세요: {url}\n"
            f"제목(참고): {title}"
        )

    result = await _run_claude(prompt)

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title or title, "content": body, "failed": False}


async def analyze_link_direct(url: str) -> dict:
    """스크래핑 없이 Claude Code가 직접 URL을 읽어서 분석한다."""
    prompt = (
        f"{LINK_ANALYSIS_PROMPT}\n\n"
        f"다음 URL의 콘텐츠를 WebFetch 도구로 직접 가져와서 분석해주세요: {url}"
    )
    result = await _run_claude(prompt)

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title, "content": body, "failed": False}


async def analyze_text(text: str) -> dict:
    """일반 텍스트를 Claude Code로 분석/정리한다."""
    prompt = f"{TEXT_ANALYSIS_PROMPT}\n\n{text}"
    result = await _run_claude(prompt)

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    first_line = text.split("\n")[0][:30].strip()
    return {"title": ai_title or first_line or "텔레그램 메모", "content": body, "failed": False}


IMAGE_ANALYSIS_PROMPT = """\
당신은 이미지 분석 전문가입니다. 이미지를 분석하여 옵시디언 마크다운 노트를 작성하세요.

## 출력 형식 (반드시 이 형식을 따르세요):

제목: (내용을 한눈에 파악할 수 있는 구체적 제목, 15자 이내)

### 이미지 설명
(이미지에 무엇이 있는지 상세 설명)

### 핵심 내용
(이미지에서 읽을 수 있는 텍스트, 도표, 데이터 등을 정리)

### 키워드
(관련 태그, 옵시디언 형식 #태그)

### 인사이트
(이 이미지에서 얻을 수 있는 핵심 정보 1-2문장)

---
규칙:
- 한국어로 작성
- 이미지에 텍스트가 있으면 반드시 추출하여 포함
- 간결하고 핵심만
- 분석 과정 설명이나 메타 코멘트 절대 포함하지 마세요
"""


async def analyze_image(image_path: str, caption: str = "") -> dict:
    """이미지를 Claude Code로 분석한다."""
    normalized_path = image_path.replace("\\", "/")
    caption_part = f"\n사용자 캡션: {caption}" if caption else ""
    prompt = (
        f"{IMAGE_ANALYSIS_PROMPT}\n\n"
        f"다음 이미지 파일을 Read 도구로 읽어서 분석해주세요: {normalized_path}"
        f"{caption_part}"
    )
    result = await _run_claude(prompt)

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title or caption[:30] or "이미지 분석", "content": body, "failed": False}
