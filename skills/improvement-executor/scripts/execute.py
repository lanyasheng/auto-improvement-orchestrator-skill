#!/usr/bin/env python3
"""Executor for low-risk generic-skill candidates."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root

from lib.common import (
    EXECUTOR_SUPPORTED_CATEGORIES,
    SCHEMA_VERSION,
    read_json,
    read_text,
    utc_now_iso,
    write_json,
    write_text,
)
from lib.state_machine import (
    DEFAULT_STATE_ROOT,
    backup_file,
    ensure_tree,
    update_state,
)


def capture_execution_trace(candidate: dict, result: dict, error: str | None = None) -> dict:
    """Capture structured execution trace for GEPA feedback."""
    return {
        "type": "execution_trace",
        "candidate_id": candidate.get("id", "unknown"),
        "category": candidate.get("category", "unknown"),
        "target_path": candidate.get("target_path", ""),
        "action": candidate.get("execution_plan", {}).get("action", "unknown"),
        "execution_status": result.get("status", "unknown"),
        "modified": result.get("modified", False),
        "diff_summary": result.get("diff_summary", {}),
        "error": error,
        "timestamp": utc_now_iso(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a ranked generic-skill candidate")
    parser.add_argument("--input", required=True, help="Ranking artifact JSON")
    parser.add_argument("--candidate-id", required=True, help="Candidate id to execute")
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--output", default=None)
    parser.add_argument("--force", action="store_true", help="Allow execution even when critic did not accept")
    return parser.parse_args()


def append_markdown_section(target_path: Path, plan: dict) -> dict:
    before = read_text(target_path)
    heading = plan["section_heading"].strip()
    content_lines = plan.get("content_lines", [])
    if heading in before:
        return {
            "status": "no_change",
            "modified": False,
            "diff": "",
            "diff_summary": {
                "reason": f"section `{heading}` already present",
                "added_lines": 0,
            },
            "after_content": before,
        }
    section = heading + "\n\n" + "\n".join(f"- {line}" for line in content_lines)
    after = before.rstrip() + "\n\n" + section + "\n"
    write_text(target_path, after)
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(target_path),
            tofile=str(target_path),
        )
    )
    return {
        "status": "success",
        "modified": True,
        "diff": diff,
        "diff_summary": {
            "reason": f"appended markdown section `{heading}`",
            "added_lines": len(content_lines) + 2,
        },
        "after_content": after,
    }


def main() -> int:
    args = parse_args()
    state_root = Path(args.state_root).expanduser().resolve()
    paths = ensure_tree(state_root)

    ranking_artifact = read_json(Path(args.input).expanduser().resolve())
    run_id = ranking_artifact["run_id"]
    target_path = ranking_artifact["target"]["path"]
    candidate = next((item for item in ranking_artifact.get("scored_candidates", []) if item["id"] == args.candidate_id), None)
    if not candidate:
        raise SystemExit(f"candidate not found: {args.candidate_id}")

    recommendation = candidate.get("recommendation")
    if recommendation != "accept_for_execution" and not args.force:
        execution_artifact = {
            "schema_version": SCHEMA_VERSION,
            "lane": ranking_artifact.get("lane", "generic-skill"),
            "run_id": run_id,
            "stage": "executed",
            "status": "unsupported",
            "created_at": utc_now_iso(),
            "candidate_id": candidate["id"],
            "candidate": candidate,
            "source_ranking_artifact": args.input,
            "result": {
                "status": "unsupported",
                "modified": False,
                "reason": f"critic recommendation is `{recommendation}`; use --force to override",
            },
            "next_step": "apply_gate",
            "next_owner": "gate",
        }
        output_path = Path(args.output).expanduser().resolve() if args.output else paths["executions"] / f"{run_id}-{candidate['id']}.json"
        execution_artifact["truth_anchor"] = str(output_path)
        write_json(output_path, execution_artifact)
        update_state(
            state_root,
            run_id=run_id,
            stage="executed",
            status="unsupported",
            target_path=target_path,
            truth_anchor=str(output_path),
            extra={"candidate_id": candidate["id"]},
        )
        print(str(output_path))
        return 0

    category = candidate.get("category")
    if category not in EXECUTOR_SUPPORTED_CATEGORIES:
        result = {
            "status": "unsupported",
            "modified": False,
            "reason": f"category `{category}` is not supported by the first runnable executor",
        }
        output_path = Path(args.output).expanduser().resolve() if args.output else paths["executions"] / f"{run_id}-{candidate['id']}.json"
        artifact = {
            "schema_version": SCHEMA_VERSION,
            "lane": ranking_artifact.get("lane", "generic-skill"),
            "run_id": run_id,
            "stage": "executed",
            "status": result["status"],
            "created_at": utc_now_iso(),
            "candidate_id": candidate["id"],
            "candidate": candidate,
            "source_ranking_artifact": args.input,
            "result": result,
            "next_step": "apply_gate",
            "next_owner": "gate",
            "truth_anchor": str(output_path),
        }
        write_json(output_path, artifact)
        update_state(
            state_root,
            run_id=run_id,
            stage="executed",
            status="unsupported",
            target_path=target_path,
            truth_anchor=str(output_path),
            extra={"candidate_id": candidate["id"]},
        )
        print(str(output_path))
        return 0

    target_file = Path(candidate["target_path"]).expanduser().resolve()
    if not target_file.exists() or not target_file.is_file():
        raise SystemExit(f"target file not found: {target_file}")

    backup_path = paths["executions"] / "backups" / run_id / f"{candidate['id']}-{target_file.name}"
    backup_file(target_file, backup_path)

    plan = candidate.get("execution_plan", {})
    action = plan.get("action")
    if action == "append_markdown_section":
        result = append_markdown_section(target_file, plan)
    else:
        result = {
            "status": "unsupported",
            "modified": False,
            "reason": f"action `{action}` is not supported",
        }

    error_msg = None if result["status"] == "success" else result.get("reason")
    execution_trace = capture_execution_trace(candidate, result, error=error_msg)

    output_path = Path(args.output).expanduser().resolve() if args.output else paths["executions"] / f"{run_id}-{candidate['id']}.json"
    execution_artifact = {
        "schema_version": SCHEMA_VERSION,
        "lane": ranking_artifact.get("lane", "generic-skill"),
        "run_id": run_id,
        "stage": "executed",
        "status": result["status"],
        "created_at": utc_now_iso(),
        "candidate_id": candidate["id"],
        "candidate": candidate,
        "source_ranking_artifact": args.input,
        "result": {
            **{key: value for key, value in result.items() if key != "after_content"},
            "backup_path": str(backup_path),
            "rollback_pointer": {
                "method": "restore_backup_file",
                "backup_path": str(backup_path),
                "target_path": str(target_file),
            },
        },
        "execution_trace": execution_trace,
        "next_step": "apply_gate",
        "next_owner": "gate",
        "truth_anchor": str(output_path),
    }
    write_json(output_path, execution_artifact)
    update_state(
        state_root,
        run_id=run_id,
        stage="executed",
        status=result["status"],
        target_path=target_path,
        truth_anchor=str(output_path),
        extra={
            "candidate_id": candidate["id"],
            "execution_modified": result.get("modified", False),
        },
    )
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
