#!/usr/bin/env python3
"""Self-test for the idea-lab guards. Run: python3 scripts/selftest.py
Uses no network (robots.txt lookups are faked). Prints PASS/FAIL per case; exit 1 on any failure."""
import importlib.util, json, os, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


web = load("guard-web")
files = load("guard-files")
policy = web.load_policy()
policy["respect_robots_txt"] = False  # network off for offline cases
results = []


def check(label, got_block, want_block):
    ok = got_block == want_block
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + label)


def wf(url):
    return web.evaluate({"tool_name": "WebFetch", "tool_input": {"url": url}}, policy)


# ---- web guard: should block
for label, url in [
    ("blocks localhost", "http://localhost:8080/admin"),
    ("blocks raw IP", "http://93.184.216.34/page"),
    ("blocks cloud metadata IP", "http://169.254.169.254/latest/meta-data/"),
    ("blocks obfuscated decimal IP", "http://2130706433/"),
    ("blocks internal host", "https://intranet/secret"),
    ("blocks credentials in URL", "https://user:pass@example.com/"),
    ("blocks URL shortener", "https://bit.ly/3abcde"),
    ("blocks punycode look-alike", "https://xn--pple-43d.com/"),
    ("blocks executable download", "https://example.com/setup.exe"),
    ("blocks zip download", "https://example.com/files/tool.zip"),
    ("blocks file scheme", "file:///etc/passwd"),
    ("blocks javascript scheme", "javascript:alert(1)"),
    ("blocks do-not-fetch domain", "https://www.linkedin.com/in/someone"),
    ("blocks very long URL", "https://example.com/?q=" + "a" * 600),
    ("blocks short-form dotted-decimal IP (127.1)", "http://127.1/admin"),
    ("blocks octal-dotted IP (0177.0.0.1)", "http://0177.0.0.1/admin"),
    ("blocks mixed hex-dotted IP (0x7f.0.0.1)", "http://0x7f.0.0.1/admin"),
    ("blocks IPv6-mapped loopback", "http://[::ffff:127.0.0.1]/admin"),
    ("blocks wildcard-DNS rebinding domain", "http://127.0.0.1.nip.io/admin"),
]:
    check(label, wf(url) is not None, True)

# ---- web guard: should allow
for label, url in [
    ("allows normal https page", "https://code.claude.com/docs/en/agent-teams"),
    ("allows github repo", "https://github.com/anthropics/claude-code"),
    ("allows slug containing 'sk-'", "https://example.com/blog/task-management-software-for-small-teams-compared"),
    ("allows numeric subdomain of a real domain", "https://123.example.com/"),
]:
    check(label, wf(url) is not None, False)

# ---- secrets in queries / URLs
secret_event = {"tool_name": "mcp__search-provider__search", "tool_input": {"query": "why does AKIAABCDEFGHIJKLMNOP fail"}}
check("blocks AWS key in a search query", web.evaluate(secret_event, policy) is not None, True)
gh_event = {"tool_name": "WebFetch", "tool_input": {"url": "https://example.com/?t=ghp_" + "a" * 36}}
check("blocks GitHub token in URL", web.evaluate(gh_event, policy) is not None, True)
plain = {"tool_name": "mcp__search-provider__search", "tool_input": {"query": "AI usage dashboard for developers competitors"}}
check("allows ordinary search query", web.evaluate(plain, policy) is not None, False)

# ---- allowlist mode
strict = dict(policy, allowlist_mode=True, allowed_domains=["github.com"])
check("allowlist mode blocks other domains", web.evaluate({"tool_input": {"url": "https://example.com/"}}, strict) is not None, True)
check("allowlist mode allows listed domain", web.evaluate({"tool_input": {"url": "https://docs.github.com/x"}}, strict) is not None, False)

# ---- robots.txt (faked fetch)
robots_policy = dict(policy, respect_robots_txt=True)
tmp_cache = tempfile.mkdtemp()
os.environ["TMPDIR"] = tmp_cache
import tempfile as _t; _t.tempdir = tmp_cache
deny = lambda u: (200, "User-agent: *\nDisallow: /private/\n")
ok, _ = web.robots_allows("https://site-a.test/private/page", deny)
check("robots.txt disallow is respected", ok, False)
ok, _ = web.robots_allows("https://site-b.test/public/page", deny)
check("robots.txt allows other paths", ok, True)
ok, _ = web.robots_allows("https://site-c.test/x", lambda u: (404, ""))
check("missing robots.txt allows (RFC 9309)", ok, True)
ok, _ = web.robots_allows("https://site-d.test/x", lambda u: (503, ""))
check("robots.txt server error disallows (RFC 9309)", ok, False)
ok, _ = web.robots_allows("https://site-e.test/x", lambda u: (None, ""))
check("unreachable robots.txt allows", ok, True)

# ---- file guard
root = tempfile.mkdtemp()
os.makedirs(os.path.join(root, "idea-lab"))
ev = lambda tool, **inp: files.evaluate({"tool_name": tool, "tool_input": inp}, root)
check("file guard inactive without a session", ev("Write", file_path=os.path.join(root, "src/app.py")) is not None, False)
open(os.path.join(root, "idea-lab", ".active"), "w").write(str(int(time.time())))
check("active: blocks writing project code", ev("Write", file_path=os.path.join(root, "src/app.py")) is not None, True)
check("active: allows writing inside idea-lab/", ev("Write", file_path=os.path.join(root, "idea-lab/x/brief.md")) is not None, False)
check("active: blocks path traversal out of idea-lab/", ev("Write", file_path=os.path.join(root, "idea-lab/../src/app.py")) is not None, True)
check("active: blocks reading .env", ev("Read", file_path=os.path.join(root, ".env")) is not None, True)
check("active: blocks reading private key", ev("Read", file_path="/home/u/.ssh/id_rsa") is not None, True)
check("active: allows .env.example", ev("Read", file_path=os.path.join(root, ".env.example")) is not None, False)
check("active: allows reading source code", ev("Read", file_path=os.path.join(root, "src/app.py")) is not None, False)
check("active: blocks grep over .env glob", ev("Grep", pattern="KEY", glob=".env*") is not None, True)
check("active: allows broad Glob **/*.py", ev("Glob", pattern="**/*.py") is not None, False)
check("active: allows Grep for the word 'secret' in code", ev("Grep", pattern="secret", path=os.path.join(root, "src")) is not None, False)
check("active: blocks Glob for **/*.pem", ev("Glob", pattern="**/*.pem") is not None, True)
old = time.time() - 4 * 3600
os.utime(os.path.join(root, "idea-lab", ".active"), (old, old))
check("stale session marker expires", ev("Write", file_path=os.path.join(root, "src/app.py")) is not None, False)

check("Windows path /c/Users/x becomes C:/Users/x", files.norm_path("/c/Users/x", True) == "C:/Users/x", True)
check("Windows path normalisation leaves normal paths alone", files.norm_path("/home/u/x", False) == "/home/u/x", True)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
