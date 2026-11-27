#!/usr/bin/env bash
# Watchdog hook for the Telegram watchman (Muse hook runtime).
# All decisions live in `telegram.py hook-check` (unit-tested). This file only
# maps its answer to the runtime functions: log, silent, wake, disable_after_run.
# Install: copy to ~/hooks/scripts/ and replace __SKILL_DIR__ on the SKILL_DIR
# line with the absolute path of this skill (see "Telegram mode ON" in SKILL.md).
set -euo pipefail
source "$HATCH_HOOK_RUNTIME"

SKILL_DIR="__SKILL_DIR__"
HOOK_STATE="${WATCHDOG_STATE_DIR:-$HOME/hooks/state}"
DRY=""
[ "${HATCH_HOOK_DRY_RUN:-0}" = "1" ] && DRY="--dry-run"

# Configuration or runtime problems must not be silent, and must not burn
# tokens either: wake at most once per hour (always visible in a dry run).
alert() {
  local reason="$1" f="$HOOK_STATE/telegram-hook-alert" now last=0
  now=$(date +%s)
  log "$reason" '{}'
  if [ -n "$DRY" ]; then
    wake "$reason" '{}'
  fi
  [ -f "$f" ] && last=$(cat "$f" 2>/dev/null || echo 0)
  if [ $((now - last)) -ge 3600 ]; then
    mkdir -p "$HOOK_STATE"
    echo "$now" > "$f"
    wake "$reason" '{}'
  fi
  silent "$reason" '{}'
}

case "$SKILL_DIR" in __SKILL_D*) alert "hook-not-configured" ;; esac
if ! RESULT="$(python3 "$SKILL_DIR/bin/telegram.py" hook-check $DRY 2>/dev/null)"; then
  alert "hook-check-failed"
fi

field() {
  printf '%s' "$RESULT" | python3 -c '
import json, sys
v = json.load(sys.stdin)[sys.argv[1]]
print(json.dumps(v) if isinstance(v, dict) else v)' "$1"
}
ACTION="$(field action)"
REASON="$(field reason)"
DETAILS="$(field details)"
log "$REASON" "$DETAILS"

case "$ACTION" in
  wake) wake "$REASON" "$DETAILS" ;;
  disable_and_wake) disable_after_run; wake "$REASON" "$DETAILS" ;;
  *) silent "$REASON" "$DETAILS" ;;
esac
