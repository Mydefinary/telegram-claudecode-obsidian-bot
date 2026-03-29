"""Tests for obsidian_writer.py - file writing and formatting."""

import os
import pytest
from unittest.mock import patch


class TestSanitizeFilename:
    """Tests for sanitize_filename() function."""

    def test_basic_filename(self):
        from obsidian_writer import sanitize_filename
        assert sanitize_filename("my_note") == "my_note"

    def test_removes_angle_brackets(self):
        from obsidian_writer import sanitize_filename
        assert "<" not in sanitize_filename("note<test>")
        assert ">" not in sanitize_filename("note<test>")

    def test_removes_colon(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("Title: Subtitle")
        assert ":" not in result

    def test_removes_quotes(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename('He said "hello"')
        assert '"' not in result

    def test_removes_backslash(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("path\\to\\file")
        assert "\\" not in result

    def test_removes_forward_slash(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("path/to/file")
        assert "/" not in result

    def test_removes_pipe(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("choice|option")
        assert "|" not in result

    def test_removes_question_mark(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("what is this?")
        assert "?" not in result

    def test_removes_asterisk(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("bold*text*")
        assert "*" not in result

    def test_strips_dots_and_spaces(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("...test...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_truncates_long_name(self):
        from obsidian_writer import sanitize_filename
        long_name = "a" * 100
        result = sanitize_filename(long_name)
        assert len(result) <= 80

    def test_empty_string_returns_untitled(self):
        from obsidian_writer import sanitize_filename
        assert sanitize_filename("") == "untitled"

    def test_all_special_chars_returns_untitled(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename(':<>"/\\|?*')
        # After removing all chars and stripping, empty -> "untitled"
        assert result == "untitled"

    def test_korean_filename(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("AI 개발 트렌드 2026")
        assert result == "AI 개발 트렌드 2026"

    def test_mixed_special_and_normal_chars(self):
        from obsidian_writer import sanitize_filename
        result = sanitize_filename("C++ 메모리 관리: 심화 가이드")
        assert ":" not in result
        assert "C++ 메모리 관리" in result


class TestFormatOriginalSection:
    """Tests for _format_original_section() function."""

    def test_empty_string(self):
        from obsidian_writer import _format_original_section
        assert _format_original_section("") == ""

    def test_none_value(self):
        from obsidian_writer import _format_original_section
        assert _format_original_section(None) == ""

    def test_whitespace_only(self):
        from obsidian_writer import _format_original_section
        assert _format_original_section("   \n  ") == ""

    def test_normal_text(self):
        from obsidian_writer import _format_original_section
        result = _format_original_section("Hello World\nSecond line")
        assert "> [!quote]- 원본 보기" in result
        assert "> Hello World" in result
        assert "> Second line" in result

    def test_starts_with_separator(self):
        from obsidian_writer import _format_original_section
        result = _format_original_section("Some content")
        assert result.startswith("\n\n---\n")

    def test_long_text_truncated(self):
        from obsidian_writer import _format_original_section
        long_text = "x" * 6000
        result = _format_original_section(long_text)
        assert "...(truncated)" in result

    def test_text_under_5000_not_truncated(self):
        from obsidian_writer import _format_original_section
        text = "x" * 4000
        result = _format_original_section(text)
        assert "...(truncated)" not in result

    def test_multiline_all_quoted(self):
        from obsidian_writer import _format_original_section
        text = "Line 1\nLine 2\nLine 3"
        result = _format_original_section(text)
        lines = result.strip().split("\n")
        # After the header line, all content lines should start with "> "
        content_lines = [l for l in lines if not l.startswith("---") and not l.startswith("> [!quote]")]
        for line in content_lines:
            if line.strip():
                assert line.startswith("> ")


class TestSaveNote:
    """Tests for save_note() function."""

    def test_creates_file(self, tmp_path):
        """save_note should create a markdown file in the vault."""
        vault_path = str(tmp_path)
        folder = "test_folder"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(
                title="Test Note",
                content="### Summary\nThis is test content.",
                source_url="https://example.com",
                source_type="link",
            )

        assert os.path.exists(filepath)
        assert filepath.endswith(".md")

    def test_file_content_has_frontmatter(self, tmp_path):
        """Saved file should contain YAML frontmatter."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(
                title="Frontmatter Test",
                content="Content here.",
                source_url="https://example.com",
                source_type="link",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        assert content.startswith("---\n")
        assert "source: link" in content
        assert 'url: "https://example.com"' in content
        assert "via: telegram-bot" in content

    def test_file_content_has_title_header(self, tmp_path):
        """Saved file should contain a H1 title."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(
                title="My Title",
                content="Some content.",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        assert "# My Title" in content

    def test_file_content_has_body(self, tmp_path):
        """Saved file should contain the analysis content."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(
                title="Body Test",
                content="### Key Points\n- Point 1\n- Point 2",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        assert "### Key Points" in content
        assert "- Point 1" in content

    def test_creates_folder_if_not_exists(self, tmp_path):
        """save_note should create the folder structure if it doesn't exist."""
        vault_path = str(tmp_path)
        folder = "deep/nested/folder"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(title="Nested Test", content="Content.")

        assert os.path.exists(filepath)

    def test_duplicate_filename_gets_counter(self, tmp_path):
        """If a file with the same name exists, a counter suffix should be added."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath1 = save_note(title="Duplicate", content="First.")
            filepath2 = save_note(title="Duplicate", content="Second.")

        assert filepath1 != filepath2
        assert os.path.exists(filepath1)
        assert os.path.exists(filepath2)
        assert "Duplicate_1.md" in filepath2

    def test_no_title_uses_timestamp(self, tmp_path):
        """If title is empty, filename should use timestamp format."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(title="", content="No title content.")

        filename = os.path.basename(filepath)
        assert filename.startswith("note_")

    def test_original_content_included(self, tmp_path):
        """If original_content is provided, it should appear as a callout."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(
                title="With Original",
                content="Analysis result.",
                original_content="This is the original text.",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        assert "> [!quote]- 원본 보기" in content
        assert "> This is the original text." in content

    def test_no_original_content(self, tmp_path):
        """If no original_content, the callout section should not appear."""
        vault_path = str(tmp_path)
        folder = "notes"

        with patch("obsidian_writer.OBSIDIAN_VAULT_PATH", vault_path), \
             patch("obsidian_writer.OBSIDIAN_FOLDER", folder):
            from obsidian_writer import save_note
            filepath = save_note(
                title="No Original",
                content="Just analysis.",
            )

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        assert "원본 보기" not in content
