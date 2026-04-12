#!/usr/bin/env python3
"""Skill Forge CLI — generate Skills and task suites.

Two primary modes:

Mode A: Generate task suite for existing skill
  python3 scripts/forge.py --from-skill /path/to/skill --output /path/to/output

Mode B: Generate skill + task suite from spec
  python3 scripts/forge.py --from-spec spec.yaml --output /path/to/output

Common flags:
  --mock       Use mock LLM (for testing)
  --evaluate   Run evaluator after generation (requires improvement-evaluator)
  --auto-improve  Run orchestrator if below SOLID (requires improvement-orchestrator)
"""

import argparse
import sys
import yaml
import json
from pathlib import Path

# Add parent directory to path so we can import sibling modules
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SKILL_DIR))

from scripts.task_suite_generator import generate_task_suite, write_task_suite
from scripts.skill_generator import generate_skill_from_spec
from interfaces.spec_schema import SkillSpec


def main():
    parser = argparse.ArgumentParser(
        description="Skill Forge: generate Skills and task suites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--from-skill",
        type=Path,
        help="Path to an existing skill directory (with SKILL.md). "
        "Generates task_suite.yaml only.",
    )
    group.add_argument(
        "--from-spec",
        type=Path,
        help="Path to a skill_spec.yaml. Generates SKILL.md + task_suite.yaml.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for generated files. "
        "Defaults to current directory.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM (for testing without API calls).",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run improvement-evaluator after generation.",
    )
    parser.add_argument(
        "--auto-improve",
        action="store_true",
        help="Run improvement-orchestrator if score below SOLID.",
    )
    parser.add_argument(
        "--install",
        type=Path,
        help="Install generated skill to this directory (e.g. ~/.claude/skills/).",
    )

    args = parser.parse_args()

    # Determine output directory
    output_dir = args.output or Path(".")

    if args.from_skill:
        # Mode A: Generate task suite for existing skill
        return handle_from_skill(args.from_skill, output_dir, args)
    elif args.from_spec:
        # Mode B: Generate skill + task suite from spec
        return handle_from_spec(args.from_spec, output_dir, args)


def handle_from_skill(
    skill_path: Path, output_dir: Path, args: argparse.Namespace
) -> int:
    """Mode A: Generate task suite for an existing SKILL.md."""
    skill_path = skill_path.resolve()

    if not skill_path.is_dir():
        print(f"Error: {skill_path} is not a directory", file=sys.stderr)
        return 1

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"Error: No SKILL.md found at {skill_md}", file=sys.stderr)
        return 1

    print(f"Analyzing SKILL.md at {skill_path}...")
    suite = generate_task_suite(skill_path, mock=args.mock)

    task_count = len(suite.get("tasks", []))
    print(f"Generated {task_count} test tasks.")

    out_file = write_task_suite(suite, output_dir)
    print(f"Task suite written to {out_file}")

    if args.evaluate or args.auto_improve:
        return run_phase3(skill_path, args.evaluate, args.auto_improve, args.mock)
    return 0


def handle_from_spec(
    spec_path: Path, output_dir: Path, args: argparse.Namespace
) -> int:
    """Mode B: Generate skill + task suite from a spec."""
    spec_path = spec_path.resolve()

    if not spec_path.exists():
        print(f"Error: Spec file not found: {spec_path}", file=sys.stderr)
        return 1

    # Load and validate spec
    spec = SkillSpec.from_yaml(spec_path)
    errors = spec.validate()
    if errors:
        for e in errors:
            print(f"Spec validation error: {e}", file=sys.stderr)
        return 1

    print(f"Generating skill '{spec.name}' from spec...")

    # Create skill directory
    skill_dir = output_dir / spec.name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Generate SKILL.md
    spec_dict = yaml.safe_load(spec_path.read_text())
    skill_md_content = generate_skill_from_spec(spec_dict)
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_md_content)
    print(f"SKILL.md written to {skill_md_path}")

    # Generate task suite from the generated SKILL.md
    suite = generate_task_suite(skill_dir, mock=args.mock)
    task_count = len(suite.get("tasks", []))
    print(f"Generated {task_count} test tasks.")

    out_file = write_task_suite(suite, skill_dir)
    print(f"Task suite written to {out_file}")

    if args.evaluate or args.auto_improve:
        return run_phase3(skill_dir, args.evaluate, args.auto_improve, args.mock)
    return 0


# ---------------------------------------------------------------------------
# Phase 3: Evaluate + Auto-Improve
# ---------------------------------------------------------------------------

EVALUATOR_SCRIPT = Path.home() / ".claude/skills/improvement-evaluator/scripts/evaluate.py"
LEARNER_SCRIPT = Path.home() / ".claude/skills/improvement-learner/scripts/self_improve.py"
ORCHESTRATOR_SCRIPT = Path.home() / ".claude/skills/improvement-orchestrator/scripts/orchestrate.py"

SOLID_THRESHOLD = 0.70
PASS_RATE_THRESHOLD = 0.60
MAX_IMPROVE_ITERATIONS = 3


