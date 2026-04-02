#!/usr/bin/env python3
"""
PR Review Trigger - Read human decisions from PR comments/labels.

This script polls a GitHub PR for:
1. Labels: "approved", "rejected", "pending-review"
2. Comments containing decision keywords: "/approve", "/reject", "LGTM", "approved", "rejected"

Usage:
    python pr_review_trigger.py --repo lanyasheng/auto-improvement-orchestrator-skill --pr-number 1 --run-id run-xxx --candidate-id cand-xxx
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple

from pr_state import PRStateManager, ReviewRecord, ReviewState


@dataclass
class DecisionSignal:
    """A detected decision signal from PR."""
    source: str  # "label" | "comment"
    decision: str  # "approve" | "reject" | "hold"
    actor: str
    timestamp: str
    raw: str  # Original label name or comment body


DECISION_LABELS = {
    "approved": "approve",
    "approve": "approve",
    "lgtm": "approve",
    "ready-to-merge": "approve",
    "rejected": "reject",
    "reject": "reject",
    "do-not-merge": "reject",
    "pending-review": "hold",
    "needs-changes": "hold",
}

DECISION_KEYWORDS = [
    (r"/approve\b", "approve"),
    (r"\bapproved\b", "approve"),
    (r"\bLGTM\b", "approve"),
    (r"\blooks good to me\b", "approve"),
    (r"/reject\b", "reject"),
    (r"\brejected\b", "reject"),
    (r"/hold\b", "hold"),
    (r"\bneeds changes\b", "hold"),
    (r"\brequest changes\b", "hold"),
]


def run_gh_command(args: List[str], repo: Optional[str] = None) -> str:
    """Run a gh CLI command and return output."""
    cmd = ["gh"]
    if repo:
        cmd.extend(["-R", repo])
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh command failed: {result.stderr}")
    return result.stdout


def get_pr_labels(repo: str, pr_number: int) -> List[str]:
    """Get labels from a PR."""
    output = run_gh_command(["pr", "view", str(pr_number), "--json", "labels"], repo)
    data = json.loads(output)
    return [label["name"].lower() for label in data.get("labels", [])]


def get_pr_comments(repo: str, pr_number: int) -> List[dict]:
    """Get comments from a PR."""
    output = run_gh_command(["pr", "view", str(pr_number), "--json", "comments,author"], repo)
    data = json.loads(output)
    return data.get("comments", [])


def get_pr_author(repo: str, pr_number: int) -> str:
    """Get PR author."""
    output = run_gh_command(["pr", "view", str(pr_number), "--json", "author"], repo)
    data = json.loads(output)
    author = data.get("author", {})
    return author.get("login", "unknown")


def detect_decision_from_labels(labels: List[str]) -> Optional[DecisionSignal]:
    """Detect decision from PR labels."""
    for label in labels:
        label_lower = label.lower()
        if label_lower in DECISION_LABELS:
            return DecisionSignal(
                source="label",
                decision=DECISION_LABELS[label_lower],
                actor="label-applier",
                timestamp=datetime.now(timezone.utc).isoformat(),
                raw=label
            )
    return None


def detect_decision_from_comments(comments: List[dict]) -> Optional[DecisionSignal]:
    """Detect decision from PR comments (most recent matching comment wins)."""
    latest_signal = None
    for comment in comments:
        body = comment.get("body", "")
        author = comment.get("author", {}).get("login", "unknown")
        timestamp = comment.get("createdAt", "")

        for pattern, decision in DECISION_KEYWORDS:
            if re.search(pattern, body, re.IGNORECASE):
                # Later comments override earlier ones
                latest_signal = DecisionSignal(
                    source="comment",
                    decision=decision,
                    actor=author,
                    timestamp=timestamp,
                    raw=body[:200]  # Truncate for storage
                )
                break

    return latest_signal


def post_comment(repo: str, pr_number: int, body: str) -> None:
    """Post a comment to a PR."""
    run_gh_command(["pr", "comment", str(pr_number), "--body", body], repo)


def add_label(repo: str, pr_number: int, label: str) -> None:
    """Add a label to a PR."""
    run_gh_command(["pr", "edit", str(pr_number), "--add-label", label], repo)


def remove_label(repo: str, pr_number: int, label: str) -> None:
    """Remove a label from a PR."""
    run_gh_command(["pr", "edit", str(pr_number), "--remove-label", label], repo)


def main() -> int:
    parser = argparse.ArgumentParser(description="PR Review Trigger - Read human decisions from PR")
    parser.add_argument("--repo", required=True, help="GitHub repo (owner/repo)")
    parser.add_argument("--pr-number", type=int, required=True, help="PR number")
    parser.add_argument("--run-id", required=True, help="Run ID from orchestrator")
    parser.add_argument("--candidate-id", required=True, help="Candidate ID")
    parser.add_argument("--state-root", default="/Users/study/.openclaw/shared-context/intel/auto-improvement/generic-skill")
    parser.add_argument("--dry-run", action="store_true", help="Don't update state, just detect")
    parser.add_argument("--create-if-missing", action="store_true", help="Create review record if not exists")
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve()
    manager = PRStateManager(state_root)

    # Get PR info
    pr_url = f"https://github.com/{args.repo}/pull/{args.pr_number}"
    pr_author = get_pr_author(args.repo, args.pr_number)
    labels = get_pr_labels(args.repo, args.pr_number)
    comments = get_pr_comments(args.repo, args.pr_number)

    print(f"PR #{args.pr_number} by @{pr_author}")
    print(f"Labels: {labels}")
    print(f"Comments: {len(comments)}")

    # Detect decision from labels first, then comments
    decision_signal = detect_decision_from_labels(labels)
    if not decision_signal:
        decision_signal = detect_decision_from_comments(comments)

    if decision_signal:
        print(f"\nDetected decision: {decision_signal.decision} (from {decision_signal.source} by @{decision_signal.actor})")
    else:
        print("\nNo decision signal detected")

    # Load or create review record
    record = manager.load_review(args.run_id, args.candidate_id)
    if not record:
        if args.create_if_missing:
            print(f"\nCreating new review record...")
            record = manager.create_review(args.run_id, args.candidate_id, args.pr_number, pr_url)
        else:
            print(f"\nNo review record found for {args.run_id}/{args.candidate_id}")
            print("Use --create-if-missing to create one")
            return 1

    # Update state based on detected decision
    if decision_signal and not args.dry_run:
        if decision_signal.decision == "approve":
            manager.approve(args.run_id, args.candidate_id, decision_source=decision_signal.source, reviewer=decision_signal.actor)
            print(f"\n✓ Updated state: APPROVED")
            # Post confirmation comment
            post_comment(args.repo, args.pr_number, f"✓ Human review approved by @{decision_signal.actor}\n\nDecision source: {decision_signal.source}\nRun: `{args.run_id}` | Candidate: `{args.candidate_id}`")
            # Add label (best effort, may fail due to GitHub API deprecation)
            try:
                add_label(args.repo, args.pr_number, "approved")
            except RuntimeError as e:
                print(f"  Note: Could not add label (GitHub API issue): {e}")
            # Remove pending-review label if exists
            try:
                remove_label(args.repo, args.pr_number, "pending-review")
            except:
                pass
        elif decision_signal.decision == "reject":
            manager.reject(args.run_id, args.candidate_id, decision_source=decision_signal.source, reviewer=decision_signal.actor)
            print(f"\n✗ Updated state: REJECTED")
            post_comment(args.repo, args.pr_number, f"✗ Human review rejected by @{decision_signal.actor}\n\nDecision source: {decision_signal.source}\nRun: `{args.run_id}` | Candidate: `{args.candidate_id}`")
            try:
                add_label(args.repo, args.pr_number, "rejected")
            except RuntimeError as e:
                print(f"  Note: Could not add label (GitHub API issue): {e}")
            try:
                remove_label(args.repo, args.pr_number, "pending-review")
            except:
                pass
        elif decision_signal.decision == "hold":
            manager.mark_reviewed(args.run_id, args.candidate_id, decision_source=decision_signal.source, reviewer=decision_signal.actor)
            print(f"\n⏸ Updated state: REVIEWED (hold)")
    else:
        print(f"\nState: {record.state} (no change)")

    # Output final state
    final_record = manager.load_review(args.run_id, args.candidate_id)
    print(f"\nFinal state: {final_record.state}")
    print(f"Receipt: {manager._review_path(args.run_id, args.candidate_id)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
