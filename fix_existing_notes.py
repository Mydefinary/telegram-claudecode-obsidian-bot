"""기존 옵시디언 노트를 새 기준으로 일괄 정리하는 스크립트.

1. 날짜 프리픽스 제거
2. 메타 코멘트 제거
3. 실패한 분석 내용은 삭제하고 리스트 출력
"""

import os
import re

from config import OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER

FOLDER = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER)

# 실패 판별 패턴
FAIL_PATTERNS = [
    "권한이 필요합니다",
    "승인해주시겠어요",
    "콘텐츠를 가져올 수 없",
    "접근이 차단",
    "로그인이 필요",
    "본문을 직접 복사",
    "URL을 알고 계시면",
    "어떤 방법이 편하신가요",
    "분석할 웹페이지 URL이나 내용을 제공",
    "분석해야 하는지 알려주",
    "콘텐츠를 제공해",
    "알려주시면 옵시디언",
    "알려주셔야 노트를",
]

# 메타 코멘트 제거 패턴
META_PATTERNS = [
    r"이제 충분한 정보를 확보했습니다\.?\s*분석 결과를 작성합니다\.?",
    r"분석 결과를 작성하겠습니다\.?",
    r"분석을 시작하겠습니다\.?",
    r"다음과 같이 분석했습니다\.?",
    r"아래와 같이 정리했습니다\.?",
]


def is_failed(content: str) -> bool:
    for pat in FAIL_PATTERNS:
        if pat in content:
            return True
    # 본문이 너무 짧으면 (프론트매터 제외)
    parts = content.split("---")
    if len(parts) >= 3:
        body = "---".join(parts[2:]).strip()
        # 제목(# ...)만 있고 내용 없는 경우
        lines = [l for l in body.split("\n") if l.strip() and not l.strip().startswith("#")]
        if len(lines) < 2:
            return True
    return False


def clean_meta(content: str) -> str:
    for pat in META_PATTERNS:
        content = re.sub(pat, "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def remove_date_prefix(filename: str) -> str:
    """2026-03-15_ 같은 날짜 프리픽스 제거"""
    return re.sub(r"^\d{4}-\d{2}-\d{2}_", "", filename)


def main():
    files = [f for f in os.listdir(FOLDER) if f.endswith(".md")]
    failed = []
    fixed = []
    renamed = []

    for f in sorted(files):
        path = os.path.join(FOLDER, f)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # 1. 실패한 노트 삭제
        if is_failed(content):
            # URL 추출
            url_match = re.search(r'url:\s*"(.+?)"', content)
            url = url_match.group(1) if url_match else f
            failed.append(url)
            os.remove(path)
            continue

        # 2. 메타 코멘트 제거
        new_content = clean_meta(content)
        if new_content != content:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            fixed.append(f)

        # 3. 날짜 프리픽스 제거
        new_name = remove_date_prefix(f)
        if new_name != f:
            new_path = os.path.join(FOLDER, new_name)
            # 충돌 방지
            counter = 1
            base, ext = os.path.splitext(new_name)
            while os.path.exists(new_path):
                new_name = f"{base}_{counter}{ext}"
                new_path = os.path.join(FOLDER, new_name)
                counter += 1
            os.rename(path, new_path)
            renamed.append(f"{f} -> {new_name}")

    print(f"\n=== 정리 완료 ===")
    print(f"삭제 (실패 노트): {len(failed)}개")
    for u in failed:
        print(f"  - {u}")
    print(f"\n메타 코멘트 제거: {len(fixed)}개")
    for f in fixed:
        print(f"  - {f}")
    print(f"\n파일명 변경: {len(renamed)}개")
    for r in renamed:
        print(f"  - {r}")


if __name__ == "__main__":
    main()
