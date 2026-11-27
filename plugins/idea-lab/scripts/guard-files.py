#!/usr/bin/env python3
"""Idea-lab file guard (PreToolUse hook).

Active only while an idea-lab run is in progress: idea-lab/.active exists and the run has shown
activity (a write inside idea-lab/ or a web call, recorded in idea-lab/.heartbeat) in the last 45 minutes.
While active:
  - writes and edits are blocked outside <project>/idea-lab/
  - reads of secret-looking files (.env, keys, credentials) are blocked
Outside a run it does nothing, so normal development is unaffected.
On SessionStart (startup/clear) it drops the marker of a run that is no longer live.
Exit 2 = block (reason on stderr), exit 0 = allow.
"""
import fnmatch, json, os, sys, time

SECRET_NAMES = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*",
                "credentials", "credentials.*", ".npmrc", ".pypirc", ".netrc", "secrets.*", "secret.*",
                "service-account*.json", "*.keystore", "*.jks", "kubeconfig", ".htpasswd"]
SECRET_OK = [".env.example", ".env.sample", ".env.template"]
SECRET_DIRS = [".ssh", ".aws", ".gnupg", ".kube", ".docker"]
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
MAX_IDLE = 45 * 60  # keep in sync with the -mmin -45 in require-evidence.sh
ABANDONED_AFTER = 10 * 60  # a live run in another session heartbeats far more often than this
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm_path(path, windows=None):
    """Make bash-style Windows paths (/c/Users/x) comparable with native ones (C:\\Users\\x)."""
    if windows is None:
        windows = os.name == "nt"
    if windows and len(path) >= 3 and path[0] == "/" and path[1].isalpha() and path[2] == "/":
        path = path[1].upper() + ":" + path[2:]
    return path


def project_root():
    return os.path.normcase(os.path.realpath(norm_path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())))


def last_activity(root):
    """Time of the run's start or latest heartbeat; None if no run marker exists."""
    lab = os.path.join(root, "idea-lab")
    try:
        start = os.path.getmtime(os.path.join(lab, ".active"))
    except OSError:
        return None
    try:
        return max(start, os.path.getmtime(os.path.join(lab, ".heartbeat")))
    except OSError:
        return start


def session_active(root, max_idle=MAX_IDLE):
    last = last_activity(root)
    return last is not None and time.time() - last < max_idle


def heartbeat(root):
    path = os.path.join(root, "idea-lab", ".heartbeat")
    try:
        with open(path, "a", encoding="utf-8"):
            pass
        os.utime(path, None)
    except OSError:
        pass


def clear_abandoned(root):
    """A new Claude Code session cannot continue an old run, so drop its marker unless it is still live."""
    if session_active(root, ABANDONED_AFTER):
        return
    for name in (".active", ".heartbeat"):
        try:
            os.remove(os.path.join(root, "idea-lab", name))
        except OSError:
            pass


def is_secret_path(path):
    norm = path.replace("\\", "/")
    base = os.path.basename(norm)
    if base in SECRET_OK:
        return False
    if any(fnmatch.fnmatch(base, pat) for pat in SECRET_NAMES):
        return True
    return any(f"/{d}/" in f"/{norm}/" for d in SECRET_DIRS)


SECRET_MARKERS = [".env", ".pem", ".key", ".p12", ".pfx", "id_rsa", "id_ed25519", "credentials", ".npmrc", ".pypirc", ".netrc", "secrets.", ".htpasswd", ".keystore"]


def glob_targets_secrets(glob):
    """True if a search glob names secret-looking files (e.g. '.env*', '**/*.pem')."""
    base = glob.replace("\\", "/").split("/")[-1].lower()
    return any(marker in base for marker in SECRET_MARKERS) and base not in SECRET_OK


def candidate_paths(tool, tool_input):
    paths, globs = [], []
    for key in ("file_path", "notebook_path", "path"):
        if isinstance(tool_input.get(key), str):
            paths.append(tool_input[key])
    if isinstance(tool_input.get("glob"), str):
        globs.append(tool_input["glob"])
    if isinstance(tool_input.get("include"), str):
        globs.append(tool_input["include"])
    if tool == "Glob" and isinstance(tool_input.get("pattern"), str):
        globs.append(tool_input["pattern"])  # for Grep, 'pattern' is a content regex, not a path
    return paths, globs


def evaluate(event, root):
    if not session_active(root):
        return None
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    allowed = os.path.join(root, "idea-lab") + os.sep
    if tool in WRITE_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        target = norm_path(target)
        resolved = os.path.normcase(os.path.realpath(target if os.path.isabs(target) else os.path.join(root, target)))
        if not (resolved + os.sep).startswith(os.path.normcase(allowed)):
            unlock = os.path.join(PLUGIN_ROOT, "scripts", "lab-session.sh").replace("\\", "/")
            return (f"during an idea-lab run, writes are allowed only inside idea-lab/ (tried: {target}). "
                    f"If no run is in progress (an earlier one was interrupted), ask the user, then run: bash \"{unlock}\" end")
        heartbeat(root)
        return None
    paths, globs = candidate_paths(tool, tool_input)
    for path in paths:
        if is_secret_path(path):
            return f"reading secret-looking files is blocked during an idea-lab session (tried: {path})"
    for glob in globs:
        if glob_targets_secrets(glob):
            return f"searching for secret-looking files is blocked during an idea-lab session (tried: {glob})"
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    root = project_root()
    if event.get("hook_event_name") == "SessionStart":
        clear_abandoned(root)
        return 0
    reason = evaluate(event, root)
    if reason:
        print(f"Idea-lab file guard blocked this call: {reason}.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
