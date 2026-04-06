import asyncio
import logging
import re
import sys
import subprocess

from config import ANALYSIS_ENGINE, CLAUDE_CMD, ANTHROPIC_API_KEY, ANTHROPIC_MODEL, OPENAI_API_KEY, OPENAI_MODEL, GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)
from prompts import get_prompts

_prompts = get_prompts()

LINK_ANALYSIS_PROMPT = _prompts["link_analysis"]
TEXT_ANALYSIS_PROMPT = _prompts["text_analysis"]
IMAGE_ANALYSIS_PROMPT = _prompts["image_analysis"]
GITHUB_ANALYSIS_PROMPT = _prompts["github_analysis"]
DEDUP_PROMPT = _prompts["dedup"]
FAIL_PATTERNS = _prompts["fail_patterns"]
META_PATTERNS = _prompts["meta_patterns"]

_YOUTUBE_PATTERN = re.compile(
    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/live/)'
)


def is_youtube_url(url: str) -> bool:
    """YouTube URL인지 판별한다."""
    return bool(_YOUTUBE_PATTERN.search(url))


def is_analysis_failed(text: str) -> bool:
    """Detect if analysis result is failed/incomplete."""
    if not text or len(text.strip()) < 30:
        return True
    for pattern in FAIL_PATTERNS:
        if pattern in text:
            return True
    return False


def clean_analysis(text: str) -> str:
    """Remove meta-commentary from analysis results."""
    for pattern in META_PATTERNS:
        text = re.sub(pattern, "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_title_from_analysis(text: str) -> str:
    """Extract 'Title: ...' or '제목: ...' line from analysis result."""
    match = re.search(r"^(?:제목|Title):\s*(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def remove_title_line(text: str) -> str:
    """Remove 'Title: ...' or '제목: ...' line from analysis result."""
    return re.sub(r"^(?:제목|Title):\s*.+\n*", "", text, count=1, flags=re.MULTILINE).strip()


# ── Engine implementations ──

async def _run_claude_cli(prompt: str, allowed_tools: str | None = "WebFetch,WebSearch,Read", timeout: int = 180) -> str:
    """Run analysis via Claude Code CLI (stdin pipe). 타임아웃 시 1회 재시도 (timeout 증가)."""
    cmd = [CLAUDE_CMD, "-p", "-"]
    if allowed_tools is not None:
        cmd += ["--allowedTools", allowed_tools]

    for attempt in range(2):
        current_timeout = timeout if attempt == 0 else timeout + 120
        logger.debug(f"Claude CLI 호출 (attempt={attempt + 1}, timeout={current_timeout}s, tools={allowed_tools or 'none'})")
        try:
            # Windows에서 콘솔 창 팝업 방지
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **kwargs,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode("utf-8")),
                timeout=current_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Claude CLI 타임아웃 ({current_timeout}초 초과, attempt={attempt + 1}), prompt={len(prompt)}자")
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            if attempt == 0:
                logger.info("Claude CLI 재시도 (타임아웃 증가)")
                continue
            logger.error(f"Claude CLI 최종 타임아웃 실패, prompt={len(prompt)}자")
            raise
        except Exception as e:
            logger.error(f"Claude CLI 프로세스 실행 실패: {e}", exc_info=True)
            raise

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error(f"Claude CLI 비정상 종료 (code={proc.returncode}): {error_msg}")
            raise RuntimeError(f"Claude CLI error: {error_msg}")

        result = stdout.decode("utf-8", errors="replace").strip()
        logger.debug(f"Claude CLI 응답 수신: {len(result)}자")
        return clean_analysis(result)


async def _run_anthropic_api(prompt: str) -> str:
    """Run analysis via Anthropic API directly."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        )

    logger.debug(f"Anthropic API 호출: model={ANTHROPIC_MODEL}")
    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.error(f"Anthropic API 호출 실패: {e}", exc_info=True)
        raise

    result = message.content[0].text
    logger.debug(f"Anthropic API 응답 수신: {len(result)}자")
    return clean_analysis(result)


async def _run_openai_api(prompt: str) -> str:
    """Run analysis via OpenAI API."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError(
            "openai package not installed. Run: pip install openai"
        )

    logger.debug(f"OpenAI API 호출: model={OPENAI_MODEL}")
    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
    except Exception as e:
        logger.error(f"OpenAI API 호출 실패: {e}", exc_info=True)
        raise

    result = response.choices[0].message.content
    logger.debug(f"OpenAI API 응답 수신: {len(result)}자")
    return clean_analysis(result)


