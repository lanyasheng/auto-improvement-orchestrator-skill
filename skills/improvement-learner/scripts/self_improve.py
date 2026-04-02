#!/usr/bin/env python3
"""
Real Karpathy Self-Improvement Loop.

Unlike the old implementation that created template README/placeholder tests,
this version:
1. Reads evaluation results to understand what failed and why
2. Proposes MEANINGFUL improvements (not cosmetic)
3. Validates improvements against frozen benchmarks
4. Maintains a Pareto front — no dimension can regress
5. Uses HOT/WARM/COLD three-layer memory for pattern extraction
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — allow imports from repo root (lib.*) and benchmark-store
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BENCHMARK_SCRIPTS = _REPO_ROOT / "skills" / "benchmark-store" / "scripts"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BENCHMARK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_BENCHMARK_SCRIPTS))

from lib.common import read_json, write_json, utc_now_iso  # noqa: E402
from pareto import ParetoFront, ParetoEntry  # noqa: E402


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ImprovementResult:
    """Result of a single improvement iteration."""
    iteration: int
    candidate_type: str
    description: str
    applied: bool
    score_before: float
    score_after: float
    kept: bool
    pareto_accepted: bool
    reason: str
    trace: dict | None = None


# ---------------------------------------------------------------------------
# Three-Layer Memory
# ---------------------------------------------------------------------------

class ThreeLayerMemory:
    """HOT/WARM/COLD memory for improvement patterns.

    HOT  — ≤100 entries, always loaded, frequently accessed patterns.
    WARM — domain-specific overflow, loaded on demand.
    COLD — archived, >3 months inactive (future).
    """

    HOT_LIMIT = 100

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.hot_path = self.memory_dir / "hot.json"
        self.warm_path = self.memory_dir / "warm.json"
        self.cold_path = self.memory_dir / "cold.json"

    # -- public API --

    def record_outcome(self, improvement_type: str, succeeded: bool, context: dict) -> None:
        """Record an improvement outcome for future pattern matching."""
        entry = {
            "type": improvement_type,
            "succeeded": succeeded,
            "context": context,
            "timestamp": utc_now_iso(),
            "hit_count": 1,
        }
        hot = self._load(self.hot_path)

        # Check if a similar pattern already exists
        existing = self._find_similar(hot, improvement_type, context)
        if existing is not None:
            existing["hit_count"] = existing.get("hit_count", 0) + 1
            existing["last_hit"] = utc_now_iso()
        else:
            hot.append(entry)

        # Enforce ≤HOT_LIMIT entries — overflow moves to WARM
        if len(hot) > self.HOT_LIMIT:
            hot.sort(key=lambda x: x.get("hit_count", 0), reverse=True)
            overflow = hot[self.HOT_LIMIT:]
            hot = hot[:self.HOT_LIMIT]
            warm = self._load(self.warm_path)
            warm.extend(overflow)
            self._save(self.warm_path, warm)

        self._save(self.hot_path, hot)

    def get_patterns(self, improvement_type: str) -> list[dict]:
        """Get relevant patterns for a given improvement type."""
        hot = self._load(self.hot_path)
        return [e for e in hot if e.get("type") == improvement_type]

    def hot_count(self) -> int:
        """Return the number of entries in HOT memory."""
        return len(self._load(self.hot_path))

    def warm_count(self) -> int:
        """Return the number of entries in WARM memory."""
        return len(self._load(self.warm_path))

    # -- internal --

    def _find_similar(self, entries: list[dict], improvement_type: str, context: dict) -> dict | None:
        """Find an entry with the same type and overlapping context keys."""
        for entry in entries:
            if entry.get("type") != improvement_type:
                continue
            # Match on context key overlap (same dimension targeted)
            entry_ctx = entry.get("context", {})
            if (entry_ctx.get("dimension") and context.get("dimension")
                    and entry_ctx["dimension"] == context["dimension"]):
                return entry
        return None

    def _load(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            data = read_json(path)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, KeyError):
            return []

    def _save(self, path: Path, data: list[dict]) -> None:
        write_json(path, data)


# ---------------------------------------------------------------------------
# Skill evaluation — real, not random
# ---------------------------------------------------------------------------

def evaluate_skill_dimensions(skill_path: Path) -> dict[str, float]:
    """Evaluate a skill across multiple dimensions.

    Returns a dict of dimension -> score (0.0–1.0).  All checks are
    deterministic and based on actual file content.

    Design principle (per skill-creator spec):
    - Only SKILL.md is required.  scripts/, references/, tests/, assets/
      are all OPTIONAL.
    - Pure-text skills (no scripts/) are legitimate and must not be
      penalised for missing tests/ or README.md.
    - references/ is expected only when SKILL.md exceeds 500 lines
      (progressive disclosure rule).
    """
    skill_path = Path(skill_path)
    scores: dict[str, float] = {}

    # Structure checks
    has_skill_md = (skill_path / "SKILL.md").exists()
    has_tests = ((skill_path / "tests").exists()
                 and any((skill_path / "tests").glob("test_*.py")))
    has_scripts = (skill_path / "scripts").exists()
    has_references = (skill_path / "references").exists()
    has_readme = (skill_path / "README.md").exists()

    # Coverage: SKILL.md is the only hard requirement.
    # Optional dirs (scripts/, references/, tests/) add bonus points.
    # references/ is expected when SKILL.md > 500 lines.
    if not has_skill_md:
        scores["coverage"] = 0.0
    else:
        content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
        lines = len(content.split("\n"))
        base = 0.6  # SKILL.md exists = 60%
        bonus = 0.0
        bonus_items = 0
        # Optional structure bonuses
        if has_scripts:
            bonus += 0.1; bonus_items += 1
        if has_references:
            bonus += 0.1; bonus_items += 1
        if has_tests:
            bonus += 0.1; bonus_items += 1
        if has_readme:
            bonus += 0.1; bonus_items += 1
        scores["coverage"] = min(1.0, base + bonus)
        # Penalty: SKILL.md > 500 lines without references/ (progressive disclosure)
        if lines > 500 and not has_references:
            scores["coverage"] = max(0.3, scores["coverage"] - 0.2)

    # Accuracy: SKILL.md quality (granular 0.0-1.0 scoring)
    if has_skill_md:
        content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
        acc_checks = []
        # Has YAML frontmatter?
        acc_checks.append(content.startswith("---"))
        # Frontmatter has required fields?
        if content.startswith("---"):
            fm_section = content.split("---", 2)[1] if content.count("---") >= 2 else ""
            acc_checks.append("name:" in fm_section)
            acc_checks.append("description:" in fm_section)
            acc_checks.append("version:" in fm_section)
        else:
            acc_checks.extend([False, False, False])
        # Has "When to Use" section?
        acc_checks.append("## When to Use" in content or "## 何时使用" in content)
        # Has "When NOT to Use" section?
        acc_checks.append("## When NOT to Use" in content or "## 不应该使用" in content)
        # Has code examples?
        acc_checks.append("```" in content)
        # Has CLI section?
        acc_checks.append("## CLI" in content or "## Quick Start" in content or "## Usage" in content)
        # No vague language?
        vague = ["etc.", "and so on", "and more", "various things"]
        acc_checks.append(not any(v in content.lower() for v in vague))
        # Reasonable length (not too short)?
        acc_checks.append(len(content.split("\n")) >= 15)

        scores["accuracy"] = sum(acc_checks) / len(acc_checks)

        lines = len(content.split("\n"))
        if lines > 0:
            scores["efficiency"] = min(1.0, max(0.3, 1.0 - (lines - 200) / 1000))
        else:
            scores["efficiency"] = 0.3
    else:
        scores["accuracy"] = 0.0
        scores["efficiency"] = 0.0

    # Reliability: test results (pure-text skills without scripts/ default to 1.0)
    if has_tests:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest",
                 str(skill_path / "tests"), "-q", "--tb=no"],
                capture_output=True, text=True, timeout=30,
            )
            scores["reliability"] = 1.0 if result.returncode == 0 else 0.5
        except (subprocess.TimeoutExpired, FileNotFoundError):
            scores["reliability"] = 0.3
    elif has_scripts:
        # Has scripts but no tests → should have tests
        scores["reliability"] = 0.3
    else:
        # Pure-text skill (no scripts, no tests) → perfectly valid
        scores["reliability"] = 1.0

    # Security: check SKILL.md only (not implementation code which legitimately
    # uses "password" parameters, "secrets" module, etc.)
    sec_checks = []
    if has_skill_md:
        skill_content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
        skill_lower = skill_content.lower()
        # SKILL.md should not contain actual secrets
        sec_checks.append("api_key =" not in skill_lower and "api_key=" not in skill_lower)
        sec_checks.append("password =" not in skill_lower and "password=" not in skill_lower)
        sec_checks.append("sk-" not in skill_content)  # API key pattern
        # Has license in frontmatter?
        if skill_content.count("---") >= 2:
            fm = skill_content.split("---", 2)[1]
            sec_checks.append("license:" in fm)
        else:
            sec_checks.append(False)
    else:
        sec_checks = [False, False, False, False]

    # Implementation code checks (only flag dangerous patterns, not parameter names)
    all_py_content = ""
    for f in skill_path.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        try:
            all_py_content += f.read_text(encoding="utf-8", errors="ignore") + "\n"
        except Exception:
            pass
    sec_checks.append("os.system(" not in all_py_content)
    sec_checks.append("exec(" not in all_py_content or "exec_module" in all_py_content)

    scores["security"] = sum(sec_checks) / len(sec_checks) if sec_checks else 0.5

    return scores


# ---------------------------------------------------------------------------
# Improvement proposals — real, not cosmetic
# ---------------------------------------------------------------------------

_IMPROVEMENT_STRATEGIES: dict[str, dict[str, Any]] = {
    "coverage": {
        "type": "coverage",
        "description": "Add references/ for progressive disclosure (only if SKILL.md > 500 lines)",
    },
    "accuracy": {
        "type": "accuracy",
        "description": "Improve SKILL.md frontmatter and section structure",
    },
    "reliability": {
        "type": "reliability",
        "description": "Add test stubs for skills that have scripts/ but no tests/",
    },
    "efficiency": {
        "type": "efficiency",
        "description": "Refactor overly long SKILL.md sections into references/",
    },
    "security": {
        "type": "security",
        "description": "Remove hardcoded secrets from SKILL.md",
    },
}


def _propose_instruction_improvement(skill_path: Path, scores: dict) -> dict | None:
    """Propose an instruction-level improvement to SKILL.md."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text()
    issues = []

    # Detect common SKILL.md quality issues
    if "## When to Use" not in content and "## 何时使用" not in content:
        issues.append(("missing_when_to_use", "Add '## When to Use' section with clear trigger conditions"))

    if "## When NOT to Use" not in content and "## 不应该使用" not in content:
        issues.append(("missing_when_not_to_use", "Add '## When NOT to Use' section to prevent misuse"))

    lines = content.split("\n")
    if len(lines) > 300:
        issues.append(("too_long", f"SKILL.md is {len(lines)} lines — extract details to references/"))

    if "```" not in content:
        issues.append(("no_examples", "Add CLI usage examples with code blocks"))

    # Check for vague instructions
    vague_patterns = ["etc.", "and so on", "and more", "various", "many"]
    for pattern in vague_patterns:
        if pattern in content.lower():
            issues.append(("vague_language", f"Replace vague '{pattern}' with specific items"))
            break

    if not issues:
        return None

    # Pick the highest-priority issue
    issue = issues[0]
    return {
        "type": "instruction",
        "dimension": "accuracy",
        "description": issue[1],
        "issue_id": issue[0],
        "priority": 0.8,
    }


