#!/usr/bin/env bash
# Runs one of this plugin's Python scripts with whichever Python 3 exists: python3, python, or py -3.
# (On Windows, "python3" is often missing or a Microsoft Store stub; "python" or "py" works.)
# If no Python 3 exists: during an active idea-lab session this BLOCKS the tool call (exit 2);
# outside a session it stays out of the way (exit 0), since lab-session.sh refuses to start without Python.
find_py() {
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
      echo "$c"; return 0
    fi
  done
  if command -v py >/dev/null 2>&1 && py -3 -c 'pass' >/dev/null 2>&1; then
    echo "py -3"; return 0
  fi
  return 1
}
script="$1"; shift
here="$(cd "$(dirname "$0")" && pwd)"
if PY="$(find_py)"; then
  exec $PY "$here/$script" "$@"
fi
root="${CLAUDE_PROJECT_DIR:-$PWD}"
if [ -f "$root/idea-lab/.active" ]; then
  echo "Idea-lab guard: no Python 3 found, so the safety guards cannot run. Blocking while an idea-lab session is active." >&2
  exit 2
fi
exit 0
