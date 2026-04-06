#!/usr/bin/env python3
"""Tests for the adversarial test generator."""

import sys
from pathlib import Path

import pytest
import yaml

# Add paths for imports
_SKILL_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SKILL_ROOT.parents[2]
sys.path.insert(0, str(_SKILL_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT))

from adversarial_generator import (
    generate_mock_suite,
    load_skill,
    parse_args,
    _extract_skill_id,
    _pick_confusion_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def skill_dir(tmp_path):
    """Create a minimal skill directory with SKILL.md."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\nname: test-skill\ncategory: tool\n---\n\n"
        "# Test Skill\n\nThis skill reviews code for quality.\n\n"
        "## Trigger\nWhen asked to review code.\n\n"
        "## Output\nA review report with findings.\n"
    )
    return tmp_path


@pytest.fixture
def deslop_skill_dir(tmp_path):
    """Create a skill directory that looks like deslop."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\nname: deslop\n---\n\n"
        "# Deslop\n\nRemove AI patterns from text.\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# TestParseArgs
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_required_skill_path(self):
        with pytest.raises(SystemExit):
            parse_args([])

    def test_defaults(self):
        args = parse_args(["--skill-path", "/some/skill"])
        assert args.skill_path == "/some/skill"
        assert args.output == "adversarial_suite.yaml"
        assert args.mock is False

    def test_mock_flag(self):
        args = parse_args(["--skill-path", "/s", "--mock"])
        assert args.mock is True

    def test_custom_output(self):
        args = parse_args(["--skill-path", "/s", "--output", "out.yaml"])
        assert args.output == "out.yaml"


# ---------------------------------------------------------------------------
# TestLoadSkill
# ---------------------------------------------------------------------------


class TestLoadSkill:
    def test_load_from_directory(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        assert "Test Skill" in content
        assert skill_id == "test-skill"

    def test_load_from_file(self, skill_dir):
        content, skill_id = load_skill(skill_dir / "SKILL.md")
        assert "Test Skill" in content
        assert skill_id == "test-skill"

    def test_missing_skill_md(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="SKILL.md not found"):
            load_skill(tmp_path)

    def test_fallback_skill_id(self, tmp_path):
        """When no frontmatter name, uses parent directory name."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# No Frontmatter\nJust content.")
        _, skill_id = load_skill(tmp_path)
        assert skill_id == tmp_path.name


# ---------------------------------------------------------------------------
# TestMockGeneration
# ---------------------------------------------------------------------------


class TestMockGeneration:
    def test_generates_valid_yaml(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)

        # Validate top-level structure
        assert suite["skill_id"] == "test-skill"
        assert suite["version"] == "1.0"
        assert "tasks" in suite
        assert isinstance(suite["tasks"], list)
        assert len(suite["tasks"]) == 5

    def test_task_ids_unique(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)
        ids = [t["id"] for t in suite["tasks"]]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_task_ids_prefixed(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)
        for task in suite["tasks"]:
            assert task["id"].startswith("adv-"), f"ID not prefixed: {task['id']}"

    def test_all_tasks_have_required_fields(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)
        for task in suite["tasks"]:
            assert "id" in task
            assert "prompt" in task and task["prompt"]
            assert "judge" in task
            assert task["judge"]["type"] == "llm-rubric"
            assert "rubric" in task["judge"]
            assert task["judge"].get("pass_threshold", 0) > 0

    def test_suite_compatible_with_evaluator_schema(self, skill_dir, tmp_path):
        """Validate the output against the evaluator's _validate_suite_schema."""
        from evaluate import _validate_suite_schema

        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)
        # Should not raise
        _validate_suite_schema(suite)

    def test_yaml_roundtrip(self, skill_dir, tmp_path):
        """Suite can be written to YAML and re-read without loss."""
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)

        out = tmp_path / "suite.yaml"
        with out.open("w") as f:
            yaml.dump(suite, f, default_flow_style=False, allow_unicode=True)

        reloaded = yaml.safe_load(out.read_text())
        assert reloaded["skill_id"] == suite["skill_id"]
        assert len(reloaded["tasks"]) == len(suite["tasks"])
        for orig, loaded in zip(suite["tasks"], reloaded["tasks"]):
            assert orig["id"] == loaded["id"]

    def test_contains_expected_adversarial_types(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)
        ids = {t["id"] for t in suite["tasks"]}
        assert "adv-empty-input" in ids
        assert "adv-long-input" in ids
        assert "adv-wrong-language" in ids
        assert "adv-domain-confusion" in ids
        assert "adv-conflicting-instructions" in ids

    def test_long_input_is_actually_long(self, skill_dir):
        content, skill_id = load_skill(skill_dir)
        suite = generate_mock_suite(content, skill_id)
        long_task = next(t for t in suite["tasks"] if t["id"] == "adv-long-input")
        assert len(long_task["prompt"]) > 5000


# ---------------------------------------------------------------------------
# TestDomainConfusion
# ---------------------------------------------------------------------------


class TestDomainConfusion:
    def test_picks_different_domain(self):
        """Should pick a confusion prompt from a domain the skill is NOT about."""
        skill_about_review = "This skill reviews code for quality issues."
        prompt = _pick_confusion_prompt(skill_about_review)
        # Should NOT pick the "review" confusion prompt since the skill IS about review
        assert "Deploy this code" not in prompt

    def test_deslop_gets_non_deslop_confusion(self, deslop_skill_dir):
        content, _ = load_skill(deslop_skill_dir)
        prompt = _pick_confusion_prompt(content)
        # deslop confusion prompt is about cover letters -- skill is about deslop
        # so it should pick something else
        assert "cover letter" not in prompt

    def test_unknown_domain_gets_some_confusion_prompt(self):
        """Skills matching no known domain get a confusion prompt from any domain."""
        prompt = _pick_confusion_prompt("This skill juggles flaming chainsaws.")
        assert len(prompt) > 20  # got a real prompt, not empty

    def test_all_domains_matched_gets_fallback(self):
        """When skill matches ALL known domains, fallback to the default prompt."""
        # Stuff every domain keyword into one string
        everything = "review test security improve deslop"
        prompt = _pick_confusion_prompt(everything)
        assert "derivative" in prompt


# ---------------------------------------------------------------------------
# TestExtractSkillId
# ---------------------------------------------------------------------------


class TestExtractSkillId:
    def test_from_name_field(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\nname: my-cool-skill\n---\n# Skill")
        assert _extract_skill_id(p.read_text(), p) == "my-cool-skill"

    def test_from_skill_id_field(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text('---\nskill_id: "another-skill"\n---\n# Skill')
        assert _extract_skill_id(p.read_text(), p) == "another-skill"

    def test_fallback_to_dirname(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("# No frontmatter")
        result = _extract_skill_id(p.read_text(), p)
        assert result == tmp_path.name
