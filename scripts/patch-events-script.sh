#!/bin/bash
set -u

event_script="${1:-}"

if [ -z "$event_script" ]; then
  echo "usage: $0 /path/to/operator-events.sh"
  exit 2
fi

if [ ! -f "$event_script" ]; then
  echo "events script not found: $event_script"
  exit 1
fi

if grep -Fq 'GRIDRUNNER_BTMGMT_FIND_SECONDS' "$event_script"; then
  echo "events script already has bounded btmgmt find: $event_script"
  exit 0
fi

if ! grep -Eq '(^|[[:space:]])(sudo[[:space:]]+)?btmgmt[[:space:]]+find([[:space:]]|$)' "$event_script"; then
  echo "events script has no btmgmt find command: $event_script"
  exit 0
fi

backup="$event_script.gridrunner-pre-btmgmt-timeout"
tmp="$event_script.gridrunner-patched.$$"

cp -p "$event_script" "$backup" || exit 1

awk '
  !patched && /(^|[[:space:]])sudo[[:space:]]+btmgmt[[:space:]]+find([[:space:]]|$)/ {
    sub(/sudo[[:space:]]+btmgmt[[:space:]]+find/, "timeout \"${GRIDRUNNER_BTMGMT_FIND_SECONDS:-12}s\" sudo btmgmt find")
    patched = 1
  }
  !patched && /(^|[[:space:]])btmgmt[[:space:]]+find([[:space:]]|$)/ {
    sub(/btmgmt[[:space:]]+find/, "timeout \"${GRIDRUNNER_BTMGMT_FIND_SECONDS:-12}s\" btmgmt find")
    patched = 1
  }
  { print }
' "$event_script" > "$tmp" || {
  rm -f "$tmp"
  exit 1
}

chmod --reference="$event_script" "$tmp" 2>/dev/null || chmod 0755 "$tmp"
mv "$tmp" "$event_script"

echo "bounded btmgmt find in events script: $event_script"
echo "backup saved: $backup"
