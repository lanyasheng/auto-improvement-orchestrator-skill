#!/usr/bin/env python3
"""Clean up old state artifacts from improvement pipeline runs.

Removes candidate_versions/, rankings/, executions/, receipts/ files
older than --days (default 30). Keeps state/ files (current_state.json etc).

Usage:
    python3 scripts/cleanup-state.py --state-root /path/to/state --days 30
"""

import argparse
import time
from pathlib import Path


def cleanup(state_root: Path, max_age_days: int, dry_run: bool = False) -> dict:
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    kept = 0
    dirs_to_clean = ["candidate_versions", "rankings", "executions", "receipts", "traces", "evaluations"]

    for subdir in dirs_to_clean:
        d = state_root / subdir
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            if f.stat().st_mtime < cutoff:
                if not dry_run:
                    f.unlink()
                removed += 1
            else:
                kept += 1

    # Clean empty backup dirs
    backups = state_root / "executions" / "backups"
    if backups.exists():
        for d in sorted(backups.iterdir(), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                if not dry_run:
                    d.rmdir()

    return {"removed": removed, "kept": kept, "dry_run": dry_run}


def main():
    parser = argparse.ArgumentParser(description="Clean up old pipeline state artifacts")
    parser.add_argument("--state-root", required=True, help="State root directory")
    parser.add_argument("--days", type=int, default=30, help="Remove files older than N days (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed")
    args = parser.parse_args()

    state_root = Path(args.state_root).expanduser().resolve()
    if not state_root.exists():
        print(f"State root not found: {state_root}")
        return

    result = cleanup(state_root, args.days, args.dry_run)
    mode = "[DRY RUN] " if result["dry_run"] else ""
    print(f"{mode}Removed: {result['removed']}, Kept: {result['kept']}")


if __name__ == "__main__":
    main()