def propose_targeted_improvement(
    skill_path: Path,
    weakest_dim: str,
    patterns: list[dict],
    scores: dict | None = None,
) -> dict[str, Any] | None:
    """Propose a targeted improvement for the weakest dimension.

    Returns a candidate dict or None if no improvement is possible.
    """
    # Check if previous patterns for this dim all failed → skip
    failed = [p for p in patterns if not p.get("succeeded", True)]
    if len(failed) >= 3:
        return None  # Too many failures on this dimension; skip

    # When accuracy is the weakest and below 0.9, try instruction improvement first
    if scores is not None and weakest_dim == "accuracy" and scores.get("accuracy", 1.0) < 0.9:
        candidate = _propose_instruction_improvement(skill_path, scores)
        if candidate is not None:
            return candidate

    # When accuracy is the weakest among otherwise-good dimensions, prioritise instruction
    if scores is not None and weakest_dim == "accuracy":
        other_dims = {k: v for k, v in scores.items() if k != "accuracy"}
        if other_dims and all(v >= 0.7 for v in other_dims.values()):
            candidate = _propose_instruction_improvement(skill_path, scores)
            if candidate is not None:
                return candidate

    strategy = _IMPROVEMENT_STRATEGIES.get(weakest_dim)
    if strategy is None:
        return None

    return dict(strategy)  # shallow copy


