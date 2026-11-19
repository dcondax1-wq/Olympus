"""K8 weekly re-test, the CLOUD half (night-kadapt 2026-11-19; engine/kalshi_adapt.py has the rules and the PC half).

    python tools/kalshi_adapt.py                 # newest public tape (<= 1 request a second), re-test every leg, the 96-window scan,
                                                 # research/lab/kalshi_adapt.json + new Decide-card items, one table
    python tools/kalshi_adapt.py --offline       # the caches only, no request
    python tools/kalshi_adapt.py --no-decide     # leave tools/web_public/business/decisions.json alone
    python tools/kalshi_adapt.py --as-of 2026-11-18 [--json] [--budget 600]

What it writes (the PC takes the shrinks within the hour after the lead ships: engine/kalshi_adapt.pc_weekly merges them, most
restrictive wins; it can only ever make a leg smaller / OFF / capped lower):
  research/lab/kalshi_adapt.json   the week's numbers per leg (8 and 4 weeks: bets, won, net per $1 after exact fees, price paid),
                                   the cuts in force ("adapt"), what changed, the scan, the calendar check, one line
  tools/web_public/business/decisions.json   new ids only: "put leg X back?" when a cut leg recovered; at most 2 new legs a week
                                   that clear the multiple-testing bar (found on the older 8 of 12 weeks, checked on the newest 4)
Caches: reads /home/user/kalshi_cache/kmetal (the K8 study's tape, read only), writes /home/user/kalshi_cache/kadapt
(KADAPT_READ / KADAPT_CACHE to move them). Public GET only, never a key, never an order, never research/lab/kalshi_clock.json.
Tests: python -X utf8 -m tests.test_kalshi_adapt
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import kalshi_adapt as KA  # noqa: E402
from engine import kalshi_clock as KC  # noqa: E402
from engine import kalshi_live as KL  # noqa: E402

READ_DIRS = [d for d in (os.environ.get("KADAPT_READ") or "/home/user/kalshi_cache/kmetal").split(os.pathsep) if d]
CACHE = os.environ.get("KADAPT_CACHE") or "/home/user/kalshi_cache/kadapt"
SERIES = ("KXGOLD15M", "KXSILVER15M")
CACHE_MAX_MB = 150
HHMM = tuple(f"{h:02d}{m:02d}" for h in range(24) for m in (0, 15, 30, 45))      # the 96 quarter-hour window closes (ET)
SIDES = ("yes", "no")
WORD = {"yes": "UP", "no": "DOWN"}
MON = KC.MON


# ================================================================================================ caches (read: kmetal; write: kadapt)
def _jl(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    yield r
    except OSError:
        return


def day_of(code):
    """'26NOV12' -> date(2026, 11, 12)."""
    return dt.date(2000 + int(code[:2]), MON.index(code[2:5]) + 1, int(code[5:7]))


def load_markets(dirs) -> dict:
    """{ticker: {res, o, c, date, hhmm, vol}} of settled markets (mk_<SERIES>.jsonl, the K8 harvest's compact rows)."""
    out = {}
    for d in dirs:
        for s in SERIES:
            for r in _jl(os.path.join(d, f"mk_{s}.jsonl")):
                if r.get("result") not in ("yes", "no") or not r.get("ticker"):
                    continue
                try:
                    code = str(r["event_ticker"]).split("-")[1]
                    out[r["ticker"]] = {"res": r["result"], "o": KA._ts(r.get("open_time")), "c": KA._ts(r.get("close_time")),
                                        "date": str(day_of(code[:7])), "hhmm": code[7:11], "vol": KA._f(r.get("volume_fp"), 0.0),
                                        "series": s}
                except (IndexError, ValueError, KeyError):
                    continue
    return out


def load_tape(dirs, cache, markets) -> dict:
    """{ticker: {t, o, res, tr}}: the K8 study's open tape (ot_<SERIES>.jsonl + the market results) and this tool's own tape."""
    out = {}
    for d in dirs:
        for s in SERIES:
            for r in _jl(os.path.join(d, f"ot_{s}.jsonl")):
                m = markets.get(r.get("t"))
                if m:
                    out[r["t"]] = {"t": r["t"], "o": r.get("o"), "res": m["res"], "tr": r.get("tr") or []}
    out.update(KA.read_tape(os.path.join(cache, "tape.jsonl")))
    return out


def load_candles(dirs) -> dict:
    """{ticker: row} of the 1-minute quotes (cd_<SERIES>.jsonl: t, hhmm, day, o, c, res, k = [[end, bid, ask, ...], ...])."""
    out = {}
    for d in dirs:
        for s in SERIES:
            for r in _jl(os.path.join(d, f"cd_{s}.jsonl")):
                if r.get("t") and r.get("res") in ("yes", "no") and isinstance(r.get("k"), list):
                    r["series"] = s
                    out[r["t"]] = r
    return out


def cache_mb(path) -> float:
    tot = 0
    for dp, _, fs in os.walk(path):
        for f in fs:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return tot / 1e6


# ================================================================================================ fetch (public GET, <= 1 a second)
def fetch_markets(pub, cache, have, since_ts) -> int:
    """Settled markets closing after since_ts -> cache/mk_<SERIES>.jsonl (the compact K8 row). -> markets added."""
    added = 0
    keep = ("ticker", "event_ticker", "open_time", "close_time", "floor_strike", "expiration_value", "result", "volume_fp", "settlement_ts")
    for s in SERIES:
        cursor, rows = None, []
        for _ in range(20):
            j = pub.get("/markets", {"series_ticker": s, "status": "settled", "min_close_ts": int(since_ts), "limit": 1000, "cursor": cursor})
            if not j:
                break
            rows += [m for m in j.get("markets") or [] if isinstance(m, dict)]
            cursor = j.get("cursor")
            if not cursor or not j.get("markets"):
                break
        new = [m for m in rows if m.get("ticker") not in have and m.get("result") in ("yes", "no")]
        if new:
            os.makedirs(cache, exist_ok=True)
            with open(os.path.join(cache, f"mk_{s}.jsonl"), "a", encoding="utf-8") as fh:
                for m in sorted(new, key=lambda m: m.get("close_time") or ""):
                    fh.write(json.dumps({k: m.get(k) for k in keep}, separators=(",", ":")) + "\n")
            added += len(new)
    return added


def _compact_candles(cs) -> list:
    def g(d, *names):
        for n in names:
            if isinstance(d, dict) and d.get(n) is not None:
                return KA._f(d.get(n))
        return None
    out = []
    for k in cs or []:
        b, a, p = k.get("yes_bid") or {}, k.get("yes_ask") or {}, k.get("price") or {}
        out.append([k.get("end_period_ts"), g(b, "close_dollars", "close"), g(a, "close_dollars", "close"), g(b, "high_dollars", "high"),
                    g(b, "low_dollars", "low"), g(a, "high_dollars", "high"), g(a, "low_dollars", "low"), g(p, "open_dollars", "open"),
                    g(p, "high_dollars", "high"), g(p, "low_dollars", "low"), g(p, "close_dollars", "close"),
                    KA._f(k.get("volume_fp"), KA._f(k.get("volume"))), KA._f(k.get("open_interest_fp"), KA._f(k.get("open_interest")))])
    return out


def fetch_candles(pub, cache, markets, candles, start, end) -> int:
    """1-minute quotes of the weekday markets in [start, end] that have none yet (batches: markets x minutes <= 9800)."""
    cut = KA._ts((pub.get("/historical/cutoff") or {}).get("market_settled_ts")) or 0.0
    todo = sorted((m["o"], t) for t, m in markets.items() if t not in candles and str(start) <= m["date"] <= str(end) and m["o"]
                  and dt.date.fromisoformat(m["date"]).weekday() < 5 and (m["vol"] or 0) > 0 and (m["c"] or 0) >= cut + 3600)
    added, i = 0, 0
    while i < len(todo):
        chunk = [todo[i]]
        j = i + 1
        while j < len(todo) and len(chunk) < 40:
            s0, e1 = chunk[0][0] - 60, markets[todo[j][1]]["c"] + 60
            if (len(chunk) + 1) * ((e1 - s0) // 60 + 1) > 9800:
                break
            chunk.append(todo[j])
            j += 1
        s0, e1 = chunk[0][0] - 60, markets[chunk[-1][1]]["c"] + 60
        d = pub.get("/markets/candlesticks", {"market_tickers": ",".join(t for _, t in chunk), "start_ts": int(s0), "end_ts": int(e1),
                                              "period_interval": 1})
        if d is None:
            break
        got = {m.get("market_ticker"): m.get("candlesticks") for m in d.get("markets") or [] if isinstance(m, dict)}
        with open(os.path.join(cache, f"cd_{markets[chunk[0][1]]['series']}.jsonl"), "a", encoding="utf-8") as fh:
            for _, t in chunk:
                if t in got:
                    m = markets[t]
                    row = {"t": t, "hhmm": m["hhmm"], "day": t.split("-")[1][:7], "o": m["o"], "c": m["c"], "res": m["res"], "vol": m["vol"],
                           "k": _compact_candles(got[t])}
                    fh.write(json.dumps(row, separators=(",", ":")) + "\n")
                    row["series"] = m["series"]
                    candles[t] = row
                    added += 1
        i = j
    return added


# ================================================================================================ the 96-window scan (pure)
def quote_m1(row, minute=1, max_back=2):
    """(yes bid, yes ask) at the end of minute `minute` of the window (up to max_back minutes earlier), 2-sided books only."""
    o = KA._f(row.get("o"))
    if o is None:
        return None
    target, best = o + 60 * minute, None
    for k in row.get("k") or []:
        try:
            e, b, a = float(k[0]), k[1], k[2]
        except (TypeError, ValueError, IndexError):
            continue
        if e > target or e < target - 60 * max_back or b is None or a is None or a <= 0 or b >= 1 or a < b or (b <= 0 and a >= 1):
            continue
        best = (float(b), float(a))
    return best


def scan_bets(candles, start, end, stake) -> dict:
    """{(series, hhmm, side): [bets]} at the 60-second quote (ask; DOWN = 1 - yes bid), spread <= 10c, price <= 70c, weekdays."""
    out = {}
    cap, spread = KA.RULES["scan_max_price"], KA.RULES["scan_max_spread"]
    for t, r in candles.items():
        try:
            day = day_of(str(r.get("day") or t.split("-")[1][:7]))
        except (ValueError, IndexError):
            continue
        if not (str(start) <= str(day) <= str(end)) or day.weekday() >= 5:
            continue
        q = quote_m1(r)
        if not q or q[1] - q[0] > spread + 1e-9:
            continue
        for side in SIDES:
            p = round(q[1] if side == "yes" else 1 - q[0], 4)
            if not (0.02 <= p <= cap):
                continue
            b = KA.make_bet(f"{r['series']}:{r['hhmm']}:{side}", day, t, KA._f(r["o"]), side, p, r["res"], stake)
            if b:
                b["ts"] = KA._f(r["o"]) + 60
                out.setdefault((r["series"], r["hhmm"], side), []).append(b)
    return out


def known_legs() -> set:
    """(series, ET close, side) of the executor's legs (the morning ones also at 06:30, their London-clock gap weeks)."""
    out = set()
    for x in KC.LEGS:
        h, m = x["open"]
        close = (h * 60 + m + 15) if x["tz"] == "ET" else None
        if close is None:
            out |= {(x["series"], "0530", x["side"]), (x["series"], "0630", x["side"])}
        else:
            out.add((x["series"], f"{close // 60:02d}{close % 60:02d}", x["side"]))
    return out


def scan(candles, as_of, stake=15.0) -> dict:
    """384 rules found on the older 8 of the last 12 weeks (cluster t >= the Bonferroni bar for 384, +10% per $1, >= 25 bets),
    checked once on the newest 4 (>= +5% per $1, >= 12 bets). The executor's own legs are left out of the list it proposes."""
    R = KA.RULES
    a = KA._day(as_of)
    h0 = a - dt.timedelta(days=7 * R["scan_holdout_weeks"] - 1)
    d0 = a - dt.timedelta(days=7 * R["scan_weeks"] - 1)
    bets = scan_bets(candles, d0, a, stake)
    bar = KA.bar_t(R["scan_rules"], R["scan_alpha"])
    rows, known = [], known_legs()
    for s in SERIES:
        for hh in HHMM:
            for side in SIDES:
                bs = bets.get((s, hh, side)) or []
                disc = [b for b in bs if b["day"] < str(h0)]
                hold = [b for b in bs if b["day"] >= str(h0)]
                sd = KA.stats(disc, R["scan_weeks"] - R["scan_holdout_weeks"])
                sh = KA.stats(hold, R["scan_holdout_weeks"])
                t = KA.cluster_t([{"cluster": b["day"], "pnl": b["pnl"], "cost": b["cost"]} for b in disc]) if disc else 0.0
                ok_d = sd.get("n", 0) >= R["scan_min_n"] and (sd.get("net_per_1") or 0) >= R["scan_min_net"] and t >= bar
                ok_h = sh.get("n", 0) >= R["scan_hold_min_n"] and (sh.get("net_per_1") or -1) >= R["scan_hold_min_net"]
                rows.append({"series": s, "hhmm": hh, "side": side, "known": (s, hh, side) in known, "disc": sd, "hold": sh,
                             "t": round(t, 2) if abs(t) != float("inf") else (99.0 if t > 0 else -99.0), "found": ok_d, "held": ok_d and ok_h})
    rows.sort(key=lambda r: -r["t"])
    return {"rules_tried": R["scan_rules"], "bar_t": round(bar, 2), "expected_false_at_5pct": round(0.05 * R["scan_rules"], 1),
            "discovery": [str(d0), str(h0 - dt.timedelta(days=1))], "held_out": [str(h0), str(a)],
            "with_data": sum(1 for r in rows if r["disc"].get("n")), "found": [r for r in rows if r["found"]],
            "passed": [r for r in rows if r["held"] and not r["known"]], "top": rows[:8]}


def leg_words(r) -> str:
    h, m = int(r["hhmm"][:2]), int(r["hhmm"][2:])
    o = (h * 60 + m - 15) % 1440
    return f"{KA.SERIES_NAME.get(r['series'], r['series'])} {WORD[r['side']]} {o // 60:02d}:{o % 60:02d}-{h:02d}:{m:02d} ET"


def new_leg_proposals(S, have_ids, room, as_of, stake=15.0) -> list:
    out = []
    for r in S["passed"]:
        if len(out) >= room:
            break
        pid = f"k8-new-{KA.SERIES_NAME.get(r['series'], 'x')}-{r['hhmm']}-{WORD[r['side']].lower()}"
        if pid in have_ids:
            continue
        d, h = r["disc"], r["hold"]
        per1 = min(d["net_per_1"], h["net_per_1"])
        gain = round(per1 * stake * h["bets_month"])
        out.append({
            "id": pid, "question": f"K8: add {leg_words(r)} as a PAPER leg (a new clock bet, {money(stake)} a bet)?",
            "why": (f"The weekly scan of all 384 windows found it on {S['discovery'][0]}..{S['discovery'][1]}: won "
                    f"{100 * d['win_rate']:.0f}% at {100 * d['avg_price']:.0f}c ({pct(d['net_per_1'])} per $1, {d['n']} bets, t {r['t']:.1f} over "
                    f"the {S['bar_t']:.2f} bar for 384 tries); the newest 4 weeks (held out): won {100 * h['win_rate']:.0f}%, "
                    f"{pct(h['net_per_1'])} per $1, {h['n']} bets.")[:240],
            "impact": (f"About {money(gain, True)} a month at {money(stake)} a bet if the smaller of the two numbers repeats "
                       f"({h['bets_month']:.0f} bets a month); $0 until it proves itself in paper and you type the phrase."),
            "impact_usd": gain, "usd_month": gain, "options": ["yes", "no", "later"], "status": "open", "source": KA.REPORT_REL,
            "applies": ("A yes = Claude adds it to the K8 clock as a PAPER leg (engine/kalshi_clock LEGS + research/lab/kalshi_clock.json "
                        "paper_legs); real money only after about 4 weeks of paper and your phrase again"),
            "risk": "Found by searching 384 windows: even past the bar it can be luck; tested at the 60-second quote, the bot buys at 20 s.",
            "recommend": "yes", "recommend_why": "Paper costs nothing and tells us in a month whether it is real.",
            "added": str(as_of), "from": "kalshi_adapt", "k8": {"kind": "new", "series": r["series"], "hhmm": r["hhmm"], "side": r["side"],
                                                                 "as_of": str(as_of)}})
    return out


def money(x, sign=False):
    return KL.money(x, sign)


def pct(x):
    return KA.pct(x)


# ================================================================================================ calendar check (task: verify)
def calendar_check(markets, start, end, cfg, today) -> dict:
    """Every ticker the executor would trade in [start, end] (its London clock + holiday skips) is in Kalshi's own list; the
    holiday lists reach 45 days ahead."""
    want = KA.wanted_tickers(start, end, cfg)
    miss = [t for t, o in want if t not in markets]
    last = max(list(KC.UK_SKIP) + list(KC.CME_SKIP))
    warn = None
    if dt.date.fromisoformat(last) < KA._day(today) + dt.timedelta(days=45):
        warn = f"the UK / CME holiday lists in engine/kalshi_clock.py end on {last}: add the next ones (UK May bank holidays, CME)"
    return {"tickers": len(want), "missing": miss[:20], "missing_n": len(miss), "holidays_until": last, "warn": warn}


# ================================================================================================ the run
def run(as_of=None, offline=False, decide=True, budget=600, report_path=None, decisions_path=None, read_dirs=None, cache=None,
        pub=None, now=None, say=print) -> dict:
    now = time.time() if now is None else now
    report_path, decisions_path = report_path or KA.LAB_REPORT, decisions_path or KA.DECISIONS
    read_dirs, cache = list(READ_DIRS if read_dirs is None else read_dirs), cache or CACHE
    cfg = KC.load_config()[0]
    a = KA._day(as_of) if as_of else KA.as_of_day(now)
    W = KA.windows_of(a)
    dirs = read_dirs + [cache]
    markets = load_markets(dirs)
    tape = load_tape(read_dirs, cache, markets)
    candles = load_candles(dirs)
    net = {"calls": 0, "markets": 0, "tape": 0, "candles": 0}
    if not offline:
        if cache_mb(cache) > CACHE_MAX_MB:
            say(f"  [!!] {cache} is over {CACHE_MAX_MB} MB: no fetch (clear it)")
        else:
            os.makedirs(cache, exist_ok=True)
            pub = pub or KA.Public(budget=budget)
            newest = max([m["c"] for m in markets.values() if m.get("c")] or [now - 86 * 86400])
            net["markets"] = fetch_markets(pub, cache, markets, newest - 86400)
            markets = load_markets(dirs)
            net["tape"] = KA.fetch_tape(pub, os.path.join(cache, "tape.jsonl"), W["long"][0], a, cfg, now=now, have=tape)["added"]
            tape = load_tape(read_dirs, cache, markets)
            d0 = a - dt.timedelta(days=7 * KA.RULES["scan_weeks"] - 1)
            net["candles"] = fetch_candles(pub, cache, markets, candles, d0, a)
            net["calls"] = pub.calls
    old = KA._jread(report_path, {}) or {}
    dec = KA._jread(decisions_path, {}) or {}
    items = dec.get("items") if isinstance(dec, dict) and isinstance(dec.get("items"), list) else []
    restored = dict(old.get("restored") or {})
    done = set(old.get("restores_applied") or [])
    for did, lid in KA.restores_from_decisions(items, done):
        restored[lid] = KL.et_day(now)
        done.add(did)
    L = KA.evaluate(KA.leg_bets(tape, W["long"][0], a, cfg), a, prev={"legs": old.get("adapt") or {}}, cfg=cfg, restored=restored, src="cloud")
    S = scan(candles, a, float(cfg["stake_usd"]))
    have = {str(i.get("id")) for i in items}
    wk = a.isocalendar()[:2]
    used = sum(1 for i in items if (i.get("k8") or {}).get("kind") == "new" and _week(i.get("added")) == wk)
    props_new = new_leg_proposals(S, have, max(0, KA.RULES["new_per_week"] - used), a, float(cfg["stake_usd"]))
    props = [p for p in L["proposals"] if p["id"] not in have] + props_new
    cal = calendar_check(markets, W["long"][0], a, cfg, a)
    doc = {"v": 1, "kind": "k8-adapt-report", "t": int(now), "as_of": str(a), "src": "cloud (tools/kalshi_adapt.py, public tape)",
           "rules": KA.RULES, "base_price": KA.BASE_PRICE, "windows": L["windows"],
           "legs": {lid: {k: r.get(k) for k in ("name", "live", "w8", "w4", "hits", "guard", "now")} for lid, r in L["legs"].items()},
           "adapt": L["adapt"], "changes": ((old.get("changes") or []) + L["changes"])[-KA.CHANGES_KEEP:], "proposals": props,
           "restored": restored, "restores_applied": sorted(done)[-40:],
           "scan": dict({k: S[k] for k in ("rules_tried", "bar_t", "expected_false_at_5pct", "discovery", "held_out", "with_data")},
                        found=[_srow(r) for r in S["found"]][:10], passed=[_srow(r) for r in S["passed"]][:10], top=[_srow(r) for r in S["top"]]),
           "calendar": cal, "data": {"tape_markets": len(tape), "candle_markets": len(candles), "fetched": net},
           "line": L["line"], "how": "Only ever tighter on its own (half size / OFF / a lower max price); back up or a new leg only with "
                                     "the owner's yes on the Decide card. engine/kalshi_adapt.py has the rules."}
    KA._jwrite(report_path, doc, indent=1)
    added = []
    if decide and props and isinstance(dec, dict) and isinstance(dec.get("items"), list):
        dec["items"] = items + props
        dec["updated"] = str(dt.date.today())
        KA._jwrite(decisions_path, dec, indent=1)
        added = [p["id"] for p in props]
    return {"doc": doc, "L": L, "scan": S, "added": added, "proposals": props}


def _week(day):
    try:
        return dt.date.fromisoformat(str(day)[:10]).isocalendar()[:2]
    except ValueError:
        return None


def _srow(r):
    return {"leg": leg_words(r), "series": r["series"], "hhmm": r["hhmm"], "side": r["side"], "known": r["known"], "t": r["t"],
            "disc": {k: r["disc"].get(k) for k in ("n", "win_rate", "net_per_1", "avg_price")},
            "hold": {k: r["hold"].get(k) for k in ("n", "win_rate", "net_per_1", "avg_price")}}


def table(res) -> list:
    d, S = res["doc"], res["scan"]
    out = [f"K8 weekly re-test as of {d['as_of']} (8 weeks {d['windows']['long'][0]}..{d['windows']['long'][1]}, "
           f"$ at {money(KC.load_config()[0]['stake_usd'])} a bet, exact fees)", ""]
    out.append(f"  {'leg':<36} {'8 wk bets':>9} {'won':>5} {'per $1':>7} {'$/mo':>7} {'paid':>5} | {'4 wk':>4} {'per $1':>7} {'paid':>5}  now")
    for lid, r in d["legs"].items():
        a, b = r["w8"] or {}, r["w4"] or {}
        now = r.get("now") or {}
        cut = ", ".join(x for x in ("OFF" if now.get("enabled") is False else "", f"x{now['size_factor']:g}" if "size_factor" in now else "",
                                    f"max {100 * now['max_price']:.0f}c" if "max_price" in now else "") if x) or ("as armed" if not r.get("guard") else "too few bets")
        out.append(f"  {r['name'] + ('' if r['live'] else ' (paper)'):<36} {a.get('n', 0):>9} {100 * (a.get('win_rate') or 0):>4.0f}% "
                   f"{pct(a.get('net_per_1')):>7} {money(a.get('usd_month') or 0, True):>7} {100 * (a.get('avg_price_all') or 0):>4.0f}c | "
                   f"{b.get('n', 0):>4} {pct(b.get('net_per_1')):>7} {100 * (b.get('avg_price_all') or 0):>4.0f}c  {cut}")
    out.append("")
    out.append("  " + d["line"])
    for c in res["L"]["changes"]:
        out.append("  CHANGED " + c["text"])
    out.append(f"  scan: {S['rules_tried']} rules ({S['with_data']} with data), bar t {S['bar_t']} (by luck ~{S['expected_false_at_5pct']:.0f} "
               f"would pass 5%); found {len(S['found'])} on {S['discovery'][0]}..{S['discovery'][1]}, "
               f"{sum(1 for r in S['found'] if r['held'])} held up on {S['held_out'][0]}..{S['held_out'][1]} ({len(S['passed'])} not a K8 leg yet)")
    for r in S["top"][:3]:
        out.append(f"    best: {leg_words(r)}{' (a K8 leg)' if r['known'] else ''}: t {r['t']:.1f}, {pct(r['disc'].get('net_per_1'))} "
                   f"({r['disc'].get('n', 0)} bets) -> held out {pct(r['hold'].get('net_per_1'))} ({r['hold'].get('n', 0)} bets)")
    cal = d["calendar"]
    out.append(f"  calendar: {cal['tickers'] - cal['missing_n']}/{cal['tickers']} executor tickers listed by Kalshi; holiday lists to "
               f"{cal['holidays_until']}" + (f"; WARNING {cal['warn']}" if cal["warn"] else ""))
    for p in res["proposals"]:
        out.append(f"  [decide] {p['question']}  ({p['impact']})")
    if res["added"]:
        out.append(f"  Decide card: +{len(res['added'])} ({', '.join(res['added'])})")
    f = d["data"]["fetched"]
    out.append(f"  data: {d['data']['tape_markets']} tape markets, {d['data']['candle_markets']} quote markets; fetched {f['calls']} "
               f"requests (+{f['markets']} markets, +{f['tape']} tape, +{f['candles']} quotes)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="K8 weekly re-test (cloud): public tape, exact fees, shrink-only + Decide proposals")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-decide", action="store_true")
    ap.add_argument("--budget", type=int, default=600)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = run(as_of=a.as_of, offline=a.offline, decide=not a.no_decide, budget=a.budget)
    if a.json:
        print(json.dumps(res["doc"], indent=1, default=str))
    else:
        print("\n".join(table(res)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
