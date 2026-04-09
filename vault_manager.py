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
    """볼트에서 중복 의심 노트 쌍을 찾는다.

    감지 기준 (둘 중 하나라도 충족):
    - 제목 유사도(SequenceMatcher) > 0.6
    - 키워드 Jaccard 유사도 > 0.5 (3개 이상 겹침)

    Returns: [{"note_a": dict, "note_b": dict, "similarity": float, "reason": str}]
    """
    notes = get_existing_notes_summary()
    if len(notes) < 2:
        return []

    pairs = []
    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            a, b = notes[i], notes[j]
            title_ratio = SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio()

            a_kw = set(k.lower() for k in a.get("keywords", []))
            b_kw = set(k.lower() for k in b.get("keywords", []))
            kw_jaccard = 0.0
            kw_overlap = 0
            if a_kw and b_kw:
                kw_overlap = len(a_kw & b_kw)
                kw_jaccard = kw_overlap / len(a_kw | b_kw)

            # 후보 판정
            if title_ratio > 0.6:
                pairs.append({
                    "note_a": a,
                    "note_b": b,
                    "similarity": round(title_ratio, 2),
                    "reason": f"제목 유사 {title_ratio:.2f}",
                })
            elif kw_jaccard > 0.5 and kw_overlap >= 3:
                pairs.append({
                    "note_a": a,
                    "note_b": b,
                    "similarity": round(kw_jaccard, 2),
                    "reason": f"키워드 {kw_overlap}개 일치 ({kw_jaccard:.2f})",
                })

    pairs.sort(key=lambda x: x["similarity"], reverse=True)
    logger.info(f"중복 스캔 완료: {len(notes)}개 노트, {len(pairs)}개 유사 쌍 발견")
    return pairs


async def scan_and_merge_duplicates(max_pairs: int = 0) -> dict:
    """중복 스캔 후 AI로 확인하여 통합한다.
    Args:
        max_pairs: 처리할 최대 쌍 수 (0=무제한). 유사도 높은 순서로 처리.
    Returns: {"scanned": int, "merged": int, "skipped": int, "details": [str]}
    """
    from analyzer import check_duplicate_content

    pairs = await scan_vault_duplicates()
    if max_pairs > 0:
        pairs = pairs[:max_pairs]

    result = {"scanned": len(pairs), "merged": 0, "skipped": 0, "details": []}
    archived_paths: set[str] = set()  # 이미 아카이브된 파일 추적

    for idx, pair in enumerate(pairs, 1):
        a = pair["note_a"]
        b = pair["note_b"]

        # 이전 단계에서 이미 아카이브된 노트는 스킵
        if a["filepath"] in archived_paths or b["filepath"] in archived_paths:
            result["skipped"] += 1
            continue

        # 파일 존재 재확인 (이전 단계에서 다른 쌍의 secondary로 이동했을 수 있음)
        if not os.path.exists(a["filepath"]) or not os.path.exists(b["filepath"]):
            result["skipped"] += 1
            continue

        a_content = _read_note_content(a["filepath"])
        b_content = _read_note_content(b["filepath"])
        if not a_content or not b_content:
            result["skipped"] += 1
            continue

        try:
            dedup = await check_duplicate_content(b["title"], b["preview"], [a])
        except Exception as e:
            logger.warning(f"중복 판정 실패: {a['filename']} <-> {b['filename']} - {e}")
            result["skipped"] += 1
            continue

        if dedup["action"] == "skip":
            merge_duplicate_notes(a["filepath"], b["filepath"])
            archived_paths.add(b["filepath"])
            result["merged"] += 1
            result["details"].append(f"[통합] {b['filename']} → {a['filename']} ({pair['reason']})")
        elif dedup["action"] == "merge":
            new_info = dedup.get("new_info", "")
            if new_info:
                try:
                    append_to_existing_note(a["filepath"], new_info)
                except Exception as e:
                    logger.warning(f"보강 실패: {a['filename']} - {e}")
            merge_duplicate_notes(a["filepath"], b["filepath"])
            archived_paths.add(b["filepath"])
            result["merged"] += 1
            result["details"].append(f"[보강통합] {b['filename']} → {a['filename']}")

        if idx % 10 == 0:
            logger.info(f"진행: {idx}/{len(pairs)}, 통합 {result['merged']}, 스킵 {result['skipped']}")

    logger.info(f"중복 통합 완료: {result['merged']}개 통합, {result['skipped']}개 스킵")
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


