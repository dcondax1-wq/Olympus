"""TRUTH CHECK (day-nqdash3 / Olympus 2 "data truth", 2026-11-20, owner: "Olympus as a whole better"; the bar: "true: real data + age, the same
account shows the same $ everywhere").

Read only. It never posts, places, arms or writes outside its report. Two passes:
  1. feeds: the published site's JSON (home.json, data.json, trades.json, payday.json, fleet_plan.json, brief.json, edge.json, k8.json, decisions.json,
     news_week.json, accounts.json) + the PC's 15-minute status post (ntfy, decoded with tools/pc_feed.py) = the TRUTH per account
     (balance, room, to pass / to payout, today, last trade). Flags: a feed that carries other numbers under a real account id, a feed older
     than its stated age, a planned account the PC does not list, the last trade missing from a file.
  2. pages (--pages, Chromium): every visible app of the doors at 390 x 844, after its feeds load: any $ that looks like a balance or a room
     for a plan size but is none of the truth numbers (nor a plan constant: start, buffer, target, payout line), a "DEMO" / "Example" banner
     while a real feed exists, an account name missing where the page lists accounts.

    python -X utf8 tools/truth_check.py                   # feeds only (~5 s), the live site + the live feed
    python -X utf8 tools/truth_check.py --pages           # + every page (~2-4 min, Chromium)
    python -X utf8 tools/truth_check.py --site DIR        # a local folder instead of the live site (tests)
    --feed FILE (a saved merged post instead of ntfy), --json OUT, --md OUT (default research/handoff/2026-11-20/olympus2/data/TRUTH.md)
Exit 0 always (it is a report); the summary line says how many problems.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SITE = "https://dcondax1-wq.github.io/"
MD_OUT = os.path.join(ROOT, "research", "handoff", "2026-11-20", "olympus2", "data", "TRUTH.md")
FEEDS = ["home.json", "data.json", "trading/trades.json", "business/payday.json", "business/fleet_plan.json", "nq/brief.json", "edge.json",
         "kalshi/k8.json", "business/decisions.json", "nq/news_week.json", "business/accounts.json", "status_feed.json"]
# the 4 accounts (owner's plan, business/accounts.json keys) and the ids each source uses for them
ACCTS = {"z50k": {"name": "Zlarior 50K", "pc": ("mffu50k_eval", "lit"), "plan": "builder50k", "biz": "zlarior"},
         "z25k2": {"name": "Zlarior 25K #2", "pc": ("b25k_2",), "plan": "builder25k", "biz": "fresh25"},
         "atlas": {"name": "ATLAS 25K", "pc": ("atlas", "acct_b"), "plan": "builder25k", "biz": "atlas"},
         "rapid": {"name": "Rapid EOD 25K", "pc": ("rapid",), "plan": "rapideod25", "biz": "rapid1"}}
# plan constants a page may print that are not an account's state (start, floors, buffers, targets, payout lines)
CONST = {25000, 24000, 25100, 26100, 26350, 26500, 26850, 27100, 52600, 26000, 50000, 48000, 50100, 52100, 53000, 53600, 54100, 51000, 24500, 25500, 26250}
# how old each feed may be before it is called stale (seconds)
MAX_AGE = {"pc": 20 * 60, "home.json": 6 * 3600, "data.json": 26 * 3600, "nq/brief.json": 26 * 3600, "edge.json": 30 * 3600,
           "kalshi/k8.json": 26 * 3600, "trading/trades.json": 3 * 86400, "business/payday.json": 3 * 86400, "business/fleet_plan.json": 3 * 86400,
           "nq/news_week.json": 3 * 86400}


def _d(x):
    return x if isinstance(x, dict) else {}


def _l(x):
    return x if isinstance(x, list) else []


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def money(v):
    return "-" if v is None else ("-" if v < 0 else "") + "${:,.2f}".format(abs(v)).replace(".00", "")


def age_words(s):
    if s is None:
        return "age unknown"
    s = max(0, s)
    return f"{int(s // 60)} min" if s < 3600 else f"{s / 3600:.1f} h" if s < 172800 else f"{s / 86400:.1f} days"


# ------------------------------------------------------------------------------------------------ loading
def get(site: str, path: str, timeout=30):
    """(json or None, error). site = an https base or a local folder."""
    try:
        if site.startswith("http"):
            req = urllib.request.Request(site.rstrip("/") + "/" + path + f"?truth={int(time.time())}", headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8")), None
        with open(os.path.join(site, path), encoding="utf-8") as fh:
            return json.load(fh), None
    except Exception as e:  # noqa: BLE001
        return None, f"{e.__class__.__name__}: {str(e)[:80]}"


def pc_post(feed_cfg: dict | None, feed_file: str | None = None):
    """The PC's newest merged status post (tools/pc_feed.pick over a 70-minute ntfy window), or (None, why)."""
    if feed_file:
        try:
            return json.load(open(feed_file, encoding="utf-8")), None
        except Exception as e:  # noqa: BLE001
            return None, str(e)
    from tools import pc_feed as PF
    c = _d(feed_cfg)
    if not c.get("topic"):
        return None, "no status_feed.json topic"
    try:
        url = f"{str(c.get('ntfy') or 'https://ntfy.sh').rstrip('/')}/{c['topic']}/json?poll=1&since=70m"
        with urllib.request.urlopen(url, timeout=30) as r:
            msgs = [json.loads(x) for x in r.read().decode("utf-8").splitlines() if x.strip()]
        L = PF.pick(msgs)
        return (L, None) if L else (None, "no status post in the last 70 minutes")
    except Exception as e:  # noqa: BLE001
        return None, f"{e.__class__.__name__}"


