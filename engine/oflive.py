"""Order flow, live and daily (day-ofmax 2026-11-25; READ-ONLY, PAPER: it never trades, sizes, arms or routes anything).

1. live_read(): the last minutes of the live tick file LE_TickRec writes (Documents\\NinjaTrader 8\\le_ticks\\NQ_<ET day>.csv,
   flushed every second) -> delta of the last 5 / 15 minutes and, at LIT's ARMED sweep level, the zone read of OF1
   (research/orderflow/PREREG_ticks.md: volume and delta within 8 ticks of the level; "absorbed" = delta against the trade and
   >= 20 % of the zone volume, i.e. aggressive orders hit into the extreme and it held). engine/brain_feed.of_bot shows it in the
   Brain's Order Flow room. Reads only the file's tail (<= TAIL_BYTES): cheap every 15 minutes, any time of day.
2. journal_kick(): once a day, after the close (engine/tickrec.autopilot), one line per finished day into
   data/orderflow_journal.jsonl: what order flow said at each LIT trade's sweep (from the day's order-flow summary,
   engine/ofsum) vs what the trade did, and a running "flow right N of M". So the owner sees it learn daily.
Standard library only (no pandas, no engine.tickrec, nothing that can trade): brain_feed / pc_report may import it.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.25
ZONE_TICKS, ABS_SHARE, MIN_ZONE = 8, 0.20, 50
TAIL_BYTES = 4_000_000
JOURNAL = os.path.join(ROOT, "data", "orderflow_journal.jsonl")
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    ET = None


def nt_dir() -> str | None:
    o = os.environ.get("OLYMPUS_NT_DIR")
    if o:
        return o
    home = os.path.expanduser("~")
    for p in (os.path.join(home, "Documents", "NinjaTrader 8"), os.path.join(home, "OneDrive", "Documents", "NinjaTrader 8")):
        if os.path.isdir(p):
            return p
    return None


def _et_day(t: float) -> str:
    return dt.datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d") if ET else time.strftime("%Y-%m-%d", time.gmtime(t))


def tail_ticks(path: str, max_bytes: int = TAIL_BYTES) -> list:
    """[(t_ms, price, size, bid, ask)] from the end of one live LE_TickRec CSV (a torn first / last line is dropped)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            raw = fh.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for ln in raw.splitlines():
        p = ln.split(",")
        if len(p) != 5 or p[0] == "t_ms":
            continue
        try:
            out.append((int(p[0]), float(p[1]), int(float(p[2])), float(p[3] or 0), float(p[4] or 0)))
        except ValueError:
            continue
    return out


def sides(ticks: list) -> list:
    """Aggressor side per trade: quote rule (price >= ask buy, <= bid sell), else the tick rule (as engine/tickrec.classify)."""
    out, last_p, last_s = [], None, 0
    for _t, p, _v, b, a in ticks:
        s = 0
        if b > 0 and a > 0 and a >= b:
            s = 1 if p >= a else (-1 if p <= b else 0)
        if s == 0 and last_p is not None:
            s = 1 if p > last_p else (-1 if p < last_p else last_s)
        out.append(s)
        last_p, last_s = p, s or last_s
    return out


def zone_read(rows, level: float, d: int) -> dict:
    """OF1 at a level: rows [(price, size, side)] -> {"vz", "dz", "read"}: absorbed / not absorbed / not tested yet."""
    vz = dz = 0
    for p, v, s in rows:
        if abs(p - level) <= ZONE_TICKS * TICK:
            vz += v
            dz += v * s
    if vz < MIN_ZONE:
        read = "not tested yet"
    elif dz * d < 0 and abs(dz) >= ABS_SHARE * vz:
        read = "absorbed"
    else:
        read = "not absorbed"
    return {"vz": int(vz), "dz": int(dz), "read": read}