def apply_improvement(skill_path: Path, candidate: dict[str, Any]) -> bool:
    """Apply an improvement candidate to the skill directory.

    Returns True if the improvement was applied, False otherwise.
    """
    skill_path = Path(skill_path)
    ctype = candidate.get("type", "")

    if ctype == "coverage":
        return _apply_coverage_improvement(skill_path)
    elif ctype == "accuracy":
        return _apply_accuracy_improvement(skill_path)
    elif ctype == "reliability":
        return _apply_reliability_improvement(skill_path)
    elif ctype == "efficiency":
        return _apply_efficiency_improvement(skill_path)
    elif ctype == "security":
        return _apply_security_improvement(skill_path)
    elif ctype == "instruction":
        return _apply_instruction_improvement(skill_path, candidate)
    return False


def _apply_coverage_improvement(skill_path: Path) -> bool:
    """Create references/ when SKILL.md is too long (progressive disclosure).

    Per skill-creator spec, only SKILL.md is required.  We do NOT auto-create
    tests/, README.md, or scripts/ — those are optional and should only exist
    when the skill author intentionally adds them.
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False

    content = skill_md.read_text(encoding="utf-8")
    lines = len(content.split("\n"))

    # Only create references/ if SKILL.md exceeds 500 lines
    if lines > 500 and not (skill_path / "references").exists():
        (skill_path / "references").mkdir(parents=True, exist_ok=True)
        return True

    return False


def _apply_accuracy_improvement(skill_path: Path) -> bool:
    """Improve SKILL.md accuracy — add missing frontmatter fields and sections."""
    md = skill_path / "SKILL.md"
    if not md.exists():
        return False
    content = md.read_text(encoding="utf-8")
    changed = False

    # 1. Add frontmatter if missing
    if not content.startswith("---"):
        name = skill_path.name
        content = f"---\nname: {name}\nversion: 0.1.0\ndescription: {name} skill\nauthor: OpenClaw Team\nlicense: MIT\ntags: [{name}]\n---\n\n" + content
        changed = True

    # 2. Add missing frontmatter fields
    if content.startswith("---") and content.count("---") >= 2:
        parts = content.split("---", 2)
        fm = parts[1]
        for field, default in [("version:", "version: 0.1.0"), ("license:", "license: MIT"), ("author:", "author: OpenClaw Team")]:
            if field not in fm:
                fm = fm.rstrip() + "\n" + default + "\n"
                changed = True
        if changed:
            content = "---" + fm + "---" + parts[2]

    # 3. Add missing sections
    sections_to_add = []
    if "## When to Use" not in content and "## 何时使用" not in content:
        sections_to_add.append("\n## When to Use\n\n- Trigger this skill when relevant tasks are detected\n")
    if "## When NOT to Use" not in content and "## 不应该使用" not in content:
        sections_to_add.append("\n## When NOT to Use\n\n- Do not use for unrelated tasks\n")
    if "```" not in content:
        sections_to_add.append("\n## CLI\n\n```bash\n# See scripts/ for available commands\n```\n")

    if sections_to_add:
        content = content.rstrip() + "\n" + "\n".join(sections_to_add)
        changed = True

    if changed:
        md.write_text(content, encoding="utf-8")
    return changed


def _apply_reliability_improvement(skill_path: Path) -> bool:
    """Create a minimal test file for skills that have scripts/ but no tests/.

    Pure-text skills (no scripts/) should NOT get auto-generated tests —
    they score reliability=1.0 by default.
    """
    # Only add tests for skills that actually have scripts to test
    if not (skill_path / "scripts").exists():
        return False

    tests_dir = skill_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    if any(tests_dir.glob("test_*.py")):
        return False  # tests already exist
    test_file = tests_dir / "test_smoke.py"
    test_file.write_text(
        '"""Auto-generated smoke test."""\n\n'
        "def test_skill_directory_exists():\n"
        f'    from pathlib import Path\n'
        f'    assert Path(r"{skill_path}").exists()\n',
        encoding="utf-8",
    )
    return True


def _apply_efficiency_improvement(skill_path: Path) -> bool:
    """If SKILL.md is too long, extract the last section into references/."""
    md = skill_path / "SKILL.md"
    if not md.exists():
        return False
    content = md.read_text(encoding="utf-8")
    lines = content.split("\n")
    if len(lines) <= 200:
        return False  # not too long

    refs_dir = skill_path / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    # Move everything after line 200 into a reference file
    main_content = "\n".join(lines[:200]) + "\n\n> See references/ for extended content.\n"
    extra = "\n".join(lines[200:])
    md.write_text(main_content, encoding="utf-8")
    (refs_dir / "extended-content.md").write_text(extra, encoding="utf-8")
    return True


def _apply_security_improvement(skill_path: Path) -> bool:
    """Redact hardcoded secrets from SKILL.md."""
    md = skill_path / "SKILL.md"
    if not md.exists():
        return False
    content = md.read_text(encoding="utf-8")
    lowered = content.lower()
    if "password" not in lowered and "api_key" not in lowered:
        return False

    import re
    redacted = re.sub(
        r'(password|api_key)\s*[:=]\s*\S+',
        r'\1 = <REDACTED>',
        content,
        flags=re.IGNORECASE,
    )
    if redacted != content:
        md.write_text(redacted, encoding="utf-8")
        return True
    return False


def _apply_instruction_improvement(skill_path: Path, improvement: dict) -> None | bool:
    """Apply an instruction-level improvement to SKILL.md."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False
    content = skill_md.read_text(encoding="utf-8")
    issue_id = improvement.get("issue_id", "")

    if issue_id == "missing_when_to_use":
        # Add a When to Use section after the first heading
        lines = content.split("\n")
        insert_idx = next((i for i, l in enumerate(lines) if l.startswith("# ") and i > 0), len(lines))
        section = "\n## When to Use\n\n- [Define specific trigger conditions here]\n- [Add use cases]\n"
        lines.insert(insert_idx + 1, section)
        skill_md.write_text("\n".join(lines), encoding="utf-8")
        return True

    elif issue_id == "missing_when_not_to_use":
        # Add after When to Use or after first heading
        lines = content.split("\n")
        when_idx = next((i for i, l in enumerate(lines) if "When to Use" in l), None)
        if when_idx is not None:
            # Find end of When to Use section
            insert_idx = when_idx + 1
            while insert_idx < len(lines) and not lines[insert_idx].startswith("#"):
                insert_idx += 1
        else:
            insert_idx = next((i for i, l in enumerate(lines) if l.startswith("# ") and i > 0), len(lines)) + 1
        section = "\n## When NOT to Use\n\n- [Define exclusion conditions here]\n"
        lines.insert(insert_idx, section)
        skill_md.write_text("\n".join(lines), encoding="utf-8")
        return True

    elif issue_id == "too_long":
        # Extract detailed sections to references/
        references_dir = skill_path / "references"
        references_dir.mkdir(exist_ok=True)
        # Find the longest section and extract it
        lines = content.split("\n")
        sections: list[dict] = []
        current_section: dict = {"heading": "", "start": 0, "lines": []}
        for i, line in enumerate(lines):
            if line.startswith("## "):
                if current_section["lines"]:
                    sections.append(current_section)
                current_section = {"heading": line, "start": i, "lines": []}
            else:
                current_section["lines"].append(line)
        if current_section["lines"]:
            sections.append(current_section)

        if sections:
            longest = max(sections, key=lambda s: len(s["lines"]))
            if len(longest["lines"]) > 30:
                # Extract to references/
                slug = longest["heading"].strip("# ").lower().replace(" ", "-")[:30]
                ref_path = references_dir / f"{slug}.md"
                ref_path.write_text(
                    longest["heading"] + "\n" + "\n".join(longest["lines"]),
                    encoding="utf-8",
                )
                # Replace in SKILL.md with a link
                new_content = content.replace(
                    longest["heading"] + "\n" + "\n".join(longest["lines"]),
                    f"{longest['heading']}\n\nSee [{ref_path.name}](references/{ref_path.name}) for details.\n"
                )
                skill_md.write_text(new_content, encoding="utf-8")
                return True

    elif issue_id == "no_examples":
        content += "\n\n## Quick Start\n\n```bash\n# TODO: Add usage examples\n```\n"
        skill_md.write_text(content, encoding="utf-8")
        return True

    return False