# ------------------------------------------------------------------------------------------------ the truth
def truth_of(L: dict | None, now: float) -> dict:
    """{key: {name, balance, room, to_target, today, last: {day, usd} | None, t, age}} from the PC post. Empty without a post."""
    out = {}
    if not isinstance(L, dict):
        return out
    t = _f(L.get("t")) or 0
    rt = _f(_d(L.get("reporter")).get("t")) or _f(L.get("rt")) or t
    accts = {a.get("id"): a for a in _l(L.get("accounts")) if isinstance(a, dict)}
    board = _d(L.get("board"))
    at = {a.get("id"): a for a in _l(_d(L.get("at")).get("a")) if isinstance(a, dict)}
    for k, spec in ACCTS.items():
        a = next((accts[i] for i in spec["pc"] if i in accts), None)
        card = board.get("atlas") if k == "atlas" else board.get("lit") if k == "z50k" else None
        ev = _d(_d(a).get("eval"))
        bal = _f(ev.get("balance")) if a else _f(_d(card).get("balance"))
        if bal is None:
            continue
        row = {"name": spec["name"], "balance": bal,
               "room": _f(ev.get("room")) if a else _f(_d(card).get("room")),
               "to_target": _f(ev.get("to_target")) if a else _f(_d(card).get("to_target")),
               "today": _f(ev.get("today")) if a else _f(_d(card).get("today_pnl")),
               "funded": "funded" in str(ev.get("status") or _d(card).get("status") or "").lower(), "t": rt, "age": now - rt if rt else None}
        if row["funded"]:                     # the ONE "to payout" (pc_feed.js payoutLines = the payout coach's need_more on the mf tracker)
            f = next((_d(r.get("f")) for r in _l(_d(L.get("mf")).get("a")) if isinstance(r, dict) and r.get("id") in spec["pc"] and r.get("f")), None)
            if f:
                try:
                    from engine import payout_coach as PCo
                    st = {"balance": bal, "cycle_start_balance": (bal - _f(f.get("cp"))) if _f(f.get("cp")) is not None else None, "best_day": _f(f.get("bd")),
                          "cycle_days": _f(f.get("cd")), "eligible_from": f.get("ef"), "payouts_n": _f(f.get("pn")), "room": row["room"]}
                    c = PCo.coach(st, "builder50k" if spec["plan"] == "builder50k" else "builder25k",
                                  dt.datetime.fromtimestamp(now, dt.timezone(dt.timedelta(hours=-5))).strftime("%Y-%m-%d"))
                    if c.get("ok"):
                        row["to_payout"] = 0.0 if c.get("eligible") else round(float(c.get("need_more") or 0), 2)
                except Exception:  # noqa: BLE001
                    pass
        tr = [x for i in spec["pc"] for x in _l(_d(at.get(i)).get("tr")) if isinstance(x, list) and len(x) >= 9 and x[1]]
        if tr:
            x = max(tr, key=lambda r: r[1])
            row["last"] = {"exit_t": int(x[1]), "day": dt.datetime.fromtimestamp(x[0], dt.timezone(dt.timedelta(hours=-5))).strftime("%Y-%m-%d"),
                           "usd": _f(x[8])}
        out[k] = row
    return out


