#!/usr/bin/env python3
"""Idea-lab file guard (PreToolUse hook).

Active only while an idea-lab session is running (marker file idea-lab/.active, valid 3 hours).
While active:
  - writes and edits are blocked outside <project>/idea-lab/
  - reads of secret-looking files (.env, keys, credentials) are blocked
Outside a session it does nothing, so normal development is unaffected.
Exit 2 = block (reason on stderr), exit 0 = allow.
"""
import fnmatch, json, os, sys, time

SECRET_NAMES = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*",
                "credentials", "credentials.*", ".npmrc", ".pypirc", ".netrc", "secrets.*", "secret.*",
                "service-account*.json", "*.keystore", "*.jks", "kubeconfig", ".htpasswd"]
SECRET_OK = [".env.example", ".env.sample", ".env.template"]
SECRET_DIRS = [".ssh", ".aws", ".gnupg", ".kube", ".docker"]
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
MAX_AGE = 3 * 3600


def norm_path(path, windows=None):
    """Make bash-style Windows paths (/c/Users/x) comparable with native ones (C:\\Users\\x)."""
    if windows is None:
        windows = os.name == "nt"
    if windows and len(path) >= 3 and path[0] == "/" and path[1].isalpha() and path[2] == "/":
        path = path[1].upper() + ":" + path[2:]
    return path


def project_root():
    return os.path.normcase(os.path.realpath(norm_path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())))


def session_active(root):
    marker = os.path.join(root, "idea-lab", ".active")
    try:
        return time.time() - os.path.getmtime(marker) < MAX_AGE
    except OSError:
        return False


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
            return f"during an idea-lab session, writes are allowed only inside idea-lab/ (tried: {target})"
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
    reason = evaluate(event, project_root())
    if reason:
        print(f"Idea-lab file guard blocked this call: {reason}.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
