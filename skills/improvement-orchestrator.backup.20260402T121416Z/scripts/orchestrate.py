#!/usr/bin/env python3
"""Orchestrator dispatch for the auto-improvement pipeline.

Coordinates the full PROPOSE → DISCRIMINATE → GATE → EXECUTE → GATE loop
with Ralph Wiggum-style retry: on revert, capture a structured failure trace
and feed it back into the next proposal round.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
REPO_ROOT = _REPO_ROOT

from lib.common import read_json, utc_now_iso, write_json

# ---------------------------------------------------------------------------
# Script paths (relative to repo root)
# ---------------------------------------------------------------------------

GENERATOR_SCRIPT = REPO_ROOT / "skills" / "improvement-generator" / "scripts" / "propose.py"
DISCRIMINATOR_SCRIPT = REPO_ROOT / "skills" / "improvement-discriminator" / "scripts" / "score.py"
EXECUTOR_SCRIPT = REPO_ROOT / "skills" / "improvement-executor" / "scripts" / "execute.py"
GATE_SCRIPT = REPO_ROOT / "skills" / "improvement-gate" / "scripts" / "gate.py"

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orchestrate the full auto-improvement pipeline",
    )
    parser.add_argument("--target", required=True, help="Target skill/file path")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Feedback/memory source (repeatable)",
    )
    parser.add_argument("--state-root", required=True, help="State directory root")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retry attempts on revert (default: 3)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run full pipeline without pausing",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def run_script(script_path, args, label):
    """Run a role script and return the artifact path it produced."""
    cmd = [sys.executable, str(script_path)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed (exit {result.returncode}):\n"
            f"  stderr: {result.stderr.strip()}\n"
            f"  stdout: {result.stdout.strip()}"
        )
    lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    if not lines:
        raise RuntimeError(f"{label} produced no output on stdout")
    raw_path = lines[-1]
    artifact_path = Path(raw_path)
    if artifact_path.is_absolute() and artifact_path.exists():
        return artifact_path
    for prefix in [Path.cwd(), REPO_ROOT]:
        candidate = prefix / raw_path
        if candidate.exists():
            return candidate.resolve()
    return artifact_path


def _run_script(cmd: list[str], label: str) -> str:
    """Run a subprocess and return its stdout (stripped).

    Raises RuntimeError on non-zero exit.
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed (exit {result.returncode}):\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def run_proposer(
    target: str,
    sources: list[str],
    state_root: str,
) -> dict[str, Any]:
    """Call propose.py and return the candidate artifact."""
    cmd = [
        sys.executable,
        str(GENERATOR_SCRIPT),
        "--target",
        str(target),
        "--state-root",
        str(state_root),
    ]
    for s in sources:
        cmd.extend(["--source", str(s)])
    artifact_path = _run_script(cmd, "proposer")
    return read_json(Path(artifact_path))


def run_discriminator(
    candidate_artifact_path: str,
    state_root: str,
) -> dict[str, Any]:
    """Call score.py and return the ranking artifact."""
    cmd = [
        sys.executable,
        str(DISCRIMINATOR_SCRIPT),
        "--input",
        str(candidate_artifact_path),
        "--state-root",
        str(state_root),
    ]
    artifact_path = _run_script(cmd, "discriminator")
    return read_json(Path(artifact_path))


def run_executor(
    ranking_artifact_path: str,
    candidate_id: str,
    state_root: str,
) -> dict[str, Any]:
    """Call execute.py and return the execution artifact."""
    cmd = [
        sys.executable,
        str(EXECUTOR_SCRIPT),
        "--input",
        str(ranking_artifact_path),
        "--candidate-id",
        candidate_id,
        "--state-root",
        str(state_root),
    ]
    artifact_path = _run_script(cmd, "executor")
    return read_json(Path(artifact_path))


def run_gate(
    ranking_artifact_path: str,
    execution_artifact_path: str,
    state_root: str,
) -> dict[str, Any]:
    """Call gate.py and return the gate receipt."""
    cmd = [
        sys.executable,
        str(GATE_SCRIPT),
        "--ranking",
        str(ranking_artifact_path),
        "--execution",
        str(execution_artifact_path),
        "--state-root",
        str(state_root),
    ]
    artifact_path = _run_script(cmd, "gate")
    return read_json(Path(artifact_path))


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def find_best_accepted(ranking_artifact: dict[str, Any]) -> dict[str, Any] | None:
    """Return the highest-scored candidate with recommendation=accept_for_execution.

    Candidates in the ranking artifact are already sorted by score (descending),
    so the first match is the best.
    """
    for candidate in ranking_artifact.get("scored_candidates", []):
        if candidate.get("recommendation") == "accept_for_execution":
            return candidate
    return None