# ------------------------------------------------------------------------------------------------ pass 1: the feeds
def feed_checks(site: str, now: float, feed_file: str | None = None) -> dict:
    F, errs = {}, {}
    for p in FEEDS:
        F[p], errs[p] = get(site, p)
    L, why = pc_post(F.get("status_feed.json"), feed_file)
    T = truth_of(L, now)
    probs, info = [], []

    def flag(level, where, what, wrong="", right=""):
        (probs if level != "info" else info).append({"level": level, "where": where, "what": what, "wrong": wrong, "right": right})

    if not L:
        flag("bad", "PC status post (ntfy)", f"no truth to compare with: {why}")
    else:
        a = now - (T[next(iter(T))]["t"] if T else (_f(L.get("t")) or now))
        if a > MAX_AGE["pc"]:
            flag("warn", "PC status post", f"the PC's report is {age_words(a)} old (it posts every 15 min)")
    # every planned account on the PC
    biz = _d(F.get("business/accounts.json"))
    planned = {r.get("key"): r for r in _l(biz.get("accounts")) if isinstance(r, dict)}
    for k, spec in ACCTS.items():
        if k not in T:
            st = str(_d(planned.get(spec["biz"])).get("status") or "")
            flag("info" if st in ("buying", "planned") else "warn", "PC status post",
                 f"{spec['name']} is not in the PC's report" + (f" (plan says '{st}')" if st else ""))
    # home.json: numbers under a real account id that are not the PC's
    h = _d(F.get("home.json"))
    hb = _d(h.get("board"))
    for a in _l(h.get("accounts")):
        if not isinstance(a, dict):
            continue
        k = next((kk for kk, s in ACCTS.items() if a.get("id") in s["pc"]), None)
        ev = _d(a.get("eval"))
        if k and k in T and _f(ev.get("balance")) is not None and abs(_f(ev["balance"]) - T[k]["balance"]) > 1:
            flag("bad" if a.get("badge") != "PAPER" else "warn", f"home.json accounts[id={a.get('id')}]",
                 f"{ACCTS[k]['name']}: home.json says balance {money(_f(ev['balance']))} (badge {a.get('badge')}, source {a.get('source')}); "
                 "any page that reads home.json without the PC post shows it", money(_f(ev["balance"])), money(T[k]["balance"]))
    for key, k in (("lit", "z50k"), ("atlas", "atlas")):
        c = _d(hb.get(key))
        if k in T and _f(c.get("balance")) is not None and abs(_f(c["balance"]) - T[k]["balance"]) > 1:
            flag("warn", f"home.json board.{key}", f"{ACCTS[k]['name']}: {c.get('source') or '?'} numbers ({c.get('badge') or 'no badge'})",
                 money(_f(c["balance"])), money(T[k]["balance"]))
        elif k in T and c.get("balance") is None:
            flag("info", f"home.json board.{key}", f"{ACCTS[k]['name']}: no numbers in the cloud copy (status '{c.get('status')}'): pages need the PC post")
    le = _d(_d(h.get("live")).get("eval"))
    if "z50k" in T and _f(le.get("balance")) is not None and abs(_f(le["balance"]) - T["z50k"]["balance"]) > 1:
        flag("warn", "home.json live.eval", "the 50K eval block (read by older apps) is the cloud's paper twin", money(_f(le["balance"])), money(T["z50k"]["balance"]))
    # trades.json: the last closed trade per account
    tj = _d(F.get("trading/trades.json"))
    AK = {"z50k": "z50k", "z25k2": "z25k2", "atlas": "atlas25f", "rapid": "rapid25"}
    for k, row in T.items():
        last = row.get("last")
        if not last:
            continue
        rows = [r for r in _l(tj.get("trades")) if isinstance(r, dict) and r.get("src") == "live" and r.get("ak") == AK[k]]
        if not any(r.get("day") == last["day"] and abs((_f(r.get("usd")) or 0) - (last["usd"] or 0)) < 1 for r in rows):
            newest = max((r.get("day") or "" for r in rows), default="none")
            flag("info", "trading/trades.json", f"{row['name']}: the {last['day']} trade ({money(last['usd'])}) is not in the file yet (newest {newest}); "
                 "pages must add the PC post's trades (Trading does: feedRows)")
    # ages
    def iso_age(s):
        try:
            return now - dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    def day_age(s):
        try:
            return now - dt.datetime.fromisoformat(str(s)[:10] + "T23:59:00+00:00").timestamp()
        except (TypeError, ValueError):
            return None
    ages = {"home.json": iso_age(h.get("built")), "data.json": iso_age(_d(F.get("data.json")).get("built")),
            "nq/brief.json": iso_age(_d(F.get("nq/brief.json")).get("built_at")), "edge.json": iso_age(_d(F.get("edge.json")).get("built")),
            "kalshi/k8.json": (now - _f(_d(F.get("kalshi/k8.json")).get("t"))) if _f(_d(F.get("kalshi/k8.json")).get("t")) else iso_age(_d(F.get("kalshi/k8.json")).get("built")),
            "trading/trades.json": day_age(_d(tj.get("data_branch")).get("to")) if tj.get("data_branch") else None,
            "business/payday.json": day_age(_d(F.get("business/payday.json")).get("date")),
            "business/fleet_plan.json": day_age(_d(F.get("business/fleet_plan.json")).get("date")),
            "nq/news_week.json": day_age(_d(F.get("nq/news_week.json")).get("built"))}
    for p, a in ages.items():
        if errs.get(p):
            flag("bad", p, f"could not load: {errs[p]}")
        elif a is None:
            flag("info", p, "no build time in the file")
        elif a > MAX_AGE.get(p, 86400):
            flag("warn", p, f"{age_words(a)} old (allowed {age_words(MAX_AGE.get(p, 86400))})")
    for s in _l(_d(_d(F.get("nq/brief.json")).get("data")).get("stale")):
        flag("info", "nq/brief.json data.stale", str(s))
    eh = _d(_d(F.get("edge.json")).get("eh"))
    if isinstance(eh.get("a"), list) and len(eh["a"]) > 3 and (day_age(eh["a"][3]) or 0) > 7 * 86400:
        flag("warn", "edge.json eh.a", f"ATLAS's edge light uses data to {eh['a'][3]} ({age_words(day_age(eh['a'][3]))} old): LEAD_WIRES nqdash3 F")
    return {"truth": T, "problems": probs, "info": info, "ages": {k: (None if v is None else int(v)) for k, v in ages.items()}, "pc": L is not None}


