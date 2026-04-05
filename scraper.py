import re
import logging
import httpx
from bs4 import BeautifulSoup
from config import GITHUB_TOKEN

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


# ── GitHub ──

_GITHUB_REPO_PATTERN = re.compile(
    r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$'
)


def is_github_repo_url(url: str) -> bool:
    """GitHub 저장소 루트 URL인지 판별한다. issues/blob 등 하위 경로는 제외."""
    return bool(_GITHUB_REPO_PATTERN.match(url))


def _parse_github_owner_repo(url: str) -> tuple[str, str]:
    """GitHub URL에서 owner, repo를 추출한다."""
    m = _GITHUB_REPO_PATTERN.match(url)
    if m:
        return m.group(1), m.group(2)
    return "", ""


async def fetch_github_repo(url: str) -> dict:
    """GitHub API로 저장소 메타데이터 + README를 ���져온다.
    API 실패 시 raw.githubusercontent.com으로 폴백.
    """
    owner, repo = _parse_github_owner_repo(url)
    if not owner or not repo:
        return {"url": url, "owner": "", "repo": "", "description": "",
                "stars": 0, "forks": 0, "language": "", "topics": [],
                "license": "", "readme_content": "", "error": "Invalid GitHub URL"}

    result = {
        "url": url, "owner": owner, "repo": repo,
        "description": "", "stars": 0, "forks": 0,
        "language": "", "topics": [], "license": "",
        "readme_content": "", "error": "",
    }

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # 1) 저장소 메타데이터
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                result["description"] = data.get("description") or ""
                result["stars"] = data.get("stargazers_count", 0)
                result["forks"] = data.get("forks_count", 0)
                result["language"] = data.get("language") or ""
                result["topics"] = data.get("topics") or []
                license_info = data.get("license")
                result["license"] = license_info.get("name", "") if license_info else ""
            else:
                logger.warning(f"GitHub API 메타데이터 실패 ({resp.status_code}): {owner}/{repo}")

            # 2) README (raw 텍스트로 직접 수신)
            readme_headers = {**headers, "Accept": "application/vnd.github.raw+json"}
            resp_readme = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers=readme_headers,
            )
            if resp_readme.status_code == 200:
                result["readme_content"] = resp_readme.text
            else:
                logger.warning(f"GitHub API README 실패 ({resp_readme.status_code}), raw 폴백 시도")
                raise httpx.HTTPStatusError("README fallback", request=resp_readme.request, response=resp_readme)

    except Exception as e:
        # API 실패 → raw.githubusercontent.com 폴백
        logger.info(f"GitHub API 실패, raw 폴백: {owner}/{repo} - {e}")
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                raw_resp = await client.get(
                    f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"
                )
                if raw_resp.status_code == 200:
                    result["readme_content"] = raw_resp.text
                else:
                    result["error"] = f"README fetch failed ({raw_resp.status_code})"
        except Exception as raw_err:
            logger.error(f"GitHub raw 폴백도 실패: {owner}/{repo} - {raw_err}")
            result["error"] = str(raw_err)

    # README 길이 제한
    if len(result["readme_content"]) > 8000:
        result["readme_content"] = result["readme_content"][:8000] + "\n...(truncated)"

    return result
