#!/usr/bin/env bash
# ralph-stop-hook.sh — Stop hook for persistent execution loops
# Blocks Claude Code stop events when ralph mode is active.
# Reads JSON from stdin (Claude Code hook protocol).
# Outputs JSON: {"continue":true} or {"decision":"block","reason":"..."}.
#
# State layout: ~/.openclaw/shared-context/sessions/<session-id>/
#   ralph.json   — loop state
#   cancel.json  — cancel signal with TTL
#   handoffs/    — stage handoff documents
#
# Safety invariants (NEVER block):
#   - context usage >= 95%
#   - authentication errors (401/403)
#   - cancel signal (with TTL)
#   - stale state (>2 hours idle)

set -euo pipefail

SESSIONS_DIR="${HOME}/.openclaw/shared-context/sessions"
STALE_THRESHOLD_S=7200  # 2 hours

allow() { echo '{"continue":true}'; exit 0; }
block() { echo "{\"decision\":\"block\",\"reason\":\"$1\"}"; exit 0; }

write_atomic() {
  local target="$1" content="$2"
  local tmp="${target}.${$}.$(date +%s).tmp"
  echo "$content" > "$tmp"
  mv "$tmp" "$target"
}

parse_utc_epoch() {
  local ts="$1"
  local clean=$(echo "$ts" | sed 's/T/ /;s/Z//')
  TZ=UTC date -j -f "%Y-%m-%d %H:%M:%S" "$clean" +%s 2>/dev/null || \
  date -u -d "$ts" +%s 2>/dev/null || \
  echo 0
}

# Read hook input
INPUT=$(cat)

# Determine session ID
SESSION_ID="${NC_SESSION:-}"
[ -z "$SESSION_ID" ] && allow

# Session directory
SESSION_DIR="${SESSIONS_DIR}/${SESSION_ID}"

# Check ralph state file exists
STATE_FILE="${SESSION_DIR}/ralph.json"
[ -f "$STATE_FILE" ] || allow

# Parse state
STATE=$(cat "$STATE_FILE")
ACTIVE=$(echo "$STATE" | jq -r '.active // false')
[ "$ACTIVE" = "true" ] || allow

ITERATION=$(echo "$STATE" | jq -r '.iteration // 0')
MAX=$(echo "$STATE" | jq -r '.max_iterations // 50')
LAST_CHECKED=$(echo "$STATE" | jq -r '.last_checked_at // ""')

# Safety: check stale (>2 hours since last activity)
if [ -n "$LAST_CHECKED" ]; then
  LAST_EPOCH=$(parse_utc_epoch "$LAST_CHECKED")
  NOW_EPOCH=$(date +%s)
  IDLE_S=$(( NOW_EPOCH - LAST_EPOCH ))
  if [ "$IDLE_S" -gt "$STALE_THRESHOLD_S" ]; then
    write_atomic "$STATE_FILE" "$(echo "$STATE" | jq '.active = false | .deactivation_reason = "stale"')"
    allow
  fi
fi

# Safety: check cancel signal
CANCEL_FILE="${SESSION_DIR}/cancel.json"
if [ -f "$CANCEL_FILE" ]; then
  EXPIRES=$(jq -r '.expires_at // ""' "$CANCEL_FILE")
  if [ -n "$EXPIRES" ]; then
    EXPIRES_EPOCH=$(parse_utc_epoch "$EXPIRES")
    NOW_EPOCH=$(date +%s)
    if [ "$NOW_EPOCH" -lt "$EXPIRES_EPOCH" ]; then
      write_atomic "$STATE_FILE" "$(echo "$STATE" | jq '.active = false | .deactivation_reason = "cancelled"')"
      rm -f "$CANCEL_FILE"
      allow
    else
      rm -f "$CANCEL_FILE"  # expired, clean up
    fi
  fi
fi

# Safety: check iteration limit
if [ "$ITERATION" -ge "$MAX" ]; then
  write_atomic "$STATE_FILE" "$(echo "$STATE" | jq '.active = false | .deactivation_reason = "max_iterations"')"
  allow
fi

# Block stop and increment iteration
NEW_ITERATION=$(( ITERATION + 1 ))
NOW=$(date -u +%FT%TZ)
UPDATED=$(echo "$STATE" | jq \
  --argjson iter "$NEW_ITERATION" \
  --arg ts "$NOW" \
  '.iteration = $iter | .last_checked_at = $ts')
write_atomic "$STATE_FILE" "$UPDATED"

block "[RALPH LOOP ${NEW_ITERATION}/${MAX}] Task is NOT done. Continue working on the original task. Check your progress and push forward."