async def _run_gemini_api(prompt: str, youtube_url: str = "") -> str:
    """Run analysis via Google Gemini API. YouTube URL은 Part.from_uri로 직접 전달."""
    try:
        from google import genai
        from google.genai.types import Part
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed. Run: pip install google-genai"
        )

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    logger.debug(f"Gemini API 호출: model={GEMINI_MODEL}, youtube={bool(youtube_url)}")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        if youtube_url:
            # YouTube URL을 Part.from_uri로 직접 전달 → 영상 오디오+시각 분석
            contents = [
                Part.from_uri(file_uri=youtube_url, mime_type="video/mp4"),
                prompt,
            ]
        else:
            contents = prompt

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=contents,
        )
    except Exception as e:
        logger.error(f"Gemini API 호출 실패: {e}", exc_info=True)
        raise

    result = response.text
    logger.debug(f"Gemini API 응답 수신: {len(result)}자")
    return clean_analysis(result)


async def _run_claude(prompt: str, allowed_tools: str | None = "WebFetch,WebSearch,Read") -> str:
    """Route to the configured analysis engine."""
    if ANALYSIS_ENGINE == "anthropic":
        return await _run_anthropic_api(prompt)
    elif ANALYSIS_ENGINE == "openai":
        return await _run_openai_api(prompt)
    else:
        return await _run_claude_cli(prompt, allowed_tools=allowed_tools)


# ── Dedup ──

async def check_duplicate_content(new_title: str, new_content: str, existing_notes: list[dict]) -> dict:
    """Check if new content duplicates existing notes.
    Returns: {"action": "new"/"skip"/"merge", "similar_file": str, "new_info": str}
    """
    if not existing_notes:
        return {"action": "new", "similar_file": "", "new_info": ""}

    notes_text = ""
    for n in existing_notes:
        notes_text += f"- File: {n['filename']}\n  Title: {n['title']}\n  Preview: {n['preview'][:150]}\n\n"

    if len(notes_text) > 3000:
        notes_text = notes_text[:3000] + "\n...(truncated)"

    new_preview = new_content[:500] if len(new_content) > 500 else new_content

    prompt = (
        f"{DEDUP_PROMPT}\n\n"
        f"<new_content>\nTitle: {new_title}\nContent:\n{new_preview}\n</new_content>\n\n"
        f"<existing_notes>\n{notes_text}\n</existing_notes>"
    )

    raw = await _run_claude(prompt, allowed_tools="")

    result = {"action": "new", "similar_file": "", "new_info": ""}

    for line in raw.split("\n"):
        line = line.strip()
        # Support both Korean and English output
        if line.startswith(("판정:", "Verdict:")):
            verdict = line.split(":", 1)[1].strip()
            if any(k in verdict for k in ("중복", "duplicate")):
                result["action"] = "skip"
            elif any(k in verdict for k in ("보강", "supplement")):
                result["action"] = "merge"
            else:
                result["action"] = "new"
        elif line.startswith(("유사노트:", "SimilarNote:")):
            val = line.split(":", 1)[1].strip()
            if val not in ("없음", "none"):
                result["similar_file"] = val
        elif line.startswith(("추가정보:", "AdditionalInfo:")):
            val = line.split(":", 1)[1].strip()
            if val not in ("없음", "none"):
                result["new_info"] = val

    return result


# ── Analysis functions ──

async def analyze_link(url: str, title: str, content: str) -> dict:
    """Analyze web page content.
    Returns: {"title": str, "content": str, "failed": bool}
    """
    if content and len(content.strip()) > 100:
        prompt = (
            f"{LINK_ANALYSIS_PROMPT}\n\n"
            f"<user_input>\n<url>{url}</url>\n<title>{title}</title>\n"
            f"<body>\n{content}\n</body>\n</user_input>"
        )
    else:
        prompt = (
            f"{LINK_ANALYSIS_PROMPT}\n\n"
            f"Fetch and analyze the content from this URL using the WebFetch tool:\n"
            f"<user_input><url>{url}</url></user_input>\n"
            f"Reference title: <user_input>{title}</user_input>"
        )

    result = await _run_claude(prompt)

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title or title, "content": body, "failed": False}


async def analyze_link_direct(url: str) -> dict:
    """Analyze URL directly via Claude (no scraping)."""
    prompt = (
        f"{LINK_ANALYSIS_PROMPT}\n\n"
        f"Fetch and analyze the content from this URL using the WebFetch tool:\n"
        f"<user_input><url>{url}</url></user_input>"
    )
    result = await _run_claude(prompt)

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title, "content": body, "failed": False}