# ------------------------------------------------------------------------------------------------ pass 2: the pages
VISIBLE = ["", "nq/", "board/", "trading/", "aegis/", "pnyx/", "demeter/", "fates/", "kronos/", "journal/", "ledger/", "business/", "business/accounts.html",
           "business/mffu.html", "hera/", "oikos/", "chrysos/", "mercury/", "compass/", "planner/", "helios/", "clio/", "atlas/", "widget/", "gate/"]
SIZE_OF = {"builder50k": (46000, 56000), "builder25k": (23000, 29000), "rapideod25": (23000, 29000)}
MONEY_RX = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d{4,6}(?:\.\d{1,2})?)")
PAYOUT_RX = re.compile(r"to payout\s*:?\s*\$\s?([\d,]+(?:\.\d+)?)", re.I)
ROOM_RX = re.compile(r"(?:drawdown left|room left|room|cushion)\s*:?\s*\$\s?([\d,]+(?:\.\d+)?)", re.I)
NOT_STATE = re.compile(r"target|floor|buffer|start|payout line|ask at|pass at|goal|line|max|plan|limit|at \$|reach|net|\bPF\b|a month|/mo|backtest|research|"
                       r"\bH[12]\b|20\d\d|best close|above \$|under \$|over \$|\+\$|you wrote|owner_note|typed|· you\b", re.I)
