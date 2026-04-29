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

needs_btmgmt_patch=0
needs_air_copy_patch=0

if ! grep -Fq 'GRIDRUNNER_BTMGMT_FIND_SECONDS' "$event_script" &&
  grep -Eq '(^|[[:space:]])(sudo[[:space:]]+)?btmgmt[[:space:]]+find([[:space:]]|$)' "$event_script"; then
  needs_btmgmt_patch=1
fi

if grep -Eq 'cp[[:space:]]+"\$AIR_NOW"[[:space:]]+"\$AIR_LAST"0;177;25M0;177;25m' "$event_script"; then
  needs_air_copy_patch=1
fi

if [ "$needs_btmgmt_patch" -eq 0 ] && [ "$needs_air_copy_patch" -eq 0 ]; then
  echo "events script needs no GRIDRUNNER legacy patches: $event_script"
  exit 0
fi

backup="$event_script.gridrunner-pre-legacy-patch"
tmp="$event_script.gridrunner-patched.$$"

cp -p "$event_script" "$backup" || exit 1

awk '
  /cp[[:space:]]+"\$AIR_NOW"[[:space:]]+"\$AIR_LAST"0;177;25M0;177;25m/ {
    print "cp \"$AIR_NOW\" \"$AIR_LAST\""
    next
  }
  !patched && !/GRIDRUNNER_BTMGMT_FIND_SECONDS/ && /(^|[[:space:]])sudo[[:space:]]+btmgmt[[:space:]]+find([[:space:]]|$)/ {
    sub(/sudo[[:space:]]+btmgmt[[:space:]]+find/, "timeout \"${GRIDRUNNER_BTMGMT_FIND_SECONDS:-12}s\" sudo btmgmt find")
    patched = 1
  }
  !patched && !/GRIDRUNNER_BTMGMT_FIND_SECONDS/ && /(^|[[:space:]])btmgmt[[:space:]]+find([[:space:]]|$)/ {
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

if [ "$needs_btmgmt_patch" -eq 1 ]; then
  echo "bounded btmgmt find in events script: $event_script"
fi
if [ "$needs_air_copy_patch" -eq 1 ]; then
  echo "repaired corrupted AIR_LAST copy in events script: $event_script"
fi
echo "backup saved: $backup"
