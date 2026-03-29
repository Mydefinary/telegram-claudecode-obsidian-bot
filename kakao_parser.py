"""카카오톡 대화 내보내기 txt를 게시글 단위로 파싱한다."""

import re
from scraper import extract_urls


# 카카오톡 날짜 구분선
DATE_HEADER = re.compile(r'^-{2,}\s+\d{4}년.*?-{2,}$')
# 카카오톡 메시지: [이름] [시간] 내용
MSG_PREFIX = re.compile(r'^\[(.+?)\]\s+\[(오전|오후)\s*\d{1,2}:\d{2}\]\s*(.*)')


def is_kakao_format(text: str) -> bool:
    """카카오톡 대화 내보내기 형식인지 감지한다."""
    lines = text.split("\n")[:20]
    for line in lines:
        if DATE_HEADER.match(line.strip()):
            return True
        if MSG_PREFIX.match(line.strip()):
            return True
    return False


def parse_kakao_txt(text: str) -> list[str]:
    """카카오톡 대화 내보내기를 게시글 단위 리스트로 반환한다.

    규칙:
    - 날짜 구분선, [이름] [시간] 메타데이터를 제거
    - "사진", "파일:" 등 텍스트로 처리 불가능한 항목 스킵
    - URL + 설명(짧은 텍스트)을 하나의 게시글로 묶음
    - 긴 텍스트는 독립 게시글
    """
    lines = text.split("\n")

    # 1단계: 개별 메시지 추출 (메타데이터 제거)
    messages = []
    current_msg = None

    for line in lines:
        stripped = line.strip()

        # 날짜 구분선 → 현재 메시지 저장 후 스킵
        if DATE_HEADER.match(stripped):
            if current_msg is not None:
                messages.append(current_msg.strip())
                current_msg = None
            continue

        # 새 메시지 시작
        m = MSG_PREFIX.match(stripped)
        if m:
            if current_msg is not None:
                messages.append(current_msg.strip())

            content = m.group(3).strip()

            # 사진/파일/동영상 등 처리 불가 항목 스킵
            if content in ("사진", "동영상") or content.startswith("파일:"):
                current_msg = None
                continue

            current_msg = content

        elif stripped and current_msg is not None:
            # 이전 메시지의 연속 줄 (카톡에서 줄바꿈된 내용)
            current_msg += "\n" + stripped

        elif not stripped and current_msg is not None:
            # 빈 줄 → 메시지 내 단락 구분 유지
            current_msg += "\n"

    if current_msg is not None:
        messages.append(current_msg.strip())

    # 빈 메시지 제거
    messages = [m for m in messages if m]

    # 2단계: 관련 메시지 그룹핑 (URL + 설명을 하나의 게시글로)
    posts = []
    i = 0

    while i < len(messages):
        msg = messages[i]

        if not msg:
            i += 1
            continue

        msg_urls = extract_urls(msg)
        msg_is_url_only = bool(msg_urls) and len(msg.strip()) - sum(len(u) for u in msg_urls) < 20
        msg_is_short_text = not msg_urls and len(msg) < 300

        # 다음 메시지 미리보기
        next_msg = messages[i + 1] if i + 1 < len(messages) else None
        next_urls = extract_urls(next_msg) if next_msg else []
        next_is_url_only = bool(next_urls) and next_msg and len(next_msg.strip()) - sum(len(u) for u in next_urls) < 20
        next_is_short_text = next_msg and not next_urls and len(next_msg) < 300

        # 패턴 1: URL만 있는 메시지 + 다음이 짧은 설명
        if msg_is_url_only and next_is_short_text:
            posts.append(msg + "\n" + next_msg)
            i += 2
            continue

        # 패턴 2: 짧은 설명 + 다음이 URL
        if msg_is_short_text and next_msg and next_urls:
            posts.append(msg + "\n" + next_msg)
            i += 2
            continue

        # 패턴 3: URL + 설명이 같은 메시지에 있거나, 긴 단독 텍스트
        posts.append(msg)
        i += 1

    return posts
