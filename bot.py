"""
텔레그램 -> Claude 분석 -> 옵시디언 자동 저장 봇
txt 파일 업로드 지원 + 큐 기반 병렬 처리
"""

import sys
import io
import os
import asyncio
import logging
import tempfile

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import TELEGRAM_BOT_TOKEN, OBSIDIAN_VAULT_PATH, OBSIDIAN_FOLDER, MAX_CONCURRENT, MESSAGE_MERGE_ENABLED, MESSAGE_MERGE_WAIT  # noqa: E402
from scraper import extract_urls, fetch_page_content
from analyzer import analyze_link, analyze_link_direct, analyze_text, analyze_image, analyze_youtube, check_duplicate_content, is_youtube_url
from obsidian_writer import save_note, copy_image_to_vault, is_url_duplicate, get_existing_notes_summary, append_to_existing_note
from kakao_parser import is_kakao_format, parse_kakao_txt
from evaluator import evaluate_note, format_eval_tags, append_to_claude_md, create_skill, save_tip_to_pool, update_note_with_eval

logger = logging.getLogger(__name__)


def split_my_thoughts(text: str) -> tuple[str, str]:
    """텍스트에서 '내생각:' 이후를 분리한다. (content, my_thoughts) 반환."""
    import re
    match = re.search(r'(?:^|\n)\s*내생각\s*[:：]\s*', text)
    if match:
        return text[:match.start()].strip(), text[match.end():].strip()
    return text, ""

# MAX_CONCURRENT is loaded from config.py (default: 3)

# 대기 중인 Claude Code 팁 저장 (callback_data -> {tip, title, ...})
pending_tips = {}


