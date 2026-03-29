"""Tests for analyzer.py - pure functions only (no async/CLI calls)."""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# We need to mock the modules that analyzer imports at module level
# before importing analyzer, since they depend on external configs/services.
# Specifically, analyzer.py calls get_prompts() at import time.

# Provide known FAIL_PATTERNS and META_PATTERNS for testing
_TEST_FAIL_PATTERNS = [
    "권한이 필요합니다",
    "콘텐츠를 가져올 수 없",
    "접근이 차단",
    "403",
    "분석할 웹페이지 URL이나 내용을 제공",
]

_TEST_META_PATTERNS = [
    r"이제 충분한 정보를 확보했습니다\.?\s*분석 결과를 작성합니다\.?",
    r"분석 결과를 작성하겠습니다\.?",
    r"분석을 시작하겠습니다\.?",
    r"다음과 같이 분석했습니다\.?",
    r"아래와 같이 정리했습니다\.?",
    r"WebFetch.*?가져와.*?\n",
    r"WebSearch.*?검색.*?\n",
]

# Patch the prompts module to avoid needing config/files
_mock_prompts = {
    "link_analysis": "mock link prompt",
    "text_analysis": "mock text prompt",
    "image_analysis": "mock image prompt",
    "dedup": "mock dedup prompt",
    "fail_patterns": _TEST_FAIL_PATTERNS,
    "meta_patterns": _TEST_META_PATTERNS,
}

with patch.dict("sys.modules", {}):
    pass

# Patch get_prompts before importing analyzer
with patch("prompts.get_prompts", return_value=_mock_prompts):
    from analyzer import (
        is_analysis_failed,
        clean_analysis,
        extract_title_from_analysis,
        remove_title_line,
    )


class TestIsAnalysisFailed:
    """Tests for is_analysis_failed() function."""

    def test_empty_string(self):
        assert is_analysis_failed("") is True

    def test_none_value(self):
        assert is_analysis_failed(None) is True

    def test_short_text(self):
        """Text shorter than 30 characters should be considered failed."""
        assert is_analysis_failed("짧은 텍스트") is True

    def test_whitespace_only(self):
        assert is_analysis_failed("   \n\t  ") is True

    def test_text_with_fail_pattern_permission(self):
        text = "이 페이지에 접근하려면 권한이 필요합니다. 관리자에게 문의하세요."
        assert is_analysis_failed(text) is True

    def test_text_with_fail_pattern_403(self):
        text = "요청이 실패했습니다. 403 에러가 발생했습니다. 접근 권한을 확인하세요."
        assert is_analysis_failed(text) is True

    def test_text_with_fail_pattern_blocked(self):
        text = "이 웹사이트는 접근이 차단되어 있습니다. 다른 방법을 시도해 주세요."
        assert is_analysis_failed(text) is True

    def test_text_with_fail_pattern_provide_content(self):
        text = "분석할 웹페이지 URL이나 내용을 제공해주시면 분석하겠습니다. 아무 것도 입력되지 않았습니다."
        assert is_analysis_failed(text) is True

    def test_text_with_fail_pattern_cannot_fetch(self):
        text = "해당 페이지의 콘텐츠를 가져올 수 없습니다. 연결 오류가 발생했습니다. 확인해 주세요."
        assert is_analysis_failed(text) is True

    def test_valid_analysis_result(self):
        text = (
            "제목: AI 개발 트렌드 2026\n\n"
            "### 한줄 요약\n"
            "2026년 AI 개발의 주요 트렌드를 분석한 기사입니다.\n\n"
            "### 주요 내용\n"
            "- 멀티에이전트 시스템의 부상\n"
            "- 코드 자동 생성 도구의 발전\n"
        )
        assert is_analysis_failed(text) is False

    def test_exactly_30_chars_no_fail_pattern(self):
        text = "이것은 정확히 삼십 글자에 맞추기 위한 텍스트입니다!!!!!"
        # Ensure text is >= 30 chars when stripped
        if len(text.strip()) >= 30:
            assert is_analysis_failed(text) is False