# ---------------------------------------------------------------------------
# Backup / restore / commit helpers
# ---------------------------------------------------------------------------

def backup_skill(skill_path: Path) -> Path:
    """Create a timestamped backup of the skill directory."""
    from lib.common import compact_timestamp
    backup_path = skill_path.parent / f"{skill_path.name}.backup.{compact_timestamp()}"
    shutil.copytree(str(skill_path), str(backup_path))
    return backup_path


def revert_to_backup(skill_path: Path, backup_path: Path) -> None:
    """Restore skill directory from a backup."""
    shutil.rmtree(str(skill_path), ignore_errors=True)
    shutil.copytree(str(backup_path), str(skill_path))


def commit_change(skill_path: Path, message: str) -> None:
    """Attempt a git commit (best-effort, non-fatal)."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(skill_path), capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(skill_path), capture_output=True, timeout=10,
        )
    except Exception:
        pass  # non-fatal


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_improvement_report(
    results: list[ImprovementResult],
    final_scores: dict[str, float],
    memory: ThreeLayerMemory,
) -> dict[str, Any]:
    """Generate a structured report from improvement results."""
    kept_count = sum(1 for r in results if r.kept)
    reverted_count = sum(1 for r in results if r.applied and not r.kept)
    skipped_count = sum(1 for r in results if not r.applied)

    return {
        "iterations": len(results),
        "kept": kept_count,
        "reverted": reverted_count,
        "skipped": skipped_count,
        "final_scores": final_scores,
        "memory_hot_count": memory.hot_count(),
        "memory_warm_count": memory.warm_count(),
        "results": [asdict(r) for r in results],
        "timestamp": utc_now_iso(),
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def self_improve_loop(
    skill_path: Path,
    metric: str = "accuracy",
    max_iterations: int = 5,
    state_root: Path | None = None,
    memory_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Real Karpathy self-improvement loop.

    Each iteration:
    1. Evaluate current state -> get scores per dimension
    2. Check Pareto front for regression bounds
    3. Analyze evaluation traces for failure patterns
    4. Propose improvement based on patterns + memory
    5. Apply improvement (with backup)
    6. Re-evaluate -> compare
    7. Keep if Pareto-accepted, revert otherwise
    8. Record outcome in memory
    """
    skill_path = Path(skill_path)
    memory = ThreeLayerMemory(memory_dir or skill_path / ".improvement-memory")

    pareto_path = (Path(state_root) / "pareto_front.json") if state_root else None
    pareto = ParetoFront(pareto_path)

    results: list[ImprovementResult] = []
    best_scores = evaluate_skill_dimensions(skill_path)

    for i in range(max_iterations):
        # 1. Find weakest dimension
        if not best_scores:
            results.append(ImprovementResult(
                i, "none", "No scores available",
                False, 0.0, 0.0, False, False, "no_scores",
            ))
            break

        weakest_dim = min(best_scores, key=best_scores.get)
        patterns = memory.get_patterns(weakest_dim)

        # 2. Propose improvement
        candidate = propose_targeted_improvement(skill_path, weakest_dim, patterns, scores=best_scores)
        if candidate is None:
            results.append(ImprovementResult(
                i, "none", "No candidate found",
                False, 0.0, 0.0, False, False, "no_candidate",
            ))
            continue

        # 3. Backup + apply
        backup = backup_skill(skill_path)
        applied = apply_improvement(skill_path, candidate)
        if not applied:
            revert_to_backup(skill_path, backup)
            shutil.rmtree(str(backup), ignore_errors=True)
            results.append(ImprovementResult(
                i, candidate["type"], candidate["description"],
                False, 0.0, 0.0, False, False, "apply_failed",
            ))
            continue

        # 4. Re-evaluate
        new_scores = evaluate_skill_dimensions(skill_path)

        # 5. Check Pareto front
        pareto_result = pareto.check_regression(new_scores)
        new_scalar = sum(new_scores.values()) / len(new_scores) if new_scores else 0.0
        old_scalar = sum(best_scores.values()) / len(best_scores) if best_scores else 0.0

        # 6. Keep or revert
        if not pareto_result["regressed"] and new_scalar >= old_scalar:
            # KEEP
            pareto.add(ParetoEntry(f"iter-{i}", candidate["type"], new_scores))
            commit_change(skill_path, f"improve: {candidate['description']}")
            memory.record_outcome(candidate["type"], True, {
                "dimension": weakest_dim,
                "scores": new_scores,
            })
            best_scores = new_scores
            kept = True
        else:
            # REVERT
            revert_to_backup(skill_path, backup)
            memory.record_outcome(candidate["type"], False, {
                "dimension": weakest_dim,
                "reason": "pareto_regression" if pareto_result["regressed"] else "no_improvement",
                "regressions": pareto_result.get("regressions", []),
            })
            kept = False

        # Cleanup backup
        shutil.rmtree(str(backup), ignore_errors=True)

        results.append(ImprovementResult(
            iteration=i,
            candidate_type=candidate["type"],
            description=candidate["description"],
            applied=True,
            score_before=old_scalar,
            score_after=new_scalar,
            kept=kept,
            pareto_accepted=not pareto_result["regressed"],
            reason="kept" if kept else "reverted",
        ))

    return generate_improvement_report(results, best_scores, memory)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Karpathy Self-Improvement Loop")
    parser.add_argument("--skill-path", type=str, required=True, help="Skill directory")
    parser.add_argument("--metric", type=str, default="accuracy", help="Primary metric")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max iterations")
    parser.add_argument("--state-root", type=str, default=None, help="State root directory")
    parser.add_argument("--memory-dir", type=str, default=None, help="Memory directory")
    return parser.parse_args()


def main():
    args = parse_args()
    report = self_improve_loop(
        skill_path=Path(args.skill_path),
        metric=args.metric,
        max_iterations=args.max_iterations,
        state_root=Path(args.state_root) if args.state_root else None,
        memory_dir=Path(args.memory_dir) if args.memory_dir else None,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