async def _show_tip_prompt(message, ev, title):
    """팁 발견 시 처리 유형 선택 버튼을 보여준다."""
    tip = ev.get("tip", "")
    if not tip or tip == "없음":
        return

    try:
        import uuid
        tip_id = str(uuid.uuid4())[:8]
        pending_tips[tip_id] = {
            "tip": tip,
            "title": title,
            "tip_desc": ev.get("tip_desc", ""),
            "tip_action": ev.get("tip_action", ""),
            "tip_confidence": ev.get("tip_confidence", 0),
            "tip_action_reason": ev.get("tip_action_reason", ""),
            "skill_name": ev.get("skill_name", ""),
            "tags": ev.get("tags", []),
        }

        tip_desc = ev.get("tip_desc", "")
        tip_action = ev.get("tip_action", "")
        tip_action_reason = ev.get("tip_action_reason", "")

        # 메시지 구성
        action_labels = {"global": "Global 반영", "skill": "Skill 제작", "풀": "팁 저장", "저장": "일반 저장"}
        msg_parts = ["[Claude Code 팁 발견]", f"팁: {tip}"]
        if tip_desc and tip_desc != "없음":
            msg_parts.append(f"설명: {tip_desc}")
        tip_confidence = ev.get("tip_confidence", 0)
        if tip_action and tip_action != "없음":
            label = action_labels.get(tip_action, tip_action)
            stars = "⭐" * tip_confidence + "☆" * (5 - tip_confidence) if tip_confidence else ""
            confidence_str = f" {stars} ({tip_confidence}/5)" if tip_confidence else ""
            msg_parts.append(f"권장: {label}{confidence_str}")
        if tip_action_reason and tip_action_reason != "없음":
            msg_parts.append(f"근거: {tip_action_reason}")

        skill_name = ev.get("skill_name", "")
        if skill_name and skill_name != "없음":
            msg_parts.append(f"스킬명: /{skill_name}")

        tags = ev.get("tags", [])
        if tags:
            msg_parts.append(f"태그: {', '.join(tags)}")

        msg_parts.append("\n어떻게 처리할까요?")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Global 반영", callback_data=f"tip_global:{tip_id}"),
                InlineKeyboardButton("Skill 제작", callback_data=f"tip_skill:{tip_id}"),
            ],
            [
                InlineKeyboardButton("팁 저장", callback_data=f"tip_pool:{tip_id}"),
                InlineKeyboardButton("스킵", callback_data=f"tip_skip:{tip_id}"),
            ],
        ])

        await message.reply_text("\n".join(msg_parts), reply_markup=keyboard)
    except Exception as e:
        logger.error(f"팁 프롬프트 전송 실패: {title} - {e}", exc_info=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "링크, 메시지, 이미지를 보내주세요.\n"
        "분석 후 옵시디언에 자동 저장합니다.\n\n"
        "지원 형식:\n"
        "- URL -> 사이트 분석\n"
        "- 텍스트 -> 내용 정리\n"
        "- 이미지 -> 이미지 분석\n"
        "- .txt 파일 -> 줄 단위 병렬 처리\n\n"
        "/start - 시작 | /help - 도움말"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    merge_state = "ON" if merge_enabled else "OFF"
    await update.message.reply_text(
        "사용법:\n"
        "- URL 보내기 -> 사이트 분석 후 옵시디언 노트 생성\n"
        "- 텍스트 보내기 -> 내용 정리 후 옵시디언 노트 생성\n"
        "- .txt 파일 보내기 -> 줄 단위로 각각 분석 (병렬 처리)\n\n"
        "txt 파일 형식:\n"
        "- 한 줄에 URL 하나 -> 각각 개별 링크 분석\n"
        "- 빈 줄로 구분된 텍스트 블록 -> 블록별 분석\n"
        "- 혼합 가능 (URL과 텍스트 섞어도 OK)\n\n"
        f"/merge - 메시지 병합 ON/OFF (현재: {merge_state}, {MESSAGE_MERGE_WAIT}초 대기)"
    )


# ── 실패 URL 수집용 ──
failed_urls_lock = asyncio.Lock()


async def process_single_item(item: str, update: Update, semaphore: asyncio.Semaphore, failed_urls: list):
    """하나의 항목(URL 또는 텍스트)을 분석하고 저장한다.
    분석 실패 시 failed_urls에 추가하고 옵시디언에는 저장하지 않는다.
    """
    async with semaphore:
        item = item.strip()
        if not item:
            return

        # '내생각:' 분리
        item, my_thoughts = split_my_thoughts(item)

        urls = extract_urls(item)

        if urls:
            url = urls[0]
            non_url_text = item
            for u in urls:
                non_url_text = non_url_text.replace(u, "").strip()

            # 중복 URL 체크
            if is_url_duplicate(url):
                await update.message.reply_text(f"[중복] {url}")
                return

            try:
                logger.info(f"URL 처리 시작: {url}")

                # YouTube는 Gemini로 분석
                if is_youtube_url(url):
                    logger.info(f"YouTube 감지, Gemini 분석: {url}")
                    result = await analyze_youtube(url)
                    page = {"title": "", "content": "", "error": ""}
                    scraped_ok = False
                else:
                    page = await fetch_page_content(url)
                    scraped_ok = not page["error"] and len(page.get("content", "").strip()) > 100

                    if page["error"]:
                        logger.warning(f"스크래핑 오류 (fallback 분석): {url} - {page['error']}")

                    if scraped_ok:
                        result = await analyze_link(url, page["title"], page["content"])
                    else:
                        logger.info(f"스크래핑 부족, Claude 직접 분석: {url}")
                        result = await analyze_link_direct(url)

                # 분석 실패 시 저장하지 않고 실패 목록에 추가
                if result["failed"]:
                    logger.warning(f"분석 실패: {url}")
                    async with failed_urls_lock:
                        desc = non_url_text or page.get("title", "")
                        failed_urls.append(f"{url} ({desc})" if desc else url)
                    return

                content = result["content"]
                if non_url_text:
                    content = f"> {non_url_text}\n\n{content}"

                title = result["title"] or page.get("title") or url.split("/")[-1]

                # 내용 중복 비교
                existing_notes = get_existing_notes_summary()
                dedup = await check_duplicate_content(title, content, existing_notes)

                if dedup["action"] == "skip":
                    await update.message.reply_text(f"[중복 스킵] {title}\n유사: {dedup['similar_file']}")
                    return

                if dedup["action"] == "merge" and dedup["similar_file"]:
                    # 기존 노트에 새 정보만 추가
                    target = None
                    for n in existing_notes:
                        if n["filename"] == dedup["similar_file"]:
                            target = n["filepath"]
                            break
                    if target:
                        new_info = dedup["new_info"] or content
                        append_to_existing_note(target, new_info)
                        await update.message.reply_text(f"[보강] {dedup['similar_file']}에 새 정보 추가")
                        return

                # 신규 저장 (원본 포함 — 스크래핑 부분 성공도 저장)
                original = page.get("content", "")
                filepath = save_note(title=title, content=content, source_url=url, source_type="link", original_content=original, my_thoughts=my_thoughts)

                # 평가
                try:
                    ev = await evaluate_note(title, content, url)
                    update_note_with_eval(filepath, format_eval_tags(ev))
                    eval_msg = f"[완료] {title} (등급: {ev['grade']})"
                    await update.message.reply_text(eval_msg)

                    # Claude Code 팁이 있으면 처리 유형 선택
                    await _show_tip_prompt(update.message, ev, title)
                except Exception as ev_err:
                    logger.error(f"평가 오류: {url} - {ev_err}", exc_info=True)
                    await update.message.reply_text(f"[완료] {title}")

            except Exception as e:
                logger.error(f"URL 처리 실패: {url} - {e}", exc_info=True)
                async with failed_urls_lock:
                    failed_urls.append(f"{url} (오류: {e})")
        else:
            try:
                logger.info(f"텍스트 처리 시작: {item[:80]}...")
                result = await analyze_text(item)

                if result["failed"]:
                    logger.warning(f"텍스트 분석 실패: {item[:80]}...")
                    async with failed_urls_lock:
                        failed_urls.append(f"텍스트: {item[:50]}...")
                    return

                # 내용 중복 비교
                existing_notes = get_existing_notes_summary()
                dedup = await check_duplicate_content(result["title"], result["content"], existing_notes)

                if dedup["action"] == "skip":
                    await update.message.reply_text(f"[중복 스킵] {result['title']}\n유사: {dedup['similar_file']}")
                    return

                if dedup["action"] == "merge" and dedup["similar_file"]:
                    target = None
                    for n in existing_notes:
                        if n["filename"] == dedup["similar_file"]:
                            target = n["filepath"]
                            break
                    if target:
                        new_info = dedup["new_info"] or result["content"]
                        append_to_existing_note(target, new_info)
                        await update.message.reply_text(f"[보강] {dedup['similar_file']}에 새 정보 추가")
                        return

                filepath = save_note(title=result["title"], content=result["content"], source_url="", source_type="text", original_content=item, my_thoughts=my_thoughts)

                # 평가
                try:
                    ev = await evaluate_note(result["title"], result["content"])
                    update_note_with_eval(filepath, format_eval_tags(ev))
                    eval_msg = f"[완료] {result['title']} (등급: {ev['grade']})"
                    await update.message.reply_text(eval_msg)

                    # Claude Code 팁이 있으면 처리 유형 선택
                    await _show_tip_prompt(update.message, ev, result["title"])
                except Exception as ev_err:
                    logger.error(f"텍스트 평가 오류: {ev_err}", exc_info=True)
                    await update.message.reply_text(f"[완료] {result['title']}")

            except Exception as e:
                logger.error(f"텍스트 처리 실패: {item[:80]}... - {e}", exc_info=True)
                async with failed_urls_lock:
                    failed_urls.append(f"텍스트 오류: {item[:50]}...")


async def process_queue(items: list[str], update: Update):
    """항목 리스트를 큐에 넣고 병렬 처리한다. 실패 URL을 마지막에 보고."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    failed_urls = []
    tasks = [process_single_item(item, update, semaphore, failed_urls) for item in items if item.strip()]
    await asyncio.gather(*tasks)

    # 실패 URL 마지막에 한번에 보고
    if failed_urls:
        msg = "[처리 실패 목록]\n" + "\n".join(f"- {u}" for u in failed_urls)
        # 텔레그램 메시지 길이 제한 (4096자)
        if len(msg) > 4000:
            msg = msg[:4000] + "\n...(더 있음)"
        await update.message.reply_text(msg)


def parse_txt_items(text: str) -> list[str]:
    """txt 내용을 항목 단위로 파싱한다.
    자동 감지:
    - 2줄 이상 빈 줄이 존재하면 → 2줄 빈 줄로 게시글 구분 (1줄 빈 줄은 같은 게시글 내 줄바꿈)
    - 2줄 빈 줄이 없으면 → 1줄 빈 줄로 게시글 구분
    """
    import re

    # 2줄 이상 빈 줄이 있는지 확인
    has_double_blank = bool(re.search(r'\n\s*\n\s*\n', text))

    if has_double_blank:
        # 2줄 빈 줄로 분할
        blocks = re.split(r'\n\s*\n\s*\n', text)
    else:
        # 1줄 빈 줄로 분할
        blocks = re.split(r'\n\s*\n', text)

    items = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        items.append(block)

    return items


# ── 메시지 병합 ──

merge_enabled = MESSAGE_MERGE_ENABLED
# {user_id: {"messages": [str], "task": asyncio.Task, "update": Update}}
_merge_buffers: dict = {}


async def _process_combined_message(text: str, urls: list[str], update: Update):
    """텍스트 + 여러 링크를 하나의 통합 노트로 처리한다."""
    non_url_text = text
    for u in urls:
        non_url_text = non_url_text.replace(u, "").strip()

    non_url_text, my_thoughts = split_my_thoughts(non_url_text)

    await update.message.reply_text(f"텍스트 + {len(urls)}개 링크 통합 분석 중...")

    sections = []
    originals = []
    first_title = ""
    source_urls = []
    failed = []

    for url in urls:
        if is_url_duplicate(url):
            sections.append(f"### {url}\n[중복 - 기존 노트 참조]")
            continue

        source_urls.append(url)

        try:
            if is_youtube_url(url):
                result = await analyze_youtube(url)
                page_content = ""
            else:
                page = await fetch_page_content(url)
                page_content = page.get("content", "")
                scraped_ok = not page["error"] and len(page_content.strip()) > 100

                if scraped_ok:
                    result = await analyze_link(url, page["title"], page_content)
                else:
                    result = await analyze_link_direct(url)

            if result["failed"]:
                failed.append(url)
                continue

            title = result["title"] or url.split("/")[-1]
            if not first_title:
                first_title = title

            sections.append(f"### {title}\n> {url}\n\n{result['content']}")

            if page_content:
                originals.append(f"[{title}]\n{page_content}")

        except Exception as e:
            logger.error(f"통합 분석 중 URL 실패: {url} - {e}", exc_info=True)
            failed.append(url)

    if not sections:
        await update.message.reply_text("[처리 실패] 모든 링크 분석에 실패했습니다.")
        return

    # 노트 구성
    content_parts = []
    if non_url_text:
        content_parts.append(f"> {non_url_text}\n")
    content_parts.extend(sections)
    combined_content = "\n\n".join(content_parts)

    combined_original = "\n\n---\n\n".join(originals) if originals else ""
    note_title = first_title or non_url_text[:30] or "Combined Note"

    filepath = save_note(
        title=note_title,
        content=combined_content,
        source_url=source_urls[0] if source_urls else "",
        source_type="link",
        original_content=combined_original,
        my_thoughts=my_thoughts,
    )

    # 평가
    try:
        ev = await evaluate_note(note_title, combined_content, source_urls[0] if source_urls else "")
        update_note_with_eval(filepath, format_eval_tags(ev))
        await update.message.reply_text(f"[완료] {note_title} (등급: {ev['grade']}, {len(sections)}개 링크 통합)")
        await _show_tip_prompt(update.message, ev, note_title)
    except Exception as ev_err:
        logger.error(f"통합 노트 평가 오류: {ev_err}", exc_info=True)
        await update.message.reply_text(f"[완료] {note_title} ({len(sections)}개 링크 통합)")

    if failed:
        await update.message.reply_text("[일부 실패]\n" + "\n".join(f"- {u}" for u in failed))


async def _process_text_message(text: str, update: Update):
    """텍스트를 분석하고 옵시디언에 저장한다."""
    urls = extract_urls(text)

    if urls:
        # URL 제거 후 남은 텍스트 확인
        non_url_text = text
        for u in urls:
            non_url_text = non_url_text.replace(u, "").strip()

        if non_url_text:
            # 텍스트 + 링크 → 하나의 통합 노트
            await _process_combined_message(text, urls, update)
        else:
            # 링크만 → 각각 독립 처리
            await update.message.reply_text(f"{len(urls)}개 링크 분석 중... (병렬 처리)")
            await process_queue(urls, update)
            await update.message.reply_text(f"--- 전체 {len(urls)}개 처리 완료 ---")
    else:
        await update.message.reply_text("텍스트 분석 중...")
        failed_urls = []
        await process_single_item(text, update, asyncio.Semaphore(1), failed_urls)
        if failed_urls:
            await update.message.reply_text("[처리 실패]\n" + "\n".join(f"- {u}" for u in failed_urls))


async def _flush_merge_buffer(user_id: int):
    """타이머 만료 시 버퍼의 메시지를 합쳐서 처리한다."""
    buf = _merge_buffers.pop(user_id, None)
    if not buf:
        return

    combined = "\n\n".join(buf["messages"])
    update = buf["update"]
    count = len(buf["messages"])

    if count > 1:
        logger.info(f"메시지 병합: user={user_id}, {count}개 -> {len(combined)}자")
        await update.message.reply_text(f"[{count}개 메시지 병합]")

    await _process_text_message(combined, update)


async def toggle_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """메시지 병합 기능 토글."""
    global merge_enabled
    merge_enabled = not merge_enabled
    state = "ON" if merge_enabled else "OFF"
    await update.message.reply_text(f"메시지 병합: {state} ({MESSAGE_MERGE_WAIT}초 대기)")


# ── 핸들러 ──

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """텍스트 메시지를 받아 분석하고 옵시디언에 저장한다."""
    text = update.message.text
    if not text or len(text.strip()) < 5:
        return

    # 병합 비활성화 시 즉시 처리
    if not merge_enabled:
        try:
            await _process_text_message(text, update)
        except Exception as e:
            logger.error(f"메시지 처리 실패: {text[:80]}... - {e}", exc_info=True)
            await update.message.reply_text(f"[오류] 처리 실패: {e}")
        return

    # 병합 모드: 버퍼에 추가하고 타이머 리셋
    user_id = update.message.from_user.id

    if user_id in _merge_buffers:
        _merge_buffers[user_id]["task"].cancel()
        _merge_buffers[user_id]["messages"].append(text)
        _merge_buffers[user_id]["update"] = update
    else:
        _merge_buffers[user_id] = {"messages": [text], "update": update}

    async def _timer():
        try:
            await asyncio.sleep(MESSAGE_MERGE_WAIT)
            await _flush_merge_buffer(user_id)
        except Exception as e:
            logger.error(f"메시지 병합 처리 실패: user={user_id} - {e}", exc_info=True)

    _merge_buffers[user_id]["task"] = asyncio.create_task(_timer())


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """txt 파일을 받아 줄 단위로 파싱 후 큐 처리한다."""
    doc = update.message.document
    if not doc:
        return

    # txt 파일만 처리
    file_name = doc.file_name or ""
    if not file_name.lower().endswith(".txt"):
        await update.message.reply_text("txt 파일만 지원합니다.")
        return

    await update.message.reply_text(f"파일 수신: {file_name}\n다운로드 중...")

    try:
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()

        # 인코딩 자동 감지 (UTF-8 우선, 실패하면 CP949)
        for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                content = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            await update.message.reply_text("파일 인코딩을 인식할 수 없습니다.")
            return

        # 카카오톡 형식 자동 감지
        if is_kakao_format(content):
            items = parse_kakao_txt(content)
            format_name = "카카오톡 대화"
        else:
            items = parse_txt_items(content)
            format_name = "일반 텍스트"

        total = len(items)

        if total == 0:
            await update.message.reply_text("파일에 처리할 내용이 없습니다.")
            return

        await update.message.reply_text(
            f"[{format_name}] 총 {total}개 항목 발견. {MAX_CONCURRENT}개씩 병렬 처리 시작..."
        )

        await process_queue(items, update)
        await update.message.reply_text(f"--- 전체 {total}개 항목 처리 완료 ---")

    except Exception as e:
        logger.error(f"문서 처리 실패: {file_name} - {e}", exc_info=True)
        await update.message.reply_text(f"파일 처리 오류: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """이미지를 받아 Claude로 분석하고 옵시디언에 저장한다."""
    # 가장 큰 해상도의 사진 선택
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    await update.message.reply_text("이미지 분석 중...")
    logger.info(f"이미지 처리 시작: file_id={photo.file_id}")

    try:
        # 이미지 다운로드
        file = await context.bot.get_file(photo.file_id)
        temp_dir = os.path.join(os.path.dirname(__file__), "temp")
        os.makedirs(temp_dir, exist_ok=True)

        temp_path = os.path.join(temp_dir, f"{photo.file_unique_id}.jpg")
        await file.download_to_drive(temp_path)

        # Claude로 분석
        result = await analyze_image(temp_path, caption)

        # 옵시디언에 이미지 복사 + 노트 저장
        vault_image_path = copy_image_to_vault(temp_path)
        vault_image_name = os.path.basename(vault_image_path)

        image_embed = f"![[{vault_image_name}]]\n\n"
        content = image_embed + result["content"]

        filepath = save_note(
            title=result["title"],
            content=content,
            source_url="",
            source_type="image",
        )

        await update.message.reply_text(f"[완료] {result['title']}")

        # 임시 파일 삭제
        try:
            os.remove(temp_path)
        except OSError as e:
            logger.warning(f"임시 이미지 삭제 실패: {temp_path} - {e}")

    except Exception as e:
        logger.error(f"이미지 처리 실패: {e}", exc_info=True)
        await update.message.reply_text(f"[오류] 이미지 분석 실패\n{e}")


async def handle_tip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claude Code 팁 처리 콜백 (Global 반영 / Skill 제작 / 스킵)."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"콜백 응답 실패: {e}")

    data = query.data
    if not data or ":" not in data:
        return

    action, tip_id = data.split(":", 1)
    tip_data = pending_tips.pop(tip_id, None)

    if not tip_data:
        await query.edit_message_text("(만료된 요청입니다)")
        return

    if action == "tip_global":
        if append_to_claude_md(tip_data["tip"], tip_data["title"]):
            await query.edit_message_text(f"[Global 적용] {tip_data['tip']}\n>> 글로벌 CLAUDE.md에 추가됨")
        else:
            await query.edit_message_text("[스킵] 이미 동일한 팁이 존재합니다")

    elif action == "tip_skill":
        skill_name = tip_data.get("skill_name", "")
        result = create_skill(
            skill_name=skill_name,
            tip=tip_data["tip"],
            tip_desc=tip_data.get("tip_desc", ""),
            source_title=tip_data["title"],
        )
        if result:
            await query.edit_message_text(f"[Skill 생성] /{skill_name}\n>> {result}")
        else:
            await query.edit_message_text("[실패] 스킬명이 없거나 이미 존재합니다")

    elif action == "tip_pool":
        result = save_tip_to_pool(
            tip=tip_data["tip"],
            tip_desc=tip_data.get("tip_desc", ""),
            source_title=tip_data["title"],
            skill_name=tip_data.get("skill_name", ""),
            tags=tip_data.get("tags", []),
        )
        if result:
            await query.edit_message_text(f"[팁 저장] {tip_data['tip']}\n>> 풀에 저장됨 (프로젝트에서 /apply-tips로 적용)")
        else:
            await query.edit_message_text("[스킵] 이미 동일한 팁이 풀에 존재합니다")

    else:  # tip_skip
        await query.edit_message_text(f"[스킵] 팁 미적용: {tip_data['tip']}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("merge", toggle_merge))
    app.add_handler(CallbackQueryHandler(handle_tip_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("[BOT] 시작! 텔레그램에서 메시지를 보내세요.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