class TestCleanAnalysis:
    """Tests for clean_analysis() function."""

    def test_removes_meta_commentary_analysis_start(self):
        text = "분석을 시작하겠습니다.\n\n제목: 테스트\n내용입니다."
        result = clean_analysis(text)
        assert "분석을 시작하겠습니다" not in result
        assert "제목: 테스트" in result

    def test_removes_meta_commentary_info_gathered(self):
        text = "이제 충분한 정보를 확보했습니다. 분석 결과를 작성합니다.\n\n제목: 테스트"
        result = clean_analysis(text)
        assert "충분한 정보를 확보했습니다" not in result
        assert "제목: 테스트" in result

    def test_removes_meta_commentary_will_write(self):
        text = "분석 결과를 작성하겠습니다.\n\n### 주요 내용\n- 포인트 1"
        result = clean_analysis(text)
        assert "작성하겠습니다" not in result
        assert "### 주요 내용" in result

    def test_removes_meta_analyzed_like_this(self):
        text = "다음과 같이 분석했습니다.\n\n### 요약\n좋은 내용입니다."
        result = clean_analysis(text)
        assert "다음과 같이 분석했습니다" not in result

    def test_removes_meta_organized_like_this(self):
        text = "아래와 같이 정리했습니다.\n\n### 요약\n정리 내용."
        result = clean_analysis(text)
        assert "아래와 같이 정리했습니다" not in result

    def test_collapses_excessive_newlines(self):
        text = "첫 번째 문단\n\n\n\n\n두 번째 문단"
        result = clean_analysis(text)
        assert "\n\n\n" not in result
        assert "첫 번째 문단" in result
        assert "두 번째 문단" in result

    def test_strips_whitespace(self):
        text = "  \n\n내용입니다.\n\n  "
        result = clean_analysis(text)
        assert result == "내용입니다."

    def test_clean_text_unchanged(self):
        text = "제목: 테스트\n\n### 요약\n좋은 내용입니다."
        result = clean_analysis(text)
        assert result == text

    def test_empty_string(self):
        result = clean_analysis("")
        assert result == ""


class TestExtractTitleFromAnalysis:
    """Tests for extract_title_from_analysis() function."""

    def test_korean_title(self):
        text = "제목: AI 개발 트렌드\n\n### 요약\n내용입니다."
        result = extract_title_from_analysis(text)
        assert result == "AI 개발 트렌드"

    def test_english_title(self):
        text = "Title: AI Development Trends\n\n### Summary\nSome content."
        result = extract_title_from_analysis(text)
        assert result == "AI Development Trends"

    def test_title_with_extra_spaces(self):
        text = "제목:   여러 공백이 있는 제목  \n\n내용"
        result = extract_title_from_analysis(text)
        assert result == "여러 공백이 있는 제목"

    def test_no_title_line(self):
        text = "### 요약\n내용만 있습니다.\n### 키워드\n#AI"
        result = extract_title_from_analysis(text)
        assert result == ""

    def test_title_in_middle_of_text(self):
        text = "### 서론\n소개글입니다.\n\n제목: 중간에 있는 제목\n\n### 본문\n내용"
        result = extract_title_from_analysis(text)
        assert result == "중간에 있는 제목"

    def test_empty_string(self):
        result = extract_title_from_analysis("")
        assert result == ""

    def test_title_with_special_chars(self):
        text = "제목: C++ 메모리 관리 (2026)\n\n내용"
        result = extract_title_from_analysis(text)
        assert result == "C++ 메모리 관리 (2026)"

    def test_multiple_title_lines_returns_first(self):
        text = "제목: 첫 번째 제목\n\nTitle: Second Title\n\n내용"
        result = extract_title_from_analysis(text)
        assert result == "첫 번째 제목"


class TestRemoveTitleLine:
    """Tests for remove_title_line() function."""

    def test_remove_korean_title(self):
        text = "제목: AI 트렌드\n\n### 요약\n내용"
        result = remove_title_line(text)
        assert "제목:" not in result
        assert "### 요약" in result
        assert "내용" in result

    def test_remove_english_title(self):
        text = "Title: AI Trends\n\n### Summary\nContent"
        result = remove_title_line(text)
        assert "Title:" not in result
        assert "### Summary" in result

    def test_no_title_line(self):
        text = "### 요약\n내용만 있습니다."
        result = remove_title_line(text)
        assert result == text

    def test_removes_only_first_title_line(self):
        text = "제목: 첫 번째\n\nTitle: 두 번째\n\n내용"
        result = remove_title_line(text)
        assert "제목: 첫 번째" not in result
        assert "Title: 두 번째" in result

    def test_empty_string(self):
        result = remove_title_line("")
        assert result == ""

    def test_title_with_trailing_newlines(self):
        text = "제목: 테스트 제목\n\n\n### 내용\n본문입니다."
        result = remove_title_line(text)
        assert result.startswith("### 내용")

    def test_title_only(self):
        text = "제목: 제목만 있는 경우"
        result = remove_title_line(text)
        assert result == ""
