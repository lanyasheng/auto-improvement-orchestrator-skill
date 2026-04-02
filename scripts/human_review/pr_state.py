#!/usr/bin/env python3
"""PR state machine for human review integration."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class ReviewState(str, Enum):
    """Minimal state machine for human review."""
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ReviewRecord:
    """Human review record tied to a PR."""
    schema_version: str = "v1"
    lane: str = "generic-skill"
    run_id: str = ""
    candidate_id: str = ""
    pr_number: int = 0
    pr_url: str = ""
    state: str = ReviewState.PENDING_REVIEW.value
    decision: Optional[str] = None
    decision_source: Optional[str] = None  # "label" | "comment" | "api"
    reviewer: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    receipt_path: Optional[str] = None
    gate_receipt_path: Optional[str] = None
    truth_anchor: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.truth_anchor:
            self.truth_anchor = f"pr:{self.pr_number}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PRStateManager:
    """Manage human review state for PRs."""

    def __init__(self, state_root: Path):
        self.state_root = Path(state_root).expanduser().resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.reviews_dir = self.state_root / "pr_reviews"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

    def _review_path(self, run_id: str, candidate_id: str) -> Path:
        return self.reviews_dir / f"{run_id}-{candidate_id}-review.json"

    def create_review(self, run_id: str, candidate_id: str, pr_number: int, pr_url: str, gate_receipt_path: Optional[str] = None) -> ReviewRecord:
        """Create a new review record in pending_review state."""
        record = ReviewRecord(
            run_id=run_id,
            candidate_id=candidate_id,
            pr_number=pr_number,
            pr_url=pr_url,
            state=ReviewState.PENDING_REVIEW.value,
            gate_receipt_path=gate_receipt_path,
        )
        self._save_review(record)
        return record

    def load_review(self, run_id: str, candidate_id: str) -> Optional[ReviewRecord]:
        """Load an existing review record."""
        path = self._review_path(run_id, candidate_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            return ReviewRecord.from_dict(json.load(f))

    def update_state(self, record: ReviewRecord, new_state: ReviewState, decision: Optional[str] = None, decision_source: Optional[str] = None, reviewer: Optional[str] = None) -> ReviewRecord:
        """Update review state."""
        record.state = new_state.value
        record.decision = decision
        record.decision_source = decision_source
        record.reviewer = reviewer
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_review(record)
        return record

    def approve(self, run_id: str, candidate_id: str, decision_source: str = "manual", reviewer: Optional[str] = None) -> ReviewRecord:
        """Mark review as approved."""
        record = self.load_review(run_id, candidate_id)
        if not record:
            raise ValueError(f"No review record found for {run_id}/{candidate_id}")
        return self.update_state(record, ReviewState.APPROVED, decision="approved", decision_source=decision_source, reviewer=reviewer)

    def reject(self, run_id: str, candidate_id: str, decision_source: str = "manual", reviewer: Optional[str] = None) -> ReviewRecord:
        """Mark review as rejected."""
        record = self.load_review(run_id, candidate_id)
        if not record:
            raise ValueError(f"No review record found for {run_id}/{candidate_id}")
        return self.update_state(record, ReviewState.REJECTED, decision="rejected", decision_source=decision_source, reviewer=reviewer)

    def mark_reviewed(self, run_id: str, candidate_id: str, decision_source: str = "manual", reviewer: Optional[str] = None) -> ReviewRecord:
        """Mark review as reviewed (intermediate state before approve/reject)."""
        record = self.load_review(run_id, candidate_id)
        if not record:
            raise ValueError(f"No review record found for {run_id}/{candidate_id}")
        return self.update_state(record, ReviewState.REVIEWED, decision_source=decision_source, reviewer=reviewer)

    def _save_review(self, record: ReviewRecord) -> None:
        path = self._review_path(record.run_id, record.candidate_id)
        with open(path, "w") as f:
            json.dump(record.to_dict(), f, indent=2)

    def list_pending(self) -> list[ReviewRecord]:
        """List all pending reviews."""
        pending = []
        for path in self.reviews_dir.glob("*-review.json"):
            with open(path, "r") as f:
                record = ReviewRecord.from_dict(json.load(f))
                if record.state == ReviewState.PENDING_REVIEW.value:
                    pending.append(record)
        return pending

    def list_all(self) -> list[ReviewRecord]:
        """List all reviews."""
        reviews = []
        for path in self.reviews_dir.glob("*-review.json"):
            with open(path, "r") as f:
                reviews.append(ReviewRecord.from_dict(json.load(f)))
        return sorted(reviews, key=lambda r: r.created_at, reverse=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PR State Manager")
    parser.add_argument("--state-root", default="/Users/study/.openclaw/shared-context/intel/auto-improvement/generic-skill")
    parser.add_argument("--action", choices=["list", "create", "approve", "reject", "show"])
    parser.add_argument("--run-id")
    parser.add_argument("--candidate-id")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--pr-url")
    args = parser.parse_args()

    manager = PRStateManager(Path(args.state_root))

    if args.action == "list":
        reviews = manager.list_all()
        for r in reviews:
            print(f"{r.run_id}/{r.candidate_id}: {r.state} (PR #{r.pr_number})")
    elif args.action == "create" and args.run_id and args.candidate_id and args.pr_number:
        record = manager.create_review(args.run_id, args.candidate_id, args.pr_number, args.pr_url or "")
        print(f"Created review: {record.truth_anchor}")
    elif args.action == "approve" and args.run_id and args.candidate_id:
        record = manager.approve(args.run_id, args.candidate_id)
        print(f"Approved: {record.truth_anchor}")
    elif args.action == "reject" and args.run_id and args.candidate_id:
        record = manager.reject(args.run_id, args.candidate_id)
        print(f"Rejected: {record.truth_anchor}")
    elif args.action == "show" and args.run_id and args.candidate_id:
        record = manager.load_review(args.run_id, args.candidate_id)
        if record:
            print(json.dumps(record.to_dict(), indent=2))
        else:
            print("No review found")
