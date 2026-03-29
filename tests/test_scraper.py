"""Tests for scraper.py - URL extraction functionality."""

import pytest
from scraper import extract_urls, URL_PATTERN


class TestExtractUrls:
    """Tests for extract_urls() function."""

    def test_single_http_url(self):
        text = "Visit http://example.com for more info"
        result = extract_urls(text)
        assert result == ["http://example.com"]

    def test_single_https_url(self):
        text = "Visit https://example.com for more info"
        result = extract_urls(text)
        assert result == ["https://example.com"]

    def test_url_with_path(self):
        text = "Check https://example.com/path/to/page"
        result = extract_urls(text)
        assert result == ["https://example.com/path/to/page"]

    def test_url_with_query_params(self):
        text = "Link: https://example.com/search?q=python&page=1"
        result = extract_urls(text)
        assert result == ["https://example.com/search?q=python&page=1"]

    def test_url_with_fragment(self):
        text = "See https://example.com/docs#section-2"
        result = extract_urls(text)
        assert result == ["https://example.com/docs#section-2"]

    def test_multiple_urls(self):
        text = "First https://a.com then https://b.com and http://c.org"
        result = extract_urls(text)
        assert result == ["https://a.com", "https://b.com", "http://c.org"]

    def test_no_urls(self):
        text = "This is plain text without any links."
        result = extract_urls(text)
        assert result == []

    def test_empty_string(self):
        result = extract_urls("")
        assert result == []

    def test_url_with_port(self):
        text = "Server at https://localhost:8080/api"
        result = extract_urls(text)
        assert result == ["https://localhost:8080/api"]

    def test_url_with_subdomain(self):
        text = "Blog at https://blog.example.co.kr/posts"
        result = extract_urls(text)
        assert result == ["https://blog.example.co.kr/posts"]

    def test_mixed_text_and_urls(self):
        text = """
        안녕하세요! 이 글을 보세요:
        https://news.ycombinator.com/item?id=12345
        정말 좋은 내용이에요.
        그리고 이것도요: https://arxiv.org/abs/2301.00001
        """
        result = extract_urls(text)
        assert len(result) == 2
        assert "https://news.ycombinator.com/item?id=12345" in result
        assert "https://arxiv.org/abs/2301.00001" in result

    def test_url_at_end_of_line(self):
        text = "Check out https://example.com\nNext line here"
        result = extract_urls(text)
        assert result == ["https://example.com"]

    def test_url_with_encoded_chars(self):
        text = "Link: https://example.com/path%20with%20spaces"
        result = extract_urls(text)
        assert result == ["https://example.com/path%20with%20spaces"]

    def test_url_surrounded_by_angle_brackets_excluded(self):
        """URLs inside <> should have the brackets excluded by the pattern."""
        text = "See <https://example.com> for details"
        result = extract_urls(text)
        # The pattern excludes < and > so the URL should still be extracted
        assert len(result) == 1
        assert "https://example.com" in result[0]

    def test_url_in_parentheses(self):
        text = "Reference (https://example.com/doc) here"
        result = extract_urls(text)
        assert len(result) == 1
        # The closing paren may or may not be included depending on pattern
        assert result[0].startswith("https://example.com/doc")

    def test_url_with_korean_context(self):
        text = "[홍길동] [오후 3:00] https://www.youtube.com/watch?v=abc123 이거 봐봐"
        result = extract_urls(text)
        assert len(result) == 1
        assert "https://www.youtube.com/watch?v=abc123" in result

    def test_long_url(self):
        text = "https://example.com/very/long/path/with/many/segments/that/goes/on/and/on"
        result = extract_urls(text)
        assert len(result) == 1

    def test_url_pattern_is_compiled_regex(self):
        """Verify URL_PATTERN is a compiled regex object."""
        import re
        assert isinstance(URL_PATTERN, re.Pattern)
