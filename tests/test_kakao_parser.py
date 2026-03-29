"""Tests for kakao_parser.py - KakaoTalk export parsing."""

import pytest
from kakao_parser import is_kakao_format, parse_kakao_txt, DATE_HEADER, MSG_PREFIX


class TestIsKakaoFormat:
    """Tests for is_kakao_format() function."""

    def test_with_date_header(self):
        text = "--------------- 2026년 3월 29일 토요일 ---------------\n[홍길동] [오후 3:00] 안녕하세요"
        assert is_kakao_format(text) is True

    def test_with_message_only(self):
        text = "[홍길동] [오후 3:00] 안녕하세요\n[김철수] [오후 3:01] 네 안녕하세요"
        assert is_kakao_format(text) is True

    def test_with_am_message(self):
        text = "[홍길동] [오전 9:30] 좋은 아침이에요"
        assert is_kakao_format(text) is True

    def test_plain_text_not_kakao(self):
        text = "This is just a regular text message\nwith multiple lines\nbut no kakao format"
        assert is_kakao_format(text) is False

    def test_empty_string(self):
        assert is_kakao_format("") is False

    def test_url_only_not_kakao(self):
        text = "https://example.com\nhttps://another.com"
        assert is_kakao_format(text) is False

    def test_similar_but_not_kakao(self):
        text = "[name] some text here\n[other] more text"
        assert is_kakao_format(text) is False

    def test_detection_within_first_20_lines(self):
        """is_kakao_format only checks the first 20 lines."""
        lines = ["일반 텍스트입니다."] * 25
        lines[19] = "--------------- 2026년 3월 29일 토요일 ---------------"
        text = "\n".join(lines)
        assert is_kakao_format(text) is True

    def test_detection_beyond_20_lines_fails(self):
        """Kakao format beyond line 20 should not be detected."""
        lines = ["일반 텍스트입니다."] * 25
        lines[21] = "--------------- 2026년 3월 29일 토요일 ---------------"
        text = "\n".join(lines)
        assert is_kakao_format(text) is False


class TestParseKakaoTxt:
    """Tests for parse_kakao_txt() function."""

    def test_simple_messages(self):
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 안녕하세요\n"
            "[김철수] [오후 3:01] 네 반갑습니다\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 2
        assert "안녕하세요" in posts[0]
        assert "네 반갑습니다" in posts[1]

    def test_skip_photo_messages(self):
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 사진\n"
            "[홍길동] [오후 3:01] 진짜 메시지\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "진짜 메시지" in posts[0]

    def test_skip_video_messages(self):
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 동영상\n"
            "[홍길동] [오후 3:01] 텍스트 메시지\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "텍스트 메시지" in posts[0]

    def test_skip_file_messages(self):
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 파일: document.pdf\n"
            "[홍길동] [오후 3:01] 이 문서 참고하세요\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "이 문서 참고하세요" in posts[0]

    def test_url_grouping_url_then_description(self):
        """URL-only message followed by short description should be grouped."""
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] https://example.com/article\n"
            "[홍길동] [오후 3:01] 이거 좋은 글이에요\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "https://example.com/article" in posts[0]
        assert "이거 좋은 글이에요" in posts[0]

    def test_url_grouping_description_then_url(self):
        """Short description followed by URL should be grouped."""
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 좋은 글 공유합니다\n"
            "[홍길동] [오후 3:01] https://example.com/article\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "좋은 글 공유합니다" in posts[0]
        assert "https://example.com/article" in posts[0]

    def test_multiline_message(self):
        """Messages with line breaks should be preserved as single message."""
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 첫 번째 줄\n"
            "두 번째 줄\n"
            "세 번째 줄\n"
            "[김철수] [오후 3:01] 다른 메시지\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 2
        assert "첫 번째 줄" in posts[0]
        assert "두 번째 줄" in posts[0]
        assert "세 번째 줄" in posts[0]

    def test_multiple_date_headers(self):
        text = (
            "--------------- 2026년 3월 28일 금요일 ---------------\n"
            "[홍길동] [오후 1:00] 어제 메시지\n"
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 오늘 메시지\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 2

    def test_empty_input(self):
        posts = parse_kakao_txt("")
        assert posts == []

    def test_only_date_headers(self):
        text = (
            "--------------- 2026년 3월 28일 금요일 ---------------\n"
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
        )
        posts = parse_kakao_txt(text)
        assert posts == []

    def test_long_text_as_independent_post(self):
        """A long text message without URL should stand alone."""
        long_msg = "이것은 아주 긴 메시지입니다. " * 50  # ~500+ chars
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            f"[홍길동] [오후 3:00] {long_msg}\n"
            "[김철수] [오후 3:01] 짧은 답변\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 2

    def test_url_with_surrounding_text_in_same_message(self):
        """URL embedded in a message with other text."""
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오후 3:00] 이 글 참고하세요 https://example.com/article 정말 좋아요\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "https://example.com/article" in posts[0]

    def test_am_time_format(self):
        text = (
            "--------------- 2026년 3월 29일 토요일 ---------------\n"
            "[홍길동] [오전 9:30] 좋은 아침이에요\n"
        )
        posts = parse_kakao_txt(text)
        assert len(posts) == 1
        assert "좋은 아침이에요" in posts[0]


class TestRegexPatterns:
    """Tests for DATE_HEADER and MSG_PREFIX regex patterns."""

    def test_date_header_matches_standard_format(self):
        line = "--------------- 2026년 3월 29일 토요일 ---------------"
        assert DATE_HEADER.match(line) is not None

    def test_date_header_with_different_day(self):
        line = "--------------- 2026년 12월 1일 월요일 ---------------"
        assert DATE_HEADER.match(line) is not None

    def test_date_header_no_match_plain_text(self):
        line = "This is not a date header"
        assert DATE_HEADER.match(line) is None

    def test_msg_prefix_afternoon(self):
        line = "[홍길동] [오후 3:00] 안녕하세요"
        match = MSG_PREFIX.match(line)
        assert match is not None
        assert match.group(1) == "홍길동"
        assert match.group(2) == "오후"
        assert match.group(3) == "안녕하세요"

    def test_msg_prefix_morning(self):
        line = "[김철수] [오전 11:30] 좋은 아침"
        match = MSG_PREFIX.match(line)
        assert match is not None
        assert match.group(1) == "김철수"
        assert match.group(2) == "오전"
        assert match.group(3) == "좋은 아침"

    def test_msg_prefix_single_digit_hour(self):
        line = "[이름] [오후 1:05] 메시지"
        match = MSG_PREFIX.match(line)
        assert match is not None

    def test_msg_prefix_double_digit_hour(self):
        line = "[이름] [오전 12:00] 자정 메시지"
        match = MSG_PREFIX.match(line)
        assert match is not None
