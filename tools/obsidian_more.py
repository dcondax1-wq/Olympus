"""ZEUS Brain, the big layer (day-obsidian2 2026-11-20; owner: "I want a huge Obsidian that learns").

Plugged into tools/obsidian_brain.py (Brain.build calls it; nothing here runs on its own). It adds, all generated, all linked:
    Trades/Trade <day> <hhmm> <bot> <side> [src]   one per trade: every published trade (live, paper, backtest: trades.json)
                                                   + the 2026 backtest trades of the loss anatomy (LIT, ATLAS, BLITZ);
                                                   prices, R, $, the reason codes of a loss, the context, links
    Lessons/Lesson <code>                          the LEARNING layer: every losing trade gets ONE main cause (the loss anatomy's
                                                   tools/win_loss_anatomy.cause_of) + the careful-human checklist flags
                                                   (checks_of); each lesson note recounts its losers, $ and examples on every
                                                   build (2026 + 2021-25), month by month, and says what that teaches
    News/News <type>                               one per news event type (CPI, NFP, FOMC ...): dates, how each bot did on those
                                                   days, the losers a release hit
    Weeks/Week <YYYY-Www>                          the weekly review: each bot's trades and $, best / worst, loss causes, news,
                                                   research written, decisions added
    Decide/Decide <id>                             one per Decide card (tools/web_public/business/decisions.json)
    Rules/Rule <name>                              one per hard rule (CLAUDE.md "Hard rules")
    ZEUS Weeks, ZEUS News, ZEUS Rules, ZEUS Trades, ZEUS Dataview (the only note with ```dataview blocks; the rest reads fine
    without plugins)
Day notes (obsidian_brain.day_notes) use day_extra() here: each bot's day, the trades as links, the losers' reasons, the news.
Same rules as the brain: no clock, no network, deterministic, every [[link]] resolves, everything goes through scrub().
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    ET = dt.timezone(dt.timedelta(hours=-5))

BOTS = {"lit": "LIT", "atlas": "ATLAS", "blitz": "BLITZ"}
BOT_NOTE = {"LIT": "Zlarior (LIT)", "ATLAS": "ATLAS", "BLITZ": "BLITZ (paper)"}
BOT_ACCT = {"LIT": "zlarior", "ATLAS": "atlas"}
SPAN_WORD = {"H1": "Jan-Jun 2026", "H2": "Jul-Oct 2026", "2021-25": "2021-25", "live": "Nov 2026 on", "": "other"}
BLITZ_USD = 150.0              # BLITZ's research size (tools/win_loss_anatomy.BLITZ_RISK): $ a trade at 1R

# ------------------------------------------------------------------------------------------------ the reason codes
# the loss anatomy's own rules (tools/win_loss_anatomy.cause_of / checks_of), reused when importable (it needs numpy)
try:
    from tools.win_loss_anatomy import cause_of as _cause_of, checks_of as _checks_of  # noqa: E402
except Exception:  # noqa: BLE001
    _cause_of = _checks_of = None


def _num(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def cause_of(r: dict):
    """ONE main cause of a losing trade (None when it did not lose $): news, wick, turned, never (the anatomy's order)."""
    if _cause_of is not None:
        return _cause_of(r)
    if (_num(r.get("usd")) or 0.0) >= 0:
        return None
    if r.get("news_in"):
        return "news"
    back = r.get("post_tgt_clean") if r.get("post_tgt_clean") is not None else r.get("post_1r_clean")
    if r.get("exit") in ("STOP", "CUT") and back:
        return "wick"
    if (_num(r.get("mfe_r")) or 0.0) >= 0.5:
        return "turned"
    return "never"


def checks_of(r: dict) -> list:
    """The careful-human checklist flags of a trade (entry facts only)."""
    if _checks_of is not None:
        return _checks_of(r)
    out = []
    if r.get("d1") == "against" and r.get("h1") == "against":
        out.append("against_htf")
    x = _num(r.get("rng_atr"))
    if x is not None and x >= 1.0:
        out.append("late")
    x = _num(r.get("news_next"))
    if x is not None and 0 <= x <= 30:
        out.append("news_soon")
    x = _num(r.get("pd_tgt_r"))
    if x is not None and 0 < x < 1.0:
        out.append("no_room")
    return out


LESSON = {   # code: (note name, plain words, what to do with it)
    "never": ("Lesson never worked", "It never worked: less than +0.5R in our favour before the stop.",
              "A real stop: the idea was wrong. Normal cost of the strategy; only a filter proven on both halves may cut it."),
    "turned": ("Lesson worked then turned", "It worked (+0.5R or more), then turned and lost.",
               "The trade was right for a while. Exit ideas (break-even, partials) were tested: check Tested and rejected first."),
    "wick": ("Lesson shaken out", "Shaken out: stopped, then price went on to our target.",
             "The stop sits 1 tick beyond the sweep (hard rule). Wider stops were tested and rejected; this is the price of tight stops."),
    "news": ("Lesson news hit", "A high-impact US release came out while the trade was open.",
             "Look at the news note of that release type: is the bot worse on those days on BOTH halves of 2026 and 2021-25?"),
    "unclassified": ("Lesson not yet classified", "A live or paper loss without the minute facts (best / worst price) yet.",
                     "It gets its reason as soon as the loss anatomy rebuilds with that day (tools/win_loss_anatomy.py build)."),
}
FLAG = {     # the careful-human checklist (tools/win_loss_anatomy.CHECKS)
    "against_htf": ("Lesson against both trends", "Taken against the daily AND the 1h trend."),
    "late": ("Lesson late entry", "Late: the day had already moved 1 daily ATR or more before the entry."),
    "news_soon": ("Lesson news soon", "A high-impact release within 30 minutes after the entry."),
    "no_room": ("Lesson no room", "The prior-day high / low sat less than 1R ahead on the target side."),
}

NEWS_TYPES = [   # (type key, note title, regex over the event name, plain words)
    ("fomc-decision", "FOMC rate decision", r"fomc rate decision", "The Fed's rate decision (14:00 ET); with projections 4 times a year."),
    ("fomc-press", "FOMC press conference", r"fomc press", "The Fed chair's press conference, 30 minutes after the decision."),
    ("fomc-minutes", "FOMC minutes", r"fomc minutes", "The minutes of the last Fed meeting, 3 weeks later (14:00 ET)."),
    ("nfp", "Jobs report (NFP)", r"non-farm payrolls|\bnfp\b", "Non-Farm Payrolls, the monthly jobs report (08:30 ET, usually the first Friday)."),
    ("adp", "ADP jobs", r"\badp\b", "ADP private payrolls, two days before the jobs report."),
    ("cpi", "CPI (consumer inflation)", r"\bcpi\b", "Consumer prices (08:30 ET): the inflation number the market fears most."),
    ("ppi", "PPI (producer inflation)", r"\bppi\b", "Producer prices (08:30 ET), the day before or after CPI."),
    ("pce", "PCE inflation", r"\bpce\b|personal income", "The Fed's own inflation gauge (Core PCE), with income and spending."),
    ("claims", "Jobless claims", r"claims", "Weekly unemployment claims (Thursday 08:30 ET)."),
    ("gdp", "GDP", r"\bgdp\b", "Gross domestic product, quarterly growth."),
    ("pmi", "PMI surveys (ISM, S&P)", r"\bpmi\b|\bism\b", "Business surveys: ISM manufacturing / services, S&P Global flash PMIs (10:00 / 09:45 ET)."),
    ("sentiment", "Consumer sentiment", r"sentiment|confidence", "Consumer sentiment / confidence surveys (10:00 ET)."),
    ("jobs-other", "Other jobs data", r"jolts|employment cost|productivity", "JOLTS openings, employment cost, productivity."),
    ("other", "Other releases", r".", "Everything else on the calendar (housing, durable goods ...)."),
]


def news_type(event: str) -> str:
    e = (event or "").lower()
    for k, _, rx, _ in NEWS_TYPES:
        if re.search(rx, e):
            return k
    return "other"


def iso_week(day: str) -> str:
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def week_days(wk: str):
    y, w = int(wk[:4]), int(wk[-2:])
    mon = dt.date.fromisocalendar(y, w, 1)
    return mon.isoformat(), (mon + dt.timedelta(days=6)).isoformat()


def _ts_et(day: str, hm: str):
    try:
        d = dt.datetime.strptime(f"{day} {hm}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        return int(d.timestamp())
    except Exception:  # noqa: BLE001
        return None


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _read_csv(path) -> list:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return [r for r in csv.DictReader(fh)]
    except Exception:  # noqa: BLE001
        return []


def _pct(a, b) -> str:
    return f"{100.0 * a / b:.0f}%" if b else "-"


def _stats(tr: list) -> dict:
    u = [float(t.get("usd") or 0) for t in tr]
    g, l = sum(x for x in u if x > 0), -sum(x for x in u if x < 0)
    return {"n": len(tr), "win": _pct(sum(1 for x in u if x > 0), len(u)), "usd": sum(u),
            "avg": (sum(u) / len(u)) if u else 0.0, "pf": (f"{g / l:.2f}" if l else ("-" if not g else "all wins"))}


class More:
    """The extra layer; `b` is the obsidian_brain.Brain being built (its helpers: add, link, usd, front, callout, md_table ...)."""

    def __init__(self, b, ob):
        self.b, self.ob = b, ob
        root = b.root
        self.anat = {}
        for k, bot in BOTS.items():
            d = _read_json(os.path.join(root, "research", "anatomy", f"trades_{k}.json"), {}) or {}
            cols = d.get("cols") or []
            self.anat[bot] = [dict(zip(cols, r)) for r in (d.get("rows") or []) if isinstance(r, list)]
        ev = _read_csv(os.path.join(root, "data", "news", "events.csv")) + _read_csv(os.path.join(root, "data", "news", "ff_archive.csv"))
        seen, self.news = set(), []
        for e in ev:
            if not re.match(r"^20\d\d-\d\d-\d\d$", e.get("date") or "") or (e.get("impact") or "high").lower() != "high":
                continue
            k = (e["date"], e.get("time_et") or "", news_type(e.get("event")))
            if k in seen:
                continue
            seen.add(k)
            self.news.append({"day": e["date"], "hm": e.get("time_et") or "", "event": e.get("event") or "", "type": k[2],
                              "src": e.get("source") or "", "t": _ts_et(e["date"], e.get("time_et") or "00:00")})
        self.news.sort(key=lambda n: (n["day"], n["hm"], n["event"]))
        self.news_by_day = {}
        for n in self.news:
            self.news_by_day.setdefault(n["day"], []).append(n)
        self.bars = self._bars()
        self.trades = self._trades()
        self.by_day = {}
        for t in self.trades:
            self.by_day.setdefault(t["day"], []).append(t)
        self.all_rows = self._all_rows()

    # ================================================================ data
    def _bars(self) -> list:
        """NQ 1m bars (data/NQ_1m.csv, futures) around the live / paper trades that the loss anatomy has no row for yet."""
        an = {(r.get("bot"), int(r["entry_t"])) for bot in self.anat for r in self.anat[bot] if r.get("entry_t") is not None}
        need = [t for t in self.b.trades if t.get("t") and t.get("xt") and (str(t.get("bot")).lower(), int(t["t"])) not in an]
        if not need:
            return []
        lo, hi = min(int(t["t"]) for t in need), max(int(t["xt"]) for t in need) + 86400
        out = []
        try:
            with open(os.path.join(self.b.root, "data", "NQ_1m.csv"), encoding="utf-8") as fh:
                next(fh, None)
                for ln in fh:
                    c = ln.split(",", 4)
                    try:
                        tt = int(float(c[0]))
                    except (ValueError, IndexError):
                        continue
                    if lo <= tt <= hi:
                        out.append((tt, float(c[2]), float(c[3])))
        except OSError:
            return []
        return sorted(out)

    def _facts_from_bars(self, t: dict, hit: list):
        """The anatomy's loss facts of one live / paper trade from the 1m bars: best excursion (R), target reached after the exit."""
        try:
            e, s, tg, t0, t1 = float(t["e"]), float(t["s"]), float(t["tg"]), int(t["t"]), int(t["xt"])
        except (KeyError, TypeError, ValueError):
            return None
        risk = abs(e - s)
        if not risk or not self.bars:
            return None
        long_ = str(t.get("side") or "").upper().startswith("L")
        inside = [b for b in self.bars if t0 <= b[0] < t1]
        if not inside:
            return None
        best = max((b[1] - e) if long_ else (e - b[2]) for b in inside) / risk
        worst = max((e - b[2]) if long_ else (b[1] - e) for b in inside) / risk
        end = _ts_et(str(t.get("day")), "15:55") or (t1 + 6 * 3600)
        after = [b for b in self.bars if t1 <= b[0] <= end]
        back = any((b[1] >= tg) if long_ else (b[2] <= tg) for b in after) if after else None
        return {"exit": t.get("k"), "mfe_r": round(best, 3), "mae_r": round(worst, 3), "news_in": bool(hit), "post_tgt_clean": back,
                "post_tgt": back, "mins": round((t1 - t0) / 60), "span": "live", "_from_bars": True}

    def _trades(self) -> list:
        """Every trade that gets a note: trades.json (live, paper, backtest at the account's size) + the anatomy's 2026 rows."""
        an = {(r.get("bot"), int(r["entry_t"])): r for bot in self.anat for r in self.anat[bot] if r.get("entry_t") is not None}
        out, used = [], set()
        for t in self.b.trades:
            bot = str(t.get("bot") or "?")
            f = an.get((bot.lower(), int(t["t"]))) if t.get("t") is not None else None
            if f:
                used.add((bot.lower(), int(t["t"])))
            out.append(self._one(bot, t.get("src") or "backtest", t, f))
        for bot in ("LIT", "ATLAS", "BLITZ"):
            for r in self.anat.get(bot, []):
                if r.get("span") not in ("H1", "H2") or (bot.lower(), int(r["entry_t"])) in used:
                    continue
                t = {"day": r.get("day"), "hm": r.get("hm"), "side": str(r.get("side") or "").upper(), "k": r.get("exit"), "r": r.get("r"),
                     "usd": r.get("usd"), "t": r.get("entry_t"),
                     "xt": r.get("exit_t"), "m": r.get("member"), "acct": BOT_ACCT.get(bot), "q": r.get("qty")}
                out.append(self._one(bot, "backtest", t, r))
        out.sort(key=lambda x: (x["day"], x["hm"], x["bot"], x["src"], x["t"] or 0))
        names = {}
        for x in out:
            base = self.ob.fname(f"Trade {x['day']} {x['hm'].replace(':', '')} {x['bot']} {x['side'].lower()}"
                                 + ("" if x["src"] == "backtest" else f" {x['src']}"))
            names[base] = names.get(base, 0) + 1
            x["name"] = base if names[base] == 1 else f"{base} {names[base]}"
        return out

    def _one(self, bot, src, t, f) -> dict:
        usd = float(t.get("usd") or 0)
        x = {"bot": bot, "src": str(src), "day": str(t.get("day")), "hm": str(t.get("hm") or "00:00"), "side": str(t.get("side") or "?").upper(),
             "exit": str(t.get("k") or (f or {}).get("exit") or "?"), "r": _num(t.get("r")), "usd": usd, "q": t.get("q"),
             "acct": t.get("acct") or BOT_ACCT.get(bot), "member": t.get("m") or (f or {}).get("member") or "", "t": t.get("t"), "xt": t.get("xt"),
             "e": t.get("e"), "s": t.get("s"), "tg": t.get("tg"), "x": t.get("x"), "risk": t.get("risk") or (f or {}).get("risk_usd"), "f": f}
        x["result"] = "win" if usd > 0.5 else ("loss" if usd < -0.5 else "flat")
        x["span"] = (f or {}).get("span") or ("H1" if x["day"] <= "2026-06-30" else "H2" if x["day"] <= "2026-10-31" else "live")
        day_news = self.news_by_day.get(x["day"], [])
        x["news"] = sorted({n["type"] for n in day_news})
        hit = [n for n in day_news if n["t"] and t.get("t") and t.get("xt") and int(t["t"]) <= n["t"] <= int(t["xt"])]
        x["news_hit"] = sorted({n["type"] for n in hit})
        if not f:
            f = self._facts_from_bars(t, hit)
            x["f"] = f
        if f:
            row = dict(f)
            row["usd"] = usd
            x["cause"] = cause_of(row) if x["result"] == "loss" else None
            x["flags"] = checks_of(row)
        else:
            x["flags"] = []
            x["cause"] = None if x["result"] != "loss" else ("news" if hit else "unclassified")
        return x

    def _all_rows(self) -> list:
        """Every losing anatomy trade (2021-25 + 2026) with its reason codes: the counts of the Lessons layer."""
        out = []
        for bot, rows in self.anat.items():
            for r in rows:
                rr = dict(r)
                rr["_bot"] = bot
                rr["_cause"] = cause_of(rr)
                rr["_flags"] = checks_of(rr)
                out.append(rr)
        return out

    # ================================================================ names the brain needs before writing
    def days(self) -> set:
        return {t["day"] for t in self.trades}

    def weeks(self, days) -> list:
        return sorted({iso_week(d) for d in days})

    def trade_link(self, t, label=None):
        return self.ob.link(t["name"], label or f"{t['hm']} {t['bot']} {t['side'].lower()}")

    def member_note(self, short: str):
        for key, s in sorted((self.b.second.get("strategies") or {}).items()):
            if isinstance(s, dict) and (s.get("short") or key) == short:
                return self.ob.fname(f"ATLAS member {s.get('short') or key} ({key})")
        return None

    # ================================================================ trade notes
    def trade_notes(self):
        ob, b = self.ob, self.b
        acct_names = {a.get("key"): b.acct_note(a) for a in b.accounts}
        for t in self.trades:
            f = t["f"] or {}
            lc = LESSON.get(t["cause"]) if t["cause"] else None
            tags = ["zeus/trade", f"bot/{t['bot'].lower()}", f"src/{t['src']}", f"result/{t['result']}"]
            tags += ([f"cause/{t['cause']}"] if t["cause"] else []) + [f"flag/{x}" for x in t["flags"]]
            fm = ob.front(tags, type="trade", bot=t["bot"], src=t["src"], date=t["day"], time=t["hm"], week=iso_week(t["day"]),
                          side=t["side"], exit=t["exit"], r=t["r"] if t["r"] is not None else "", pnl=round(t["usd"], 2),
                          result=t["result"], account=t["acct"] or "", member=t["member"], cause=t["cause"] or "",
                          flags=t["flags"], session=f.get("session") or "", vix_band=f.get("vix_band") or "",
                          news=[NT_TITLE[n] for n in t["news"]], span=SPAN_WORD.get(t["span"], t["span"]))
            kind = "success" if t["result"] == "win" else "failure" if t["result"] == "loss" else "note"
            rtxt = f"{t['r']:+.2f}R" if t["r"] is not None else ""
            size = " (BLITZ research size $150 a trade)" if t["bot"] == "BLITZ" and t["src"] == "backtest" else ""
            if f.get("_from_bars"):
                size += " · reasons from the NQ 1m bars (data/NQ_1m.csv)"
            lines = [fm, f"# {t['bot']} {t['side'].lower()} · {t['day']} {t['hm']} ET", "",
                     ob.callout(kind, f"{ob.usd(t['usd'], True)} · {rtxt} · {t['exit']} · {t['src']}",
                                [f"{ob.link(BOT_NOTE.get(t['bot'], 'ZEUS Home'))} · {ob.link('Day ' + t['day'], t['day'])} · "
                                 f"{ob.link('Week ' + iso_week(t['day']), iso_week(t['day']))}{size}"]), ""]
            rows = [["Entry", t["e"]], ["Stop", t["s"]], ["Target", t["tg"]], ["Exit price", t["x"]], ["Micros", t["q"]],
                    ["Risk $", ob.usd(t["risk"]) if t["risk"] else ""], ["Minutes in", f.get("mins")],
                    ["Best (MFE)", f"{f['mfe_r']:+.2f}R" if _num(f.get("mfe_r")) is not None else ""],
                    ["Worst (MAE)", f"{-abs(f['mae_r']):+.2f}R" if _num(f.get("mae_r")) is not None else ""]]
            rows = [r for r in rows if r[1] not in (None, "")]
            if rows:
                lines += ["## The trade", "", ob.md_table(["", ""], rows), ""]
            if t["result"] == "loss":
                lines += ["## Why it lost (reason codes)", ""]
                lines += [f"- Main cause: {ob.link(lc[0], t['cause'])}: {lc[1]}"]
                lines += [f"- Checklist: {ob.link(FLAG[x][0], x)}: {FLAG[x][1]}" for x in t["flags"]] or ["- Checklist: clean (a careful human would have taken it too)"]
                lines += [""]
            elif t["flags"]:
                lines += ["## Checklist flags (it still won)", ""] + [f"- {ob.link(FLAG[x][0], x)}: {FLAG[x][1]}" for x in t["flags"]] + [""]
            ctx = [("Session", f.get("session")), ("VIX", f.get("vix_band")), ("Daily trend", f.get("d1")), ("1h trend", f.get("h1")),
                   ("ES 1h", f.get("es_h1")), ("Day's range before entry (ATR)", f.get("rng_atr"))]
            ctx = [[a, v] for a, v in ctx if v not in (None, "")]
            if ctx:
                lines += ["## Context", "", ob.md_table(["", ""], ctx), ""]
            if t["news"]:
                lines += ["## News that day", ""] + [f"- {ob.link('News ' + NT_TITLE[n], NT_TITLE[n])}" + (" (came out during the trade)" if n in t["news_hit"] else "")
                                                     for n in t["news"]] + [""]
            post = [("Target reached later that session", f.get("post_tgt")), ("Move 60 min after the exit (R)", f.get("after60_r"))]
            post = [[a, ("yes" if v else "no") if isinstance(v, bool) else v] for a, v in post if v not in (None, "")]
            if post:
                lines += ["## After the exit (hindsight, never used by a rule)", "", ob.md_table(["", ""], post), ""]
            links = [f"- Strategy: {ob.link(BOT_NOTE[t['bot']])}" if t["bot"] in BOT_NOTE else ""]
            mn = self.member_note(t["member"]) if t["bot"] == "ATLAS" and t["member"] else None
            if mn and mn in b.names:
                links.append(f"- Member: {ob.link(mn, t['member'])}")
            if t["acct"] in acct_names:
                links.append(f"- Account: {ob.link(acct_names[t['acct']])}")
            links.append(f"- {ob.link('ZEUS Trades')} · {ob.link('ZEUS Lessons')} · {ob.link('ZEUS Home')}")
            lines += ["## Links", ""] + [x for x in links if x]
            b.add("Trades", t["name"], "\n".join(lines))

    # ================================================================ the Lessons layer
    def _lesson_tables(self, rows_all, rows_2026):
        ob = self.ob
        out = []
        tab = []
        for bot in ("LIT", "ATLAS", "BLITZ"):
            lost_all = [r for r in self.all_rows if r["_bot"] == bot and (_num(r.get("usd")) or 0) < 0]
            for sp in ("H1", "H2", "2021-25"):
                L = [r for r in lost_all if r.get("span") == sp]
                M = [r for r in rows_all if r["_bot"] == bot and r.get("span") == sp]
                if not L:
                    continue
                lu = -sum(float(r["usd"]) for r in L)
                mu = -sum(float(r["usd"]) for r in M)
                tab.append([ob.link(BOT_NOTE[bot]), SPAN_WORD[sp], len(M), f"{len(M)}/{len(L)} ({_pct(len(M), len(L))})", ob.usd(-mu, True), _pct(mu, lu)])
        if tab:
            out += [ob.md_table(["Bot", "Period", "Losers", "Share of losers", "$ lost", "Share of $ lost"], tab), "",
                    "_Backtests with costs in: LIT at its live size, ATLAS at $250 a trade, BLITZ at $150 a trade (research sizes)._", ""]
        months = {}
        for t in rows_2026:
            months.setdefault(t["day"][:7], []).append(t)
        if months:
            out += ["### Month by month (2026 trades, live + paper + backtest)", "",
                    self.ob.md_table(["Month", "Losers", "$ lost", "Bots"], [[ob.link("Month " + m, m), len(v), ob.usd(sum(x["usd"] for x in v), True),
                                                                             ", ".join(sorted({x["bot"] for x in v}))] for m, v in sorted(months.items())]), ""]
        return out

    def _examples(self, rows_2026):
        ob = self.ob
        if not rows_2026:
            return ["_No 2026 trade with this code yet._"]
        newest = sorted(rows_2026, key=lambda t: (t["day"], t["hm"], t["name"]), reverse=True)[:12]
        worst = sorted(rows_2026, key=lambda t: (t["usd"], t["day"], t["name"]))[:5]
        return (["### Newest", ""] + [f"- {ob.link(t['name'], t['day'] + ' ' + t['hm'] + ' ' + t['bot'])} {ob.usd(t['usd'], True)} ({t['src']})" for t in newest]
                + ["", "### Biggest", ""] + [f"- {ob.link(t['name'], t['day'] + ' ' + t['hm'] + ' ' + t['bot'])} {ob.usd(t['usd'], True)} ({t['src']})" for t in worst] + [""])

    def lesson_notes(self):
        ob, b = self.ob, self.b
        losers26 = [t for t in self.trades if t["result"] == "loss"]
        self.lesson_summary = []
        for code, (nm, words, todo) in LESSON.items():
            rows_all = [r for r in self.all_rows if r["_cause"] == code]
            r26 = [t for t in losers26 if t["cause"] == code]
            lost = sum(t["usd"] for t in r26)
            self.lesson_summary.append((nm, code, len(rows_all), len(r26), lost))
            lines = [ob.front(["zeus/lesson", f"cause/{code}"], type="lesson", code=code, losers_all=len(rows_all), losers_2026=len(r26),
                              usd_2026=round(lost)),
                     f"# Lesson: {words.split(':')[0].rstrip('.')}", "",
                     ob.callout("tip", f"Code `{code}` · {len(r26)} losers in 2026 ({ob.usd(lost, True)}) · {len(rows_all)} in all backtests",
                                [words, f"**What it teaches:** {todo}"]), "",
                     "## How often (recounted on every build)", ""] + self._lesson_tables(rows_all, r26)
            lines += ["## Examples", ""] + self._examples(r26)
            lines += ["## Links", "", f"- {ob.link('ZEUS Lessons')} · {ob.link('ZEUS Trades')} · {ob.link('ZEUS Home')}"]
            for k, (fn, _) in FLAG.items():
                n = sum(1 for t in r26 if k in t["flags"])
                if n:
                    lines.append(f"- With the checklist flag {ob.link(fn, k)}: {n} of them")
            b.add("Lessons", nm, "\n".join(lines))
        for code, (nm, words) in FLAG.items():
            fl_all = [r for r in self.all_rows if code in r["_flags"]]
            los = [r for r in fl_all if (_num(r.get("usd")) or 0) < 0]
            r26 = [t for t in losers26 if code in t["flags"]]
            w26 = [t for t in self.trades if t["result"] == "win" and code in t["flags"]]
            verdict = []
            tab = []
            for bot in ("LIT", "ATLAS", "BLITZ"):
                worse = []
                for sp in ("H1", "H2", "2021-25"):
                    F = [r for r in fl_all if r["_bot"] == bot and r.get("span") == sp]
                    A = [r for r in self.all_rows if r["_bot"] == bot and r.get("span") == sp]
                    if not A:
                        continue
                    fs, as_ = _stats(F), _stats(A)
                    tab.append([ob.link(BOT_NOTE[bot]), SPAN_WORD[sp], fs["n"], fs["win"], ob.usd(fs["avg"], True), ob.usd(as_["avg"], True), ob.usd(fs["usd"], True)])
                    worse.append(bool(F) and fs["avg"] < as_["avg"] and fs["usd"] < 0)
                if worse and all(worse):
                    verdict.append(f"{BOT_NOTE[bot]}: these trades LOST money in every period: a filter candidate (test it first; no live change without proof).")
                elif worse:
                    verdict.append(f"{BOT_NOTE[bot]}: not consistent across periods: skipping them would also skip winners. Keep taking them.")
            self.lesson_summary.append((nm, code, len(los), len(r26), sum(t["usd"] for t in r26)))
            lines = [ob.front(["zeus/lesson", f"flag/{code}"], type="lesson", code=code, flagged_all=len(fl_all), losers_2026=len(r26),
                              winners_2026=len(w26)),
                     f"# Lesson: {words.split(':')[0].rstrip('.')}", "",
                     ob.callout("tip", f"Checklist flag `{code}` · 2026: {len(r26)} losers, {len(w26)} winners",
                                [words, "A careful human would have skipped these. Does skipping pay? The table answers it, period by period."]), "",
                     "## Would skipping pay? (every trade with the flag, losers AND winners)", "",
                     ob.md_table(["Bot", "Period", "Trades", "Won", "Avg $ with flag", "Avg $ all trades", "Net $ with flag"], tab) if tab else "_No backtest table yet._", "",
                     "## What ZEUS learned", ""] + ([f"- {v}" for v in verdict] or ["- Not enough trades yet."]) + ["",
                     "## Losers with the flag", ""] + self._examples(r26)
            if w26:
                lines += ["## Winners it would have skipped (2026, newest)", ""] + [
                    f"- {ob.link(t['name'], t['day'] + ' ' + t['hm'] + ' ' + t['bot'])} {ob.usd(t['usd'], True)}" for t in sorted(w26, key=lambda t: (t["day"], t["hm"], t["name"]), reverse=True)[:10]] + [""]
            lines += ["## Links", "", f"- {ob.link('ZEUS Lessons')} · {ob.link('ZEUS Trades')} · {ob.link('ZEUS Home')}"]
            b.add("Lessons", nm, "\n".join(lines))

    def lessons_block(self) -> list:
        ob = self.ob
        rows = [[ob.link(nm, code), n_all, n26, ob.usd(u, True)] for nm, code, n_all, n26, u in self.lesson_summary]
        return ["## Reason codes (recounted on every build)", "",
                "Every losing trade gets ONE main cause and the checklist flags; each lesson note keeps its own counts and examples.", "",
                ob.md_table(["Lesson", "Losers in all backtests", "Losers 2026", "$ 2026"], rows), ""]

    # ================================================================ news
    def news_notes(self):
        ob, b = self.ob, self.b
        days_by_type = {}
        for n in self.news:
            days_by_type.setdefault(n["type"], []).append(n)
        self.news_types = [k for k, *_ in NEWS_TYPES if k in days_by_type]
        anat_all = [(bot, r) for bot, rows in self.anat.items() for r in rows]
        hub = []
        for k, title, _, words in NEWS_TYPES:
            ev = days_by_type.get(k)
            if not ev:
                continue
            dset = {n["day"] for n in ev}
            tab = []
            for bot in ("LIT", "ATLAS", "BLITZ"):
                rows = [r for bb, r in anat_all if bb == bot]
                if not rows:
                    continue
                on = [r for r in rows if r.get("day") in dset]
                off = [r for r in rows if r.get("day") not in dset]
                if not on:
                    continue
                s1, s0 = _stats(on), _stats(off)
                tab.append([ob.link(BOT_NOTE[bot]), s1["n"], s1["win"], ob.usd(s1["avg"], True), s1["pf"], ob.usd(s0["avg"], True), s0["pf"]])
            hit = [t for t in self.trades if k in t["news_hit"]]
            ondays = [t for t in self.trades if k in t["news"]]
            hub.append([ob.link("News " + title, title), len(ev), ev[-1]["day"], len(ondays), ob.usd(sum(t["usd"] for t in ondays), True)])
            lines = [ob.front(["zeus/news", f"news/{k}"], type="news", news_type=k, releases=len(ev), last=ev[-1]["day"]),
                     f"# News: {title}", "", ob.callout("info", f"{len(ev)} high-impact releases {ev[0]['day'][:4]}-{ev[-1]['day'][:4]}", [words]), "",
                     "## How the bots did on these days (all backtests, costs in)", "",
                     ob.md_table(["Bot", "Trades on release days", "Won", "Avg $", "PF", "Avg $ other days", "PF other days"], tab) if tab else "_No backtest trade on these days._", "",
                     "## 2026 trades on these days", ""]
            lines += ([f"- {ob.link(t['name'], t['day'] + ' ' + t['hm'] + ' ' + t['bot'])} {ob.usd(t['usd'], True)}" + (" · released during the trade" if t in hit else "")
                       for t in sorted(ondays, key=lambda t: (t["day"], t["hm"], t["name"]), reverse=True)[:40]] or ["_none_"])
            lines += ["", "## Releases (newest first)", ""]
            for n in sorted(ev, key=lambda n: (n["day"], n["hm"]), reverse=True)[:80]:
                dl = ob.link("Day " + n["day"], n["day"]) if n["day"] in b.day_set else n["day"]
                lines.append(f"- {dl} {n['hm']} ET · {n['event']}")
            if len(ev) > 80:
                lines.append(f"- ... and {len(ev) - 80} older")
            lines += ["", f"{ob.link('ZEUS News')} · {ob.link('Lesson news hit')} · {ob.link('Lesson news soon')} · {ob.link('ZEUS Home')}"]
            b.add("News", "News " + title, "\n".join(lines))
        self.news_hub_rows = hub
        up = [n for n in self.news if n["day"] >= (b.days[-1] if b.days else "")][:20]
        lines = [ob.front(["zeus/news", "zeus/hub"], type="hub"), "# ZEUS News", "",
                 ob.callout("info", f"{len(self.news)} high-impact US releases, {len(hub)} types", ["From data/news/events.csv (official calendars) + the ForexFactory archive. "
                                                                                                  "Each type note shows how every bot did on those days."]), "",
                 ob.md_table(["Type", "Releases", "Last", "2026 trades those days", "$ those days"], hub), ""]
        if up:
            lines += ["## Next on the calendar", ""] + [f"- {n['day']} {n['hm']} ET · {ob.link('News ' + NT_TITLE[n['type']], n['event'])}" for n in up] + [""]
        lines += [f"Back to {ob.link('ZEUS Home')}"]
        b.add("", "ZEUS News", "\n".join(lines))

    # ================================================================ days (used by obsidian_brain.day_notes)
    def day_extra(self, d: str) -> list:
        ob = self.ob
        tr = self.by_day.get(d, [])
        out = []
        if tr:
            rows = []
            for bot in ("LIT", "ATLAS", "BLITZ"):
                for src in ("live", "paper", "backtest"):
                    x = [t for t in tr if t["bot"] == bot and t["src"] == src]
                    if x:
                        s = _stats(x)
                        rows.append([ob.link(BOT_NOTE[bot]), src, s["n"], s["win"], ob.usd(s["usd"], True)])
            out += ["## What each bot did", "", ob.md_table(["Bot", "Source", "Trades", "Won", "Net $"], rows), "",
                    "## Every trade", ""] + [f"- {self.trade_link(t)} · {t['src']} · {t['exit']} · {ob.usd(t['usd'], True)}" for t in tr] + [""]
            los = [t for t in tr if t["result"] == "loss"]
            if los:
                out += ["## Lessons of the day", ""]
                for t in los:
                    why = ob.link(LESSON[t["cause"]][0], t["cause"])
                    fl = ", ".join(ob.link(FLAG[x][0], x) for x in t["flags"])
                    out.append(f"- {self.trade_link(t)} {ob.usd(t['usd'], True)}: {why}" + (f" · flags {fl}" if fl else ""))
                out.append("")
        nw = self.news_by_day.get(d, [])
        if nw:
            out += ["## News", ""] + [f"- {n['hm']} ET · {ob.link('News ' + NT_TITLE[n['type']], n['event'])}" for n in nw] + [""]
        out += [f"Week: {ob.link('Week ' + iso_week(d), iso_week(d))}", ""]
        return out

    # ================================================================ weeks
    def week_notes(self):
        ob, b = self.ob, self.b
        wks = self.weeks(b.days)
        self.week_list = wks
        wd = {}
        for w in b.W:
            if re.match(r"^20\d\d-\d\d-\d\d$", w["date"]):
                wd.setdefault(iso_week(w["date"]), []).append(w)
        dec = {}
        for i in (b.decisions.get("items") or []):
            if isinstance(i, dict) and re.match(r"^20\d\d-\d\d-\d\d$", str(i.get("added") or "")):
                dec.setdefault(iso_week(i["added"]), []).append(i)
        for i, wk in enumerate(wks):
            a, z = week_days(wk)
            days = [d for d in b.days if a <= d <= z]
            tr = [t for d in days for t in self.by_day.get(d, [])]
            nav = [ob.link("Week " + wks[i - 1], "<- " + wks[i - 1]) if i else "", ob.link("Week " + wks[i + 1], wks[i + 1] + " ->") if i + 1 < len(wks) else ""]
            tags = ["zeus/week"] + sorted({f"bot/{t['bot'].lower()}" for t in tr})
            tot = {}
            for t in tr:
                tot.setdefault((t["bot"], t["src"]), []).append(t)
            lines = [ob.front(tags, type="week", week=wk, start=a, end=z, trades=len(tr), pnl=round(sum(t["usd"] for t in tr), 2)),
                     f"# Week {wk} ({a} to {z})", "", " · ".join(x for x in nav if x) + f" · {ob.link('ZEUS Weeks')}", ""]
            if tot:
                lines += [ob.callout("money", "The week in $", [" · ".join(f"{bt} {src}: {ob.usd(sum(t['usd'] for t in v), True)}" for (bt, src), v in sorted(tot.items()))]), ""]
                rows = []
                for (bt, src), v in sorted(tot.items()):
                    s = _stats(v)
                    best, worst = max(v, key=lambda t: (t["usd"], t["name"])), min(v, key=lambda t: (t["usd"], t["name"]))
                    rows.append([ob.link(BOT_NOTE.get(bt, "ZEUS Home"), bt), src, s["n"], s["win"], s["pf"], ob.usd(s["usd"], True),
                                 self.trade_link(best, ob.usd(best["usd"], True)), self.trade_link(worst, ob.usd(worst["usd"], True))])
                lines += ["## Each bot", "", ob.md_table(["Bot", "Source", "Trades", "Won", "PF", "Net $", "Best", "Worst"], rows), ""]
                los = [t for t in tr if t["result"] == "loss"]
                if los:
                    cc = {}
                    for t in los:
                        cc[t["cause"]] = cc.get(t["cause"], 0) + 1
                    top = sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))
                    lines += ["## Lessons of the week", "", f"{len(los)} losing trades: " + ", ".join(f"{ob.link(LESSON[c][0], c)} {n}" for c, n in top) + ".",
                              "", f"Biggest share: **{top[0][0]}**: {LESSON[top[0][0]][2]}", ""]
            else:
                lines += ["_No trades this week._", ""]
            nw = [n for d in sorted(self.news_by_day) if a <= d <= z for n in self.news_by_day[d]]
            if nw:
                lines += ["## News", ""] + [f"- {n['day']} {n['hm']} ET · {ob.link('News ' + NT_TITLE[n['type']], n['event'])}" for n in nw] + [""]
            if wd.get(wk):
                lines += ["## Research written", ""] + [f"- {ob.link(w['name'], w['short'])} ({w['verdict']})" for w in sorted(wd[wk], key=lambda w: (w["date"], w["stem"]))] + [""]
            if dec.get(wk):
                lines += ["## Decide cards added", ""] + [f"- {ob.link(self.decide_name(x), ob.oneline(x.get('question'), 120))} ({x.get('status') or 'open'})"
                                                          for x in dec[wk] if x.get("id")] + [""]
            lines += ["## Days", "", " · ".join(ob.link("Day " + d, d) for d in days) or "_none_"]
            b.add("Weeks", "Week " + wk, "\n".join(lines))
        rows = []
        for wk in reversed(wks):
            a, z = week_days(wk)
            tr = [t for d in b.days if a <= d <= z for t in self.by_day.get(d, [])]
            liv = [t for t in tr if t["src"] != "backtest"]
            rows.append([ob.link("Week " + wk, wk), len(tr), ob.usd(sum(t["usd"] for t in tr), True), len(liv), ob.usd(sum(t["usd"] for t in liv), True)])
        b.add("", "ZEUS Weeks", "\n".join([ob.front(["zeus/hub", "zeus/week"], type="hub"), "# ZEUS Weeks", "",
                                           ob.callout("abstract", f"{len(wks)} weekly reviews", ["Each week: every bot's trades and $, best and worst trade, the losses' "
                                                                                                "reasons, the news, the research and the decisions."]), "",
                                           ob.md_table(["Week", "Trades", "Net $", "Live + paper", "Live + paper $"], rows), "", f"Back to {ob.link('ZEUS Home')}"]))

    # ================================================================ Decide cards
    def decide_name(self, i) -> str:
        return self.ob.fname("Decide " + str(i.get("id")))

    def decide_notes(self):
        ob, b = self.ob, self.b
        for i in (b.decisions.get("items") or []):
            if not isinstance(i, dict) or not i.get("id"):
                continue
            st = str(i.get("status") or "open")
            src = os.path.basename(str(i.get("source") or ""))[:-3] if str(i.get("source") or "").endswith(".md") else ""
            txt = " ".join(str(i.get(k) or "") for k in ("question", "why", "impact", "applies"))
            ss = self.ob.strat_of(txt)
            accts = [b.acct_note(a) for a in b.accounts if re.search(r"\b" + re.escape(str(a.get("name"))) + r"\b", txt)]
            kind = {"open": "question", "yes": "success", "no": "failure"}.get(st, "note")
            rows = [["Status", st], ["Added", i.get("added")], ["$ a month", ob.usd(i.get("usd_month"), True) if i.get("usd_month") is not None else ""],
                    ["Claude recommends", i.get("recommend")], ["Changes", i.get("applies")]]
            by = i.get("usd_month_by") or {}
            if isinstance(by, dict) and by:
                rows.append(["$ a month by market", " · ".join(f"{k.replace('_', '-').replace('y2021-25', '2021-25')}: {ob.usd(v, True)}" for k, v in sorted(by.items()))])
            lines = [ob.front(["zeus/decide", f"decide/{tagify(st)}"], type="decide", id=i.get("id"), status=st, added=i.get("added"),
                              usd_month=i.get("usd_month") if i.get("usd_month") is not None else "", recommend=i.get("recommend") or ""),
                     f"# Decide: {ob.unlink_md(ob.oneline(i.get('question'), 200))}", "",
                     ob.callout(kind, f"{st.upper()} · {ob.usd(i.get('usd_month'), True) + ' a month' if i.get('usd_month') is not None else 'no $ estimate'}",
                                ["Answer it on the Decide card (Business app): YES / NO / LATER."]), "",
                     ob.md_table(["", ""], [[a, ob.unlink_md(str(v))] for a, v in rows if v not in (None, "")]), ""]
            for k, lab in (("why", "Why"), ("impact", "Impact"), ("risk", "Risk"), ("recommend_why", "Why Claude recommends that")):
                if i.get(k):
                    lines += [f"## {lab}", "", ob.unlink_md(str(i[k])), ""]
            links = []
            if src in b.Wby:
                links.append(f"- Write-up: {b.wl(src)}")
            links += [f"- Strategy: {ob.link(ob.STRAT[k][0])}" for k in ss] + [f"- Account: {ob.link(a)}" for a in accts]
            links.append(f"- {ob.link('ZEUS Decisions')} · {ob.link('ZEUS Home')}")
            b.add("Decide", self.decide_name(i), "\n".join(lines + ["## Links", ""] + links))

    # ================================================================ hard rules
    def rules(self) -> list:
        md = self.ob.read_text(os.path.join(self.b.root, "CLAUDE.md"))
        sec = self.ob.section(md, r"^Hard rules")
        items, cur = [], None
        for ln in sec.splitlines():
            if ln.startswith("- "):
                cur = [ln[2:].strip()]
                items.append(cur)
            elif cur is not None and ln.startswith((" ", "\t")) and ln.strip():
                cur.append(ln.strip())
        out = []
        for it in items:
            text = " ".join(it)
            m = re.match(r"\*\*(.+?)\*\*:?\s*", text)
            title = (m.group(1) if m else re.split(r"[:(.;]", text)[0]).strip(" :")
            out.append({"title": self.ob.oneline(title, 60), "text": text})
        return out

    RULE_LINKS = [(r"stop|target|sweep", ["Zlarior (LIT)", "ATLAS", "Lesson shaken out"]),
                  (r"strategy change|tested and rejected|proof", ["ZEUS Lessons", "Zlarior (LIT)", "ATLAS"]),
                  (r"prop price|builder 50k|25k", ["ZEUS Decisions"]),
                  (r"paper only|live", ["ZEUS State"]),
                  (r"futures data|yahoo|cfd", ["ZEUS News"])]

    def rule_notes(self):
        ob, b = self.ob, self.b
        rs = self.rules()
        self.rule_names = []
        for r in rs:
            nm = ob.fname("Rule " + r["title"])
            self.rule_names.append((nm, r))
            rel = []
            for rx, targets in self.RULE_LINKS:
                if re.search(rx, r["text"].lower()):
                    rel += [x for x in targets if x not in rel]
            lines = [ob.front(["zeus/rule"], type="rule"), f"# Hard rule: {r['title']}", "",
                     ob.callout("warning", "Never broken", [ob.unlink_md(r["text"])]), "",
                     "## Touches", ""] + [f"- {ob.link(x)}" for x in rel] + ["", f"{ob.link('ZEUS Rules')} · {ob.link('ZEUS Home')}"]
            b.add("Rules", nm, "\n".join(lines))
        b.add("", "ZEUS Rules", "\n".join([ob.front(["zeus/hub", "zeus/rule"], type="hub"), "# ZEUS Rules", "",
                                           ob.callout("warning", f"{len(rs)} hard rules", ["From CLAUDE.md: every helper reads them before any work."]), ""]
                                          + [f"- {ob.link(nm, r['title'])}: {ob.unlink_md(ob.oneline(r['text'], 180))}" for nm, r in self.rule_names]
                                          + ["", f"Back to {ob.link('ZEUS Home')}"]))

    # ================================================================ trades hub + dataview
    def trades_hub(self):
        ob, b = self.ob, self.b
        rows = []
        for bot in ("LIT", "ATLAS", "BLITZ"):
            for src in ("live", "paper", "backtest"):
                x = [t for t in self.trades if t["bot"] == bot and t["src"] == src]
                if x:
                    s = _stats(x)
                    rows.append([ob.link(BOT_NOTE[bot]), src, s["n"], s["win"], s["pf"], ob.usd(s["usd"], True)])
        real = sorted([t for t in self.trades if t["src"] != "backtest"], key=lambda t: (t["day"], t["hm"], t["name"]), reverse=True)
        lines = [ob.front(["zeus/hub", "zeus/trade"], type="hub"), "# ZEUS Trades", "",
                 ob.callout("money", f"{len(self.trades)} trade notes", ["Every published trade (live, paper, backtest at the account's size) + the 2026 "
                                                                         "backtests of the loss anatomy. Losers carry reason codes (see the lessons)."]), "",
                 ob.md_table(["Bot", "Source", "Trades", "Won", "PF", "Net $"], rows), "",
                 "## Live and paper (newest first)", ""] + ([f"- {self.trade_link(t, t['day'] + ' ' + t['hm'] + ' ' + t['bot'])} · {t['src']} · {t['exit']} · {ob.usd(t['usd'], True)}"
                                                             for t in real] or ["_none yet_"])
        lines += ["", "## By week", "", " · ".join(ob.link("Week " + w, w) for w in reversed(self.week_list)), "", f"Back to {ob.link('ZEUS Home')}"]
        b.add("", "ZEUS Trades", "\n".join(lines))

    def dataview(self):
        ob, b = self.ob, self.b
        q = [("Live and paper trades", 'TABLE date, time, bot, src, exit, r, pnl, cause\nFROM "{f}/Trades"\nWHERE src != "backtest"\nSORT date DESC, time DESC'),
             ("Losers by reason code", 'TABLE length(rows) AS losers, sum(rows.pnl) AS dollars\nFROM "{f}/Trades"\nWHERE result = "loss"\nGROUP BY cause\nSORT sum(rows.pnl) ASC'),
             ("Each bot by week", 'TABLE sum(rows.pnl) AS dollars, length(rows) AS trades\nFROM "{f}/Trades"\nGROUP BY week + " " + bot AS wb\nSORT wb DESC\nLIMIT 40'),
             ("Open Decide cards", 'TABLE usd_month AS "$ a month", recommend, added\nFROM "{f}/Decide"\nWHERE status = "open"'),
             ("Weeks", 'TABLE trades, pnl\nFROM "{f}/Weeks"\nSORT week DESC'),
             ("Research rejected lately", 'TABLE date, status\nFROM "{f}/Research"\nWHERE contains(file.tags, "verdict/rejected")\nSORT date DESC\nLIMIT 25')]
        lines = [ob.front(["zeus/hub", "zeus/dataview"], type="hub"), "# ZEUS Dataview", "",
                 ob.callout("info", "Only for the Dataview plugin", ["Every note has front matter (type, bot, date, pnl, cause, week ...). With the free "
                                                                     "Dataview community plugin on, these tables fill themselves. Without it, use the hub notes: "
                                                                     f"{ob.link('ZEUS Trades')}, {ob.link('ZEUS Weeks')}, {ob.link('ZEUS Lessons')}."]), ""]
        for title, body in q:
            lines += [f"## {title}", "", "```dataview", body.replace("{f}", "ZEUS Brain"), "```", ""]
        lines += ["_Inside the PC vault the folder is OLYMPUS/ZEUS Brain: change the FROM lines there if a table stays empty._", "", f"Back to {ob.link('ZEUS Home')}"]
        b.add("", "ZEUS Dataview", "\n".join(lines))

    # ================================================================ home additions
    def home_block(self) -> list:
        ob, b = self.ob, self.b
        out = []
        if self.week_list:
            wk = self.week_list[-1]
            a, z = week_days(wk)
            tr = [t for d in b.days if a <= d <= z for t in self.by_day.get(d, [])]
            out += ["## This week", "", ob.callout("money", f"{ob.link('Week ' + wk, wk)}: {len(tr)} trades · {ob.usd(sum(t['usd'] for t in tr), True)}",
                                                   [" · ".join(ob.link("Week " + w, w) for w in reversed(self.week_list[-8:]))]), ""]
        top = sorted([x for x in self.lesson_summary if x[1] in LESSON], key=lambda x: (x[4], x[0]))[:5]
        out += ["## What the losses teach", ""] + [f"- {ob.link(nm, code)}: {n26} losers in 2026, {ob.usd(u, True)}" for nm, code, _, n26, u in top] + [""]
        out += ["## More hubs", "",
                f"- {ob.link('ZEUS Trades')}: {len(self.trades)} trade notes · {ob.link('ZEUS Weeks')}: {len(self.week_list)} weekly reviews",
                f"- {ob.link('ZEUS News')}: {len(self.news)} releases, {len(self.news_types)} types · {ob.link('ZEUS Rules')}: {len(self.rule_names)} hard rules",
                f"- {ob.link('ZEUS Dataview')}: live tables if you turn on the Dataview plugin (optional)", ""]
        return out


def tagify(s):
    return re.sub(r"[^a-z0-9_/-]+", "-", str(s or "other").lower()).strip("-") or "other"


NT_TITLE = {k: t for k, t, _, _ in NEWS_TYPES}
