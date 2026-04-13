#!/usr/bin/env python3
"""Export session feedback into markdown so QMD/study-brain can index it."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SkillStats:
    total: int = 0
    corrections: int = 0
    partials: int = 0
    acceptances: int = 0

    @property
    def correction_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.corrections / self.total


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export feedback.jsonl into a markdown artifact for QMD indexing",
    )
    parser.add_argument(
        "--input",
        default="feedback-store/feedback.jsonl",
        help="Input feedback JSONL path",
    )
    parser.add_argument(
        "--output",
        default=f"feedback-store/{datetime.now().strftime('%Y-%m-%d')}-session-feedback-hotspots.md",
        help="Output markdown path",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of hotspot skills to include",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=2,
        help="Minimum events before a skill is considered a hotspot",
    )
    return parser.parse_args(argv)


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def compute_skill_stats(events: list[dict[str, Any]]) -> dict[str, SkillStats]:
    stats: dict[str, SkillStats] = defaultdict(SkillStats)
    for event in events:
        skill_id = event.get("skill_id", "")
        outcome = event.get("outcome", "")
        if not skill_id:
            continue

        bucket = stats[skill_id]
        bucket.total += 1
        if outcome == "correction":
            bucket.corrections += 1
        elif outcome == "partial":
            bucket.partials += 1
        elif outcome == "acceptance":
            bucket.acceptances += 1
    return stats


def normalize_dimension(value: Any) -> str:
    if not value or value == "None":
        return "unknown"
    return str(value)


def build_markdown(events: list[dict[str, Any]], top: int, min_events: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats = compute_skill_stats(events)
    recent_events = sorted(events, key=lambda item: item.get("timestamp", ""), reverse=True)
    correction_dimensions = Counter(
        normalize_dimension(event.get("dimension_hint"))
        for event in events
        if event.get("outcome") == "correction"
    )

    ranked = [
        (skill_id, stat)
        for skill_id, stat in stats.items()
        if stat.total >= min_events and stat.corrections > 0
    ]
    ranked.sort(
        key=lambda item: (item[1].correction_rate, item[1].corrections, item[1].total),
        reverse=True,
    )

    lines = [
        "---",
        "title: Session Feedback Hotspots",
        "source: session-feedback-analyzer",
        f"generated_at: {now}",
        "tags: [session-feedback, lessons, skill-quality]",
        "---",
        "",
        "# Session Feedback Hotspots",
        "",
        "This artifact is auto-generated from `feedback.jsonl`. It converts runtime correction signals into a markdown artifact that can be indexed by QMD or imported into study-brain.",
        "",
        "## Snapshot",
        "",
        f"- Total feedback events: {len(events)}",
        f"- Correction events: {sum(1 for event in events if event.get('outcome') == 'correction')}",
        f"- Partial events: {sum(1 for event in events if event.get('outcome') == 'partial')}",
        f"- Acceptance events: {sum(1 for event in events if event.get('outcome') == 'acceptance')}",
        "",
        "## Top Correction Dimensions",
        "",
    ]

    if correction_dimensions:
        for dimension, count in correction_dimensions.most_common(5):
            lines.append(f"- `{dimension}`: {count}")
    else:
        lines.append("- No correction dimensions detected yet")

    lines.extend([
        "",
        "## Skill Hotspots",
        "",
    ])

    if ranked:
        for skill_id, stat in ranked[:top]:
            lines.extend([
                f"### `{skill_id}`",
                f"- Total events: {stat.total}",
                f"- Corrections: {stat.corrections}",
                f"- Partials: {stat.partials}",
                f"- Acceptances: {stat.acceptances}",
                f"- Correction rate: {stat.correction_rate:.0%}",
                "",
            ])
    else:
        lines.append("- No hotspot skill has reached the current threshold yet.")
        lines.append("")

    lines.extend([
        "## Recent Correction Examples",
        "",
    ])

    correction_examples = [
        event for event in recent_events
        if event.get("outcome") in {"correction", "partial"}
    ][:10]
    if correction_examples:
        for event in correction_examples:
            snippet = str(event.get("user_message_snippet", "")).strip() or "(no snippet)"
            lines.append(
                f"- `{event.get('timestamp', '')}` | `{event.get('skill_id', '')}` | `{event.get('outcome', '')}` | `{normalize_dimension(event.get('dimension_hint'))}` | {snippet}"
            )
    else:
        lines.append("- No correction-like examples available.")

    lines.extend([
        "",
        "## Suggested Next Actions",
        "",
        "- Review hotspot skills with repeated corrections first.",
        "- Promote durable fixes into `study-brain` lessons or skill docs.",
        "- Keep this file indexed by QMD so recall can use recent correction patterns.",
        "",
    ])

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    events = load_events(input_path)
    markdown = build_markdown(events, top=args.top, min_events=args.min_events)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown + "\n", encoding="utf-8")

    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