# ── Karpathy LLM Wiki: 교차 참조 린팅 ──

def lint_missing_links(min_score: int = 8, max_per_note: int = 3) -> list[dict]:
    """볼트의 모든 노트를 스캔해 누락된 교차 참조를 찾는다.

    각 노트에 대해 find_related_notes를 실행하고, 이미 ## 관련 노트 섹션에
    링크되지 않은 것만 후보로 반환.

    Returns: [{"filepath", "filename", "title", "missing": [{"filename","title","score"}]}]
    """
    from obsidian_writer import find_related_notes

    notes = get_existing_notes_summary()
    suggestions = []

    for note in notes:
        content = _read_note_content(note["filepath"])
        if not content:
            continue

        # 이미 ## 관련 노트 섹션에 있는 링크 추출
        existing_links = set()
        related_match = re.search(r'## 관련 노트\n(.*?)(?:\n##|\n---|\Z)', content, re.DOTALL)
        if related_match:
            for link in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', related_match.group(1)):
                # 경로가 있을 경우 마지막 부분만 사용
                existing_links.add(link.split("/")[-1].strip().lower())

        # 관련 노트 찾기 (저장된 본문 사용)
        related = find_related_notes(
            note["title"],
            content,
            exclude_filename=note["filename"],
        )

        # 점수가 충분하고 아직 링크되지 않은 것만
        missing = []
        for r in related:
            if r["score"] < min_score:
                continue
            if r["title"].lower() in existing_links:
                continue
            if r["filename"].replace(".md", "").lower() in existing_links:
                continue
            missing.append(r)
            if len(missing) >= max_per_note:
                break

        if missing:
            suggestions.append({
                "filepath": note["filepath"],
                "filename": note["filename"],
                "title": note["title"],
                "missing": missing,
            })

    logger.info(f"린팅 완료: {len(notes)}개 노트 스캔, {len(suggestions)}개 노트에 누락 링크 발견")
    return suggestions


def apply_lint_links(suggestions: list[dict]) -> dict:
    """lint_missing_links()의 결과를 실제로 적용한다 (양방향 링크 자동 생성).
    Returns: {"updated": int, "links_added": int}
    """
    from obsidian_writer import add_related_links

    result = {"updated": 0, "links_added": 0}

    for s in suggestions:
        try:
            # add_related_links는 ## 관련 노트 섹션이 있으면 스킵하므로,
            # 직접 기존 섹션에 추가하는 방식으로 처리
            content = _read_note_content(s["filepath"])
            if not content:
                continue

            new_links = "\n".join(f"- [[{m['title']}]]" for m in s["missing"])

            if "## 관련 노트" in content:
                # 기존 섹션에 추가
                content = content.replace(
                    "## 관련 노트\n",
                    f"## 관련 노트\n{new_links}\n",
                    1,
                )
            else:
                # 새 섹션 생성 (## 평가 앞)
                section = f"\n\n## 관련 노트\n{new_links}\n"
                if "## 평가" in content:
                    content = content.replace("## 평가", f"{section}\n## 평가", 1)
                else:
                    content += section

            with open(s["filepath"], "w", encoding="utf-8") as f:
                f.write(content)

            # 역방향 링크
            add_related_links(s["filepath"], s["missing"])

            result["updated"] += 1
            result["links_added"] += len(s["missing"])
        except Exception as e:
            logger.error(f"린트 적용 실패: {s['filename']} - {e}")

    logger.info(f"린트 적용 완료: {result['updated']}개 노트, {result['links_added']}개 링크 추가")
    return result


def find_orphan_notes() -> list[dict]:
    """관련 노트 섹션이 없거나 비어있는 고립 노트를 찾는다.
    Returns: [{"filename", "title", "filepath"}]
    """
    notes = get_existing_notes_summary()
    orphans = []

    for note in notes:
        content = _read_note_content(note["filepath"])
        if not content:
            continue

        related_match = re.search(r'## 관련 노트\n(.*?)(?:\n##|\n---|\Z)', content, re.DOTALL)
        if not related_match or not re.search(r'\[\[[^\]]+\]\]', related_match.group(1)):
            orphans.append({
                "filename": note["filename"],
                "title": note["title"],
                "filepath": note["filepath"],
            })

    return orphans
