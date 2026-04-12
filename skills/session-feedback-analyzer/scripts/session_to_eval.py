#!/usr/bin/env python3
"""Convert session feedback into evaluator task_suite.yaml format.

Reuses analyze.py's detection and classification logic to extract
real user interactions with a specific skill, then converts them
into task_suite.yaml tasks that the improvement-evaluator can run.

Usage:
    python3 scripts/session_to_eval.py \
        --skill-id deslop \
        --session-dir ~/.claude/projects/ \
        --output ./task_suites/deslop-from-sessions/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Reuse analyze.py's detection logic
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import yaml
except ImportError:
    print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from analyze import (
    FeedbackEvent,
    analyze_sessions,
    classify_outcome,
    iter_session_files,
    parse_session,
    detect_skill_invocations,
    _extract_user_text,
)


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


def _extract_conversation_context(
    messages: list[dict[str, Any]],
    invocation_idx: int,
    window: int = 5,
) -> dict[str, str]:
    """Extract user prompt and AI response around a skill invocation."""
    # Find the user message that triggered the skill invocation
    user_prompt = ""
    for idx in range(invocation_idx - 1, max(-1, invocation_idx - window - 1), -1):
        if idx < 0:
            break
        entry = messages[idx]
        if entry.get("type") == "user":
            user_prompt = _extract_user_text(entry)
            break

    # Find the AI response after the invocation
    ai_response = ""
    for idx in range(invocation_idx + 1, min(len(messages), invocation_idx + window + 1)):
        entry = messages[idx]
        if entry.get("type") == "assistant":
            msg = entry.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                ai_response = " ".join(parts)[:500]
            elif isinstance(content, str):
                ai_response = content[:500]
            break

    # Find user's subsequent response (correction or acceptance)
    user_response = ""
    for idx in range(invocation_idx + 1, min(len(messages), invocation_idx + 10)):
        entry = messages[idx]
        if entry.get("type") == "user":
            text = _extract_user_text(entry)
            # Skip system-injected messages
            if any(m in text for m in ("Base directory for this skill", "<command-name>", "---\nname:")):
                continue
            user_response = text[:300]
            break

    return {
        "user_prompt": user_prompt,
        "ai_response": ai_response,
        "user_response": user_response,
    }


# ---------------------------------------------------------------------------
# Task generation
# ---------------------------------------------------------------------------


def _make_task_id(skill_id: str, event: FeedbackEvent, idx: int) -> str:
    """Generate deterministic task ID."""
    h = hashlib.sha256(f"{event.event_id}:{idx}".encode()).hexdigest()[:8]
    return f"session-{skill_id}-{h}"


def _build_task_from_event(
    skill_id: str,
    event: FeedbackEvent,
    context: dict[str, str],
    idx: int,
) -> dict[str, Any] | None:
    """Convert a FeedbackEvent + context into a task_suite task."""
    prompt = context["user_prompt"]
    if not prompt or len(prompt) < 10:
        return None

    task_id = _make_task_id(skill_id, event, idx)

    if event.outcome == "acceptance":
        # Acceptance: use llm-rubric to check quality
        rubric = (
            f"The user accepted the AI's response to this prompt. "
            f"Score the output based on: "
            f"1) Does it address the user's request? "
            f"2) Is the output well-structured and complete? "
            f"3) Does it follow the skill's guidelines?"
        )
        if context["ai_response"]:
            rubric += f"\n\nReference (accepted response excerpt): {context['ai_response'][:200]}"

        return {
            "id": task_id,
            "description": f"Session-extracted acceptance case ({event.timestamp[:10]})",
            "prompt": prompt,
            "judge": {
                "type": "llm-rubric",
                "rubric": rubric,
                "pass_threshold": 0.6,
            },
            "timeout_seconds": 120,
            "source": "session-feedback-analyzer",
        }

    elif event.outcome == "correction":
        # Correction: extract what went wrong
        correction_text = context["user_response"] or event.user_message_snippet
        if not correction_text:
            return None

        # For corrections, build a judge that checks the output avoids the mistake
        rubric = (
            f"The user corrected the AI's response to this prompt. "
            f"The correction was: \"{correction_text[:200]}\"\n\n"
            f"Score the output based on: "
            f"1) Does it avoid the mistake the user pointed out? "
            f"2) Does it address the user's original request? "
            f"3) Is the response complete and well-formed?"
        )
        if event.dimension_hint:
            rubric += f"\n\nThe issue was in the '{event.dimension_hint}' dimension."

        return {
            "id": task_id,
            "description": f"Session-extracted correction case: {event.correction_type} ({event.timestamp[:10]})",
            "prompt": prompt,
            "judge": {
                "type": "llm-rubric",
                "rubric": rubric,
                "pass_threshold": 0.7,
            },
            "timeout_seconds": 120,
            "source": "session-feedback-analyzer",
        }

    return None


# ---------------------------------------------------------------------------
# Dataset splitting
# ---------------------------------------------------------------------------


def _deterministic_split(
    tasks: list[dict],
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
) -> dict[str, list[dict]]:
    """Split tasks into train/val/holdout using deterministic hash."""
    train, val, holdout = [], [], []
    for task in tasks:
        h = int(hashlib.sha256(task["id"].encode()).hexdigest(), 16) % 100
        if h < int(train_ratio * 100):
            train.append(task)
        elif h < int((train_ratio + val_ratio) * 100):
            val.append(task)
        else:
            holdout.append(task)
    return {"train": train, "val": val, "holdout": holdout}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def extract_eval_tasks(
    skill_id: str,
    session_dir: Path,
) -> list[dict[str, Any]]:
    """Extract evaluation tasks from session data for a specific skill."""
    tasks: list[dict[str, Any]] = []

    for session_path in iter_session_files(session_dir):
        messages = parse_session(session_path)
        if not messages:
            continue

        invocations = detect_skill_invocations(messages)
        invocations = [inv for inv in invocations if inv.skill_id == skill_id]

        for i, invocation in enumerate(invocations):
            next_idx = invocations[i + 1].message_index if i + 1 < len(invocations) else None

            event = classify_outcome(messages, invocation, next_idx)
            if not event:
                continue

            context = _extract_conversation_context(messages, invocation.message_index)
            task = _build_task_from_event(skill_id, event, context, len(tasks))
            if task:
                tasks.append(task)

    return tasks


def write_task_suite(
    skill_id: str,
    tasks: list[dict],
    output_dir: Path,
    description: str = "",
) -> Path:
    """Write tasks as a task_suite.yaml file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    suite = {
        "skill_id": skill_id,
        "version": "1.0",
        "description": description or f"Auto-extracted from session history for {skill_id}",
        "generated_by": "session-to-eval",
        "tasks": tasks,
    }
    output_path = output_dir / "task_suite.yaml"
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(suite, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract evaluation task suites from session history",
    )
    parser.add_argument("--skill-id", required=True, help="Target skill ID")
    parser.add_argument(
        "--session-dir",
        default=str(Path.home() / ".claude" / "projects"),
        help="Root directory for session JSONL files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for task_suite.yaml",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="Minimum tasks required (default: 3)",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Split into train/val/holdout subdirectories",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    session_dir = Path(args.session_dir).expanduser()
    output_dir = Path(args.output).expanduser()

    if not session_dir.exists():
        print(f"Session directory not found: {session_dir}", file=sys.stderr)
        return 1

    tasks = extract_eval_tasks(args.skill_id, session_dir)

    if len(tasks) < args.min_samples:
        print(
            f"Only {len(tasks)} tasks extracted (minimum: {args.min_samples}). "
            f"Not enough session data for skill '{args.skill_id}'.",
            file=sys.stderr,
        )
        if not tasks:
            return 1

    if args.split and len(tasks) >= 5:
        splits = _deterministic_split(tasks)
        for split_name, split_tasks in splits.items():
            if split_tasks:
                split_dir = output_dir / split_name
                path = write_task_suite(args.skill_id, split_tasks, split_dir,
                                        f"{split_name} split for {args.skill_id}")
                print(f"  {split_name}: {len(split_tasks)} tasks → {path}")
    else:
        path = write_task_suite(args.skill_id, tasks, output_dir)
        print(f"Generated {len(tasks)} tasks → {path}")

    # Summary
    from collections import Counter
    sources = Counter(
        "correction" if "correction" in t.get("description", "") else "acceptance"
        for t in tasks
    )
    print(f"  Sources: {dict(sources)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
