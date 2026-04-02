#!/usr/bin/env python3
"""Tests for the improvement-executor execute module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# repo root for lib.common imports
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
REPO_ROOT = _REPO_ROOT

_execute_path = REPO_ROOT / "skills" / "improvement-executor" / "scripts" / "execute.py"
_spec = importlib.util.spec_from_file_location("execute", _execute_path)
execute = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(execute)


# ---------------------------------------------------------------------------
# capture_execution_trace
# ---------------------------------------------------------------------------


class TestCaptureExecutionTrace:
    def test_basic_structure(self):
        candidate = {
            "id": "cand-01-readme",
            "category": "docs",
            "target_path": "/tmp/skill/README.md",
            "execution_plan": {"action": "append_markdown_section"},
        }
        result = {
            "status": "success",
            "modified": True,
            "diff_summary": {"reason": "appended section", "added_lines": 4},
        }
        trace = execute.capture_execution_trace(candidate, result)

        assert trace["type"] == "execution_trace"
        assert trace["candidate_id"] == "cand-01-readme"
        assert trace["category"] == "docs"
        assert trace["target_path"] == "/tmp/skill/README.md"
        assert trace["action"] == "append_markdown_section"
        assert trace["execution_status"] == "success"
        assert trace["modified"] is True
        assert trace["diff_summary"]["added_lines"] == 4
        assert trace["error"] is None
        assert "timestamp" in trace

    def test_with_error(self):
        candidate = {"id": "cand-02-ref", "category": "reference"}
        result = {"status": "failed", "modified": False}
        trace = execute.capture_execution_trace(
            candidate, result, error="file not found"
        )
        assert trace["error"] == "file not found"
        assert trace["execution_status"] == "failed"

    def test_missing_fields_default_gracefully(self):
        trace = execute.capture_execution_trace({}, {})
        assert trace["candidate_id"] == "unknown"
        assert trace["category"] == "unknown"
        assert trace["action"] == "unknown"
        assert trace["execution_status"] == "unknown"
        assert trace["modified"] is False


# ---------------------------------------------------------------------------
# append_markdown_section
# ---------------------------------------------------------------------------


class TestAppendMarkdownSection:
    def test_appends_new_section(self, tmp_path):
        md_file = tmp_path / "README.md"
        md_file.write_text("# My Skill\n\nSome content.\n", encoding="utf-8")

        plan = {
            "section_heading": "## Operator Notes",
            "content_lines": [
                "This skill is advisory.",
                "Pair with external tooling.",
            ],
        }
        result = execute.append_markdown_section(md_file, plan)

        assert result["status"] == "success"
        assert result["modified"] is True
        assert result["diff_summary"]["added_lines"] == 4  # heading + blank + 2 lines
        after = md_file.read_text(encoding="utf-8")
        assert "## Operator Notes" in after
        assert "- This skill is advisory." in after
        assert "- Pair with external tooling." in after

    def test_no_change_when_section_exists(self, tmp_path):
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# My Skill\n\n## Operator Notes\n\n- Already here.\n",
            encoding="utf-8",
        )

        plan = {
            "section_heading": "## Operator Notes",
            "content_lines": ["New line."],
        }
        result = execute.append_markdown_section(md_file, plan)

        assert result["status"] == "no_change"
        assert result["modified"] is False
        assert result["diff_summary"]["added_lines"] == 0

    def test_diff_is_valid_unified_diff(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n", encoding="utf-8")

        plan = {
            "section_heading": "## New Section",
            "content_lines": ["Line one."],
        }
        result = execute.append_markdown_section(md_file, plan)

        assert result["diff"].startswith("---")
        assert "@@" in result["diff"]
        assert "+## New Section" in result["diff"]