# ---------------------------------------------------------------------------
# Failure trace (Ralph Wiggum feedback loop)
# ---------------------------------------------------------------------------


def extract_failure_trace(
    receipt: dict[str, Any],
    execution_artifact: dict[str, Any],
    state_root: str,
) -> str:
    """Extract structured failure trace and write it to a temp file.

    The returned path can be passed as --source to the next proposer round,
    enabling the Ralph Wiggum retry pattern: failures feed forward as
    context for the next attempt.
    """
    trace = {
        "type": "failure_trace",
        "candidate_id": receipt.get("candidate_id"),
        "decision": receipt.get("decision"),
        "reason": receipt.get("reason"),
        "execution_status": execution_artifact.get("result", {}).get("status"),
        "diff": execution_artifact.get("result", {}).get("diff", ""),
        "gate_blockers": receipt.get("blockers", []),
        "timestamp": utc_now_iso(),
    }
    run_id = receipt.get("run_id", "unknown")
    trace_dir = Path(state_root) / "traces"
    trace_path = trace_dir / f"trace-{run_id}.json"
    write_json(trace_path, trace)
    return str(trace_path)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    target: str,
    sources: list[str],
    state_root: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Run the full PROPOSE → DISCRIMINATE → EXECUTE → GATE loop.

    Returns a summary dict with the final outcome.
    """
    # Mutable copy so we can append failure traces across retries
    active_sources = list(sources)
    final_decision = "no_candidates"
    final_candidate_id: str | None = None
    final_artifact_path: str | None = None
    attempts_used = 0

    for attempt in range(1, max_retries + 1):
        attempts_used = attempt
        # 1. PROPOSE
        candidate_artifact = run_proposer(target, active_sources, state_root)
        candidate_artifact_path = candidate_artifact.get("truth_anchor", "")

        # 2. DISCRIMINATE (score + rank)
        ranking_artifact = run_discriminator(candidate_artifact_path, state_root)
        ranking_artifact_path = ranking_artifact.get("truth_anchor", "")

        # 3. Find best accepted candidate
        best = find_best_accepted(ranking_artifact)
        if not best:
            final_decision = "no_accepted_candidates"
            print(f"  No accepted candidates in attempt {attempt}/{max_retries}")
            break

        candidate_id = best["id"]

        # 4. EXECUTE
        execution_artifact = run_executor(
            ranking_artifact_path,
            candidate_id,
            state_root,
        )
        execution_artifact_path = execution_artifact.get("truth_anchor", "")

        # 5. GATE (verify after execution)
        receipt = run_gate(
            ranking_artifact_path,
            execution_artifact_path,
            state_root,
        )

        # 6. DECIDE
        decision = receipt.get("decision", "reject")
        final_decision = decision
        final_candidate_id = candidate_id
        final_artifact_path = receipt.get("truth_anchor")

        if decision == "keep":
            print(f"  Kept: {candidate_id}")
            break
        elif decision == "revert":
            # Ralph Wiggum: capture trace, inject into next round
            trace_path = extract_failure_trace(
                receipt, execution_artifact, state_root,
            )
            active_sources.append(trace_path)
            print(
                f"  Reverted, retrying ({attempt}/{max_retries})"
            )
            continue
        elif decision == "pending_promote":
            print(f"  Pending human review: {candidate_id}")
            break
        else:  # reject
            print(f"  Rejected: {candidate_id}")
            break

    return {
        "target": target,
        "attempts": attempts_used,
        "max_retries": max_retries,
        "final_decision": final_decision,
        "final_candidate_id": final_candidate_id,
        "final_artifact_path": final_artifact_path,
    }


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------


def print_summary(summary: dict[str, Any]) -> None:
    """Print a human-readable pipeline summary."""
    print("\nPipeline Summary:")
    print(f"  Target: {summary['target']}")
    print(f"  Attempts: {summary['attempts']}/{summary['max_retries']}")
    print(f"  Final Decision: {summary['final_decision']}")
    print(f"  Candidate: {summary.get('final_candidate_id', 'N/A')}")
    print(f"  Artifact: {summary.get('final_artifact_path', 'N/A')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = str(Path(args.target).expanduser().resolve())
    state_root = str(Path(args.state_root).expanduser().resolve())
    sources = [str(Path(s).expanduser().resolve()) for s in args.source if s]

    try:
        summary = run_pipeline(
            target=target,
            sources=sources,
            state_root=state_root,
            max_retries=args.max_retries,
        )
    except RuntimeError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
