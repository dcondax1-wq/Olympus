"""What may leave the PC about calls (security review H1, lead 2026-11-20): only {business, outcome, ts}, and only when the repo that
would carry it is PRIVATE. The olympus repo is public today, so this refuses and everything stays on the PC.

  python -m tools.caller.export DEST       writes DEST/caller/outcomes.json when GitHub says the repo is private; refuses otherwise
Transcripts, summaries, emails, numbers, consents and outbox drafts never leave the PC through here.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402

FIELDS = ("business", "outcome", "ts")


def repo_private(repo: str, opener=None, token: str = "") -> bool:
    """True only if the GitHub API answers for `repo` with "private": true. A 404, an error, or no answer = not proven private = False."""
    opener = opener or urllib.request.urlopen
    hdr = {"Accept": "application/vnd.github+json", "User-Agent": "olympus-caller"}
    if token:
        hdr["Authorization"] = "Bearer " + token
    try:
        with opener(urllib.request.Request(f"https://api.github.com/repos/{repo}", headers=hdr), timeout=15) as r:
            return json.loads(r.read().decode()).get("private") is True
    except Exception:
        return False


def outcomes(h=None) -> list:
    rows = []
    for p in sorted(glob.glob(os.path.join(C.state_dir(h), "inbox", "*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                rows.append({k: str(r.get(k, ""))[:120] for k in FIELDS})
    return rows


def export(dest: str, h=None, opener=None, token: str = "", repo: str | None = None) -> dict:
    repo = repo or str(C.settings(h).get("inbox_repo") or "dcondax1-wq/olympus")
    if not repo_private(repo, opener, token):
        return {"ok": False, "why": f"{repo} is not proven private: nothing leaves the PC (call records stay in <home>/caller/)"}
    d = os.path.join(dest, "caller")
    os.makedirs(d, exist_ok=True)
    rows = outcomes(h)
    with open(os.path.join(d, "outcomes.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=0)
    return {"ok": True, "rows": len(rows)}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    r = export(sys.argv[1], token=os.environ.get("GH_TOKEN", ""))
    print(r)
    sys.exit(0 if r["ok"] else 1)
