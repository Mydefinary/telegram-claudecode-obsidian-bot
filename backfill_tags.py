"""기존 팁 파일에 태그를 소급 추가하는 스크립트.

~/.claude/tips/ 디렉토리의 .md 파일 중 tags 필드가 없는 팁에
Claude CLI를 호출하여 태그를 자동 생성한다.
"""

import asyncio
import os
import re
import sys

from analyzer import _run_claude

TIPS_DIR = os.path.expanduser("~/.claude/tips")

TAG_PROMPT = """\
다음 Claude Code 팁의 내용을 읽고, 관련 기술 키워드 태그를 3-7개 추출하세요.

규칙:
- 영문 소문자와 하이픈만 사용
- 공식 패키지명이나 널리 통용되는 약칭 사용
- 쉼표로 구분하여 한 줄로 출력
- 태그만 출력, 다른 설명 없이

예: python, async, testing, multi-agent, claude-code

팁:
{tip_content}

태그:"""


def get_tips_without_tags() -> list[dict]:
    """태그가 없는 팁 파일 목록을 반환한다."""
    tips = []

    if not os.path.exists(TIPS_DIR):
        return tips

    for f in sorted(os.listdir(TIPS_DIR)):
        if not f.endswith(".md"):
            continue

        filepath = os.path.join(TIPS_DIR, f)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                content = fh.read()

            # 이미 tags 필드가 있고 비어있지 않으면 스킵
            tags_match = re.search(r'^tags:\s*\[(.+)\]', content, re.MULTILINE)
            if tags_match and tags_match.group(1).strip():
                continue

            # 본문에서 팁 내용 추출
            tip_content = ""
            in_body = False
            for line in content.split("\n"):
                if line.strip() == "---" and not in_body:
                    in_body = True
                    continue
                if in_body and line.strip() == "---":
                    in_body = False
                    continue
                if not in_body and line.strip().startswith("---"):
                    continue

            # frontmatter 이후 본문 전체
            parts = content.split("---")
            body = "---".join(parts[2:]).strip() if len(parts) >= 3 else ""

            tips.append({
                "filename": f,
                "filepath": filepath,
                "content": content,
                "body": body,
            })
        except Exception:
            continue

    return tips


def add_tags_to_frontmatter(filepath: str, content: str, tags: list[str]):
    """팁 파일의 frontmatter에 tags와 declined 필드를 추가/갱신한다."""
    tags_str = ", ".join(tags)

    # tags 필드가 이미 있으면 교체
    if re.search(r'^tags:', content, re.MULTILINE):
        content = re.sub(r'^tags:.*$', f'tags: [{tags_str}]', content, count=1, flags=re.MULTILINE)
    else:
        # applied: 행 앞에 삽입
        content = content.replace("applied:", f"tags: [{tags_str}]\napplied:", 1)

    # declined 필드가 없으면 추가
    if not re.search(r'^declined:', content, re.MULTILINE):
        content = content.replace("applied:", "applied: []\ndeclined:", 1)
        # applied가 이미 []면 중복 방지
        content = content.replace("applied: []\napplied:", "applied:", 1)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


async def backfill():
    tips = get_tips_without_tags()
    total = len(tips)

    if total == 0:
        print("태그가 필요한 팁이 없습니다.")
        return

    print(f"태그 추가 대상: {total}개 팁")

    success = 0
    failed = 0

    for i, tip in enumerate(tips, 1):
        print(f"[{i}/{total}] {tip['filename']}")

        try:
            prompt = TAG_PROMPT.format(tip_content=tip["body"][:2000])
            raw = await _run_claude(prompt)

            # 태그 파싱
            tags = [t.strip().lower().replace(" ", "-") for t in raw.split(",") if t.strip()]
            tags = [t for t in tags if re.match(r'^[a-z0-9-]+$', t)]

            if not tags:
                print(f"  -> 태그 추출 실패")
                failed += 1
                continue

            add_tags_to_frontmatter(tip["filepath"], tip["content"], tags)
            print(f"  -> 태그 추가: {', '.join(tags)}")
            success += 1

        except Exception as e:
            print(f"  -> 오류: {e}")
            failed += 1

    print(f"\n--- 완료: 성공 {success}개, 실패 {failed}개 ---")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(backfill())
