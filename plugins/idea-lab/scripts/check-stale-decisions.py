#!/usr/bin/env python3
"""Idea-lab stale-decision reminder (SessionStart hook).

idea-lab/decisions.md logs each evaluation with "outcome: pending", but nothing
updates that once the real outcome is known unless someone remembers to. This
nudges at the start of a session when a logged decision has sat pending for a
while, so /idea-lab:review-decisions eventually has something real to grade.
Does nothing in projects without an idea-lab/decisions.md file. Always exits 0
(a missing or unreadable file is not an error here).
"""
import datetime, os, sys

STALE_AFTER_DAYS = 14


def norm_path(path, windows=None):
    if windows is None:
        windows = os.name == "nt"
    if windows and len(path) > 2 and path[0] == "/" and path[2] == "/" and path[1].isalpha():
        return path[1].upper() + ":" + path[2:]
    return path


def project_root():
    return os.path.normcase(os.path.realpath(norm_path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())))


def parse_date(text):
    try:
        return datetime.datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def find_stale(lines, today, stale_after_days=STALE_AFTER_DAYS):
    """Return [(date, slug), ...] for lines still 'outcome: pending' past the threshold."""
    stale = []
    for line in lines:
        if "|" not in line or "outcome:" not in line.lower():
            continue
        parts = [p.strip() for p in line.split("|")]
        date = parse_date(parts[0])
        outcome = parts[-1].split(":", 1)[-1].strip().lower() if ":" in parts[-1] else ""
        if date and outcome == "pending" and (today - date).days > stale_after_days:
            stale.append((date, parts[1] if len(parts) > 1 else "?"))
    return stale


def main():
    path = os.path.join(project_root(), "idea-lab", "decisions.md")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return 0
    stale = find_stale(lines, datetime.date.today())
    if stale:
        print(f"Idea-lab: {len(stale)} logged decision(s) are still 'outcome: pending' after "
              f"{STALE_AFTER_DAYS}+ days. Update idea-lab/decisions.md with what actually happened, "
              "so /idea-lab:review-decisions has something real to grade:")
        for date, slug in stale[:5]:
            print(f"  - {date.isoformat()}: {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
