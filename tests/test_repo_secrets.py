"""REPO SECRETS (team Q2 "privacy and security audit", 2026-11-14): nothing secret in the committed tree, and every private path the
teams added is gitignored. docs/PRIVACY.md is the plain table; tools/site_privacy.py holds the detectors.

  a. keys       no API key, token, private key, webhook or password assignment in a tracked file outside tests/ (tests hold obviously
                fake ones on purpose: they check that redaction works)
  b. identity   the owner's git name(s) and email(s) appear in no tracked file; no personal folder (C:\\Users\\<name>\\) outside tests;
                no age phrase in the public sources (tools/web_public)
  c. accounts   a real broker account id (this PC's heartbeat, or --state) only in the files that hold it today (the account code,
                docs/CLAUDE_REFERENCE.md, two research hand-off logs, tests); no broker id at all in tools/web_public or the write-ups
  d. ignore     every private path the teams added is gitignored, and no tracked file sits in a private folder
  e. history    (only with --history, ~4 min) no high-confidence key was ever committed, and no private file was ever added

  python -X utf8 -m tests.test_repo_secrets [--state STATE.json] [--history]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_privacy as SP  # noqa: E402

RES: list = []
# the files that hold a real broker account id today (2026-11-14). They are not published (the site scrub cuts any id that reaches a
# page) and an id gives no access, but a NEW file with one fails here: review it, or mask it to the last 4 digits.
ACCOUNT_FILES_OK = ("engine/account_rename.py", "engine/new_accounts.py", "docs/CLAUDE_REFERENCE.md",
                    "research/handoff/2026-10-25/a5_logs/test_nt_outgoing.txt", "research/handoff/2026-10-26/MORNING_REPORT.md")
# every private path the teams added (where it is written) -> must be gitignored
PRIVATE_PATHS = ("money_out/household.json", "money_out/agency.json", "money_out/index.json", "money_out_log.txt",          # money import, agency
                 "data/money_rules.json", "data/money_ledger.json", "data/money_report/state.json", "docs/reports/money_week_2026-11-15.md",
                 "data/day/day.json", "data/day/inbox.json", "data/day/cache/x.ics", "data/inbox/day.jsonl", "data/inbox/money.jsonl",   # connect the day
                 "data/inbox/health.jsonl", "data/inbox/cards.jsonl", "data/health/x.json", "data/cards/x.json",                       # ME1 health / cards
                 "data/agency/business.json", "data/agency/invoices.json", "data/agency/invoices/INV-2026-0001.html",                 # agency billing
                 "data/pc_report/state.json", "data/pc_publish/site/index.html", "data/live_site/site/index.html", "netlify.json",    # reports, publish
                 "ntfy.json", ".olympus/ntfy.json", "calendars.json", "money_inbox/cash.jsonl", "cash.jsonl", "money_keep/sibyl_forward.json",
                 "dash/state.json", "site/data.json", "logs/heartbeat_last.json", "logs/pc_hb/heartbeat.json", "data/alerts.json",    # build, heartbeat
                 "data/tv.json", "data/autostart.json", "data/live_state.json", "data/accounts.json", "data/account_b.json", "data/account_c.json",
                 "data/nt_accounts_allow.json", "data/goals_money.json", "data/push.json", "data/push_pc_key.json", "data/memory.db", ".env",
                 ".env.local.ps1", "kalshi.pem", "data/fleet.json", "data/eval_anchor.json", "data/broker_balance.json")
PRIVATE_DIRS = ("money_out/", "data/day/", "data/inbox/", "data/agency/", "data/pc_report/", "data/pc_publish/", "data/live_site/", "logs/",
                ".olympus/", "data/health/", "data/cards/", "money_keep/", "dash/", "site/")
SKIP_EXT = {".csv", ".gz", ".zip", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".glb", ".hdr", ".ogg", ".m4a", ".mp3", ".woff", ".woff2", ".ttf", ".ico",
            ".pdf", ".wasm", ".bin", ".pyc"}


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:900]})" if info and not cond else ""), flush=True)
    return bool(cond)


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else None


def git(*a, timeout=120) -> str:
    try:
        r = subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def tracked() -> list:
    return [f for f in git("ls-files", "-z").split("\0") if f]


def texts(files):
    for rel in files:
        if os.path.splitext(rel)[1].lower() in SKIP_EXT:
            continue
        p = os.path.join(ROOT, rel)
        try:
            if os.path.getsize(p) > 20_000_000:
                continue
            with open(p, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        if b"\0" in raw[:4000]:
            continue
        yield rel, raw.decode("utf-8", "replace")


def scan_tree(files, can_names, can_ids):
    keys, names, folders, ids_where, web_ids, ages = [], [], [], {}, [], []
    low_names = [(lb, v.lower()) for lb, v in can_names]
    for rel, t in texts(files):
        is_test = rel.startswith("tests/")
        low = t.lower()
        if not is_test:
            for name, lit, rx in SP.TOKEN_RX:
                if lit in t:
                    keys += [f"{rel}: {name}" for _m in rx.finditer(t)]
            if any(w in low for w in SP.KEY_WORDS):
                keys += [f"{rel}: a key / password assignment" for _m in SP.KEY_ASSIGN_RX.finditer(t)]
            if "sers" in t or "/home/" in t:
                folders += [f"{rel}: {SP.masked(m.group(0))}" for m in SP.USER_PATH_RX.finditer(t) if not SP._user_ok(m.group(2) or m.group(4) or "")]
        names += [f"{rel}: {lb}" for lb, v in low_names if v in low]
        for _lb, v in can_ids:
            if v in t:
                ids_where.setdefault(rel, 0)
                ids_where[rel] += 1
        if rel.startswith(("tools/web_public/", "research/writeups/")):
            web_ids += [f"{rel}: {SP.masked(m.group(0))}" for m in SP.ACCT_ID_RX.finditer(t) if SP.acct_kind(m.group(1), m.group(2))]
        if rel.startswith("tools/web_public/") and (" turn " in low or "birth" in low):
            ages += [f"{rel}: {SP.masked(m.group(0))}" for m in SP.AGE_RX.finditer(t)]
    return keys, names, folders, ids_where, web_ids, ages


def main() -> int:
    files = tracked()
    if not files and not os.path.isdir(os.path.join(ROOT, ".git")) and not os.path.isfile(os.path.join(ROOT, ".git")):
        print("[SKIP] not a git checkout (the PC's code zip): this test checks the committed tree, run it in the repo")
        return 0
    if not check("the tracked tree is readable (git ls-files)", len(files) > 100, len(files)):
        print(f"\n{len(RES) - RES.count(False)}/{len(RES)} passed")
        return 1
    can = SP.canaries(arg("--state"))
    can_names = [(lb, v) for lb, v in can if "git author" in lb]
    can_ids = [(lb, v) for lb, v in can if "broker" in lb]
    print(f"  {len(files)} tracked files; canaries: {len(can_names)} git names / emails, {len(can_ids)} broker ids"
          + ("" if can_ids else " (no heartbeat on this PC and no --state: the real-id part is skipped)"))
    keys, names, folders, ids_where, web_ids, ages = scan_tree(files, can_names, can_ids)
    check("a. no API key, token, private key, webhook or password assignment in a tracked file outside tests/", not keys, keys[:8])
    check("b. the owner's git name(s) and email(s) are in no tracked file (git metadata only)", not names, names[:8])
    check("b. no personal folder (C:\\Users\\<name>\\, /Users/<name>/) outside tests/", not folders, folders[:8])
    check("b. no age phrase (with the goal's date it gives the birthday away) in the public sources", not ages, ages[:6])
    extra = sorted(f for f in ids_where if not (f.startswith("tests/") or f in ACCOUNT_FILES_OK))
    if can_ids:
        check("c. a real broker account id only in the files that hold it today (account code, the reference, two hand-off logs, tests)",
              not extra, extra[:8])
    else:
        print("[SKIP] c. no real broker ids known on this machine (run with --state STATE.json)")
    check("c. no broker account id at all in the public sources (tools/web_public) or the research write-ups", not web_ids, web_ids[:6])
    # d. .gitignore
    out = git("check-ignore", "--no-index", "-v", "--non-matching", *PRIVATE_PATHS)
    not_ignored = [ln.split("\t", 1)[-1] for ln in out.splitlines() if ln.startswith("::")]
    check("d. every private path the teams added is gitignored", out and not not_ignored, not_ignored)
    inside = [f for f in files if f.startswith(PRIVATE_DIRS) or os.path.basename(f) in ("ntfy.json", "netlify.json", "calendars.json", "household.json")]
    check("d. no tracked file sits in a private folder (money_out, data/day, data/inbox, data/agency, logs, .olympus, dash, site ...)", not inside, inside[:8])
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("d. the test fixtures stay tracked (calendar .ics, bank .ofx / .qfx are fake on purpose)", not git("check-ignore", "--no-index", "tests/fixtures/calendar/google.ics",
                                                                                                        "tests/fixtures/money_import/bank.ofx").strip() and "/site/" in gi)
    if "--history" in sys.argv:
        rx = (r"(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY-----|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}|"
              r"xox[abprs]-[A-Za-z0-9-]{10,}|nfp_[A-Za-z0-9]{30,}|sk-ant-[A-Za-z0-9_-]{20,}|discord(app)?[.]com/api/webhooks/[0-9]+/)")
        hist = git("log", "--all", "--format=", "--name-only", "-G" + rx, "--", ".", timeout=1800)
        bad = sorted({ln.strip() for ln in hist.splitlines() if ln.strip() and not ln.startswith("tests/")})
        check("e. history: no high-confidence key was ever committed outside tests/ (their fake fixtures)", not bad, bad[:8])
        added = git("log", "--all", "--diff-filter=A", "--format=", "--name-only", "--", *[":(glob)" + s for s in (
            "**/.env", "**/.env.*", "data/alerts.json", "data/tv.json", "**/ntfy.json", "**/netlify.json", "**/calendars.json", "data/day/**",
            "data/inbox/**", "data/agency/**", "money_out/**", "**/household.json", "data/money_ledger.json", "data/goals_money.json", "logs/**",
            "**/*.pem", "data/push_pc_key.json", "data/accounts.json")], timeout=900)
        check("e. history: no private or secret file was ever added", not added.strip(), added.split()[:8])
    else:
        print("[SKIP] e. the history search (~4 min): run with --history")
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
