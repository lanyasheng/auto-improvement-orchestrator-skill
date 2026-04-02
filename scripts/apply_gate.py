#!/usr/bin/env python3
"""Gate for the first runnable generic-skill lane."""

from __future__ import annotations

import argparse
from pathlib import Path

from lane_common import (
    DEFAULT_STATE_ROOT,
    KEEP_CATEGORIES,
    SCHEMA_VERSION,
    append_pending_promote,
    append_veto,
    ensure_tree,
    make_receipt_path,
    protected_target,
    read_json,
    restore_backup,
    update_state,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply gate decision for generic-skill lane")
    parser.add_argument("--ranking", required=True, help="Ranking artifact JSON")
    parser.add_argument("--execution", required=True, help="Execution artifact JSON")
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def load_candidate(ranking_artifact: dict, candidate_id: str) -> dict:
    for candidate in ranking_artifact.get("scored_candidates", []):
        if candidate["id"] == candidate_id:
            return candidate
    raise KeyError(f"candidate not found in ranking artifact: {candidate_id}")


def maybe_restore(execution_artifact: dict) -> dict:
    result = execution_artifact.get("result", {})
    rollback = result.get("rollback_pointer")
    if not rollback or not result.get("modified"):
        return {"attempted": False, "success": False, "reason": "no modified file to restore"}
    backup_path = Path(rollback["backup_path"]).expanduser().resolve()
    target_path = Path(rollback["target_path"]).expanduser().resolve()
    restore_backup(backup_path, target_path)
    return {
        "attempted": True,
        "success": True,
        "backup_path": str(backup_path),
        "target_path": str(target_path),
    }


def main() -> int:
    args = parse_args()
    state_root = Path(args.state_root).expanduser().resolve()
    ensure_tree(state_root)

    ranking_artifact = read_json(Path(args.ranking).expanduser().resolve())
    execution_artifact = read_json(Path(args.execution).expanduser().resolve())
    run_id = ranking_artifact["run_id"]
    candidate_id = execution_artifact["candidate_id"]
    candidate = load_candidate(ranking_artifact, candidate_id)
    execution_result = execution_artifact.get("result", {})

    recommendation = candidate.get("recommendation")
    category = candidate.get("category")
    target_path = candidate.get("target_path")
    keep_eligible = (
        recommendation == "accept_for_execution"
        and category in KEEP_CATEGORIES
        and candidate.get("risk_level") == "low"
        and not protected_target(target_path)
        and execution_result.get("status") in {"success", "no_change"}
    )

    rollback_outcome = {"attempted": False, "success": False, "reason": "not_needed"}
    reason = ""
    if keep_eligible:
        decision = "keep"
        reason = "low-risk docs/reference/guardrail candidate executed successfully"
    elif recommendation == "reject":
        decision = "revert" if execution_result.get("modified") else "reject"
        rollback_outcome = maybe_restore(execution_artifact)
        reason = "critic rejected candidate under conservative gate"
    elif recommendation == "hold":
        decision = "pending_promote"
        rollback_outcome = maybe_restore(execution_artifact)
        reason = "critic marked candidate as hold; persisted to pending_promote for later human/control-plane review"
    elif execution_result.get("status") == "unsupported":
        decision = "reject"
        reason = execution_result.get("reason", "executor returned unsupported")
    elif execution_result.get("status") not in {"success", "no_change"}:
        decision = "revert" if execution_result.get("modified") else "reject"
        rollback_outcome = maybe_restore(execution_artifact)
        reason = f"execution status `{execution_result.get('status')}` did not pass gate"
    else:
        decision = "pending_promote"
        rollback_outcome = maybe_restore(execution_artifact)
        reason = "candidate is not auto-keep eligible in first runnable version; escalated to pending_promote"

    output_path = Path(args.output).expanduser().resolve() if args.output else make_receipt_path(state_root, "gate", run_id, candidate_id)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "lane": ranking_artifact.get("lane", "generic-skill"),
        "run_id": run_id,
        "stage": "gated",
        "status": "success",
        "created_at": utc_now_iso(),
        "decision": decision,
        "reason": reason,
        "candidate_id": candidate_id,
        "candidate_category": category,
        "source_ranking_artifact": args.ranking,
        "source_execution_artifact": args.execution,
        "rollback": rollback_outcome,
        "next_step": "propose_candidates" if decision == "keep" else "human_promote_review" if decision == "pending_promote" else "re-propose_or_manual_override",
        "next_owner": "proposer" if decision == "keep" else "human" if decision == "pending_promote" else "proposer",
        "truth_anchor": str(output_path),
    }
    write_json(output_path, receipt)

    if decision == "pending_promote":
        append_pending_promote(
            state_root,
            {
                "run_id": run_id,
                "candidate_id": candidate_id,
                "category": category,
                "target_path": target_path,
                "recommendation": recommendation,
                "receipt_path": str(output_path),
                "created_at": utc_now_iso(),
            },
        )
    elif decision in {"reject", "revert"}:
        append_veto(
            state_root,
            {
                "run_id": run_id,
                "candidate_id": candidate_id,
                "category": category,
                "target_path": target_path,
                "decision": decision,
                "reason": reason,
                "receipt_path": str(output_path),
                "created_at": utc_now_iso(),
            },
        )

    update_state(
        state_root,
        run_id=run_id,
        stage={
            "keep": "gated_keep",
            "pending_promote": "gated_pending",
            "revert": "gated_revert",
            "reject": "gated_reject",
        }[decision],
        status=decision,
        target_path=ranking_artifact["target"]["path"],
        truth_anchor=str(output_path),
        extra={
            "candidate_id": candidate_id,
            "decision": decision,
            "receipt_path": str(output_path),
        },
    )
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
