#!/usr/bin/env python3
"""Shared helpers for the generic-skill auto-improvement lane."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_STATE_ROOT = Path("$OPENCLAW_ROOT/shared-context/intel/auto-improvement/generic-skill")
SCHEMA_VERSION = "1.0"
KEEP_CATEGORIES = {"docs", "reference", "guardrail"}
EXECUTOR_SUPPORTED_CATEGORIES = {"docs", "reference", "guardrail"}
PROTECTED_KEYWORDS = (
    "trading",
    "gateway",
    "openclaw-company-orchestration-proposal",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    cleaned = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "item"


def ensure_tree(state_root: Path) -> dict[str, Path]:
    state_root = state_root.expanduser().resolve()
    mapping = {
        "root": state_root,
        "candidate_versions": state_root / "candidate_versions",
        "rankings": state_root / "rankings",
        "executions": state_root / "executions",
        "state": state_root / "state",
        "receipts": state_root / "receipts",
    }
    for path in mapping.values():
        path.mkdir(parents=True, exist_ok=True)
    init_state_files(mapping)
    return mapping


def init_state_files(paths: dict[str, Path]) -> None:
    defaults = {
        paths["state"] / "current_state.json": {
            "lane": "generic-skill",
            "status": "idle",
            "stage": "idle",
            "current_run_id": None,
            "target_path": None,
            "next_step": "propose_candidates",
            "next_owner": "proposer",
            "truth_anchor": str(paths["state"] / "current_state.json"),
            "updated_at": None,
        },
        paths["state"] / "pending_promote.json": {
            "pending": [],
            "last_updated": None,
        },
        paths["state"] / "veto.json": {
            "vetoes": [],
            "last_updated": None,
        },
        paths["state"] / "last_run.json": {
            "lane": "generic-skill",
            "last_run_id": None,
            "last_stage": "idle",
            "last_status": "idle",
            "last_updated": None,
            "truth_anchor": str(paths["state"] / "last_run.json"),
        },
    }
    for path, payload in defaults.items():
        if not path.exists():
            write_json(path, payload)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def infer_source_kind(path: Path) -> str:
    lowered = str(path).lower()
    if ".feedback" in lowered or "feedback" in path.name.lower():
        return "feedback"
    if "learning" in lowered:
        return "learnings"
    if "memory" in lowered:
        return "memory"
    return "source"


def load_source_paths(target: Path, explicit_sources: Iterable[str] | None = None) -> list[Path]:
    sources: list[Path] = []
    for raw in explicit_sources or []:
        if not raw:
            continue
        source = Path(raw).expanduser()
        if source.exists():
            sources.append(source.resolve())
    candidates = [target / "memory", target / "learnings", target / ".feedback"]
    for candidate in candidates:
        if candidate.exists():
            sources.append(candidate.resolve())
    seen: set[str] = set()
    deduped: list[Path] = []
    for source in sources:
        key = str(source)
        if key not in seen:
            deduped.append(source)
            seen.add(key)
    return deduped


def expand_source(source: Path) -> list[dict[str, Any]]:
    if source.is_file():
        return [load_source_entry(source)]
    entries: list[dict[str, Any]] = []
    for child in sorted(source.rglob("*")):
        if not child.is_file():
            continue
        if child.suffix.lower() not in {".md", ".txt", ".json", ".log"}:
            continue
        entries.append(load_source_entry(child))
    return entries


def load_source_entry(path: Path) -> dict[str, Any]:
    raw = read_text(path)
    snippet = " ".join(raw.split())[:400]
    return {
        "path": str(path),
        "kind": infer_source_kind(path),
        "characters": len(raw),
        "snippet": snippet,
    }


def normalize_target(target: str) -> Path:
    return Path(target).expanduser().resolve()


def choose_doc_file(target: Path) -> Path | None:
    if target.is_file():
        return target
    preferred = [target / "README.md", target / "SKILL.md"]
    preferred.extend(sorted((target / "references").glob("*.md")) if (target / "references").exists() else [])
    for candidate in preferred:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    markdown_files = sorted(target.glob("*.md"))
    return markdown_files[0].resolve() if markdown_files else None


def choose_reference_file(target: Path) -> Path | None:
    if target.is_file():
        return target if "reference" in target.name.lower() else None
    references_dir = target / "references"
    if not references_dir.exists():
        return None
    candidates = sorted(references_dir.glob("*.md"))
    return candidates[0].resolve() if candidates else None


def choose_guardrail_file(target: Path) -> Path | None:
    if target.is_file():
        name = target.name.lower()
        return target if "guardrail" in name or "safety" in name else None
    references_dir = target / "references"
    if not references_dir.exists():
        return None
    for candidate in sorted(references_dir.glob("*.md")):
        name = candidate.name.lower()
        if "guardrail" in name or "safety" in name:
            return candidate.resolve()
    return None


def compute_target_profile(target: Path) -> dict[str, Any]:
    markdown_files = []
    if target.is_dir():
        markdown_files = [str(path.resolve()) for path in sorted(target.rglob("*.md"))]
    elif target.is_file() and target.suffix.lower() == ".md":
        markdown_files = [str(target.resolve())]
    return {
        "path": str(target),
        "exists": target.exists(),
        "kind": "directory" if target.is_dir() else "file" if target.is_file() else "missing",
        "name": target.name,
        "has_references": (target / "references").exists() if target.is_dir() else False,
        "markdown_files": markdown_files[:20],
    }


def classify_feedback(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "limitations": [],
        "examples": [],
        "workflow": [],
        "tests": [],
        "guardrails": [],
        "prompt": [],
    }
    for entry in entries:
        snippet = entry.get("snippet", "")
        lowered = snippet.lower()
        if any(word in lowered for word in ("limit", "boundary", "expect", "integrat", "not automate", "manual")):
            buckets["limitations"].append(snippet)
        if any(word in lowered for word in ("example", "sample", "demo", "usage")):
            buckets["examples"].append(snippet)
        if any(word in lowered for word in ("workflow", "step", "orchestrat", "process", "route")):
            buckets["workflow"].append(snippet)
        if any(word in lowered for word in ("test", "validate", "smoke", "check")):
            buckets["tests"].append(snippet)
        if any(word in lowered for word in ("guardrail", "safe", "risk", "do not", "don't", "must not")):
            buckets["guardrails"].append(snippet)
        if any(word in lowered for word in ("prompt", "too long", "navigat", "discoverability", "section")):
            buckets["prompt"].append(snippet)
    return buckets


def protected_target(target_path: str) -> bool:
    lowered = target_path.lower()
    return any(keyword in lowered for keyword in PROTECTED_KEYWORDS)


def next_step_for_stage(stage: str) -> tuple[str, str]:
    mapping = {
        "proposed": ("rank_candidates", "critic"),
        "ranked": ("execute_candidate", "executor"),
        "executed": ("apply_gate", "gate"),
        "gated_keep": ("propose_candidates", "proposer"),
        "gated_pending": ("human_promote_review", "human"),
        "gated_revert": ("inspect_failure_and_re-propose", "proposer"),
        "gated_reject": ("re-propose_or_manual_override", "proposer"),
    }
    return mapping.get(stage, ("inspect_state", "human"))


def update_state(
    state_root: Path,
    *,
    run_id: str,
    stage: str,
    status: str,
    target_path: str,
    truth_anchor: str,
    extra: dict[str, Any] | None = None,
) -> None:
    paths = ensure_tree(state_root)
    current_state_path = paths["state"] / "current_state.json"
    last_run_path = paths["state"] / "last_run.json"
    next_step, next_owner = next_step_for_stage(stage)
    payload = {
        "lane": "generic-skill",
        "current_run_id": run_id,
        "stage": stage,
        "status": status,
        "target_path": target_path,
        "next_step": next_step,
        "next_owner": next_owner,
        "truth_anchor": truth_anchor,
        "updated_at": utc_now_iso(),
    }
    if extra:
        payload.update(extra)
    write_json(current_state_path, payload)
    last_run = {
        "lane": "generic-skill",
        "last_run_id": run_id,
        "last_stage": stage,
        "last_status": status,
        "last_updated": payload["updated_at"],
        "truth_anchor": truth_anchor,
        "target_path": target_path,
    }
    if extra:
        for key in ("decision", "candidate_id", "target_path", "receipt_path"):
            if key in extra:
                last_run[key] = extra[key]
    write_json(last_run_path, last_run)


def append_pending_promote(state_root: Path, entry: dict[str, Any]) -> Path:
    paths = ensure_tree(state_root)
    pending_path = paths["state"] / "pending_promote.json"
    payload = read_json(pending_path)
    payload.setdefault("pending", []).append(entry)
    payload["last_updated"] = utc_now_iso()
    write_json(pending_path, payload)
    return pending_path


def append_veto(state_root: Path, entry: dict[str, Any]) -> Path:
    paths = ensure_tree(state_root)
    veto_path = paths["state"] / "veto.json"
    payload = read_json(veto_path)
    payload.setdefault("vetoes", []).append(entry)
    payload["last_updated"] = utc_now_iso()
    write_json(veto_path, payload)
    return veto_path


def make_receipt_path(state_root: Path, prefix: str, run_id: str, candidate_id: str | None = None) -> Path:
    paths = ensure_tree(state_root)
    suffix = f"-{candidate_id}" if candidate_id else ""
    return paths["receipts"] / f"{prefix}-{run_id}{suffix}.json"


def make_run_id(target: Path) -> str:
    return f"generic-skill-{slugify(target.name)}-{compact_timestamp()}"


def backup_file(target: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, destination)
    return destination


def restore_backup(backup_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, target_path)