# pages that must show every account's truth (data truth slice: nq/, trading/, board/)
MUST_SHOW = ("nq/", "trading/", "board/")


def page_checks(site: str, T: dict, pages=None, wait_ms=7000) -> list:
    """Each page's visible text after its feeds load: balance-like / room-like $ that match no account's truth or a plan constant."""
    from playwright.sync_api import sync_playwright
    bal_ok = {round(r["balance"]) for r in T.values()} | CONST
    room_ok = {round(r["room"]) for r in T.values() if r.get("room") is not None}
    lo, hi = 23000, 56000
    out = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        for path in pages or VISIBLE:
            p = ctx.new_page()
            url = site.rstrip("/") + "/" + path
            row = {"page": path or "(root)", "url": url, "bad_balances": [], "bad_rooms": [], "demo": False, "names": [], "error": None, "missing": [], "bad_payout": []}
            try:
                p.goto(url, wait_until="load", timeout=45000)
                p.wait_for_timeout(wait_ms)
                txt = p.evaluate("() => document.body ? document.body.innerText : ''")
                frames = p.evaluate("() => [...document.querySelectorAll('iframe')].length")
                row["frames"] = frames
                for m in MONEY_RX.finditer(txt):
                    v = float(m.group(1).replace(",", ""))
                    if lo <= v <= hi and round(v) not in bal_ok and not any(abs(round(v) - c) <= 1 for c in bal_ok):
                        near = txt[max(0, m.start() - 40):m.end() + 12].replace("\n", " ")
                        if not NOT_STATE.search(near):
                            row["bad_balances"].append({"value": v, "context": txt[max(0, m.start() - 60):m.end() + 20].replace("\n", " ").strip()})
                for m in ROOM_RX.finditer(txt):
                    v = float(m.group(1).replace(",", ""))
                    if 50 <= v <= 3000 and room_ok and not any(abs(v - r) <= 1 for r in room_ok):
                        row["bad_rooms"].append({"value": v, "context": txt[max(0, m.start() - 40):m.end() + 20].replace("\n", " ").strip()})
                dm = re.search(r"\bDEMO\b|Example numbers|EXAMPLE", txt)
                row["demo"] = bool(dm)
                pay_ok = {round(r["to_payout"]) for r in T.values() if r.get("to_payout") is not None}
                for m in PAYOUT_RX.finditer(txt):
                    v = float(m.group(1).replace(",", ""))
                    if pay_ok and not any(abs(v - x) <= 1 for x in pay_ok):
                        row["bad_payout"].append({"value": v, "context": txt[max(0, m.start() - 50):m.end() + 10].replace("\n", " ").strip()})
                row["demo_ctx"] = txt[max(0, dm.start() - 50):dm.end() + 70].replace("\n", " ").strip() if dm else ""
                if path in MUST_SHOW:                  # my pages: every account's balance (and ATLAS's today) must be on screen
                    flat = txt.replace(",", "")
                    row["missing"] = [f"{r['name']} {money(r['balance'])}" for r in T.values() if str(int(round(r["balance"]))) not in flat
                                      and str(int(r["balance"])) not in flat]
                    row["missing"] += [f"{r['name']} today {money(r['today'])}" for r in T.values() if r.get("today") and abs(r["today"]) >= 1
                                       and str(int(round(abs(r["today"])))) not in flat and str(int(abs(r["today"]))) not in flat]
                row["names"] = [r["name"] for r in T.values() if r["name"].split(" ")[0] in txt]
            except Exception as e:  # noqa: BLE001
                row["error"] = f"{e.__class__.__name__}: {str(e)[:100]}"
            finally:
                p.close()
            out.append(row)
        br.close()
    return out


