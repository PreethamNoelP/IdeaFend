#!/usr/bin/env python3
"""Idea-lab web guard (PreToolUse hook).

Blocks risky URLs and secret-looking strings in web and search tool calls.
Reads the hook event as JSON on stdin. Exit 2 = block (reason on stderr), exit 0 = allow.
Policy lives in security/policy.json. If the policy file is unreadable, strict defaults apply.
"""
import hashlib, ipaddress, json, os, re, sys, tempfile, time
from urllib import error, request, robotparser
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "block_private_hosts": True, "block_ip_hosts": True, "block_url_shorteners": True,
    "block_executable_extensions": True, "block_credentials_in_url": True,
    "block_punycode_hosts": True, "max_url_length": 500, "respect_robots_txt": True,
    "do_not_fetch_domains": [], "allowlist_mode": False, "allowed_domains": [],
    "url_shorteners": [], "blocked_extensions": [], "secret_patterns": [],
    "block_dns_rebinding_domains": True, "dns_rebinding_domains": [],
    "block_oversized_fetches": True, "max_fetch_bytes": 5_000_000, "max_fetches_per_run": 60,
}
URL_KEYS = {"url", "urls", "uri", "link", "links", "href"}
URL_RE = re.compile(r"(?i)\b(?:https?|ftp|file|data|javascript):[^\s\"'<>]+")


def load_policy():
    policy = dict(DEFAULTS)
    path = os.path.join(os.environ.get("CLAUDE_PLUGIN_ROOT", HERE), "security", "policy.json")
    try:
        with open(path, encoding="utf-8") as fh:
            policy.update(json.load(fh))
    except Exception:
        pass
    return policy


def walk(obj, key=None):
    """Yield (key, string) for every string inside a JSON-like object."""
    if isinstance(obj, str):
        yield key, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, k)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from walk(v, key)


def extract_urls(tool_input):
    urls = []
    for key, text in walk(tool_input):
        urls.extend(URL_RE.findall(text))
        if key and key.lower() in URL_KEYS and not URL_RE.search(text) and text.strip():
            urls.append("https://" + text.strip())
    return urls


def project_root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def bump_fetch_count(root):
    """Increment and return this run's allowed-fetch count. None if no lab session is active
    (the cap only bounds a single run, not all web use); resets when a new session starts."""
    lab_dir = os.path.join(root, "idea-lab")
    active_path = os.path.join(lab_dir, ".active")
    if not os.path.isfile(active_path):
        return None
    count_path = os.path.join(lab_dir, ".fetch-count")
    try:
        fresh = os.path.isfile(count_path) and os.path.getmtime(count_path) >= os.path.getmtime(active_path)
        count = int(open(count_path, encoding="utf-8").read().strip()) if fresh else 0
    except Exception:
        count = 0
    count += 1
    try:
        with open(count_path, "w", encoding="utf-8") as fh:
            fh.write(str(count))
    except Exception:
        pass
    return count


def _head_content_length(url):
    req = request.Request(url, method="HEAD", headers={"User-Agent": "idea-lab-guard"})
    try:
        with request.urlopen(req, timeout=3) as resp:
            cl = resp.headers.get("Content-Length")
            return int(cl) if cl is not None else None
    except Exception:
        return None


def host_matches(host, domain):
    domain = domain.lower().lstrip(".")
    return host == domain or host.endswith("." + domain)


def get_robots(base, fetch=None, ttl=86400):
    cache_dir = os.path.join(tempfile.gettempdir(), "idea-lab-robots")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, hashlib.sha1(base.encode()).hexdigest() + ".json")
    try:
        with open(cache_file, encoding="utf-8") as fh:
            cached = json.load(fh)
        if time.time() - cached["ts"] < ttl:
            return cached["status"], cached["text"]
    except Exception:
        pass
    if fetch is None:
        fetch = _fetch_robots
    status, text = fetch(base + "/robots.txt")
    try:
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "status": status, "text": text}, fh)
    except Exception:
        pass
    return status, text


def _fetch_robots(url):
    req = request.Request(url, headers={"User-Agent": "idea-lab-guard"})
    try:
        with request.urlopen(req, timeout=3) as resp:
            return resp.status, resp.read(524288).decode("utf-8", "replace")
    except error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return None, ""