async def analyze_text(text: str) -> dict:
    """Analyze plain text."""
    # 텍스트 길이 제한 (링크 분석과 동일한 6000자)
    truncated = text[:6000] + "\n...(truncated)" if len(text) > 6000 else text
    prompt = f"{TEXT_ANALYSIS_PROMPT}\n\n<user_input>\n{truncated}\n</user_input>"
    # 텍스트 분석은 내용이 이미 제공되므로 도구 불필요
    result = await _run_claude(prompt, allowed_tools="")

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    first_line = text.split("\n")[0][:30].strip()
    return {"title": ai_title or first_line or "Telegram Note", "content": body, "failed": False}


async def analyze_image(image_path: str, caption: str = "") -> dict:
    """Analyze an image."""
    normalized_path = image_path.replace("\\", "/")
    caption_part = f"\n<caption>{caption}</caption>" if caption else ""
    prompt = (
        f"{IMAGE_ANALYSIS_PROMPT}\n\n"
        f"Read and analyze this image file using the Read tool: {normalized_path}"
        f"{caption_part}"
    )
    result = await _run_claude(prompt, allowed_tools="Read")

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title or caption[:30] or "Image Analysis", "content": body, "failed": False}


async def analyze_youtube(url: str) -> dict:
    """Analyze YouTube video via Gemini API (Part.from_uri로 영상 직접 분석).
    Gemini 실패 시 Claude CLI로 폴백.
    Returns: {"title": str, "content": str, "failed": bool}
    """
    logger.info(f"YouTube Gemini 분석: {url}")
    prompt = LINK_ANALYSIS_PROMPT
    result = None

    # 1차: Gemini 시도
    if GEMINI_API_KEY:
        try:
            result = await _run_gemini_api(prompt, youtube_url=url)
        except Exception as e:
            logger.warning(f"YouTube Gemini 실패, Claude 폴백: {url} - {e}")

    # 2차: Gemini 실패 또는 미설정 시 Claude CLI 직접 분석
    if not result or is_analysis_failed(result):
        logger.info(f"YouTube Claude 폴백 분석: {url}")
        try:
            return await analyze_link_direct(url)
        except Exception as e:
            logger.error(f"YouTube 분석 최종 실패: {url} - {e}", exc_info=True)
            return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    return {"title": ai_title or "YouTube", "content": body, "failed": False}


async def analyze_github(url: str) -> dict:
    """GitHub 저장소를 분석한다. API로 메타데이터+README 취득 후 Claude 분석.
    Returns: {"title": str, "content": str, "failed": bool}
    """
    from scraper import fetch_github_repo

    logger.info(f"GitHub 저장소 분석: {url}")
    repo_data = await fetch_github_repo(url)

    if repo_data["error"] and not repo_data["readme_content"]:
        logger.warning(f"GitHub fetch 실패, 직접 분석 폴백: {url}")
        return await analyze_link_direct(url)

    # 메타데이터 + README를 프롬프트에 조합
    meta_parts = [f"- URL: {url}"]
    if repo_data["description"]:
        meta_parts.append(f"- Description: {repo_data['description']}")
    if repo_data["language"]:
        meta_parts.append(f"- Language: {repo_data['language']}")
    if repo_data["stars"]:
        meta_parts.append(f"- Stars: {repo_data['stars']:,} | Forks: {repo_data['forks']:,}")
    if repo_data["topics"]:
        meta_parts.append(f"- Topics: {', '.join(repo_data['topics'])}")
    if repo_data["license"]:
        meta_parts.append(f"- License: {repo_data['license']}")

    meta_section = "\n".join(meta_parts)
    readme = repo_data["readme_content"] or "(README not available)"

    prompt = (
        f"{GITHUB_ANALYSIS_PROMPT}\n\n"
        f"<user_input>\n## Repository Information\n{meta_section}\n\n"
        f"## README\n{readme}\n</user_input>"
    )

    result = await _run_claude(prompt, allowed_tools="")

    if is_analysis_failed(result):
        return {"title": "", "content": "", "failed": True}

    ai_title = extract_title_from_analysis(result)
    body = remove_title_line(result)
    repo_name = f"{repo_data['owner']}/{repo_data['repo']}"
    return {"title": ai_title or repo_name, "content": body, "failed": False}
