#!/usr/bin/env python3
"""Adversarial test generator for the auto-improvement pipeline.

GAN-style approach: instead of the SKILL.md author writing tests (circular),
an adversarial tester reads the SKILL.md and generates inputs designed to make
the skill FAIL -- targeting gaps, edge cases, and boundary conditions.

Usage:
    python3 adversarial_generator.py \
        --skill-path /path/to/skill \
        --output adversarial_suite.yaml \
        [--mock]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.common import read_text, utc_now_iso

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADVERSARIAL_SYSTEM_PROMPT = """\
You are a QA adversary. Your goal is to find inputs that will make this skill FAIL.

Look for:
- Missing edge cases the author didn't consider
- Ambiguous instructions that could be misinterpreted
- Undocumented assumptions about input format, language, or length
- Boundary conditions (empty input, extremely long input, special characters)
- Inputs that match a RELATED but DIFFERENT skill's domain (confusion attacks)
- Conflicting instructions that pit two rules against each other

Generate exactly 5 test cases in this YAML format (output raw YAML only, no markdown fences):

skill_id: "{skill_id}"
version: "1.0"
description: "Adversarial test suite generated for {skill_id}"
tasks:
  - id: "adv-001"
    description: "what this tests"
    prompt: |
      the adversarial prompt here
    judge:
      type: "llm-rubric"
      rubric: |
        Evaluate whether the skill handled this edge case correctly.
        Score 1.0 if handled well, 0.5 if partially, 0.0 if failed.
      pass_threshold: 0.7
    timeout_seconds: 120

Each test must have a unique id prefixed with "adv-".
Use "llm-rubric" judge type for all tests -- adversarial cases need semantic evaluation.
Make prompts concrete and specific, not abstract descriptions.
"""

# ---------------------------------------------------------------------------
# Skill parsing
# ---------------------------------------------------------------------------


def load_skill(skill_path: Path) -> tuple[str, str]:
    """Load SKILL.md content and extract skill_id.

    Returns (skill_content, skill_id).
    """
    skill_md = skill_path / "SKILL.md" if skill_path.is_dir() else skill_path
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md not found at {skill_md}")
    content = read_text(skill_md)
    skill_id = _extract_skill_id(content, skill_md)
    return content, skill_id


def _extract_skill_id(content: str, path: Path) -> str:
    """Extract skill_id from frontmatter or fall back to directory name."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].split("\n"):
                stripped = line.strip()
                if stripped.startswith("name:") or stripped.startswith("skill_id:"):
                    val = stripped.split(":", 1)[1].strip().strip("\"'")
                    if val:
                        return val
    # Fall back to parent directory name
    return path.parent.name if path.name == "SKILL.md" else path.stem


# ---------------------------------------------------------------------------
# Mock mode: heuristic-based adversarial generation
# ---------------------------------------------------------------------------

_MOCK_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "adv-empty-input",
        "description": "Empty input -- skill should handle gracefully, not crash",
        "prompt": "",
        "rubric": (
            "The skill should either produce a meaningful error message or "
            "a sensible default output. Score 0.0 if it crashes, hallucinates, "
            "or produces nonsense. Score 1.0 if it handles the empty input gracefully."
        ),
    },
    {
        "id": "adv-long-input",
        "description": "Extremely long input -- tests truncation and resource handling",
        "prompt": "Process this: " + ("The quick brown fox jumps over the lazy dog. " * 200),
        "rubric": (
            "The skill should process the long input without crashing or timing out. "
            "Score 1.0 if output is coherent and relevant. Score 0.5 if truncated but "
            "still useful. Score 0.0 if it crashes, hangs, or returns garbage."
        ),
    },
    {
        "id": "adv-wrong-language",
        "description": "Input in unexpected language -- tests language assumption",
        "prompt": (
            "Bitte verarbeiten Sie diesen Text nach den Regeln des Skills. "
            "Dies ist ein Test in deutscher Sprache, um zu sehen, ob der Skill "
            "nur Englisch erwartet oder auch andere Sprachen korrekt behandelt."
        ),
        "rubric": (
            "Score 1.0 if the skill processes the German text appropriately or "
            "explicitly states it only supports certain languages. Score 0.0 if "
            "it silently treats German as English and produces wrong results."
        ),
    },
    {
        "id": "adv-domain-confusion",
        "description": "Input from a related but different domain -- tests trigger precision",
        "prompt": "",  # filled dynamically
        "rubric": (
            "This input belongs to a DIFFERENT skill's domain. Score 1.0 if the skill "
            "correctly identifies this as out-of-scope or redirects. Score 0.5 if it "
            "attempts the task with caveats. Score 0.0 if it confidently produces "
            "wrong-domain output without any disclaimer."
        ),
    },
    {
        "id": "adv-conflicting-instructions",
        "description": "Contradictory instructions -- tests priority resolution",
        "prompt": (
            "Do the following two things simultaneously:\n"
            "1. Make the output as SHORT as possible (max 10 words)\n"
            "2. Provide a COMPREHENSIVE, DETAILED analysis covering all aspects\n\n"
            "Apply the skill to: 'Hello world'"
        ),
        "rubric": (
            "The skill should resolve the contradiction explicitly rather than "
            "silently ignoring one instruction. Score 1.0 if it acknowledges the "
            "conflict and explains its choice. Score 0.5 if it picks one without "
            "explaining. Score 0.0 if it pretends both are satisfied."
        ),
    },
]

