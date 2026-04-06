import os
import re
import logging
import shutil
from datetime import datetime
from config import OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER

logger = logging.getLogger(__name__)


def get_existing_urls() -> set:
    """옵시디언 텔레그램 폴더 내 모든 노트의 URL을 수집한다."""
    folder_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)
    urls = set()
    if not os.path.exists(folder_path):
        return urls
    for f in os.listdir(folder_path):
        if not f.endswith(".md"):
            continue
        try:
            with open(os.path.join(folder_path, f), "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("url:"):
                        url = line.split("url:", 1)[1].strip().strip('"').strip("'")
                        if url:
                            urls.add(url)
                        break
                    if line.strip() == "---" and urls:
                        break
        except Exception as e:
            logger.warning(f"노트 URL 읽기 실패: {f} - {e}")
            continue
    return urls


def is_url_duplicate(url: str) -> bool:
    """해당 URL이 이미 옵시디언에 저장되어 있는지 확인한다."""
    if not url:
        return False
    return url in get_existing_urls()


def get_existing_notes_summary() -> list[dict]:
    """옵시디언 텔레그램 폴더 내 모든 노트의 제목 + 핵심 내용을 수집한다."""
    folder_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)
    notes = []
    if not os.path.exists(folder_path):
        return notes
    for f in sorted(os.listdir(folder_path)):
        if not f.endswith(".md"):
            continue
        try:
            filepath = os.path.join(folder_path, f)
            with open(filepath, "r", encoding="utf-8") as fh:
                content = fh.read()

            # 프론트매터에서 URL 추출
            url = ""
            url_match = re.search(r'url:\s*"(.+?)"', content)
            if url_match:
                url = url_match.group(1)

            # 프론트매터 이후 본문
            parts = content.split("---")
            body = "---".join(parts[2:]).strip() if len(parts) >= 3 else content

            # 제목 추출
            title = f.replace(".md", "")
            title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

            # 본문 앞부분 (평가 섹션 제외)
            body_preview = body.split("## 평가")[0].strip()[:300]

            notes.append({
                "filename": f,
                "filepath": filepath,
                "title": title,
                "url": url,
                "preview": body_preview,
            })
        except Exception as e:
            logger.warning(f"노트 요약 읽기 실패: {f} - {e}")
            continue
    return notes


def append_to_existing_note(filepath: str, new_content: str):
    """기존 노트에 새로운 내용을 추가한다."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 평가 섹션 앞에 삽입
        if "## 평가" in content:
            parts = content.split("## 평가", 1)
            updated = parts[0].rstrip() + f"\n\n---\n### 추가 정보\n{new_content}\n\n## 평가" + parts[1]
        else:
            updated = content.rstrip() + f"\n\n---\n### 추가 정보\n{new_content}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
        logger.info(f"노트 보강 완료: {filepath}")
    except Exception as e:
        logger.error(f"노트 보강 실패: {filepath} - {e}", exc_info=True)
        raise


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자를 제거한다."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    return name[:80] if name else "untitled"


def _format_original_section(original: str) -> str:
    """원본 콘텐츠를 옵시디언 접이식 callout으로 포맷한다."""
    if not original or not original.strip():
        return ""
    text = original.strip()
    if len(text) > 5000:
        text = text[:5000] + "\n...(truncated)"
    lines = text.split("\n")
    quoted = "\n".join(f"> {line}" for line in lines)
    return f"\n\n---\n> [!quote]- 원본 보기\n{quoted}\n"


def _format_my_thoughts_section(thoughts: str) -> str:
    """내 생각 섹션을 포맷한다. 전체 텍스트를 보존."""
    if not thoughts or not thoughts.strip():
        return ""
    return f"\n\n---\n## 💭 내 생각\n\n{thoughts.strip()}\n"


def save_note(title: str, content: str, source_url: str = "", source_type: str = "link", original_content: str = "", my_thoughts: str = "") -> str:
    """분석 결과를 옵시디언 마크다운 파일로 저장한다."""
    folder_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)
    os.makedirs(folder_path, exist_ok=True)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    safe_title = sanitize_filename(title) if title else f"note_{timestamp}"
    filename = f"{safe_title}.md"
    filepath = os.path.join(folder_path, filename)

    # 동일 파일명 충돌 방지
    counter = 1
    while os.path.exists(filepath):
        filename = f"{safe_title}_{counter}.md"
        filepath = os.path.join(folder_path, filename)
        counter += 1

    # 옵시디언 프론트매터 + 본문 구성
    tags_line = 'tags: [my-thought]\n' if my_thoughts else ''
    frontmatter = f"""---
created: {date_str} {time_str}
source: {source_type}
url: "{source_url}"
{tags_line}via: telegram-bot
---