def live_read(level: float | None = None, d: int = 0, now: float | None = None, nd: str | None = None) -> dict | None:
    """The live order-flow read for the Brain (None when there is no live tick file for today)."""
    nd = nd or nt_dir()
    if not nd:
        return None
    now = now or time.time()
    p = os.path.join(nd, "le_ticks", f"NQ_{_et_day(now)}.csv")
    tk = tail_ticks(p)
    if not tk:
        return None
    sd = sides(tk)
    end = tk[-1][0]
    out = {"t": int(end // 1000), "age_s": int(max(0, now - end / 1000))}
    for mins in (5, 15):
        a = end - mins * 60_000
        v = sum(x[2] for x in tk if x[0] > a)
        dl = sum(x[2] * s for x, s in zip(tk, sd) if x[0] > a)
        out[f"v{mins}"], out[f"d{mins}"] = int(v), int(dl)
    if level is not None and d in (1, -1):
        a = end - 30 * 60_000
        out["level"] = {"px": level, "d": d, **zone_read([(x[1], x[2], s) for x, s in zip(tk, sd) if x[0] > a], level, d)}
    return out


# ------------------------------------------------------------------------------------------------ daily journal
def _read_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _jl(p) -> list:
    out = []
    try:
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                    if isinstance(r, dict):
                        out.append(r)
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def lit_trades_of(day: str, root: str = ROOT) -> list:
    """Zlarior's (LIT) entries of one ET day with their result: [{"t", "d", "stop", "entry", "pnl"}] from the bot's own ledger
    (data/live_state.json) and the data pipe's archive (logs/datapipe/ledger_archive.jsonl, kept 15-minute copies)."""
    rows = list((_read_json(os.path.join(root, "data", "live_state.json"), {}) or {}).get("ledger") or [])
    rows += [r for r in _jl(os.path.join(root, "logs", "datapipe", "ledger_archive.jsonl")) if r.get("bot") in (None, "zlarior")
             and str(r.get("src") or "main") == "main"]
    ent, pnl = {}, {}
    for r in rows:
        try:
            et_ = int(r.get("entry_t") or 0)
        except (TypeError, ValueError):
            continue
        if not et_ or _et_day(et_) != day:
            continue
        if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok", True) and r.get("stop"):
            ent.setdefault(et_, {"t": et_, "d": 1 if r["side"] == "buy" else -1, "stop": float(r["stop"]),
                                 "entry": float(r.get("entry") or 0)})
        elif r.get("side") == "exit" and r.get("pnl") is not None:
            pnl.setdefault(et_, {})[int(r.get("t") or 0)] = float(r["pnl"])
    return [{**e, "pnl": round(sum((pnl.get(k) or {}).values()), 2) if k in pnl else None} for k, e in sorted(ent.items())]


def _summary(day: str, root: str) -> dict | None:
    """The day's order-flow summary (engine/ofsum files under logs/datapipe/days/<day>/of) as plain lists."""
    d = os.path.join(root, "logs", "datapipe", "days", day, "of")
    try:
        with gzip.open(os.path.join(d, "NQ_bars5m.csv.gz"), "rt") as fh:
            bars = [{k: float(v) if v not in ("", None) else 0.0 for k, v in r.items()} for r in csv.DictReader(fh)]
        with gzip.open(os.path.join(d, "NQ_fp5m.csv.gz"), "rt") as fh:
            fp = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
    except (OSError, ValueError):
        return None
    return {"bars": bars, "fp": fp}


def said_at(S: dict, t_entry: int, d: int, stop: float) -> dict:
    """What order flow said at a trade's sweep: the bar of the 6 before entry with the extreme (low for a long), OF1's zone
    read at that extreme, and the 15-minute delta before entry."""
    bars = S["bars"]
    idx = [i for i, b in enumerate(bars) if t_entry - 1800 <= b["t"] < t_entry]
    if not idx:
        return {"read": "no data"}
    j = min(idx, key=lambda i: bars[i]["l"]) if d == 1 else max(idx, key=lambda i: bars[i]["h"])
    ext = bars[j]["l"] if d == 1 else bars[j]["h"]
    rows = [(bars[j]["l"] + f["k"] * TICK, f["a"] + f["b"] + f["u"], 0) for f in S["fp"] if int(f["bar"]) == j]
    vz = sum(v for p, v, _ in rows if abs(p - ext) <= ZONE_TICKS * TICK)
    dz = sum(f["a"] - f["b"] for f in S["fp"] if int(f["bar"]) == j and abs(bars[j]["l"] + f["k"] * TICK - ext) <= ZONE_TICKS * TICK)
    read = "not tested" if vz <= 0 else ("absorbed" if dz * d < 0 and abs(dz) >= ABS_SHARE * vz else "not absorbed")
    d15 = sum(b["buy"] - b["sell"] for b in bars if t_entry - 900 <= b["t"] < t_entry)
    return {"read": read, "vz": int(vz), "dz": int(dz), "d15": int(d15), "ext": ext}


def journal_day(day: str, root: str = ROOT) -> dict | None:
    S = _summary(day, root)
    if S is None:
        return None
    trades = lit_trades_of(day, root)
    rec = {"day": day, "trades": []}
    for tr in trades:
        s = said_at(S, tr["t"], tr["d"], tr["stop"])
        agree = None
        if tr["pnl"] is not None and s["read"] in ("absorbed", "not absorbed"):
            agree = (s["read"] == "absorbed") == (tr["pnl"] > 0)
        rec["trades"].append({"t": tr["t"], "d": tr["d"], "pnl": tr["pnl"], **s, "agree": agree})
    rth = [b for b in S["bars"] if 570 <= _mod(b["t"]) < 960]
    if rth:
        rec["rth_delta"] = int(sum(b["buy"] - b["sell"] for b in rth))
        rec["rth_move"] = round(rth[-1]["c"] - rth[0]["o"], 2)
        rec["flow_matched_price"] = (rec["rth_delta"] > 0) == (rec["rth_move"] > 0) if rec["rth_move"] else None
    rec["line"] = _line(rec)
    return rec


def _mod(t: float) -> int:
    x = dt.datetime.fromtimestamp(t, ET) if ET else dt.datetime.utcfromtimestamp(t)
    return x.hour * 60 + x.minute


def _line(rec: dict) -> str:
    md = dt.date.fromisoformat(rec["day"]).strftime("%b %d")
    if rec["trades"]:
        bits = []
        for t in rec["trades"]:
            hm = dt.datetime.fromtimestamp(t["t"], ET).strftime("%H:%M") if ET else ""
            res = "open" if t["pnl"] is None else (f"won ${t['pnl']:,.0f}" if t["pnl"] > 0 else f"lost ${-t['pnl']:,.0f}")
            verdict = "" if t["agree"] is None else (" (flow was right)" if t["agree"] else " (flow was wrong)")
            bits.append(f"LIT {'long' if t['d'] == 1 else 'short'} {hm}: flow said {t['read'].upper()} -> {res}{verdict}")
        return f"{md}: " + "; ".join(bits)
    if "rth_delta" in rec:
        who = "buyers" if rec["rth_delta"] > 0 else "sellers"
        m = "agreed with" if rec.get("flow_matched_price") else "did not match"
        return f"{md}: no LIT trade. Day delta {rec['rth_delta']:+,} ({who}), price {rec['rth_move']:+.0f} pts: flow {m} price"
    return f"{md}: no LIT trade"


def journal_kick(root: str = ROOT, days_back: int = 5, now: float | None = None, journal: str | None = None) -> dict:
    """Append the finished ET days (last days_back) that have a summary and no journal line yet. Never raises."""
    try:
        now = now or time.time()
        jp = journal or JOURNAL
        have = {r.get("day") for r in _jl(jp)}
        today = _et_day(now)
        base = os.path.join(root, "logs", "datapipe", "days")
        try:
            cands = sorted(d for d in os.listdir(base) if len(d) == 10 and d < today)[-days_back:]
        except OSError:
            cands = []
        new = []
        for d in cands:
            if d in have:
                continue
            rec = journal_day(d, root)
            if rec:
                new.append(rec)
        if new:
            os.makedirs(os.path.dirname(jp), exist_ok=True)
            with open(jp, "a", encoding="utf-8") as fh:
                for r in new:
                    fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        return {"added": [r["day"] for r in new]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {str(e)[:80]}"}


def journal_tally(path: str | None = None) -> dict:
    rows = _jl(path or JOURNAL)
    ag = [t["agree"] for r in rows for t in r.get("trades") or [] if t.get("agree") is not None]
    return {"days": len(rows), "right": sum(1 for a in ag if a), "judged": len(ag),
            "last": rows[-1].get("line") if rows else None}


# ------------------------------------------------------------------------------------------------ big-ofpipe 2026-11-26
PAPER_STATE = os.path.join(ROOT, "data", "of_paper.json")
OFP_MAX = 300
_READ_CODE = {True: "a", False: "n"}


def paper_tiny(root: str = ROOT, now: float | None = None) -> dict | None:
    """The Order Flow pillar's PAPER bot (engine/of_paper.py) for the 15-minute status ext post, <= OFP_MAX bytes (stdlib only):
    {"d": day, "t": last run, "ln": plain line, "n": paper trades taken, "o": open, "R": day R, "lv": [[level, price, a|n|u]],
     "lb": [[hh:mm, take|skip|no read, won|lost|open]]}. PAPER: nothing here is a real trade. Today's state only, else None."""
    try:
        S = _read_json(os.path.join(root, "data", "of_paper.json"), None)
        now = now or time.time()
        if not isinstance(S, dict) or S.get("day") != _et_day(now) or not S.get("paper"):
            return None
        td = S.get("today") or {}
        rows = [r for r in S.get("rows") or [] if r.get("lane") == "A" and r.get("day") == S["day"]]
        lv = []
        for L in S.get("levels") or []:
            hit = next((r for r in rows if r.get("level") == L.get("name")), None)
            lv.append([str(L.get("name"))[:4], L.get("px"), _READ_CODE.get(hit.get("absorbed"), "n") if hit else "u"])
        hm = lambda t: dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M") if ET else ""
        lb = [[hm(r["t"]), r.get("decision"), None if r.get("pnl") is None else ("won" if r["pnl"] > 0 else "lost")] for r in S.get("lit") or []]
        out = {"p": 1, "d": S["day"], "t": S.get("t"), "n": td.get("taken"), "o": td.get("open"), "R": td.get("R"), "lv": lv[:8], "lb": lb[:4],
               "ln": str(S.get("line") or "")[:160]}
        while len(json.dumps(out, separators=(",", ":"))) > OFP_MAX and (out["ln"] or out["lb"] or out["lv"]):
            if out["ln"]:
                out["ln"] = out["ln"][: max(0, len(out["ln"]) - 40)]
            elif out["lb"]:
                out["lb"].pop()
            else:
                out["lv"].pop()
        return out
    except Exception:  # noqa: BLE001
        return None


OFL_MAX = 400
_SIM_RX = __import__("re").compile(r"^(Sim|Playback)\d+$")


def _short_why(w) -> str | None:
    """A refusal in a few plain words for the room (day-ofready2)."""
    w = str(w or "")
    if not w:
        return None
    for key, say in (("day cap", "skipped: day cap (1 a day)"), ("news blackout", "skipped: news"), ("not chased", "skipped: late"),
                     ("entry cut", "skipped: after the entry cut"), ("kill switch", "skipped: kill switch"),
                     ("hedging", "skipped: another account holds the other side"), ("one position", "skipped: account already in a trade"),
                     ("lane is OFF", "skipped: lane off"), ("already has an open trade", "skipped: lane already in a trade"),
                     ("through the stop", "skipped: price already past the stop"), ("stopped before entry", "no fill: the stop traded first"),
                     ("must exist in NinjaTrader", "skipped: Sim account missing in NinjaTrader"), ("skip: 1 micro", "skipped: stop too wide for the $ risk"),
                     ("daily loss", "skipped: daily loss limit"), ("floor", "skipped: max-loss floor"),
                     ("target", "target"), ("stop", "stop"), ("flat", "flat time")):
        if key in w:
            return say
    # red team #38: an unmatched refusal goes into the ntfy status ext and the PUBLIC NQ_lane.json; firm / account texts can name
    # another account ("hedging: <account> holds ...", "account '<id>' is not ..."): no quoted name, no id-like run, ever
    try:
        from .notify import mask_ids
        w = mask_ids(w)
    except Exception:  # noqa: BLE001
        pass
    w = __import__("re").sub(r"'[^']*'|\"[^\"]*\"", "<account>", w)
    w = __import__("re").sub(r"[\w-]*\d{5,}[\w-]*|\.\.\.\d+", "<id>", w)
    return w[:40]


def lane_tiny(root: str = ROOT, now: float | None = None) -> dict | None:
    """day-ofready2: the order-flow LANE on the practice account (engine/of_lane.py: data/of_lane.json + data/of_lane_state.json) for
    the 15-minute status ext block "ofl" (day-ofroom2's control room reads exactly these keys), <= OFL_MAX bytes, stdlib only:
    {"on", "account" (a Sim name only), "cap", "used", "day", "trades": [{"t", "dir", "qty", "status", "pnl", "why"}] (today's,
    newest 4)}. pnl = simulation $ after costs (practice money). None when the lane has never been set up. Never raises."""
    try:
        cfg = _read_json(os.path.join(root, "data", "of_lane.json"), None)
        S = _read_json(os.path.join(root, "data", "of_lane_state.json"), None)
        if not isinstance(cfg, dict) and not isinstance(S, dict):
            return None
        cfg, S = cfg if isinstance(cfg, dict) else {}, S if isinstance(S, dict) else {}
        now = now or time.time()
        today = _et_day(now)
        acct = str(cfg.get("account") or "Sim102").strip()
        acct = acct if _SIM_RX.match(acct) else "not Sim"
        cap = cfg.get("max_per_day", 1)
        cap = cap if isinstance(cap, int) and not isinstance(cap, bool) and cap >= 1 else 1
        tr = [t for t in S.get("trades") or [] if isinstance(t, dict) and t.get("day") == today and S.get("day") == today]
        slots = {int(t["entry_t"]) // 300 for t in tr if t.get("entry_t") and (t.get("filled") or t.get("status") in ("sending", "open", "fallback", "unknown"))}
        hm = lambda t: dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M") if (ET and t) else None   # noqa: E731
        rows = [{"t": hm(t.get("t_sig") or t.get("entry_t")), "dir": "long" if t.get("d") == 1 else "short", "qty": t.get("qty"),
                 "status": "open" if t.get("status") == "fallback" else t.get("status"),
                 "pnl": None if t.get("pnl") is None else round(float(t["pnl"]), 2),
                 "why": _short_why(t.get("why")) if t.get("status") != "open" else None} for t in tr][-4:]
        out = {"on": cfg.get("on") is True, "account": acct, "cap": cap, "used": len(slots), "day": today, "trades": rows}
        while len(json.dumps(out, separators=(",", ":"))) > OFL_MAX and out["trades"]:
            out["trades"].pop(0)
        return out
    except Exception:  # noqa: BLE001
        return None


def setup_of(setup: dict, now: float | None = None, nd: str | None = None) -> dict:
    """The OF input field for a LIT setup (for the live setup score, big-setupscore): OF1's read at the setup's sweep extreme from
    the live tick file. setup = {"side": "LONG"|"SHORT", "plan": {"stop": price}} (the Brain's setup row; the plan's stop is 1 tick
    beyond the sweep extreme). -> {"of1": "absorbed"|"not absorbed"|"not tested yet"|None, "of_vz", "of_dz", "of_d15", "of_age_s",
    "of_level"}. of1 None = no live tick file / stale (> 15 min) / no stop: score it as 'no OF read', never as a no.
    PAPER / read only. Research basis: research/orderflow/LITERATURE.md (#2 sweep context), PREREG_ticks OF1 constants."""
    out = {"of1": None, "of_vz": None, "of_dz": None, "of_d15": None, "of_age_s": None, "of_level": None}
    try:
        side = str((setup or {}).get("side", "")).upper()
        d = 1 if side.startswith("L") else -1 if side.startswith("S") else 0
        st = ((setup or {}).get("plan") or {}).get("stop")
        if not d or st is None:
            return out
        lvl = float(st) + d * TICK
        r = live_read(lvl, d, now=now, nd=nd)
        if not r or r.get("age_s", 9999) > 900:
            return out
        lv = r.get("level") or {}
        out.update(of1=lv.get("read"), of_vz=lv.get("vz"), of_dz=lv.get("dz"), of_d15=r.get("d15"), of_age_s=r.get("age_s"), of_level=lvl)
        return out
    except Exception:  # noqa: BLE001
        return out


def setup_of_hist(day: str, t_entry: int, d: int, stop: float, root: str = ROOT) -> dict:
    """The same field for a PAST setup from the day's order-flow summary (said_at), for backtesting the score."""
    S = _summary(day, root)
    if S is None:
        return {"of1": None}
    s = said_at(S, int(t_entry), int(d), float(stop))
    rd = s.get("read")
    return {"of1": rd if rd in ("absorbed", "not absorbed", "not tested") else None, "of_vz": s.get("vz"), "of_dz": s.get("dz"),
            "of_d15": s.get("d15")}
