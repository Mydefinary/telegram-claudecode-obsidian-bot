"""Tests for evaluator.py - parse_eval_result() function."""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Mock analyzer module's dependencies before importing evaluator
# evaluator.py imports _run_claude from analyzer, which triggers prompt loading
_mock_prompts = {
    "link_analysis": "mock",
    "text_analysis": "mock",
    "image_analysis": "mock",
    "dedup": "mock",
    "eval": "mock eval prompt",
    "fail_patterns": [],
    "meta_patterns": [],
}

with patch("prompts.get_prompts", return_value=_mock_prompts):
    from evaluator import parse_eval_result, _FIELD_MAP, _SCORE_FIELDS


class TestParseEvalResultKorean:
    """Tests for parse_eval_result() with Korean format output."""

    KOREAN_EVAL = """\
최신성: 4
실용성: 5
신뢰도: 3
깊이: 4
개발자적합성: 5
클코적용성: 4
종합등급: A
한줄평: 멀티에이전트 패턴의 실무 적용 가이드로서 높은 가치
클코팁: CLAUDE.md에 에이전트 오케스트레이션 패턴 규칙 추가
팁설명: 여러 서브에이전트를 효율적으로 관리하는 규칙을 설정
처리유형: global
권장도: 5
유형근거: 모든 프로젝트에 범용 적용 가능한 원칙
스킬명: multi-agent-orchestration
태그: multi-agent, claude-code, orchestration, automation"""

    def test_scores_parsed_correctly(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert result["freshness"] == 4
        assert result["practicality"] == 5
        assert result["reliability"] == 3
        assert result["depth"] == 4
        assert result["relevance"] == 5
        assert result["claude_code"] == 4

    def test_grade_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert result["grade"] == "A"

    def test_summary_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert "멀티에이전트" in result["summary"]

    def test_tip_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert "에이전트 오케스트레이션" in result["tip"]

    def test_tip_desc_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert "서브에이전트" in result["tip_desc"]

    def test_tip_action_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert result["tip_action"] == "global"

    def test_tip_confidence_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert result["tip_confidence"] == 5

    def test_tip_action_reason_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert "범용" in result["tip_action_reason"]

    def test_skill_name_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert result["skill_name"] == "multi-agent-orchestration"

    def test_tags_parsed(self):
        result = parse_eval_result(self.KOREAN_EVAL)
        assert isinstance(result["tags"], list)
        assert "multi-agent" in result["tags"]
        assert "claude-code" in result["tags"]
        assert "orchestration" in result["tags"]
        assert "automation" in result["tags"]


class TestParseEvalResultEnglish:
    """Tests for parse_eval_result() with English format output."""

    ENGLISH_EVAL = """\
Freshness: 3
Practicality: 4
Reliability: 5
Depth: 3
DevRelevance: 4
ClaudeCodeApplicability: 2
Grade: B
OneLiner: Solid overview of testing strategies for modern web apps
CCTip: Add pre-commit hook that runs pytest before allowing commits
TipDesc: Ensures all tests pass before any code is committed to the repo
Action: skill
Confidence: 4
ActionReason: Useful as an on-demand workflow rather than a global rule
SkillName: pre-commit-test
Tags: testing, pytest, git, ci-cd"""

    def test_scores_parsed_correctly(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert result["freshness"] == 3
        assert result["practicality"] == 4
        assert result["reliability"] == 5
        assert result["depth"] == 3
        assert result["relevance"] == 4
        assert result["claude_code"] == 2

    def test_grade_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert result["grade"] == "B"

    def test_summary_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert "testing strategies" in result["summary"]

    def test_tip_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert "pre-commit" in result["tip"]

    def test_tip_action_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert result["tip_action"] == "skill"

    def test_tip_confidence_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert result["tip_confidence"] == 4

    def test_skill_name_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert result["skill_name"] == "pre-commit-test"

    def test_tags_parsed(self):
        result = parse_eval_result(self.ENGLISH_EVAL)
        assert "testing" in result["tags"]
        assert "pytest" in result["tags"]
        assert "git" in result["tags"]
        assert "ci-cd" in result["tags"]


class TestParseEvalResultEdgeCases:
    """Edge case tests for parse_eval_result()."""

    def test_empty_string(self):
        result = parse_eval_result("")
        assert result["grade"] == "D"
        assert result["freshness"] == 0
        assert result["tags"] == []

    def test_no_tip(self):
        text = """\
최신성: 2
실용성: 2
신뢰도: 3
깊이: 2
개발자적합성: 1
클코적용성: 1
종합등급: D
한줄평: 일반적인 뉴스 기사로 개발자에게 실용적 가치 낮음
클코팁: 없음
팁설명: 없음
처리유형: 없음
권장도: 0
유형근거: 없음
스킬명: 없음
태그: 없음"""
        result = parse_eval_result(text)
        assert result["tip"] == "없음"
        assert result["tags"] == []
        assert result["skill_name"] == "없음"

    def test_partial_output(self):
        """Parser should handle incomplete output gracefully."""
        text = "최신성: 3\n실용성: 4\n종합등급: C"
        result = parse_eval_result(text)
        assert result["freshness"] == 3
        assert result["practicality"] == 4
        assert result["grade"] == "C"
        # Unspecified fields should have defaults
        assert result["reliability"] == 0
        assert result["depth"] == 0
        assert result["tags"] == []

    def test_score_with_extra_text(self):
        """Scores may have extra text after the number."""
        text = "최신성: 4점 (최신 트렌드)\n실용성: 5점"
        result = parse_eval_result(text)
        assert result["freshness"] == 4
        assert result["practicality"] == 5

    def test_grade_extracts_first_char(self):
        """Grade should only take the first character."""
        text = "종합등급: B+ (우수)"
        result = parse_eval_result(text)
        assert result["grade"] == "B"

    def test_tags_comma_separated(self):
        text = "태그: python, async, testing, multi-agent"
        result = parse_eval_result(text)
        assert len(result["tags"]) == 4
        assert "python" in result["tags"]
        assert "async" in result["tags"]

    def test_tags_none_value_returns_empty_list(self):
        text = "태그: 없음"
        result = parse_eval_result(text)
        assert result["tags"] == []

    def test_unknown_keys_ignored(self):
        text = "알 수 없는키: 값\n최신성: 3"
        result = parse_eval_result(text)
        assert result["freshness"] == 3

    def test_lines_without_colon_ignored(self):
        text = "이것은 그냥 텍스트입니다\n최신성: 4\n더 많은 텍스트"
        result = parse_eval_result(text)
        assert result["freshness"] == 4


class TestFieldMappings:
    """Tests to verify field mapping dictionaries are correct."""

    def test_korean_field_map_covers_all_output_fields(self):
        expected_ko_keys = {
            "최신성", "실용성", "신뢰도", "깊이", "개발자적합성", "클코적용성",
            "종합등급", "한줄평", "클코팁", "팁설명", "처리유형", "권장도",
            "유형근거", "스킬명", "태그",
        }
        for key in expected_ko_keys:
            assert key in _FIELD_MAP, f"Missing Korean key: {key}"

    def test_english_field_map_covers_all_output_fields(self):
        expected_en_keys = {
            "Freshness", "Practicality", "Reliability", "Depth",
            "DevRelevance", "ClaudeCodeApplicability",
            "Grade", "OneLiner", "CCTip", "TipDesc", "Action", "Confidence",
            "ActionReason", "SkillName", "Tags",
        }
        for key in expected_en_keys:
            assert key in _FIELD_MAP, f"Missing English key: {key}"

    def test_score_fields_are_numeric(self):
        """All score fields should map to known numeric field names."""
        expected_score_fields = {
            "freshness", "practicality", "reliability",
            "depth", "relevance", "claude_code", "tip_confidence",
        }
        assert _SCORE_FIELDS == expected_score_fields
