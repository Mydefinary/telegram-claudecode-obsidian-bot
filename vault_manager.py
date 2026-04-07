"""
볼트 관리: 중복 스캔, 통합, 저품질 노트 정리
/cleanup 명령으로 수동 실행
"""

import os
import re
import shutil
import logging
from difflib import SequenceMatcher

from config import OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER
from obsidian_writer import get_existing_notes_summary, append_to_existing_note

logger = logging.getLogger(__name__)


def _get_folder_path() -> str:
    return os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)


def _get_archive_path() -> str:
    path = os.path.join(_get_folder_path(), "_archive")
    os.makedirs(path, exist_ok=True)
    return path


def _read_note_content(filepath: str) -> str:
    """노트 전체 내용을 읽는다."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"노트 읽기 실패: {filepath} - {e}")
        return ""


def _extract_grade_and_score(content: str) -> tuple[str, int]:
    """노트 내용에서 평가 등급과 총점을 추출한다."""
    grade = ""
    total = 0

    grade_match = re.search(r'종합등급:\s*([A-D])', content)
    if grade_match:
        grade = grade_match.group(1)

    # 각 항목 점수 합산
    for field in ['최신성', '실용성', '신뢰도', '깊이', '개발자', '클코적용성', 'Freshness', 'Practicality', 'Reliability', 'Depth', 'Dev', 'Claude']:
        match = re.search(rf'{field}[^:]*:\s*⭐*\s*\((\d)/5\)', content)
        if match:
            total += int(match.group(1))

    return grade, total


async def scan_vault_duplicates() -> list[dict]:
    """볼트에서 제목 유사도가 높은 노트 쌍을 찾는다.
    Returns: [{"note_a": dict, "note_b": dict, "similarity": float}]
    """
    notes = get_existing_notes_summary()
    if len(notes) < 2:
        return []

    pairs = []
    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            a, b = notes[i], notes[j]
            ratio = SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio()
            if ratio > 0.6:
                pairs.append({
                    "note_a": a,
                    "note_b": b,
                    "similarity": round(ratio, 2),
                })

    pairs.sort(key=lambda x: x["similarity"], reverse=True)
    logger.info(f"중복 스캔 완료: {len(notes)}개 노트, {len(pairs)}개 유사 쌍 발견")
    return pairs


async def scan_and_merge_duplicates() -> dict:
    """중복 스캔 후 AI로 확인하여 통합한다.
    Returns: {"scanned": int, "merged": int, "details": [str]}
    """
    from analyzer import check_duplicate_content

    pairs = await scan_vault_duplicates()
    result = {"scanned": len(pairs), "merged": 0, "details": []}

    for pair in pairs:
        a = pair["note_a"]
        b = pair["note_b"]

        # AI로 중복 확인
        a_content = _read_note_content(a["filepath"])
        b_content = _read_note_content(b["filepath"])

        if not a_content or not b_content:
            continue

        # a를 기존, b를 신규로 비교
        dedup = await check_duplicate_content(b["title"], b["preview"], [a])

        if dedup["action"] == "skip":
            # 완전 중복 → b를 아카이브
            merge_duplicate_notes(a["filepath"], b["filepath"])
            result["merged"] += 1
            result["details"].append(f"[통합] {b['filename']} → {a['filename']} (유사도: {pair['similarity']})")
        elif dedup["action"] == "merge":
            # 보강 → b의 고유 내용을 a에 추가 후 아카이브
            new_info = dedup.get("new_info", "")
            if new_info:
                append_to_existing_note(a["filepath"], new_info)
            merge_duplicate_notes(a["filepath"], b["filepath"])
            result["merged"] += 1
            result["details"].append(f"[보강통합] {b['filename']} → {a['filename']}")

    logger.info(f"중복 통합 완료: {result['merged']}개 통합")
    return result


def merge_duplicate_notes(primary_path: str, secondary_path: str):
    """secondary 노트를 _archive/로 이동한다."""
    archive = _get_archive_path()
    filename = os.path.basename(secondary_path)
    dest = os.path.join(archive, filename)

    # 파일명 충돌 방지
    counter = 1
    while os.path.exists(dest):
        name, ext = os.path.splitext(filename)
        dest = os.path.join(archive, f"{name}_{counter}{ext}")
        counter += 1

    try:
        shutil.move(secondary_path, dest)
        logger.info(f"노트 아카이브: {filename} → _archive/")
    except Exception as e:
        logger.error(f"노트 아카이브 실패: {filename} - {e}")


def find_cleanup_candidates() -> list[dict]:
    """불필요한 노트 후보를 찾는다 (재귀 스캔).
    기준: 본문 50자 미만, 또는 등급 D + 총점 8점 이하
    Returns: [{"filepath": str, "filename": str, "reason": str}]
    """
    folder_path = _get_folder_path()
    if not os.path.exists(folder_path):
        return []

    SKIP_DIRS = {"_archive", "attachments", ".obsidian", ".trash", "_templates"}
    candidates = []

    md_files = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                md_files.append((root, f))

    for root, f in sorted(md_files, key=lambda x: x[1]):
        filepath = os.path.join(root, f)
        content = _read_note_content(filepath)
        if not content:
            continue

        # 프론트매터 이후의 본문 길이 체크
        body = content
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                body = content[end + 3:].strip()

        # ## 평가 제거 후 순수 본문 길이
        eval_pos = body.find("## 평가")
        if eval_pos != -1:
            body = body[:eval_pos].strip()

        # 원본 보기 제거
        orig_pos = body.find("> [!quote]- 원본 보기")
        if orig_pos != -1:
            body = body[:orig_pos].strip()

        # 제목 헤더 제거
        body = re.sub(r'^#\s+.+\n*', '', body).strip()

        if len(body) < 50:
            candidates.append({"filepath": filepath, "filename": f, "reason": f"본문 부족 ({len(body)}자)"})
            continue

        # 등급 D + 총점 8 이하
        grade, total = _extract_grade_and_score(content)
        if grade == "D" and total > 0 and total <= 8:
            candidates.append({"filepath": filepath, "filename": f, "reason": f"저품질 (등급 {grade}, {total}점)"})

    logger.info(f"정리 후보: {len(candidates)}개 노트")
    return candidates


def cleanup_notes(candidates: list[dict]) -> dict:
    """정리 후보 노트를 _archive/로 이동한다.
    Returns: {"moved": int, "errors": int}
    """
    result = {"moved": 0, "errors": 0}

    for c in candidates:
        try:
            merge_duplicate_notes("", c["filepath"])  # primary 불필요, secondary만 이동
            result["moved"] += 1
        except Exception as e:
            logger.error(f"정리 실패: {c['filename']} - {e}")
            result["errors"] += 1

    logger.info(f"정리 완료: {result['moved']}개 이동, {result['errors']}개 실패")
    return result
