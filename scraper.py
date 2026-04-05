import re
import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# URL 끝에 붙는 불필요한 문자 (괄호, 구두점, 유니코드 제어문자 등)
_URL_TRAIL_JUNK = re.compile(r'[)\]},;:!?.\'"]+$|[\ufffc\ufeff\u200b-\u200f\u202a-\u202e]+')


def _clean_url(url: str) -> str:
    """URL 끝의 괄호, 구두점, 유니코드 제어문자를 제거한다."""
    return _URL_TRAIL_JUNK.sub('', url)


def extract_urls(text: str) -> list[str]:
    raw = URL_PATTERN.findall(text)
    return [_clean_url(u) for u in raw]


async def fetch_page_content(url: str) -> dict:
    """URL에서 페이지 제목과 본문 텍스트를 추출한다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"페이지 fetch 실패: {url} - {e}", exc_info=True)
        return {"url": url, "title": "", "content": "", "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 불필요한 태그 제거
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    try:
        title = soup.title.get_text(strip=True) if soup.title else ""
    except Exception:
        title = ""

    # 본문 추출 (article 우선, 없으면 body)
    article = soup.find("article") or soup.find("main") or soup.body
    text = article.get_text(separator="\n", strip=True) if article else ""

    # 너무 긴 텍스트 제한 (Claude CLI 입력 제한 방지)
    max_chars = 6000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(truncated)"

    return {"url": url, "title": title, "content": text, "error": ""}