"""

    header = f"# {title or 'Telegram Note'}\n\n"
    thoughts_section = _format_my_thoughts_section(my_thoughts)
    original_section = _format_original_section(original_content)
    full_content = frontmatter + header + content + thoughts_section + original_section + "\n"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)
        logger.info(f"노트 저장: {filepath}")
    except Exception as e:
        logger.error(f"노트 저장 실패: {filepath} - {e}", exc_info=True)
        raise

    return filepath


def copy_image_to_vault(image_path: str) -> str:
    """이미지를 옵시디언 vault의 첨부파일 폴더에 복사한다."""
    attachments_dir = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER, "attachments")
    os.makedirs(attachments_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(image_path)[1] or ".jpg"
    dest_name = f"img_{timestamp}{ext}"
    dest_path = os.path.join(attachments_dir, dest_name)

    try:
        shutil.copy2(image_path, dest_path)
        logger.info(f"이미지 복사: {image_path} -> {dest_path}")
    except Exception as e:
        logger.error(f"이미지 복사 실패: {image_path} - {e}", exc_info=True)
        raise
    return dest_path


def extract_keywords_from_content(content: str) -> list[str]:
    """콘텐츠에서 키워드를 추출한다. ### 키워드 섹션의 #태그 파싱."""
    # "### 키워드" 또는 "### Keywords" 섹션 찾기
    match = re.search(r'###\s*(?:키워드|Keywords)\s*\n(.*?)(?:\n###|\n---|\Z)', content, re.DOTALL)
    if not match:
        return []
    section = match.group(1)
    # #태그 형식 파싱 (예: #AI, #개발, #claude-code)
    tags = re.findall(r'#([\w가-힣-]+)', section)
    return [t.lower() for t in tags if len(t) > 1]


def find_related_notes(title: str, content: str, exclude_filename: str = "") -> list[dict]:
    """기존 노트와 제목+키워드 로컬 매칭으로 관련 노트를 찾는다. AI 호출 없음.
    Returns: [{"filename": str, "title": str, "score": int}] (상위 5개)
    """
    from difflib import SequenceMatcher

    existing = get_existing_notes_summary()
    new_keywords = set(extract_keywords_from_content(content))
    new_title_words = set(w.lower() for w in re.split(r'\s+', title) if len(w) > 1)

    scored = []
    for note in existing:
        if note["filename"] == exclude_filename:
            continue

        score = 0

        # 제목 단어 겹침
        note_title_words = set(w.lower() for w in re.split(r'\s+', note["title"]) if len(w) > 1)
        title_overlap = len(new_title_words & note_title_words)
        score += title_overlap * 2

        # 키워드 겹침
        note_keywords = set(extract_keywords_from_content(note.get("preview", "")))
        keyword_overlap = len(new_keywords & note_keywords)
        score += keyword_overlap * 3

        # 제목 유사도 (SequenceMatcher)
        ratio = SequenceMatcher(None, title.lower(), note["title"].lower()).ratio()
        if ratio > 0.4:
            score += int(ratio * 5)

        if score >= 2:
            scored.append({"filename": note["filename"], "title": note["title"], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]


def add_related_links(filepath: str, related_notes: list[dict]):
    """노트에 ## 관련 노트 섹션을 추가한다. 이미 있으면 스킵."""
    if not related_notes:
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"관련 노트 링크 추가 실패 (읽기): {filepath} - {e}")
        return

    # 이미 관련 노트 섹션이 있으면 스킵
    if "## 관련 노트" in content:
        return

    # 링크 섹션 구성
    links = "\n".join(f"- [[{n['title']}]]" for n in related_notes)
    section = f"\n\n## 관련 노트\n{links}\n"

    # 삽입 위치: ## 평가 앞, 없으면 원본 보기 앞, 없으면 파일 끝
    if "## 평가" in content:
        content = content.replace("## 평가", f"{section}\n## 평가", 1)
    elif "> [!quote]- 원본 보기" in content:
        content = content.replace("> [!quote]- 원본 보기", f"{section}\n> [!quote]- 원본 보기", 1)
    else:
        content += section

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"관련 노트 {len(related_notes)}개 링크 추가: {os.path.basename(filepath)}")
    except Exception as e:
        logger.warning(f"관련 노트 링크 추가 실패 (쓰기): {filepath} - {e}")

    # 역방향 링크 추가 (관련 노트 각각에 새 노트 링크 추가)
    new_note_title = ""
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if title_match:
        new_note_title = title_match.group(1).strip()

    if not new_note_title:
        return

    folder_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)
    for note in related_notes:
        note_path = os.path.join(folder_path, note["filename"])
        if not os.path.exists(note_path):
            continue
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                note_content = f.read()

            # 이미 이 노트에 대한 링크가 있으면 스킵
            if f"[[{new_note_title}]]" in note_content:
                continue

            # 관련 노트 섹션이 있으면 거기에 추가, 없으면 새로 생성
            new_link = f"- [[{new_note_title}]]"
            if "## 관련 노트" in note_content:
                # 기존 섹션의 마지막 줄 뒤에 추가
                note_content = note_content.replace("## 관련 노트\n", f"## 관련 노트\n{new_link}\n", 1)
            else:
                # 새 섹션 추가 (평가 앞)
                back_section = f"\n\n## 관련 노트\n{new_link}\n"
                if "## 평가" in note_content:
                    note_content = note_content.replace("## 평가", f"{back_section}\n## 평가", 1)
                else:
                    note_content += back_section

            with open(note_path, "w", encoding="utf-8") as f:
                f.write(note_content)
        except Exception as e:
            logger.warning(f"역방향 링크 추가 실패: {note['filename']} - {e}")