# ------------------------------------------------------------------------------------------------ report
def report_md(R: dict, now: float) -> str:
    T = R["truth"]
    lines = [f"# Truth check ({dt.datetime.fromtimestamp(now, dt.timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
             "Read only (tools/truth_check.py). TRUTH = the PC's own 15-minute report; every other number is checked against it.", "",
             "## The truth now (PC report)", "", "| account | balance | room | to pass | to payout (coach) | today | last trade | age |", "|---|---|---|---|---|---|---|---|"]
    for k, r in T.items():
        last = r.get("last")
        lines.append(f"| {r['name']} | {money(r['balance'])} | {money(r['room'])} | {'-' if r['funded'] else money(r['to_target'])} | {money(r.get('to_payout')) if r['funded'] else '-'} | {money(r['today'])} | "
                     f"{(last['day'] + ' ' + money(last['usd'])) if last else '-'} | {age_words(r['age'])} |")
    lines += ["", f"## Problems ({len(R['problems'])})", "", "| level | where | what | shown | should be |", "|---|---|---|---|---|"]
    for p in R["problems"]:
        lines.append(f"| {p['level']} | {p['where']} | {p['what']} | {p['wrong']} | {p['right']} |")
    lines += ["", f"## Notes ({len(R['info'])})", ""] + [f"- {p['where']}: {p['what']}" for p in R["info"]]
    if R.get("pages") is not None:
        lines += ["", "## Pages (390 x 844, after their feeds load)", "", "| page | wrong balance-like $ | wrong room $ | wrong to payout | DEMO shown | accounts named | missing (nq / trading / board) |", "|---|---|---|---|---|---|---|"]
        for p in R["pages"]:
            if p["error"]:
                lines.append(f"| {p['page']} | error: {p['error']} | | | |")
                continue
            bb = "; ".join(f"{money(x['value'])} ({x['context'][:70]})" for x in p["bad_balances"][:3]) or "-"
            rr = "; ".join(f"{money(x['value'])} ({x['context'][:60]})" for x in p["bad_rooms"][:3]) or "-"
            pp = "; ".join(f"{money(x['value'])} ({x['context'][:60]})" for x in p.get("bad_payout") or []) or "-"
            lines.append(f"| {p['page']} | {bb} | {rr} | {pp} | {('YES: ' + p.get('demo_ctx', '')[:90]) if p['demo'] else '-'} | {', '.join(p['names']) or '-'} | {'; '.join(p.get('missing') or []) or '-'} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--feed", default=None)
    ap.add_argument("--pages", action="store_true")
    ap.add_argument("--only", default="", help="comma list of page paths for --pages")
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=MD_OUT)
    ap.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    now = a.now or time.time()
    R = feed_checks(a.site, now, a.feed)
    if a.pages:
        R["pages"] = page_checks(a.site, R["truth"], [x for x in a.only.split(",") if x] or None)
    if a.md:
        os.makedirs(os.path.dirname(a.md), exist_ok=True)
        open(a.md, "w", encoding="utf-8").write(report_md(R, now))
    if a.json:
        json.dump(R, open(a.json, "w"), indent=1, default=str)
    nb = len(R["problems"]) + sum(1 for p in R.get("pages") or [] if p["bad_balances"] or p["bad_rooms"] or p["error"] or p.get("missing") or p.get("bad_payout"))
    print(f"truth check: {len(R['truth'])} accounts in the PC report, {len(R['problems'])} feed problems, {len(R['info'])} notes"
          + (f", {sum(1 for p in R['pages'] if p['bad_balances'] or p['bad_rooms'])} pages with a wrong $" if a.pages else "") + f" -> {a.md}")
    return 0 if nb >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
