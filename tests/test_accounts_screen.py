"""NQ Accounts screen + the 7-day keep-alive for a NEWLY added Rapid EOD 25K (day-accounts 2026-11-23). Paper only, no network.

    python -X utf8 -m tests.test_accounts_screen [--shots]      (~1 min; the browser part skips without Playwright)

  a. static: tools/web_public/nq/accounts.html / accounts.js / acctcore.js / accounts.css: textContent only, no outside address,
     OLYMPUS NIGHT palette, the NQ page links it
  b. node: acctcore.build on a PC post with 5 accounts (Zlarior 50K, 25K #2, ATLAS funded, Rapid EOD 25K, the NEW Rapid EOD 25K #2
     that business/accounts.json does not list): one card each, funded ATLAS from $0, $ to pass / payout + ETA, bots + armed,
     the 7-day clock green 4+ / gold 2-3 / red 0-1 + the red banner, the PC's age, last 4 only; CME days + the act day = Python
  c. the new Rapid end to end: START phrase consent (go.armed_accounts -> keepalive.start_consent) covers slot rapid2 on a Rapid EOD
     25K, its MFFU plan id, owner name "Rapid EOD 25K #2", clock7 rows from mf + the heartbeat's keepalive block, the cloud K7
     (pc_silent_check): keep-alive fills from the PC's k7 rows count, and the 1st Rapid's push no longer silences the 2nd's
  d. browser 390 x 844: the cards from a mocked PC post, taps >= 44 px, no sideways scroll, nothing fetched off the site; --shots
     writes research/handoff/2026-11-23/accounts/*.png
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
WEB = os.path.join(ROOT, "tools", "web_public")
NQ = os.path.join(WEB, "nq")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-23", "accounts")
ET = ZoneInfo("America/New_York")


def et(y, m, d, hh=0, mm=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


NOW = et(2026, 11, 23, 11, 40)          # Mon 11-23 11:40 ET
T = NOW - 4 * 60                        # the PC posted 4 min ago


# ------------------------------------------------------------------------------------------------ the PC post (as tools/pc_report.py sends it)
def post(t=T, lts=None, on=None, ar=None):
    """(core, [ext]): 5 accounts. lts = {pc id: last traded day}; on = keep-alive switches; ar = {bot id: [on, armed]}."""
    from engine import clock7
    lts = lts if lts is not None else {"mffu50k_eval": "2026-11-20", "b25k_2": "2026-11-19", "atlas": "2026-11-20", "rapid": "2026-11-17", "rapid2": None}
    on = on if on is not None else {"lit": True, "atlas": True, "rapid": True, "rapid2": True, "x:b25k_2": True}
    ar = ar if ar is not None else {"lit": [1, 1], "atlas": [1, 1], "b25k_2": [1, 1], "rapid": [1, 1], "rapid2": [1, 1]}

    def ev(b, s, today, tt):
        mll = 2000.0 if s == 50000 else 1000.0
        fl = max(b - (1000.0 if s == 25000 else 1046.0), s - mll)
        return {"start_balance": s, "balance": b, "profit": round(b - s, 2), "to_target": round(s + (3000 if s == 50000 else 1500) - b, 2),
                "target_balance": s + (3000 if s == 50000 else 1500), "floor": fl, "room": round(b - fl, 2), "mll": mll, "today": today, "status": "open"}

    def acct(i, name, plan, b, s, today):
        return {"id": i, "name": name, "plan": plan, "kind": "eval", "source": "pc", "badge": "LIVE", "conn": {"present": True, "t": t, "running": True, "connected": True},
                "eval": ev(b, s, today, t), "pnl": {"today": today}, "running": True, "trades": [], "days": []}
    lit = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "source": "PC bot", "balance": 49214.0, "floor": 48168.0, "room": 1046.0,
           "mll": 2000.0, "to_target": 3786.0, "today_pnl": 22.0, "status": "open"}
    atlas = {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "badge": "LIVE", "source": "PC bot (account B)", "balance": 25401.0,
             "floor": 24401.0, "room": 1000.0, "mll": 1000.0, "profit": 401.0, "today_pnl": -35.0, "status": "funded"}
    core = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": t, "every_s": 300, "price": 27402.0,
            "pc_verdict": {"code": "TRADING", "label": "TRADING", "level": "good", "t": t},
            "pc": {"running": True, "adapter": "ninjatrader", "present": True, "t": t, "age_s": 0, "silent": False},
            "reporter": {"t": t + 30, "server": True, "nt": True, "market_open": True, "mode": "LIVE", "problems": []},
            "board": {"v": 1, "kind": "le-board", "t": t, "data_t": t, "where": "live", "today": "2026-11-23", "running": True, "level": "good", "lit": lit, "atlas": atlas, "lines": []},
            "accounts": [acct("mffu50k_eval", "MFFU 50K Eval", "Builder 50K", 49214.0, 50000.0, 22.0),
                         acct("b25k_2", "Zlarior Builder 25K #2", "Builder 25K", 25024.0, 25000.0, 0.0),
                         acct("rapid", "Rapid EOD 25K", "Rapid EOD 25K", 25000.0, 25000.0, 0.0),
                         acct("rapid2", "Rapid EOD 25K #2", "Rapid EOD 25K", 25000.0, 25000.0, 0.0)],
            "ar": ar}
    mf = {"t": t, "a": [{"id": "mffu50k_eval", "nm": "Zlarior 50K", "sd": "2026-10-19", "l4": "6016"},
                        {"id": "b25k_2", "nm": "Zlarior 25K #2", "sd": "2026-11-18", "l4": "6019"},
                        {"id": "atlas", "nm": "ATLAS 25K funded", "sd": "2026-11-17", "l4": "6018"},
                        {"id": "rapid", "nm": "Rapid EOD 25K", "sd": "2026-11-17", "l4": "0004"},
                        {"id": "rapid2", "nm": "Rapid EOD 25K #2", "sd": "2026-11-23", "l4": "0007"}]}
    for r in mf["a"]:
        if lts.get(r["id"]):
            r["lt"] = lts[r["id"]]
    k7 = clock7.build(mf, {"on": on, "last": {}, "lane": {}}, t)
    ext = {"v": 1, "kind": "le-live-ext", "src": "pc_report", "t": t, "rt": t + 28, "part": 0, "of": 1,
           "x": {"mf": mf, "k7": {"a": [{k: v for k, v in r.items() if v is not None} for r in (k7 or {}).get("a", [])]}}}
    return core, [ext]


def ndjson(core, exts) -> str:
    lines = [{"event": "message", "time": e["rt"], "message": json.dumps(e)} for e in exts]
    lines.append({"event": "message", "time": core["reporter"]["t"], "message": json.dumps(core)})
    return "\n".join(json.dumps(x) for x in lines) + "\n"


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    h, js, cj, css = (AK.read(os.path.join(NQ, f)) for f in ("accounts.html", "accounts.js", "acctcore.js", "accounts.css"))
    js = js.replace("'http://www.w3.org/2000/svg'", "'SVG_NS'", 1)   # night-nq-accounts: the SVG namespace is a name, not an address (only that exact string)
    bad = r"\.innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|https?://|method:|XMLHttpRequest|WebSocket|sendBeacon|document\.cookie|localStorage|sessionStorage"
    check("a. accounts.js / acctcore.js: textContent only, no outside address, GET only, no storage; the core has no fetch and no DOM",
          not re.search(bad, js + cj) and "textContent" in js and "fetch(" not in cj and "document." not in cj, re.findall(bad, js + cj)[:4])
    check("a. accounts.html: phone viewport, one h1, a polite status pill, a role=alert banner, the PC feed before the page module",
          "viewport-fit=cover" in h and h.count("<h1") == 1 and 'aria-live="polite"' in h and 'role="alert"' in h
          and h.index('src="../pc_feed.js') < h.index('src="accounts.js') and not re.search(r"https?://", h))
    check("a. OLYMPUS NIGHT: black, cards #16131e, violet #3e255e / #4d2e76 / glow #9d59ee, gold #f1c14b, mint #77db89; no brown / olive",
          all(c in css for c in ("#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89")) and not re.search(r"olive|brown|marble", css, re.I))
    check("a. the NQ page links the Accounts screen", 'href="accounts.html"' in AK.read(os.path.join(NQ, "index.html")))
    names = " ".join([h, js, cj])
    check("a. no account id or private name in the screen's files (only the last 4 from the PC post)", not re.search(r"MFFU(EV|SF)\d|demetrades|Zlarior\w*@", names))


# ------------------------------------------------------------------------------------------------ b. node: the core
HARNESS = r"""
const fs = require('fs'), path = require('path');
(async () => {
  const dir = path.dirname(process.argv[2]);
  const F = require(path.join(dir, 'pc_feed.cjs')); globalThis.PC_FEED = F;
  const D = await import(path.join(dir, 'nqdesk.mjs')), K7 = await import(path.join(dir, 'clock7.mjs')), A = await import(path.join(dir, 'acctcore.mjs'));
  const IN = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), out = {};
  const et = (t) => { const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(t * 1000)).map((x) => [x.type, x.value])); return { date: `${p.year}-${p.month}-${p.day}`, min: +p.hour * 60 + +p.minute }; };
  for (const [name, sc] of Object.entries(IN.scen)) {
    const lite = sc.nd ? F.parseLatest(sc.nd) : null, now = sc.now;
    const h = lite ? F.homeOver({}, lite, now, null) : {};
    const e = et(now);
    out[name] = A.build(D.accounts(h, IN.biz, now), K7.rows(lite, now), { lite, biz: IN.biz, payday: IN.payday, nowS: now, today: K7.tradingDay(now), minuteET: e.min, etDate: e.date });
  }
  out.cme = IN.days.map((d) => [d, A.fullClosure(d), A.earlyClose(d)]);
  out.act = IN.acts.map(([b, t]) => { const e = et(t); return [b, t, A.actDay(b, K7.tradingDay(t), e.min, e.date)]; });
  out.safe = ['MFFUEV1234567 x', 'Rapid EOD 25K #2', 'acct 987654321'].map(A.safeName);
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def node_run(scen, days, acts):
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="ac-")
    try:
        shutil.copy(os.path.join(WEB, "pc_feed.js"), os.path.join(tmp, "pc_feed.cjs"))
        for f in ("nqdesk", "clock7", "acctcore"):
            shutil.copy(os.path.join(NQ, f + ".js"), os.path.join(tmp, f + ".mjs"))
        shutil.copy(os.path.join(NQ, "goals_model.js"), os.path.join(tmp, "goals_model.js"))   # acctcore imports the ONE goals model (QA #4)
        open(os.path.join(tmp, "package.json"), "w").write('{"type": "module"}')               # ... a .js ES module next to the .mjs copies
        hp = os.path.join(tmp, "harness.cjs")
        open(hp, "w", encoding="utf-8").write(HARNESS)
        biz = json.load(open(os.path.join(WEB, "business", "accounts.json"), encoding="utf-8"))
        payday = json.load(open(os.path.join(WEB, "business", "payday.json"), encoding="utf-8"))
        ip = os.path.join(tmp, "in.json")
        json.dump({"scen": scen, "biz": biz, "payday": payday, "days": days, "acts": acts}, open(ip, "w", encoding="utf-8"))
        r = subprocess.run([exe, hp, hp, ip], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[-2000:])
            return {"_error": r.stderr[-800:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_b():
    from engine import cme_calendar as CC, keepalive as K
    days = [(dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat() for i in range(730)]
    acts = []
    for i in range(50):                                   # bases over Nov 2026 .. Jan 2027 (Thanksgiving, Christmas, New Year), each day at 10:00 + 15:45 ET
        b = dt.date(2026, 11, 10) + dt.timedelta(days=i)
        for k in range(0, 8):
            d = b + dt.timedelta(days=k)
            for hh, mm in ((10, 0), (15, 45)):
                acts.append([b.isoformat(), et(d.year, d.month, d.day, hh, mm)])
    c1, e1 = post()
    stale = post(t=NOW - 3 * 3600)
    calm = post(lts={"mffu50k_eval": "2026-11-23", "b25k_2": "2026-11-23", "atlas": "2026-11-20", "rapid": "2026-11-23", "rapid2": None})
    off = post(on={"lit": True, "atlas": True, "x:b25k_2": True}, ar={"lit": [1, 1], "atlas": [1, 1], "b25k_2": [1, 1], "rapid": [1, 1], "rapid2": [1, 0]})
    scen = {"today": {"nd": ndjson(c1, e1), "now": NOW}, "stale": {"nd": ndjson(*stale), "now": NOW}, "calm": {"nd": ndjson(*calm), "now": NOW},
            "off": {"nd": ndjson(*off), "now": NOW}, "none": {"nd": None, "now": NOW}}
    r = node_run(scen, days, acts)
    if r is None:
        print("  (node not installed: part b skipped)")
        return
    if "_error" in r:
        check("b. node harness runs", False, r["_error"])
        return
    M = r["today"]
    C = {c["key"]: c for c in M["cards"]}
    keys = [c["key"] for c in M["cards"]]
    check("b. one card per account, the owner's order + the NEW Rapid (not in accounts.json) after them: 5 cards",
          keys[:4] == ["zlarior", "atlas", "rapid1", "fresh25"] and keys[4:] == ["rapid2"], keys)
    n = C.get("rapid2") or {}
    check("b. the new Rapid's card: 'Rapid EOD 25K #2', Eval, last 4 ··0007, $25,000, $1,000 room, $1,500 to pass, LIT + ATLAS + BLITZ paper",
          n.get("name") == "Rapid EOD 25K #2" and n.get("stage") == "Eval" and n.get("l4") == "0007" and n.get("balance") == "$25,000"
          and n.get("room") == "$1,000" and (n.get("goal") or {}).get("text") == "$1,500" and [b["name"] for b in n.get("bots") or []] == ["LIT", "ATLAS", "BLITZ"], n)
    k = n.get("clock") or {}
    check("b. its 7-day clock: no trade yet, counts from its start Mon 11/23, MFFU's last day Sun 11/29, 6 days left (green), keep-alive ON, acts Fri 11/27? no: "
          "the last FULL session before Sat 11/28 = Wed 11/25 (Thu 11/26 + Fri 11/27 are half days)",
          k.get("lf") is None and k.get("hard") == "2026-11-29" and k.get("left") == 6 and k.get("lvl") == "ok" and k.get("on") is True and k.get("act") == "2026-11-25", k)
    a = C.get("atlas") or {}
    check("b. ATLAS funded the MFFU way: +$401 from $0, today -$35, +$1,699 to the first payout (ask the max $1,000 at $2,100), ATLAS only, no BLITZ",
          a.get("stage") == "Funded" and a.get("balance") == "+$401" and a.get("today") == "-$35" and (a.get("goal") or {}).get("text") == "+$1,699"
          and "$1,000 at $2,100" in (a.get("goal") or {}).get("sub", "") and [b["name"] for b in a.get("bots") or []] == ["ATLAS"] and "1st payout" in a.get("eta", ""), a)
    z = C.get("zlarior") or {}
    check("b. Zlarior 50K: $49,214, +$22 today, $1,046 of $2,000 room (gold bar), $3,786 to pass, funded + payout ETA from payday.json, LIT ARMED",
          z.get("balance") == "$49,214" and z.get("today") == "+$22" and z.get("room") == "$1,046" and z.get("roomOf") == "$2,000" and z.get("roomLvl") == "ok"
          and (z.get("goal") or {}).get("text") == "$3,786" and z.get("eta", "").startswith("Funded ~") and "1st payout ~" in z.get("eta", "")
          and (z.get("bots") or [{}])[0] == {"name": "LIT", "state": "armed"}, z)
    lv = {c["key"]: (c.get("clock") or {}).get("lvl") for c in M["cards"]}
    lf = {c["key"]: (c.get("clock") or {}).get("left") for c in M["cards"]}
    check("b. colours by days left: Zlarior 4 (green), 25K #2 3 (gold), ATLAS 4 (green), Rapid 1 (red), new Rapid 6 (green)",
          lf == {"zlarior": 4, "fresh25": 3, "atlas": 4, "rapid1": 1, "rapid2": 6} and lv == {"zlarior": "ok", "fresh25": "warn", "atlas": "ok", "rapid1": "bad", "rapid2": "ok"}, (lf, lv))
    b = M.get("banner") or {}
    check("b. the big red banner names the account at risk and its last day (Rapid EOD 25K, Tue 11/24), 1 at risk",
          b.get("level") == "bad" and "1 account at risk" in b.get("title", "") and "Rapid EOD 25K (last day Tue 11/24)" in b.get("text", "")
          and "Rapid EOD 25K #2" not in b.get("text", "") and M["counts"]["risk"] == 1, b)
    check("b. the PC's age on top: 'PC 4 min ago' (green); every card 'PC 4 min ago'",
          M["pc"]["text"] == "PC 4 min ago" and M["pc"]["level"] == "ok" and all(c["ageText"] == "PC 4 min ago" for c in M["cards"] if c["has"]), (M["pc"], [c["ageText"] for c in M["cards"]]))
    S = r["stale"]
    check("b. a PC quiet for 3 h: 'PC 3 h ago' in red, cards marked not fresh, the banner adds 'turn it on'",
          S["pc"]["level"] == "bad" and S["pc"]["text"].startswith("PC 3 h") and not any(c["fresh"] for c in S["cards"]) and "turn it on" in (S.get("banner") or {}).get("text", ""), S["pc"])
    Ca = r["calm"]
    check("b. every account traded: no banner, every clock green",
          Ca.get("banner") is None and all((c.get("clock") or {}).get("lvl") == "ok" for c in Ca["cards"]), [(c["key"], (c.get("clock") or {}).get("left")) for c in Ca["cards"]])
    O = {c["key"]: c for c in r["off"]["cards"]}.get("rapid2") or {}
    check("b. the new Rapid before START arms it: LIT / ATLAS 'on' (not armed), keep-alive OFF",
          [x["state"] for x in O.get("bots") or []][:2] == ["on", "on"] and (O.get("clock") or {}).get("on") is False, O)
    N = r["none"]
    check("b. no PC post: 'PC not heard from' in red, the plan rows from accounts.json, no made-up numbers, a warn banner",
          N["pc"]["text"] == "PC not heard from" and all(c["balance"] == "-" for c in N["cards"]) and (N.get("banner") or {}).get("level") == "warn", N["pc"])
    txt = json.dumps(r["today"])
    check("b. only the last 4 digits ever (no 5+ digit run that is not money / a date)", not re.search(r"(?<![\d$,.-])\d{5,}(?![\d,])", txt.replace("2026", "")), re.findall(r"\d{5,}", txt)[:4])
    check("b. safeName turns a broker id into its last 4", r["safe"] == ["··4567 x", "Rapid EOD 25K #2", "acct ··4321"], r["safe"])
    bad = [d for d, f, e in r["cme"] if f != CC.full_closure(d) or e != CC.early_close(d)]
    check("b. CME closures + early halts = engine/cme_calendar on every day of 2026-2027", not bad, bad[:5])
    mism = []
    for base, t, act in r["act"]:
        p = K.plan(base, t).get("act_day")
        if p != act:
            mism.append((base, dt.datetime.fromtimestamp(t, ET).strftime("%m-%d %H:%M"), act, p))
    check(f"b. the keep-alive act day = engine/keepalive.plan in the daytime ({len(r['act'])} cases, Thanksgiving + Christmas + New Year)", not mism, mism[:5])


# ------------------------------------------------------------------------------------------------ c. the new Rapid end to end
def part_c():
    from engine import go, account_cli, keepalive as K, clock7, mffu_view
    from engine.tradovate import LIVE_PHRASE
    import tools.pc_silent_check as P
    inv = [{"role": "main", "name": "MFFU-REAL-0050", "mffu": True, "id": "zlarior"},
           {"role": "b", "name": "MFFU-REAL-0025", "armed": True, "mffu": True, "id": "atlas"},
           {"role": "rapid", "name": "MFFU-REAL-R004", "armed": True, "mffu": True, "id": "rapid", "plan": "rapideod25"},
           {"role": "rapid", "name": "MFFU-REAL-R007", "armed": True, "mffu": True, "id": "rapid2", "plan": "rapideod25"},
           {"role": "extra", "name": "MFFU-REAL-0019", "armed": True, "mffu": True, "id": "b25k_2", "plan": "builder25k"}]
    real = account_cli.inventory
    account_cli.inventory = lambda *a, **k: [dict(x) for x in inv]
    try:
        armed = go.armed_accounts()
    finally:
        account_cli.inventory = real
    check("c. START's armed list: the new Rapid EOD 25K in slot rapid2 is its own key (not a duplicate of the 1st Rapid)",
          [k for k, _l, _n in armed] == ["lit", "atlas", "rapid", "rapid2", "x:b25k_2"] and armed[3][1].startswith("Rapid EOD 25K"), armed)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "keepalive.json")
        r = K.start_consent(LIVE_PHRASE, armed, now=et(2026, 11, 23, 17), path=p)
        on = json.load(open(p, encoding="utf-8"))["accounts"]
        check("c. typing I ACCEPT LIVE RISK turns the keep-alive ON for the new Rapid too (rapid2), and all 5",
              on.get("rapid2") is True and sorted(r["keys"]) == sorted(["lit", "atlas", "rapid", "rapid2", "x:b25k_2"]), (r, on))
        p2 = os.path.join(tmp, "k2.json")
        json.dump({"accounts": {}, "owner_off": {"rapid2": "off"}}, open(p2, "w", encoding="utf-8"))
        r2 = K.start_consent(LIVE_PHRASE, armed, now=et(2026, 11, 23, 17), path=p2)
        check("c. one he turned OFF himself stays off at the next START", "rapid2" not in r2["keys"] and any("Rapid EOD 25K" in x for x in r2["kept_off"]), r2)
    obj = types.SimpleNamespace(spec={"lane": "rapid", "slot": "rapid2", "preset": "mffu_rapid_eod_25k"}, slot="rapid2")
    g = {"key": "rapid2", "main": {"obj": obj}, "lanes": [{"obj": obj, "kind": "extra"}]}
    check("c. the keep-alive sees the 2nd Rapid 25K as an MFFU Rapid EOD 25K (its rule applies)", K._plan_id(g) == "mffu_rapid_eod_25k", K._plan_id(g))
    check("c. owner names: 'Rapid EOD 25K' and 'Rapid EOD 25K #2' (never a broker id)",
          mffu_view.owner_name("rapid", "Rapid EOD 25K", "Rapid EOD 25K", "eval") == "Rapid EOD 25K"
          and mffu_view.owner_name("rapid2", "Rapid EOD 25K #2", "Rapid EOD 25K", "eval") == "Rapid EOD 25K #2")
    from engine import rapid as RP
    try:
        spec = RP.lane_spec({"account": "Sim104", "eval_start": "2026-11-23", "plan": "mffu_rapid_eod_25k", "stage": "eval"}, {}, slot="rapid2", dup=True)
    except Exception as e:  # noqa: BLE001
        spec = {"error": repr(e)}
    check("c. the 2nd Rapid's LIT lane: id rapid2, slot rapid2, name '... #2' (the k7 / mf / glance id)",
          spec.get("id") == "rapid2" and spec.get("slot") == "rapid2" and str(spec.get("name", "")).endswith("#2"), spec)
    mf = {"a": [{"id": "rapid", "nm": "Rapid EOD 25K", "sd": "2026-11-17", "lt": "2026-11-17"}, {"id": "rapid2", "nm": "Rapid EOD 25K #2", "sd": "2026-11-23"}]}
    k = clock7.build(mf, {"on": {"rapid": True, "rapid2": True}, "last": {"rapid2": "2026-11-25"}, "lane": {}}, et(2026, 11, 25, 18, 30)) or {}
    R = {x["id"]: x for x in k.get("a") or []}
    check("c. clock7 (the PC's k7 block): the new Rapid counts from the day before its start, then from its keep-alive fill; ON from its switch",
          (R.get("rapid2") or {}).get("lf") == "2026-11-25" and (R.get("rapid2") or {}).get("on") is True and (R.get("rapid2") or {}).get("hard") == "2026-12-02", R)
    k0 = clock7.build(mf, {"on": {"rapid2": True}}, et(2026, 11, 23, 12)) or {}
    r0 = next((x for x in k0.get("a") or [] if x["id"] == "rapid2"), {})
    check("c. before its first trade: base 'start', MFFU's last day Sun 11-29, act Wed 11-25", r0.get("base") == "start" and r0.get("hard") == "2026-11-29" and r0.get("act") == "2026-11-25", r0)

    # the cloud K7: the PC is off on Mon 11-23 10:00 ET; both Rapids last filled Tue 11-17 (act Mon 11-23)
    now = et(2026, 11, 23, 10)
    mf2 = {"a": [{"id": "rapid", "nm": "Rapid EOD 25K", "sd": "2026-11-17", "lt": "2026-11-17"},
                 {"id": "rapid2", "nm": "Rapid EOD 25K #2", "sd": "2026-11-16", "lt": "2026-11-17"}]}
    rows = clock7.build(mf2, None, now)["a"]
    st, msgs = P.k7_step({}, now - 5 * 3600, now, rows, fetched=True, sent=["PC looks off: Rapid EOD 25K must trade by Tue 11-24"])
    check("c. cloud K7: the 1st Rapid's push already went today -> the NEW Rapid (#2) still gets its own (FOUND: a name substring silenced it)",
          [m["title"] for m in msgs] == ["PC looks off: Rapid EOD 25K #2 must trade by Tue 11-24"], [m["title"] for m in msgs])
    st, msgs = P.k7_step({}, now - 5 * 3600, now, rows, fetched=True, sent=["PC looks off: Rapid EOD 25K #2 must trade by Tue 11-24"])
    check("c. and the other way: #2 sent, the 1st Rapid still pushes", [m["title"] for m in msgs] == ["PC looks off: Rapid EOD 25K must trade by Tue 11-24"], [m["title"] for m in msgs])
    st, msgs = P.k7_step({}, now - 5 * 3600, now, rows, fetched=True, sent=[])
    check("c. nothing sent yet: both Rapids push, one each", sorted(m["key"] for m in msgs) == ["k7cloud:rapid2:2026-11-23", "k7cloud:rapid:2026-11-23"], [m["key"] for m in msgs])
    # the PC's ext post: mf says the new Rapid last traded 11-17, the PC's k7 (keep-alive fill Fri 11-20) says later
    pc_k7 = clock7.build(mf2, {"on": {"rapid": True, "rapid2": True}, "last": {"rapid2": "2026-11-20"}}, now)
    ext = {"kind": "le-live-ext", "x": {"mf": mf2, "k7": {"a": [{k_: v for k_, v in r.items() if k_ not in ("act", "dl")} for r in pc_k7["a"]]}}}
    fr = {r["id"]: r for r in P.feed_clock([{"time": now - 3 * 3600, "message": json.dumps(ext)}], now)}
    check("c. cloud K7 reads the keep-alive's fill from the PC's k7 rows (Fri 11-20 -> last day Fri 11-27, act Wed 11-25), keep-alive ON; the 1st Rapid unchanged",
          (fr.get("rapid2") or {}).get("lf") == "2026-11-20" and (fr.get("rapid2") or {}).get("hard") == "2026-11-27" and (fr.get("rapid2") or {}).get("on") is True
          and (fr.get("rapid") or {}).get("hard") == "2026-11-24" and (fr.get("rapid") or {}).get("on") is True, fr)
    st, msgs = P.k7_step({}, now - 5 * 3600, now, list(fr.values()), fetched=True, sent=[])
    check("c. so after a keep-alive fill the cloud does not cry wolf: only the 1st Rapid (really due) pushes", [m["key"] for m in msgs] == ["k7cloud:rapid:2026-11-23"], [m["key"] for m in msgs])
    ext2 = {"kind": "le-live-ext", "x": {"mf": {"a": [mf2["a"][0]]}, "k7": ext["x"]["k7"]}}
    fr2 = {r["id"] for r in P.feed_clock([{"time": now, "message": json.dumps(ext2)}], now)}
    check("c. an account the mf block lost (cut for size) still comes from the PC's k7 rows", fr2 == {"rapid", "rapid2"}, fr2)


# ------------------------------------------------------------------------------------------------ d. the browser
def part_d():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    at = dt.datetime.fromtimestamp(NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    srv, origin = AK.serve({"/home.json": None})
    shots = "--shots" in sys.argv
    try:
        with AK.browser() as br:
            for name, (core, exts) in (("today", post()), ("calm", post(lts={"mffu50k_eval": "2026-11-23", "b25k_2": "2026-11-23", "atlas": "2026-11-20", "rapid": "2026-11-23", "rapid2": None}))):
                ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": ndjson(core, exts)})
                p.goto(f"{origin}/nq/accounts.html?at={at}")
                p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
                p.wait_for_timeout(700)
                p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
                o = p.evaluate("""() => ({ pc: document.getElementById('pc').textContent, lvl: document.getElementById('pc').dataset.level,
                    keys: [...document.querySelectorAll('.ac-card')].map((c) => c.dataset.key), k7: [...document.querySelectorAll('.ac-card')].map((c) => c.dataset.k7),
                    h: [...document.querySelectorAll('.ac-card h2')].map((e) => e.textContent), banner: !document.getElementById('banner').hidden,
                    bt: document.getElementById('bannerTitle').textContent, txt: document.getElementById('cards').textContent })""")
                if name == "today":
                    check("d. 390 px: 5 cards from the PC post (the new Rapid EOD 25K #2 last), 'PC 4 min ago' green, the red 7-day banner up",
                          o["keys"] == ["zlarior", "atlas", "rapid1", "fresh25", "rapid2"] and o["pc"] == "PC 4 min ago" and o["lvl"] == "ok" and o["banner"]
                          and "at risk" in o["bt"] and o["k7"] == ["ok", "ok", "bad", "warn", "ok"] and "Rapid EOD 25K #2" in o["h"], o)
                    check("d. the words: +$401 funded, Keep-alive ON, LIT · ARMED, BLITZ · paper only, ··0007, MFFU's last day",
                          all(s in o["txt"] for s in ("+$401", "Keep-alive ON", "LIT · ARMED", "BLITZ · paper only", "··0007", "MFFU's last day", "1st payout")), o["txt"][:300])
                else:
                    check("d. every account traded: no banner, every clock green", not o["banner"] and set(o["k7"]) == {"ok"}, o)
                check(f"d. {name}: taps >= 44 px, no sideways scroll, nothing fetched off the site (ntfy mocked), no console error",
                      not AK.taps(p) and AK.no_sideways(p) and not off and not errs and p.mocked, (AK.taps(p)[:4], off[:3], errs[:3]))
                if shots:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.screenshot(path=os.path.join(SHOTS, f"accounts-390-{name}.png"), full_page=False)
                    if name == "today":
                        p.screenshot(path=os.path.join(SHOTS, "accounts-390-full.png"), full_page=True)
                        p.evaluate("document.getElementById('acct-rapid2').scrollIntoView({block: 'center'})")
                        p.screenshot(path=os.path.join(SHOTS, "accounts-390-new-rapid.png"), full_page=False)
                ctx.close()
            # PC quiet 3 hours: honest stale header
            core, exts = post(t=NOW - 3 * 3600)
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": ndjson(core, exts)})
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
            o = p.evaluate("() => ({ pc: document.getElementById('pc').textContent, lvl: document.getElementById('pc').dataset.level, bx: document.getElementById('bannerText').textContent })")
            check("d. a PC quiet 3 h: 'PC 3 h ... ago' in red, the banner says to turn it on", o["pc"].startswith("PC 3 h") and o["lvl"] == "bad" and "turn it on" in o["bx"], o)
            if shots:
                p.screenshot(path=os.path.join(SHOTS, "accounts-390-stale.png"), full_page=False)
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    if "--static" not in sys.argv:
        part_d()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
