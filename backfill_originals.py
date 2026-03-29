"""기존 옵시디언 노트에 원본 콘텐츠를 소급 추가하는 스크립트.

URL이 있는 노트: 재스크래핑하여 원본 추가
텍스트 노트: 원본 복구 불가 (스킵)
"""

import asyncio
import os
import re
import sys

from config import OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER
from scraper import fetch_page_content


def get_notes_without_original() -> list[dict]:
    """원본 섹션이 없는 노트 목록을 반환한다."""
    folder_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)
    notes = []

    if not os.path.exists(folder_path):
        return notes

    for f in sorted(os.listdir(folder_path)):
        if not f.endswith(".md"):
            continue

        filepath = os.path.join(folder_path, f)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                content = fh.read()

            # 이미 원본 섹션이 있으면 스킵
            if "[!quote]- 원본 보기" in content:
                continue

            # URL 추출
            url_match = re.search(r'url:\s*"(.+?)"', content)
            url = url_match.group(1) if url_match else ""

            # source 타입 추출
            source_match = re.search(r'source:\s*(\S+)', content)
            source = source_match.group(1) if source_match else ""

            if not url:
                continue  # URL 없는 텍스트 노트는 원본 복구 불가

            notes.append({
                "filename": f,
                "filepath": filepath,
                "url": url,
                "source": source,
                "content": content,
            })
        except Exception:
            continue

    return notes


def insert_original_section(filepath: str, content: str, original: str):
    """노트에 원본 섹션을 삽입한다. 평가 섹션 앞에 넣는다."""
    if not original or not original.strip():
        return False

    text = original.strip()
    if len(text) > 5000:
        text = text[:5000] + "\n...(truncated)"

    lines = text.split("\n")
    quoted = "\n".join(f"> {line}" for line in lines)
    original_section = f"\n---\n> [!quote]- 원본 보기\n{quoted}\n"

    # 평가 섹션 앞에 삽입
    if "## 평가" in content:
        parts = content.split("\n---\n## 평가", 1)
        updated = parts[0].rstrip() + "\n" + original_section + "\n---\n## 평가" + parts[1]
    else:
        updated = content.rstrip() + "\n" + original_section

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(updated)

    return True


async def backfill():
    notes = get_notes_without_original()
    total = len(notes)

    if total == 0:
        print("원본이 없는 URL 노트가 없습니다.")
        return

    print(f"원본 추가 대상: {total}개 노트")

    success = 0
    failed = 0

    for i, note in enumerate(notes, 1):
        print(f"[{i}/{total}] {note['filename']} - {note['url'][:60]}...")

        try:
            page = await fetch_page_content(note["url"])

            if page["error"] or len(page.get("content", "").strip()) < 50:
                print(f"  -> 스크래핑 실패: {page.get('error', '내용 부족')}")
                failed += 1
                continue

            if insert_original_section(note["filepath"], note["content"], page["content"]):
                print(f"  -> 원본 추가 완료")
                success += 1
            else:
                print(f"  -> 원본 내용 없음, 스킵")
                failed += 1

        except Exception as e:
            print(f"  -> 오류: {e}")
            failed += 1

    print(f"\n--- 완료: 성공 {success}개, 실패 {failed}개 ---")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(backfill())
