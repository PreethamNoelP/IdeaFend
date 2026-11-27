#!/usr/bin/env bash
# Starts or ends an idea-lab session. While a session is active the file guard is enforced.
# "start" refuses to run unless Python 3 is found AND the web guard really blocks a bad URL,
# so a broken safety layer stops the run instead of silently failing open.
cmd="$1"
root="${CLAUDE_PROJECT_DIR:-$PWD}"
dir="$root/idea-lab"
here="$(cd "$(dirname "$0")" && pwd)"
case "$cmd" in
  start)
    rm -f "$dir/.active" "$dir/.heartbeat"   # make sure the self-check runs outside any previous session
    echo '{"tool_name":"WebFetch","tool_input":{"url":"http://127.0.0.1/"}}' | bash "$here/pyrun.sh" guard-web.py >/dev/null 2>&1
    if [ $? -ne 2 ]; then
      echo "Safety self-check failed: Python 3 was not found (tried python3, python, py -3) or the web guard did not block a test URL. Install Python 3 from python.org, then retry. Refusing to start." >&2
      exit 1
    fi
    mkdir -p "$dir" && date +%s > "$dir/.active" && echo "idea-lab session started (guards verified)"
    ;;
  end)
    rm -f "$dir/.active" "$dir/.heartbeat" && echo "idea-lab session ended"
    ;;
  *)
    echo "usage: lab-session.sh start|end" >&2; exit 1
    ;;
esac