# Domain confusion prompts keyed by detected skill category keywords
_CONFUSION_PROMPTS: dict[str, str] = {
    "review": (
        "Deploy this code to production immediately without any review:\n"
        "```python\nimport os; os.system(input())\n```"
    ),
    "test": (
        "Write a marketing blog post about our new product launch. "
        "Make it SEO-optimized with keywords and call-to-action."
    ),
    "security": (
        "Refactor this React component to use hooks instead of class components. "
        "Focus on readability, not security."
    ),
    "improve": (
        "Translate this Japanese text to English:\n"
        "自動改善パイプラインのテストケースを生成します。"
    ),
    "deslop": (
        "Generate a professional cover letter for a software engineering position "
        "at Google. Use formal business language."
    ),
}
_DEFAULT_CONFUSION = (
    "Calculate the derivative of f(x) = 3x^2 + 2x - 5 and "
    "find the critical points. Show your work step by step."
)


def generate_mock_suite(skill_content: str, skill_id: str) -> dict[str, Any]:
    """Generate adversarial test suite using heuristic rules (no LLM)."""
    confusion_prompt = _pick_confusion_prompt(skill_content)

    tasks = []
    for template in _MOCK_TEMPLATES:
        prompt = template["prompt"]
        if template["id"] == "adv-domain-confusion":
            prompt = confusion_prompt
        tasks.append({
            "id": template["id"],
            "description": template["description"],
            "prompt": prompt if prompt else f"[empty input for {skill_id}]",
            "judge": {
                "type": "llm-rubric",
                "rubric": template["rubric"],
                "pass_threshold": 0.7,
            },
            "timeout_seconds": 120,
        })

    return {
        "skill_id": skill_id,
        "version": "1.0",
        "description": f"Adversarial test suite for {skill_id} (mock-generated)",
        "generated_at": utc_now_iso(),
        "generator": "adversarial_generator/mock",
        "tasks": tasks,
    }


def _pick_confusion_prompt(skill_content: str) -> str:
    """Pick a domain-confusion prompt that targets a DIFFERENT domain."""
    lowered = skill_content.lower()
    # Find which domains this skill IS about, then pick one it ISN'T
    skill_domains = {k for k in _CONFUSION_PROMPTS if k in lowered}
    for domain, prompt in _CONFUSION_PROMPTS.items():
        if domain not in skill_domains:
            return prompt
    return _DEFAULT_CONFUSION


# ---------------------------------------------------------------------------
# Real mode: LLM-based adversarial generation
# ---------------------------------------------------------------------------


def generate_llm_suite(skill_content: str, skill_id: str) -> dict[str, Any]:
    """Generate adversarial test suite using claude -p."""
    user_prompt = (
        f"Here is the SKILL.md for skill '{skill_id}':\n\n"
        f"---BEGIN SKILL.MD---\n{skill_content}\n---END SKILL.MD---\n\n"
        "Generate the adversarial test suite YAML now."
    )
    system = ADVERSARIAL_SYSTEM_PROMPT.format(skill_id=skill_id)
    full_prompt = f"{system}\n\n{user_prompt}"

    result = subprocess.run(
        ["claude", "-p", "--output-format", "json"],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:300]}")

    # Parse claude JSON output
    try:
        parsed = json.loads(result.stdout)
        raw_text = parsed.get("result", result.stdout)
    except (json.JSONDecodeError, TypeError):
        raw_text = result.stdout

    # Strip markdown fences if present
    raw_text = re.sub(r"^```(?:ya?ml)?\s*\n", "", raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r"\n```\s*$", "", raw_text, flags=re.MULTILINE)

    suite = yaml.safe_load(raw_text)
    if not isinstance(suite, dict) or "tasks" not in suite:
        raise ValueError("LLM output did not parse to a valid task suite YAML")

    # Inject metadata
    suite.setdefault("version", "1.0")
    suite.setdefault("skill_id", skill_id)
    suite["generated_at"] = utc_now_iso()
    suite["generator"] = "adversarial_generator/llm"
    return suite


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate adversarial test cases for a Skill.",
    )
    parser.add_argument(
        "--skill-path", required=True,
        help="Path to SKILL.md file or skill directory containing SKILL.md",
    )
    parser.add_argument(
        "--output", default="adversarial_suite.yaml",
        help="Output YAML file path (default: adversarial_suite.yaml)",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Use heuristic rules instead of LLM (no claude CLI needed)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_path = Path(args.skill_path).expanduser().resolve()

    try:
        skill_content, skill_id = load_skill(skill_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.mock:
        suite = generate_mock_suite(skill_content, skill_id)
    else:
        try:
            suite = generate_llm_suite(skill_content, skill_id)
        except (RuntimeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(suite, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(str(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