def robots_allows(url, fetch=None):
    """RFC 9309 behaviour: 2xx parse, 4xx allow, 5xx disallow, network error allow."""
    parsed = urlparse(url)
    status, text = get_robots(f"{parsed.scheme}://{parsed.netloc}", fetch)
    if status is None or 400 <= status < 500:
        return True, ""
    if status >= 500:
        return False, "robots.txt returned a server error, so access is treated as disallowed"
    rp = robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    if rp.can_fetch("Claude-User", url):
        return True, ""
    return False, "the site's robots.txt disallows automated access to this path"


def check_url(url, policy, fetch=None, head=None):
    """Return a reason string if the URL must be blocked, else None."""
    if len(url) > int(policy["max_url_length"]):
        return "URL is unusually long (possible data smuggling in the address)"
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return f"scheme '{parsed.scheme}' is not allowed"
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return "URL has no host"
    if policy["block_credentials_in_url"] and (parsed.username or parsed.password):
        return "URL contains embedded credentials"
    if policy["block_ip_hosts"]:
        labels = host.split(".")
        if 1 <= len(labels) <= 4 and all(re.fullmatch(r"0x[0-9a-f]+|[0-9]+", lbl) for lbl in labels):
            return "numeric host (obfuscated IP address)"
        try:
            ipaddress.ip_address(host)
            return "raw IP address host"
        except ValueError:
            pass
    if policy["block_private_hosts"]:
        if host == "localhost" or host.endswith((".local", ".localhost", ".internal", ".localdomain", ".lan", ".home.arpa")):
            return "local or internal host"
        if "." not in host:
            return "single-label internal host name"
    if policy["block_punycode_hosts"] and any(label.startswith("xn--") for label in host.split(".")):
        return "internationalised (punycode) host: possible look-alike domain"
    if policy["block_url_shorteners"] and any(host_matches(host, d) for d in policy["url_shorteners"]):
        return "URL shortener hides the real destination"
    if policy["block_dns_rebinding_domains"] and any(host_matches(host, d) for d in policy["dns_rebinding_domains"]):
        return "domain is a wildcard DNS service that can be pointed at any IP, including internal ones"
    if policy["block_executable_extensions"]:
        path = parsed.path.lower()
        for ext in policy["blocked_extensions"]:
            if path.endswith(ext):
                return f"file type '{ext}' (download or executable) is not allowed"
    for domain in policy["do_not_fetch_domains"]:
        if host_matches(host, domain):
            return f"{domain} is on the do-not-fetch list (restricts automated access); edit security/policy.json to change"
    if policy["allowlist_mode"] and not any(host_matches(host, d) for d in policy["allowed_domains"]):
        return "domain is not on the allowlist (allowlist mode is on)"
    if policy["block_oversized_fetches"]:
        length = (head or _head_content_length)(url)
        if length is not None and length > int(policy["max_fetch_bytes"]):
            return f"response is {length:,} bytes, over the {int(policy['max_fetch_bytes']):,}-byte limit"
    if policy["respect_robots_txt"]:
        ok, why = robots_allows(url, fetch)
        if not ok:
            return why
    return None


def check_secrets(tool_input, policy):
    for _, text in walk(tool_input):
        for pattern in policy["secret_patterns"]:
            try:
                if re.search(pattern, text):
                    return "text looks like it contains a secret or credential"
            except re.error:
                continue
    return None


def evaluate(event, policy, fetch=None, head=None):
    tool_input = event.get("tool_input", {})
    reason = check_secrets(tool_input, policy)
    if reason:
        return reason
    for url in extract_urls(tool_input):
        reason = check_url(url, policy, fetch, head)
        if reason:
            return f"{reason}: {url[:120]}"
    if policy.get("max_fetches_per_run"):
        count = bump_fetch_count(project_root())
        if count is not None and count > int(policy["max_fetches_per_run"]):
            return (f"this run has already made {count} web fetch/search calls "
                     f"(limit is {policy['max_fetches_per_run']}); start a fresh run or tell the user if you need more")
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        print("Idea-lab web guard: could not read the hook event, blocking to be safe.", file=sys.stderr)
        return 2
    reason = evaluate(event, load_policy())
    if reason:
        print(f"Idea-lab web guard blocked this call: {reason}. Do not retry this URL; pick a different source or tell the user.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
