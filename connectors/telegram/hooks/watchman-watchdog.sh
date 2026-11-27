#!/usr/bin/env bash
# Watchdog hook for the Telegram watchman (Muse hook runtime).
# All decisions live in `telegram.py hook-check` (unit-tested). This file only
# maps its answer to the runtime functions: log, silent, wake, disable_after_run.
# Install: copy to ~/hooks/scripts/ and replace __SKILL_DIR__ with the absolute
# path of this skill (see "Telegram mode ON" in SKILL.md).
set -euo pipefail
source "$HATCH_HOOK_RUNTIME"

SKILL_DIR="__SKILL_DIR__"
DRY=""
[ "${HATCH_HOOK_DRY_RUN:-0}" = "1" ] && DRY="--dry-run"

if ! RESULT="$(python3 "$SKILL_DIR/bin/telegram.py" hook-check $DRY 2>/dev/null)"; then
  log "hook-check failed" '{}'
  silent "hook-check-error" '{}'
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