def _run_learner(skill_dir: Path, mock: bool = False) -> float:
    """Run learner for structural scoring. Returns weighted score 0.0-1.0."""
    if not LEARNER_SCRIPT.exists():
        print("  Learner: skipped (not installed)")
        return 0.0
    import subprocess
    cmd = [sys.executable, str(LEARNER_SCRIPT),
           "--skill-path", str(skill_dir), "--max-iterations", "0",
           "--state-root", str(skill_dir / ".forge-state")]
    if mock:
        cmd.append("--mock")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  Learner: error ({result.stderr.strip()[:100]})")
        return 0.0
    try:
        import json as _json
        # Learner may print status messages before JSON; parse last valid JSON line
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                data = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            scores = data.get("final_scores", data.get("dimensions", {}))
            if scores:
                vals = [v.get("score", v) if isinstance(v, dict) else float(v) for v in scores.values()]
                weighted = sum(vals) / len(vals) if vals else 0.0
                print(f"  Learner: {weighted:.3f}")
                return weighted
    except Exception:
        pass
    print("  Learner: could not parse score")
    return 0.0


def _run_evaluator(skill_dir: Path, mock: bool = False) -> float | None:
    """Run evaluator on task_suite. Returns pass_rate or None if no suite."""
    task_suite = skill_dir / "task_suite.yaml"
    if not task_suite.exists():
        return None
    if not EVALUATOR_SCRIPT.exists():
        print("  Evaluator: skipped (not installed)")
        return None
    import subprocess
    state_root = skill_dir / ".forge-state"
    cmd = [sys.executable, str(EVALUATOR_SCRIPT),
           "--task-suite", str(task_suite),
           "--standalone",
           "--state-root", str(state_root),
           "--skill-path", str(skill_dir)]
    if mock:
        cmd.append("--mock")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  Evaluator: error ({result.stderr.strip()[:100]})")
        return None
    try:
        import json as _json
        output_path = Path(result.stdout.strip().split("\n")[-1])
        if output_path.exists():
            data = _json.loads(output_path.read_text())
            pr = data.get("evaluation", {}).get("pass_rate", data.get("pass_rate"))
            if pr is not None:
                print(f"  Evaluator: pass_rate={pr:.2f}")
                return float(pr)
    except Exception:
        pass
    print("  Evaluator: could not parse pass_rate")
    return None


def _run_orchestrator(skill_dir: Path, task_suite: Path | None, mock: bool = False) -> bool:
    """Run one orchestrator cycle. Returns True on success."""
    if not ORCHESTRATOR_SCRIPT.exists():
        print("  Orchestrator: skipped (not installed)")
        return False
    import subprocess
    state_root = skill_dir / ".forge-state" / "orchestrator"
    cmd = [sys.executable, str(ORCHESTRATOR_SCRIPT),
           "--target", str(skill_dir),
           "--state-root", str(state_root),
           "--auto"]
    if task_suite and task_suite.exists():
        cmd.extend(["--task-suite", str(task_suite)])
    if mock:
        cmd.append("--eval-mock")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if result.returncode != 0:
        print(f"  Orchestrator: failed ({result.stderr.strip()[:100]})")
        return False
    # Check decision from stdout
    for line in result.stdout.split("\n"):
        if "Final Decision:" in line:
            decision = line.split(":", 1)[1].strip()
            print(f"  Orchestrator: {decision}")
            return decision in ("keep", "pending_promote")
    return True


def _classify_tier(score: float) -> str:
    if score >= 0.85:
        return "POWERFUL"
    elif score >= 0.70:
        return "SOLID"
    elif score >= 0.55:
        return "GENERIC"
    return "WEAK"


def run_phase3(
    skill_dir: Path,
    do_evaluate: bool,
    do_auto_improve: bool,
    mock: bool = False,
) -> int:
    """Phase 3: Evaluate and optionally auto-improve."""
    print("\n--- Phase 3: Evaluation ---")

    learner_score = _run_learner(skill_dir, mock)
    pass_rate = _run_evaluator(skill_dir, mock) if do_evaluate else None
    tier = _classify_tier(learner_score)

    needs_improve = (
        learner_score < SOLID_THRESHOLD
        or (pass_rate is not None and pass_rate < PASS_RATE_THRESHOLD)
    )

    if needs_improve and do_auto_improve:
        print(f"\n--- Phase 3b: Auto-Improve (below SOLID: {learner_score:.3f}/{tier}) ---")
        task_suite = skill_dir / "task_suite.yaml"
        for iteration in range(1, MAX_IMPROVE_ITERATIONS + 1):
            print(f"  Iteration {iteration}/{MAX_IMPROVE_ITERATIONS}")
            success = _run_orchestrator(
                skill_dir,
                task_suite if task_suite.exists() else None,
                mock,
            )
            if not success:
                print("  Orchestrator did not succeed, stopping.")
                break
            # Re-evaluate
            learner_score = _run_learner(skill_dir, mock)
            tier = _classify_tier(learner_score)
            if learner_score >= SOLID_THRESHOLD:
                print(f"  Reached SOLID: {learner_score:.3f}")
                break

    print(f"\n--- Phase 3 Result ---")
    print(f"  Learner: {learner_score:.3f} ({tier})")
    if pass_rate is not None:
        print(f"  Pass rate: {pass_rate:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
