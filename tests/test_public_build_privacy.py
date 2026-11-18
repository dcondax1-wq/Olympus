"""PUBLIC BUILD PRIVACY (team Q2 "privacy and security audit", 2026-11-14): nothing private in what leaves the PC publicly.
docs/PRIVACY.md is the plain table. The two public outputs: the static site (tools/build_web_dashboard.py -> the folder / zip on
Netlify, tools/pc_publish.py) and the public ntfy status topic (tools/pc_report.lite, tools/web_public/status_feed.json).
tools/site_privacy.py holds the detectors and the scrub the build runs last.

  a. detectors   each detector finds its planted value in a fake site (card number by Luhn, bank account number, email, phone, street
                 address, state + ZIP, an age / birthday, the owner's name / email canaries, API keys and tokens, the private ntfy alert topic, a broker
                 account, a personal folder C:\\Users\\<name>, a tailnet name, a Tailscale IP, household / day / inbox / health / cards /
                 agency / calendar / key files by name or content); a clean fake site (prices, epoch times, shas, Sim101, Kalshi
                 tickers, versions, colors, the docstring's example topic) has none
  b. scrub       broker ids keep the last 4 digits, a personal folder becomes <you>, a commit author goes, an email is masked, an
                 age goes, a private file is removed; JSON stays valid; numbers, code (.js) and clean files are untouched
  c. sources     the build copies no private folder (money_out, data/day, data/agency, data/inbox, .olympus) and runs the scrub last;
                 money_publish.KEEP has no household / agency; pc_publish scrubs the Kalshi feed it adds; the research write-ups
                 carry no personal folder and no full broker account id
  d. planted     a state.json with planted private values (broker ids in the heartbeat, notices, verdict and launch lines, a commit
                 author, a personal folder, an email, an age) through the REAL build: none of them in the site, the masked ids are
                 (they reached the page and were cut), data.json / home.json still load
  e. ntfy        the public status (pc_report.lite) has no PC name, no broker id, no personal folder, no email; the eval numbers stay
  f. real build  (skipped with --fast) the full site from --state (default data/pc_publish/dash/state.json, else none) into a temp
                 folder (~300 MB, deleted after): zero findings, the canaries (git authors' names / emails, the state's and this
                 PC's broker account ids, the private ntfy topic) nowhere

  python -X utf8 -m tests.test_public_build_privacy [--fast] [--state STATE.json] [--site DIR (scan this build instead of f's)]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_privacy as SP  # noqa: E402

RES: list = []
FAST = "--fast" in sys.argv
TMP_BASE = os.environ.get("LE_TEST_TMP") or None


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else None


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:900]})" if info and not cond else ""), flush=True)
    return bool(cond)


# planted values are made at run time, so this file itself never holds a real-looking secret (tests/test_repo_secrets scans it)
def fake():
    d = {}
    d["card"] = "4111" + " 1111" * 3                                   # the Visa test number (passes Luhn)
    d["amex"] = "3782" + "82246310005"
    d["not_card"] = "4111" + "1111" * 2 + "1112"                       # fails Luhn
    d["acct_no"] = "Checking account #: " + "1234" + "5678" + "9012"
    d["email"] = "jane.q.planted" + "@" + "gmail.com"
    d["phone"] = "(415) 86" + "7-5309"
    d["street"] = "1600 Pennsylvania" + " Avenue"
    d["zip"] = "Springfield, IL" + " 62704"
    d["ghp"] = "gh" + "p_" + "A1b2C3d4" * 5
    d["pem"] = "-----BEGIN RSA " + "PRIVATE KEY-----"
    d["tg"] = "123456789" + ":AA" + "x" * 33
    d["nfp"] = "nf" + "p_" + "Z9y8X7w6" * 5
    d["skant"] = "sk-" + "ant-" + "q" * 30
    d["jwt"] = "ey" + "J" + "a" * 12 + ".ey" + "J" + "b" * 12 + "." + "c" * 20
    d["assign"] = '"pass' + 'word": "' + "hunter2" * 3 + '"'
    d["topic"] = "nq-" + "amber-" + "falcon-" + "river-" + "1234"
    d["broker"] = "MFFUEVBLDR" + "123456789"
    d["broker2"] = "APEX-" + "12345678"
    d["broker_low"] = "mffuevbldr" + "618293570"                       # 2026-11-18: lower case, and letters + digits before the number
    d["broker_mix"] = "MFFUSFBLD25K" + "718392465"
    d["path"] = "C:\\" + "Users\\" + "Jane Planted" + "\\Documents\\nq"
    d["path_json"] = "C:\\\\" + "Users\\\\" + "Jane Planted" + "\\\\nq"
    d["tailnet"] = "olympus-pc" + ".tail9f3e2" + ".ts.net"
    d["tsip"] = "100.101" + ".102.103"
    d["name"] = "Jane Q" + " Planted"
    return d


def write(base, rel, text):
    p = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def kinds(found):
    return sorted({f["kind"] for f in found})


# ------------------------------------------------------------------------------------------------ a. detectors
def detectors(tmp):
    F = fake()
    bad = os.path.join(tmp, "bad")
    plant = {
        "card number": ("pay.md", f"card {F['card']} and amex {F['amex']}"),
        "account number": ("bank.md", F["acct_no"]),
        "email": ("contact.md", f"write to {F['email']}"),
        "phone": ("call.md", f"call {F['phone']} now"),
        "street address": ("where.md", f"lives at {F['street']}"),
        "state + ZIP": ("zip.md", F["zip"]),
        "token": ("keys.js", f"const a = '{F['ghp']}'; // {F['pem']}\nconst t = '{F['tg']}', n = '{F['nfp']}', k = '{F['skant']}', j = '{F['jwt']}';\n{{{F['assign']}}}"),
        "ntfy topic": ("alerts.json", json.dumps({"topic": F["topic"]})),
        "broker account": ("acct.json", json.dumps({"lines": [f"trading {F['broker']}", F["broker2"], F["broker_low"], F["broker_mix"]]})),
        "user folder": ("paths.json", '{"log": "' + F["path_json"] + '"}'),
        "tailnet name": ("link.md", f"open https://{F['tailnet']}/site/"),
        "tailscale IP": ("ip.md", f"phone at {F['tsip']}"),
        "canary": ("about.md", "made by " + F["name"].replace(" ", ".")),
        "age / birthday": ("goal.md", "a red car before I " + "turn 30 (Jan 5, 2031)"),
    }
    for kind, (rel, text) in plant.items():
        write(bad, "plant/" + rel, text)
    for rel, body in (("money/household.json", '{"kind": "olympus-household"}'), ("day/day.json", "{}"), ("x/inbox.json", "{}"),
                      ("h/stats.json", '{"v": 1, "kind": "olympus-health", "steps": 9000}'), ("cards.json", "[]"),
                      ("money/agency.json", '{"private": true}'), ("cal/work.ics", "BEGIN:VCALENDAR"), ("cfg.json", '{"telegram_token": "123"}'),
                      ("calendars.json", "{}"), ("ntfy.json", "{}"), ("netlify.json", "{}"), (".env.local", "X=1"), ("inbox/cash.jsonl", "{}")):
        write(bad, rel, body)
    found = SP.scan(bad, canaries=[("the owner's name", F["name"])])
    by = {}
    for f in found:
        by.setdefault(f["kind"], set()).add(f["file"])
    for kind, (rel, _t) in plant.items():
        check(f"a. the {kind} detector finds its planted value", "plant/" + rel in by.get(kind, set()), sorted(by.get(kind, set())))
    ids = [f for f in found if f["file"] == "plant/acct.json" and f["kind"] == "broker account"]
    check("a. the broker detector finds all 4 id shapes (MFFUEVBLDR..., APEX-..., lower-case mffuev..., MFFUSFBLD25K...)", len(ids) == 4, [str(f) for f in ids])
    toks = {f["why"] for f in found if f["kind"] == "token"}
    check("a. the token detector names each planted key (GitHub, private key, Telegram, Netlify, Anthropic, JWT, a password)",
          {"GitHub token", "private key", "Telegram bot token", "Netlify token", "OpenAI / Anthropic key", "JWT", "a key / password assignment"} <= toks, toks)
    pf = {f["file"] for f in found if f["kind"] == "private file"}
    want = {"money/household.json", "day/day.json", "x/inbox.json", "h/stats.json", "cards.json", "money/agency.json", "cal/work.ics", "cfg.json",
            "calendars.json", "ntfy.json", "netlify.json", ".env.local", "inbox/cash.jsonl"}
    check("a. private files are found by name or content (household, day, inbox, health, cards, agency, calendar, alert keys, ntfy / netlify settings, .env, inbox lines)",
          want <= pf, sorted(want - pf))
    check("a. a value is never printed whole (masked in every finding)", all(F["broker"] not in str(f) and F["email"] not in str(f) for f in found))
    check("a. a 16-digit number that fails Luhn is not a card", not SP.scan_text(F["not_card"], "x.md") and SP.luhn(F["card"]) and not SP.luhn(F["not_card"]))
    # a clean site: what the real one is full of
    clean = os.path.join(tmp, "clean")
    write(clean, "data.json", json.dumps({"t": 1794000386, "t_ms": 1794000386123, "price": 27101.25, "pnl": -168.81, "sha": "8579abdebd209f92181bef46589fe41c6dcb8807",
                                          "acct": "Sim101", "ticker": "KXNASDAQ100U-26NOV14H1600", "color": "#123456", "v": "1.2.3", "ip_like": "100.5",
                                          "date": "2026-11-14", "time": "10:45", "rr": "1:2.5", "range": "02:00-15:30", "vix": "VIX 17.5",
                                          "docs": "open https://<your-pc>.<your-tailnet>.ts.net/site/ on the phone; see you@example.com",
                                          "path": "C:\\Users\\<you>\\.olympus\\ntfy.json", "topic_example": "nq-amber-falcon-river-7291",
                                          "acct_label": "MFFU Builder 50K", "big": 12345678901234567, "fiction": "555-0100"}))
    write(clean, "app.js", "const T = 1794000386; const x = [27101.25, 4111.5, 2026]; // version 0.160.0\nfetch('./money/index.json');")
    write(clean, "notes.md", "Trades 2-4 a week; PF 2.91; +$9,919 (about $2,670 a month). The stop sits 1 tick beyond the sweep.")
    found = SP.scan(clean)
    check("a. a clean fake site (prices, epoch times, shas, Sim101, a Kalshi ticker, versions, placeholders, the doc's example topic) has no findings",
          not found, [str(f) for f in found][:8])


# ------------------------------------------------------------------------------------------------ b. scrub
def scrub(tmp):
    F = fake()
    s = os.path.join(tmp, "scrub")
    doc = {"accounts": [{"broker_account": F["broker"], "balance": 49313.54}], "notice": f"LONG · {F['broker']} entered 2 MNQ",
           "log": F["path"], "rule_changes": [{"commit": {"sha": "abc123", "who": "planted-user", "when": "2026-11-03", "why": "merge"}}],
           "learnings": [{"who": "dev", "text": "kept"}], "contact": f"mail {F['email']}", "n": 1794000386, "id_num": 123456789012,
           "goal": "a red car before I " + "turn 30 (Jan 5, 2031)"}
    write(s, "data.json", json.dumps(doc, separators=(",", ":")))
    write(s, "writeups/x.md", f"The 25K eval ({F['broker']}) under {F['path']}.")
    write(s, "app.js", f"const id = '{F['broker']}';")
    write(s, "money/household.json", '{"kind": "olympus-household"}')
    write(s, "clean.json", '{"a": 1, "b": "MFFU Builder 50K"}')
    t0 = os.path.getmtime(os.path.join(s, "clean.json"))
    time.sleep(0.02)
    rep = SP.scrub(s, [("the planted email", F["email"])])
    d = json.load(open(os.path.join(s, "data.json"), encoding="utf-8"))
    mid = F["broker"][:10] + SP.MASK + F["broker"][-4:]
    check("b. a broker id keeps only its last 4 digits, in fields and in sentences", d["accounts"][0]["broker_account"] == mid and mid in d["notice"] and F["broker"] not in json.dumps(d), d)
    check("b. a personal folder becomes <you>", d["log"].startswith("C:\\Users\\<you>\\") and "Planted" not in d["log"], d["log"])
    check("b. a commit author ('who' next to a 'sha') is dropped; a team's 'who' elsewhere stays", "who" not in d["rule_changes"][0]["commit"] and d["learnings"][0]["who"] == "dev", d)
    check("b. an email (a canary too) keeps only its first letter", F["email"] not in json.dumps(d) and d["contact"] == "mail j***@gmail.com", d["contact"])
    check("b. a canary with no generic mask (a full name) becomes <private>", SP.clean_string("by " + F["name"], [F["name"]]) == "by <private>")
    check("b. any other email keeps only its first letter (j***@gmail.com)", SP.clean_string("mail " + "bob.jones" + "@" + "gmail.com") == "mail b***@gmail.com"
          and SP.clean_string("you@example.com") == "you@example.com")
    check("b. a card number in a text keeps only its last 4 digits", SP.clean_string("card " + F["card"]) == "card " + SP.MASK + "1111")
    check("b. an age goes, the goal stays ('a red car (Jan 5, 2031)')", d["goal"] == "a red car (Jan 5, 2031)", d["goal"])
    check("b. numbers are untouched (epoch time, a long integer, a balance)", d["n"] == 1794000386 and d["id_num"] == 123456789012 and d["accounts"][0]["balance"] == 49313.54)
    md = open(os.path.join(s, "writeups", "x.md"), encoding="utf-8").read()
    check("b. a write-up (.md) is masked the same way", F["broker"] not in md and mid in md and "<you>" in md, md)
    check("b. code (.js) is never rewritten (the scan still reports it: code must not hold it)", F["broker"] in open(os.path.join(s, "app.js"), encoding="utf-8").read()
          and any(f["file"] == "app.js" for f in SP.scan(s)))
    check("b. a private file is removed", not os.path.exists(os.path.join(s, "money", "household.json")) and any("household" in r for r in rep["removed"]), rep)
    check("b. a clean file is not rewritten", os.path.getmtime(os.path.join(s, "clean.json")) == t0)
    write(s, "broken.json", '{"x": "' + F["broker"])
    try:
        r2 = SP.scrub(s, [])
        ok = isinstance(r2, dict)
    except Exception as e:  # noqa: BLE001
        ok, r2 = False, e
    check("b. scrub never raises on a broken JSON file (it stays; the scan still sees it)", ok and any(f["file"] == "broken.json" for f in SP.scan(s)), r2)


# ------------------------------------------------------------------------------------------------ c. sources
def sources():
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    m = re.search(r'for app in \(([^)]*)\):', b)
    apps = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    check("c. the build's app copy list names folders of tools/web_public only (no path, no private folder)",
          apps and all(re.match(r"^[a-z0-9_]+$", a) for a in apps) and not set(apps) & {"money_out", "day", "money", "data", "household", "health", "cards", "calendars"},
          [a for a in apps if not re.match(r"^[a-z0-9_]+$", a)])
    code = "\n".join(ln for ln in b.splitlines() if not ln.lstrip().startswith("#"))
    check("c. the build never reads the private folders (money_out, data/day, data/agency, data/inbox, .olympus, household)",
          not re.search(r"money_out|[\"']data[\"']\s*,\s*[\"'](?:day|agency|inbox)[\"']|data/(?:day|agency|inbox)\b|\.olympus|household|agency\.json", code))
    check("c. the build runs tools/site_privacy.scrub as its last step (after every writer, before the summary)",
          "site_privacy" in b and b.find("_privacy.scrub(") > b.find("pinakes_build.py") and b.find("_privacy.scrub(") < b.find('open(os.path.join(out, ".nojekyll")'))
    from tools import money_publish
    check("c. money_publish.KEEP (what the public site gets from money_out) has no household / agency / cards / health",
          not {"household", "agency", "cards", "health", "day"} & set(money_publish.KEEP), sorted(money_publish.KEEP))
    pp = open(os.path.join(ROOT, "tools", "pc_publish.py"), encoding="utf-8").read()
    check("c. pc_publish scrubs the Kalshi feed it adds to the site (before the upload)", "site_privacy" in pp and pp.find("add_kalshi(site, cfg)") < pp.find("scrub(site") < pp.find("site_files(site)"))
    bad = []
    for d in (os.path.join(ROOT, "research", "writeups"), os.path.join(ROOT, "research", "lit"), os.path.join(ROOT, "research", "lab")):
        for p, rel in SP.iter_files(d):
            if p.endswith(".md"):
                t = open(p, encoding="utf-8", errors="replace").read()
                bad += [f"{os.path.basename(d)}/{rel}: {f['kind']}" for f in SP.scan_text(t, rel) if f["kind"] in ("user folder", "broker account", "email", "token")]
    check("c. the research write-ups the build publishes hold no personal folder, full broker id, email or key", not bad, bad[:6])
    # 2026-11-18 (night-priv): the data the site now publishes straight from the repo (board/board.json, trading/trades.json,
    # business/accounts.json / plan.json / work.json, kalshi, brain, status_feed.json ...): no finding at all, no canary
    can = [(lb, v) for lb, v in SP.canaries(None, handles=False)]
    web = os.path.join(ROOT, "tools", "web_public")
    pub = []
    for p, rel in SP.iter_files(web):
        if os.path.splitext(rel)[1].lower() not in (".json", ".md", ".txt", ".csv", ".webmanifest") or rel.startswith("agency/") or SP.LICENSE_RX.search(rel):
            continue
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        pub += [str(f) for f in SP.scan_text(txt, rel, can) if not allow_reviewed(f)]
    check("c. the committed public data files (board, trading, business, kalshi, brain, status feed ...) have no private finding or canary",
          not pub, pub[:8])


# ------------------------------------------------------------------------------------------------ d. a planted state through the real build
def planted_state(t):
    F = fake()
    b1, b2 = F["broker"], "MFFUEVBLD" + "987654321"
    acct = {"name": b1, "adapter": "ninjatrader", "is_live": True, "label": "LIVE", "enabled": True}
    return F, b1, b2, {
        "last_run": t, "runs": 1,
        "pc": {"present": True, "t": t, "age_s": 30, "silent": False, "running": True, "adapter": "ninjatrader", "host": "PLANT-PC", "model": "lit",
               "acct": {"v": 1, "t": t, "account": {"name": b1, "adapter": "ninjatrader", "kind": "live", "label": "LIVE ACCOUNT"}, "running": True,
                        "eval": {"start": "2026-10-19", "days": {}}, "trades": [], "orders": [], "day_pnl": 0},
               "health": {"v": 1, "t": t, "account": acct, "auto": {"resume": {"on": True, "account": b1}}, "log": F["path"]},
               "launch": {"facts": {"lit_account": b1}, "items": [{"key": "allow", "detail": f"{b1} and {b2} may receive orders"}]},
               "ai": {"rule_changes": [{"t": t, "changes": [], "commit": {"sha": "abc123", "who": "planted-git-user", "when": "2026-11-03", "why": "merge"}}]}},
        "notices": [{"t": t, "account": b1, "title": f"LONG · {b1}", "src": f"pc:{b1}", "body": f"mail {F['email']}"},
                    {"t": t, "title": "Goal", "body": "a red car before I " + "turn 30 (Jan 5, 2031)"}],
        "pc_verdict": {"code": "TRADING", "reason": f"Trading on {b1}", "checks": [[f"account {b1}", True]]},
    }


def planted_build(tmp):
    t = int(time.time())
    F, b1, b2, st = planted_state(t)
    d = os.path.join(tmp, "planted")
    os.makedirs(os.path.join(d, "dash"))
    os.makedirs(os.path.join(d, "runs"))
    with open(os.path.join(d, "runs", "index.json"), "w") as fh:
        json.dump({}, fh)
    write(d, "writeups/2026-11-14_planted.md", "---\ntitle: Planted\ndate: 2026-11-14\nstatus: info\nfamily: other\nsummary: The 25K eval ("
          + b2 + ") passes.\n---\n# Planted\n\nLogs under " + F["path"] + ". Contact " + F["email"] + ".\n")
    with open(os.path.join(d, "dash", "state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    out = os.path.join(d, "site")
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "build_web_dashboard.py"), "--state", os.path.join(d, "dash", "state.json"),
                        "--chart", os.path.join(d, "dash", "chart.png"), "--out", out, "--runs", os.path.join(d, "runs"), "--writeups", os.path.join(d, "writeups")],
                       capture_output=True, text=True, timeout=900, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if not check("d. the real build runs on the planted state", r.returncode == 0 and os.path.isfile(os.path.join(out, "data.json")), (r.stdout + r.stderr)[-900:]):
        return
    check("d. the build says what the privacy step did", "privacy:" in r.stdout, r.stdout[-400:])
    can = [("planted broker id", b1), ("planted broker id 2", b2), ("planted commit author", "planted-git-user"), ("planted email", F["email"]),
           ("planted folder name", "Jane Planted")]
    found = SP.scan(out, can, allow=allow_reviewed)
    check("d. none of the planted private values is in the built site (ids, author, email, folder)", not found, [str(f) for f in found][:10])
    raw = open(os.path.join(out, "data.json"), encoding="utf-8").read()
    home = open(os.path.join(out, "home.json"), encoding="utf-8").read()
    m1 = b1[:10] + SP.MASK + b1[-4:]
    m2 = b2[:9] + SP.MASK + b2[-4:]
    check("d. the masked ids are there (the values reached the page and were cut to the last 4 digits)", m1 in raw and m1 in home and m2 in raw, [m1 in raw, m1 in home, m2 in raw])
    try:
        dj, hj = json.loads(raw), json.loads(home)
        ok = isinstance(dj.get("live"), dict) and isinstance(hj.get("live"), dict) and "accounts" in dj and dj["live"].get("pc", {}).get("host") == "PLANT-PC"
    except ValueError as e:
        ok = False
        dj = e
    check("d. data.json and home.json still load with their shape (live, accounts, the PC card)", ok, str(dj)[:300])
    wi = os.path.join(out, "writeups", "index.json")
    check("d. the planted write-up is published, masked", os.path.isfile(wi) and b2 not in open(wi, encoding="utf-8").read() and "Planted" in open(wi, encoding="utf-8").read())


# reviewed, harmless matches in the real site: third-party contacts in vendored licences / libraries, the Kalshi kit's generic SSH
# user and its own fake git author. Anything else fails.
AGENCY_DEMO = ("agency/fixture.json", "agency/call_fixture.json", "agency/leads.json")   # B1 / B2's committed demo data


def allow_reviewed(f):
    # the agency's committed demo files list BUSINESSES (invented ones, and the public OpenStreetMap sample city), never the owner:
    # their street addresses / ZIPs / phones are the product's sample. The owner's own batch (agency/my_leads.json) is NOT allowed.
    if f["file"] in AGENCY_DEMO and f["kind"] in ("street address", "state + ZIP", "phone"):
        return True
    if f["kind"] == "email":
        if re.search(r"(^|/)(OFL|LICENSE|NOTICE|COPYING)[^/]*$", f["file"]) or f["file"].startswith(("olympus/three-addons/", "assets/")):
            return True
        if f["file"].startswith("kalshi/kalshi_status_vm.py"):
            return True                       # git@github.com (the SSH user) and pc@liquidity-engine.local (its own fake author)
    return False


# ------------------------------------------------------------------------------------------------ e. the public ntfy status topic
def ntfy():
    from tools import pc_report as PR
    F = fake()
    t = 1794000386
    b1 = F["broker"]
    live = {"v": 1, "kind": "le-live", "t": t, "every_s": 60, "host": "PLANT-PC", "price": 27101.0, "day_pnl": 0,
            "pc_verdict": {"code": "TRADING", "label": "TRADING YOUR EVAL", "level": "ok", "reason": f"Trading on {b1} from {F['path']}", "t": t},
            "pc": {"running": True, "adapter": "ninjatrader", "host": "PLANT-PC", "present": True, "t": t, "model": "lit"},
            "board": {"t": t, "data_t": t, "host": "PLANT-PC", "running": True,
                      "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "balance": 49313.54, "room": 1145.34, "mll": 2000.0,
                              "waiting": f"waiting for a sweep on {b1}", "window": {"open": True, "text": "entries 02:00-15:30 ET"}},
                      "lines": [{"level": "ok", "text": f"{b1} mail {F['email']}"}], "trades": [{"acct": "lit", "entry_t": t - 60, "usd": 120.0}]},
            "accounts": [{"id": "lit", "name": f"MFFU 50K ({b1})", "conn": {"present": True, "host": "PLANT-PC"}, "eval": {"balance": 49313.54, "room": 1145.34}}]}
    snap = {"t": t + 60, "hb": {"host": "PLANT-PC", "running": True}, "hb_t": t, "hb_age": 60, "hb_src": "pc_hb", "server": True, "nt": True,
            "market_open": True, "entry_hours": True, "mode": "LIVE", "live": live}
    # 2026-11-18 (night-priv): the newer free-text parts of the status (the Brain glance's log lines, the Kalshi rewards card) with
    # the id shapes and network names the old pass let through: lower case / letters+digits ids, a Tailscale IP, a tailnet name, a key
    live["pc"]["glance"] = {"v": 1, "bots": [{"id": "lit", "log": [f"route {F['broker_low']}", f"funded {F['broker_mix']}", f"link http://{F['tsip']}:8766",
                                                                    f"via {F['tailnet']}", f"key {F['ghp']}", f"alerts {F['topic']}"]}]}
    snap["kalshi_rewards"] = {"v": 1, "text": f"paper on {F['tailnet']} by {F['email']}"}
    snap["hb"]["life"] = {"acc": {f"x:{b1}": {"label": f"Zlarior {b1}", "stage": "eval", "bal": 1}}, "ev": [{"t": t, "stage": "eval", "title": f"on {b1}"}]}
    L, exts = PR.posts(snap)
    raw = json.dumps(L, ensure_ascii=False)
    rawx = json.dumps(exts, ensure_ascii=False)
    leak = [k for k in ("broker_low", "broker_mix", "tsip", "tailnet", "ghp", "topic") if F[k].lower() in (raw + rawx).lower()]
    check("e. no lower-case / letters+digits broker id, Tailscale IP, tailnet name, key or alert topic in the glance / Kalshi card",
          not leak and SP.MASK + "3570" in raw + rawx and SP.MASK + "2465" in raw + rawx, (leak, (raw + rawx)[:900]))
    em = [v for v in SP.status_canaries() if "@" in v]
    check("e. public_status masks this PC's canaries by default (the owner's git email in a free-text line)",
          all(v.lower() not in json.dumps(SP.public_status({"note": "from " + v}), ensure_ascii=False).lower() for v in em), len(em))
    check("e. the ext posts (le-live-ext: brd, life, mf, ...) pass the same privacy pass: no PC name, broker id (life keys too), folder, email",
          exts and "PLANT-PC" not in rawx and b1 not in rawx and F["email"] not in rawx and "Jane Planted" not in rawx
          and all(len(json.dumps(e, ensure_ascii=False).encode("utf-8")) <= PR.MAX_STATUS_BYTES for e in exts), rawx[:600])
    check("e. the public status has no PC name (host) anywhere", "PLANT-PC" not in raw and '"host"' not in raw, raw[:400])
    check("e. the public status has no full broker id, no personal folder, no email", b1 not in raw and "Jane Planted" not in raw and F["email"] not in raw, raw[:600])
    from tools import pc_feed as _PF
    _M = _PF.merge(L, exts)                    # the core + ext posts merged back, as the phone reads them
    check("e. the eval numbers the site needs stay (balance, drawdown left, the verdict, the last trade)",
          _M.get("board", {}).get("lit", {}).get("room") == 1145.34 and _M.get("pc_verdict", {}).get("code") == "TRADING" and (_M.get("board", {}).get("trades") or [{}])[0].get("usd") == 120.0, _M)
    check("e. still under ntfy's 4 KB message size", len(raw.encode("utf-8")) <= PR.MAX_STATUS_BYTES)
    src = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    check("e. pc_report posts only lite() (through site_privacy.public_status) to the status topic", "public_status" in src)
    feed = json.load(open(os.path.join(ROOT, "tools", "web_public", "status_feed.json"), encoding="utf-8"))
    check("e. the public status topic is not the private alert topic shape (status_feed.json)", not SP.NTFY_TOPIC_RX.search(feed.get("topic", "")) and feed.get("topic"))


# ------------------------------------------------------------------------------------------------ f. the real, full build
def real_build(tmp):
    site = arg("--site")
    state = arg("--state")
    if not state:
        for c in (os.path.join(ROOT, "data", "pc_publish", "dash", "state.json"), os.path.join(ROOT, "dash", "state.json")):
            if os.path.isfile(c):
                state = c
                break
    can = SP.canaries(state)
    print(f"  canaries: {len(can)} ({', '.join(sorted({lb for lb, _v in can}))}); state: {'yes' if state else 'none (an empty state)'}")
    if not site:
        site = os.path.join(tmp, "site")
        chart = os.path.join(os.path.dirname(state), "chart.png") if state else os.path.join(tmp, "chart.png")
        t0 = time.time()
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "build_web_dashboard.py"), "--state", state or os.path.join(tmp, "none.json"),
                            "--chart", chart, "--out", site], capture_output=True, text=True, timeout=1800, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if not check("f. the full site builds", r.returncode == 0 and os.path.isfile(os.path.join(site, "index.html")), (r.stdout + r.stderr)[-900:]):
            return
        print(f"  built in {time.time() - t0:.0f} s: {sum(1 for _ in SP.iter_files(site))} files")
    t0 = time.time()
    found = SP.scan(site, can, allow=allow_reviewed)
    print(f"  scanned in {time.time() - t0:.0f} s")
    by = {}
    for f in found:
        by[f["kind"]] = by.get(f["kind"], 0) + 1
    check("f. the public site has no private finding (cards, accounts, emails, phones, addresses, names, keys, topics, broker ids, folders, private files)",
          not found, f"{by}; " + "; ".join(str(f) for f in found[:12]))
    check("f. no canary (the owner's git name / email, the state's and this PC's broker ids, the ntfy alert topic) anywhere in it",
          not [f for f in found if f["kind"] == "canary"], [str(f) for f in found if f["kind"] == "canary"][:6])


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="privacy-", dir=TMP_BASE)
    snap_path = os.path.join(ROOT, "tools", "web_hub_snapshot.json")      # a local build refreshes it: put it back as it was
    try:
        with open(snap_path, "rb") as fh:
            snap = fh.read()
    except OSError:
        snap = None
    try:
        detectors(tmp)
        scrub(tmp)
        sources()
        planted_build(tmp)
        shutil.rmtree(os.path.join(tmp, "planted"), ignore_errors=True)
        ntfy()
        if FAST and not arg("--site"):
            print("[SKIP] --fast: the full build (f) was skipped")
        else:
            real_build(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if snap is not None:
            with open(snap_path, "wb") as fh:
                fh.write(snap)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
