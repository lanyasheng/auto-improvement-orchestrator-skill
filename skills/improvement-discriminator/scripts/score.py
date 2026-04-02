#!/usr/bin/env python3
"""Critic for the generic-skill lane.

Phase 1 adds an optional skill-evaluator evidence mode so ranking can use
rubric/category/boundary evidence in addition to the original heuristic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))      # scripts/

from rubric_evidence import build_evaluator_evidence
from lib.common import (
    KEEP_CATEGORIES,
    SCHEMA_VERSION,
    protected_target,
    read_json,
    utc_now_iso,
    write_json,
)
from lib.state_machine import (
    DEFAULT_STATE_ROOT,
    ensure_tree,
    update_state,
)

DEFAULT_CATEGORY_WEIGHTS = {
    "docs": 4.0,
    "reference": 3.5,
    "guardrail": 3.5,
    "workflow": 1.5,
    "prompt": 1.0,
    "tests": 1.5,
}
CATEGORY_BONUS = DEFAULT_CATEGORY_WEIGHTS  # backward compat alias
RISK_PENALTY = {"low": 0.0, "medium": 2.0, "high": 4.5}
HEURISTIC_WEIGHT = 0.7
EVALUATOR_WEIGHT = 0.3


# ---------------------------------------------------------------------------
# Multi-reviewer panel (Phase 2A)
# ---------------------------------------------------------------------------


class ReviewerConfig:
    """Configuration for a single reviewer in the panel."""

    def __init__(
        self,
        name: str,
        category_weights: dict | None = None,
        risk_sensitivity: float = 1.0,
        use_evaluator: bool = False,
    ):
        self.name = name
        self.category_weights = category_weights or dict(DEFAULT_CATEGORY_WEIGHTS)
        self.risk_sensitivity = risk_sensitivity
        self.use_evaluator = use_evaluator


DEFAULT_REVIEWERS = [
    ReviewerConfig(
        "structural",
        category_weights={
            "docs": 5.0,
            "reference": 4.0,
            "guardrail": 4.0,
            "workflow": 2.0,
            "prompt": 1.5,
            "tests": 2.0,
        },
    ),
    ReviewerConfig(
        "conservative",
        risk_sensitivity=1.5,
        category_weights={
            "docs": 3.0,
            "reference": 3.0,
            "guardrail": 5.0,
            "workflow": 1.0,
            "prompt": 0.5,
            "tests": 1.0,
        },
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score and rank generic-skill candidates")
    parser.add_argument("--input", required=True, help="Candidate artifact JSON")
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--use-evaluator-evidence",
        action="store_true",
        help="Blend Phase 1 skill-evaluator rubric/category/boundary evidence into scoring.",
    )
    parser.add_argument(
        "--panel",
        action="store_true",
        help="Enable multi-reviewer blind panel scoring (Phase 2A).",
    )
    return parser.parse_args()


def heuristic_score(candidate: dict) -> tuple[float, float]:
    category = candidate.get("category", "unknown")
    risk_level = candidate.get("risk_level", "medium")
    source_refs = candidate.get("source_refs", []) or []
    executor_support = bool(candidate.get("executor_support"))
    base = 4.0
    category_bonus = CATEGORY_BONUS.get(category, 0.5)
    source_signal = min(len(source_refs), 3) * 0.5
    support_bonus = 0.5 if executor_support else 0.0
    protected_penalty = 2.5 if protected_target(candidate.get("target_path", "")) else 0.0
    risk_penalty = RISK_PENALTY.get(risk_level, 2.0) + protected_penalty
    score = max(0.0, min(10.0, round(base + category_bonus + source_signal + support_bonus - risk_penalty, 2)))
    return score, round(risk_penalty, 2)


def build_blockers(candidate: dict, *, evidence: dict | None = None) -> list[str]:
    blockers: list[str] = []
    category = candidate.get("category", "unknown")
    risk_level = candidate.get("risk_level", "medium")

    if protected_target(candidate.get("target_path", "")):
        blockers.append("protected_target")
    if not candidate.get("executor_support"):
        blockers.append("executor_not_supported")
    if category not in KEEP_CATEGORIES:
        blockers.append("not_auto_keep_category")
    if risk_level != "low":
        blockers.append(f"risk_{risk_level}")

    if evidence:
        skill_level = evidence.get("skill_profile", {}).get("skill_level")
        evaluator_verdict = evidence.get("verdict")
        if skill_level == "Level 1" and category in {"workflow", "prompt", "tests"}:
            blockers.append("skill_level_insufficient_for_structural_change")
        if evaluator_verdict == "reject":
            blockers.append("evaluator_reject")
    return blockers


def build_recommendation(candidate: dict, score: float, blockers: list[str], evidence: dict | None = None) -> str:
    is_low_risk_keep = (
        candidate.get("category") in KEEP_CATEGORIES
        and candidate.get("risk_level") == "low"
        and bool(candidate.get("executor_support"))
        and not protected_target(candidate.get("target_path", ""))
    )
    if evidence:
        boundary = evidence.get("boundary", {})
        if is_low_risk_keep and boundary.get("auto_promote_eligible") and evidence.get("verdict") != "reject":
            return "accept_for_execution"
        if evidence.get("verdict") == "reject" or score < 4.0:
            return "reject"
        return "hold"

    if is_low_risk_keep:
        return "accept_for_execution"
    if candidate.get("risk_level") == "high" or score < 4.0:
        return "reject"
    return "hold"


def build_judge_notes(candidate: dict, recommendation: str, blockers: list[str], evidence: dict | None = None) -> list[str]:
    judge_notes: list[str] = []
    if recommendation == "accept_for_execution":
        judge_notes.append("低风险 + 文档/引用类候选，可交给第一版 executor。")
    if "executor_not_supported" in blockers:
        judge_notes.append("当前 executor 只支持 docs/reference/guardrail 的简单文案追加。")
    if "protected_target" in blockers:
        judge_notes.append("目标路径属于保护区域，需要人工 gate。")
    if "skill_level_insufficient_for_structural_change" in blockers:
        judge_notes.append("skill-evaluator rubric 认为当前目标 skill 级别过低，不宜直接推进结构性改动。")
    if recommendation == "hold":
        judge_notes.append("先进入 pending_promote / human review，等待后续 richer judge。")
    if recommendation == "reject":
        judge_notes.append("当前判断认为收益不足、证据不足或风险过高。")
    if evidence:
        rubric = evidence.get("rubric", {})
        judge_notes.append(
            f"Phase 1 evaluator evidence: {rubric.get('evaluator_category', 'process-type')} rubric, verdict={evidence.get('verdict')}, overall={evidence.get('overall_score_10', 0):.2f}/10。"
        )
        for limitation in evidence.get("limitations", [])[:2]:
            judge_notes.append(limitation)
    return judge_notes


def score_candidate(candidate: dict, *, use_evaluator_evidence: bool = False) -> dict:
    heuristic, risk_penalty = heuristic_score(candidate)
    evidence = build_evaluator_evidence(candidate) if use_evaluator_evidence else None
    evaluator_score = evidence.get("overall_score_10") if evidence else None
    final_score = heuristic
    if evaluator_score is not None:
        final_score = round((heuristic * HEURISTIC_WEIGHT) + (evaluator_score * EVALUATOR_WEIGHT), 2)

    blockers = build_blockers(candidate, evidence=evidence)
    recommendation = build_recommendation(candidate, final_score, blockers, evidence=evidence)
    judge_notes = build_judge_notes(candidate, recommendation, blockers, evidence=evidence)

    payload = {
        **candidate,
        "score": final_score,
        "heuristic_score": heuristic,
        "risk_penalty": risk_penalty,
        "recommendation": recommendation,
        "blockers": blockers,
        "judge_notes": judge_notes,
        "judge_adapter": {
            "name": "heuristic+evaluator-phase1" if use_evaluator_evidence else "rule-based-heuristic-v1",
            "future_replacement": "full-skill-evaluator-adapter",
            "evaluated_at": utc_now_iso(),
            "evaluator_evidence_enabled": use_evaluator_evidence,
        },
    }
    if evidence:
        payload["score_components"] = {
            "heuristic_weight": HEURISTIC_WEIGHT,
            "evaluator_weight": EVALUATOR_WEIGHT,
            "heuristic_score": heuristic,
            "evaluator_score": evaluator_score,
        }
        payload["evaluator_score"] = evaluator_score
        payload["evaluator_evidence"] = evidence
    return payload


def _heuristic_score_with_config(candidate: dict, config: ReviewerConfig) -> tuple[float, float]:
    """Compute heuristic score using reviewer-specific category weights and risk sensitivity."""
    category = candidate.get("category", "unknown")
    risk_level = candidate.get("risk_level", "medium")
    source_refs = candidate.get("source_refs", []) or []
    executor_support = bool(candidate.get("executor_support"))
    base = 4.0
    category_bonus = config.category_weights.get(category, 0.5)
    source_signal = min(len(source_refs), 3) * 0.5
    support_bonus = 0.5 if executor_support else 0.0
    protected_penalty = 2.5 if protected_target(candidate.get("target_path", "")) else 0.0
    raw_risk = RISK_PENALTY.get(risk_level, 2.0) + protected_penalty
    risk_penalty = round(raw_risk * config.risk_sensitivity, 2)
    score = max(0.0, min(10.0, round(base + category_bonus + source_signal + support_bonus - risk_penalty, 2)))
    return score, risk_penalty


def score_candidate_with_config(candidate: dict, config: ReviewerConfig) -> dict:
    """Score a candidate using a specific ReviewerConfig.

    Mirrors score_candidate() but substitutes the reviewer's category_weights
    and risk_sensitivity.  Evaluator evidence is blended only when
    config.use_evaluator is True.
    """
    heuristic, risk_penalty = _heuristic_score_with_config(candidate, config)
    evidence = build_evaluator_evidence(candidate) if config.use_evaluator else None
    evaluator_score = evidence.get("overall_score_10") if evidence else None
    final_score = heuristic
    if evaluator_score is not None:
        final_score = round((heuristic * HEURISTIC_WEIGHT) + (evaluator_score * EVALUATOR_WEIGHT), 2)

    blockers = build_blockers(candidate, evidence=evidence)
    recommendation = build_recommendation(candidate, final_score, blockers, evidence=evidence)
    judge_notes = build_judge_notes(candidate, recommendation, blockers, evidence=evidence)

    payload = {
        **candidate,
        "score": final_score,
        "heuristic_score": heuristic,
        "risk_penalty": risk_penalty,
        "recommendation": recommendation,
        "blockers": blockers,
        "judge_notes": judge_notes,
        "reviewer": config.name,
        "judge_adapter": {
            "name": f"multi-reviewer-{config.name}",
            "future_replacement": "full-skill-evaluator-adapter",
            "evaluated_at": utc_now_iso(),
            "evaluator_evidence_enabled": config.use_evaluator,
        },
    }
    if evidence:
        payload["score_components"] = {
            "heuristic_weight": HEURISTIC_WEIGHT,
            "evaluator_weight": EVALUATOR_WEIGHT,
            "heuristic_score": heuristic,
            "evaluator_score": evaluator_score,
        }
        payload["evaluator_score"] = evaluator_score
        payload["evaluator_evidence"] = evidence
    return payload


def run_multi_reviewer_panel(
    candidate: dict,
    reviewers: list[ReviewerConfig] | None = None,
) -> dict:
    """Run blind multi-reviewer panel on a candidate.

    Each reviewer scores independently (no visibility into other scores).
    The panel then determines consensus via cognitive labels:
      - CONSENSUS: all reviewers agree on the recommendation
      - VERIFIED:  2+ reviewers agree (majority)
      - DISPUTED:  no majority; default recommendation becomes "hold"
    """
    reviewers = reviewers or DEFAULT_REVIEWERS
    reviews: list[dict] = []
    for reviewer in reviewers:
        scored = score_candidate_with_config(candidate, reviewer)
        reviews.append({
            "reviewer": reviewer.name,
            "score": scored["score"],
            "recommendation": scored["recommendation"],
        })

    # --- Determine consensus ---
    recommendations = [r["recommendation"] for r in reviews]
    unique_recs = set(recommendations)

    if len(unique_recs) == 1:
        label = "CONSENSUS"
        final_rec = recommendations[0]
    else:
        # Find the most common recommendation
        from collections import Counter
        counts = Counter(recommendations)
        most_common_rec, most_common_count = counts.most_common(1)[0]
        if most_common_count >= 2:
            label = "VERIFIED"
            final_rec = most_common_rec
        else:
            label = "DISPUTED"
            final_rec = "hold"  # Default to hold on dispute

    avg_score = sum(r["score"] for r in reviews) / len(reviews)
    return {
        "panel_reviews": reviews,
        "cognitive_label": label,
        "final_recommendation": final_rec,
        "aggregated_score": round(avg_score, 2),
    }


def main() -> int:
    args = parse_args()
    state_root = Path(args.state_root).expanduser().resolve()
    ensure_tree(state_root)

    candidate_artifact = read_json(Path(args.input).expanduser().resolve())
    run_id = candidate_artifact["run_id"]
    target_path = candidate_artifact["target"]["path"]
    raw_candidates = candidate_artifact.get("candidates", [])

    if args.panel:
        # Multi-reviewer panel mode (Phase 2A)
        panel_results = []
        for candidate in raw_candidates:
            panel = run_multi_reviewer_panel(candidate)
            panel_results.append({
                **candidate,
                "score": panel["aggregated_score"],
                "recommendation": panel["final_recommendation"],
                "panel": panel,
            })
        ranked_candidates = sorted(panel_results, key=lambda item: item["score"], reverse=True)
    else:
        ranked_candidates = sorted(
            [score_candidate(candidate, use_evaluator_evidence=args.use_evaluator_evidence) for candidate in raw_candidates],
            key=lambda item: item["score"],
            reverse=True,
        )

    output_path = Path(args.output).expanduser().resolve() if args.output else state_root / "rankings" / f"{run_id}.json"
    ranking_artifact = {
        "schema_version": SCHEMA_VERSION,
        "lane": candidate_artifact.get("lane", "generic-skill"),
        "run_id": run_id,
        "stage": "ranked",
        "status": "success",
        "created_at": utc_now_iso(),
        "source_candidate_artifact": args.input,
        "target": candidate_artifact["target"],
        "critic_mode": "multi-reviewer-panel" if args.panel else ("heuristic+evaluator-phase1" if args.use_evaluator_evidence else "heuristic-only"),
        "scored_candidates": ranked_candidates,
        "summary": {
            "accept_for_execution": sum(1 for item in ranked_candidates if item["recommendation"] == "accept_for_execution"),
            "hold": sum(1 for item in ranked_candidates if item["recommendation"] == "hold"),
            "reject": sum(1 for item in ranked_candidates if item["recommendation"] == "reject"),
            "evaluator_evidence_enabled": args.use_evaluator_evidence,
        },
        "next_step": "execute_candidate",
        "next_owner": "executor",
        "truth_anchor": str(output_path),
    }
    write_json(output_path, ranking_artifact)
    update_state(
        state_root,
        run_id=run_id,
        stage="ranked",
        status="success",
        target_path=target_path,
        truth_anchor=str(output_path),
        extra={
            "ranked_candidate_count": len(ranked_candidates),
            "top_candidate_id": ranked_candidates[0]["id"] if ranked_candidates else None,
            "critic_mode": ranking_artifact["critic_mode"],
        },
    )
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
