import re
import httpx
from bs4 import BeautifulSoup


URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text)


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
        return {"url": url, "title": "", "content": "", "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 불필요한 태그 제거
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # 본문 추출 (article 우선, 없으면 body)
    article = soup.find("article") or soup.find("main") or soup.body
    text = article.get_text(separator="\n", strip=True) if article else ""

    # 너무 긴 텍스트 제한 (Claude CLI 입력 제한 방지)
    max_chars = 6000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(truncated)"

    return {"url": url, "title": title, "content": text, "error": ""}
