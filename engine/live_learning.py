"""Live learning (owner order 2026-10-25: Zlarior and ATLAS "should learn, like a human trader without emotion").

What a disciplined trader learns from real trading, without ever touching the setup: how much the fills really cost, how far
the live result sits from the backtest, and which size knobs the evidence points at. Research is clear that letting the bot
re-tune its own entries / filters / size hurts (research/writeups/lit-learning-loop.md: OBSERVE mode; hq-habits.md: the weekly
self-check lost money), so this module has exactly ONE automatic effect, and it can only make sizing more conservative:

1. EXECUTION LEARNING (auto-applied, conservative only; switch live_model.json lit_sizing "learn_costs", default OFF)
   From the real fills (engine/fill_audit.live_trades: the PC ledger archive, NinjaTrader legs and outgoing\\ order states),
   per bot (Zlarior = LIT, ATLAS = the routed second strategies; ATLAS v2 is a paper shadow and has no fills):
     entry slippage    fill vs the model's entry price, ticks (+ = worse for us)
     exit slippage     a stop / BE fill vs the stop price, a target fill vs the target, ticks (+ = worse)
     latency           signal (1m CISD close / bar open) -> routed, and -> filled, seconds
     commission        $ a micro actually booked: $1.90 + the real balance's shortfall vs the fills' P&L
                       (engine/broker_balance.py's daily real cash, when present), clipped to [$1.90, $4.00]
   Learned cost reserve (the last WINDOW broker fills, at least MIN_OBS observations, else exactly today's assumption):
     reserve_ticks = min(4, max(1, ceil(p75 of the adverse slippage)))   (adverse = max(0, slip) of every entry + stop exit)
     comm          = min(4.00, max(1.90, median commission a micro))
   engine/sizing.cost_reserve prices one micro's full stop-out as (stop + reserve_ticks x 0.25) x $2 + comm instead of
   (stop + 1 tick) x $2 + $1.90: the micros shrink so the $ risk stays the same at the learned cost, and every ceiling (room
   to the floor, the room_f / safe_cap share, the soft daily loss, the weekly loss) is re-checked at that price. It never
   raises the micros: reserve 1 tick and $1.90 (nothing learned yet) = the exact same size. Switch absent / false = today's
   exact behaviour (tests/test_learning_live.py proves both).

2. TRADE REVIEW JOURNAL (observe): every finished live / paper trade of Zlarior, ATLAS and ATLAS v2 gets a record: what the
   backtest twin did on the same bars (lit_live replay / second.run), the differences (entry time, fill, exit, $, R), the
   rule checks (engine/brain._checks via brain.replay, PC only, optional), the loss cause code (engine/lit_learn.cause_codes,
   the same codes as the LIT journal) and MFE / MAE (R, from the 1m bars). Missed (twin only) and extra (live only) trades
   get a record too. Weekly summary (Mon-Fri): live vs backtest gap in $ and R, slippage, latency, missed / extra trades
   and "is the live result inside the expected band" (engine/health_band.py for Zlarior, engine/second_scorecard.py for
   ATLAS). Pushed Sunday evening (kind "weekly", one push a week).

3. PROPOSALS, NOT CHANGES: the LIT learning loop (engine/lit_learn.py, OBSERVE mode) keeps its shadow size knobs; they show
   as "The bot suggests" cards with the evidence and "would have changed $X" on the journal (lit_learn.simulate). Approval is
   an existing command (python -m engine.lit_learn mode apply / revert <id>); nothing here applies anything. The cost reserve
   gets a card too when it learned more than 1 tick and learn_costs is off.

Never arms, routes, sends or changes an order, an entry, a stop or a target.

Stores (machine-local, logs/ is gitignored): logs/learning/costs.json (the PC's learned costs), reviews.jsonl, weekly.json,
cash.json (daily real cash). The cloud keeps its journal in state.json "learning_live".

  python -m engine.live_learning costs        # PC: rebuild the learned costs from the fill audit store, print them
  python -m engine.live_learning show         # the dashboard block (costs, reviews, weekly, suggestions)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "logs", "learning")
ET = ZoneInfo("America/New_York")
VERSION = 1
TICK, PV, COMM = 0.25, 2.0, 1.90
RESERVE_MIN, RESERVE_MAX = 1.0, 4.0          # ticks: never below today's 1-tick assumption, never above 4
COMM_MAX = 4.00                              # $ a micro round trip: a learned commission is clipped to [$1.90, $4.00]
WINDOW = 30                                  # the last 30 broker fills
MIN_OBS = 5                                  # fewer slippage observations: nothing learned (1 tick, $1.90)
REVIEW_KEEP = 400
BOTS = {"lit": "Zlarior", "atlas": "ATLAS", "atlas_v2": "ATLAS v2"}
ATLAS_KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim", "sh_asia", "sh_trend")


def _p(store, name):
    return os.path.join(store or STORE, name)


def _f(v, d=2):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else round(x, d)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    os.replace(tmp, path)


def trading_day(t) -> str:
    e = dt.datetime.fromtimestamp(int(t), ET)
    return (e + dt.timedelta(hours=6)).date().isoformat()        # 18:00 ET belongs to the next session


def _hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M") if t else "-"


def pctl(xs, q):
    """Linear-interpolated percentile q (0..100) of xs; None when empty."""
    v = sorted(float(x) for x in xs if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * float(q) / 100.0
    i = int(math.floor(k))
    j = min(i + 1, len(v) - 1)
    return v[i] + (v[j] - v[i]) * (k - i)


def _med(xs):
    return pctl(xs, 50)


# ================================================================================================ 1. execution learning
def obs_of(rec: dict, bot: str = "lit") -> dict:
    """One execution observation from an engine/fill_audit.live_trades record (pure). Slippage + = worse for us."""
    d = int(rec.get("dir") or 0) or 1
    o = {"bot": bot, "entry_t": rec.get("entry_t"), "day": rec.get("day"), "qty": int(rec.get("qty") or 0),
         "adapter": rec.get("adapter"), "fill_src": rec.get("fill_src"), "exit_src": rec.get("exit_src"),
         "entry_slip_ticks": None, "exit_kind": rec.get("exit_kind"), "exit_slip_ticks": None,
         "latency_route_s": None, "latency_fill_s": None, "live_pnl": None}
    me, fe = rec.get("model_entry"), rec.get("fill_entry")
    if me is not None and fe is not None:
        o["entry_slip_ticks"] = round((float(fe) - float(me)) * d / TICK, 2) + 0.0
    xk = str(rec.get("exit_kind") or "").upper()
    xp = rec.get("exit_px")
    if xp is not None and rec.get("exit_src") == "broker":
        if xk in ("STOP", "BE"):
            lvl = rec.get("be_stop") if xk == "BE" and rec.get("be_stop") is not None else rec.get("stop")
            if lvl is not None:
                o["exit_slip_ticks"] = round((float(lvl) - float(xp)) * d / TICK, 2) + 0.0
        elif xk == "TARGET" and rec.get("target") is not None:
            o["exit_slip_ticks"] = round((float(rec["target"]) - float(xp)) * d / TICK, 2) + 0.0
    et_ = rec.get("entry_t")
    if et_ and rec.get("t_route"):
        o["latency_route_s"] = round(float(rec["t_route"]) - float(et_), 1)
    if et_ and rec.get("t_fill") and rec.get("fill_src") == "broker":
        o["latency_fill_s"] = round(float(rec["t_fill"]) - float(et_), 1)
    if fe is not None and xp is not None and o["qty"]:
        o["live_pnl"] = round((float(xp) - float(fe)) * d * PV * o["qty"] - COMM * o["qty"], 2)
    return o


def _src_map(store=None) -> dict:
    """entry_t -> the ledger's "src" (the second strategy key of a routed ATLAS entry; absent = LIT)."""
    from engine import fill_audit as fa
    out = {}
    for r in fa._jl_read(fa._p(store, "ledger.jsonl")):
        if r.get("entry_t") is not None and r.get("side") in ("buy", "sell") and r.get("src"):
            out[int(r["entry_t"])] = str(r["src"])
    return out


def bot_of_src(src) -> str:
    return "atlas" if src and str(src) not in ("lit", "LIT") else "lit"


def exec_obs(store=None, journal_path=None) -> list:
    """Every routed trade of the PC (fill audit store) as an observation, tagged by bot. Never raises."""
    try:
        from engine import fill_audit as fa
        recs = fa.live_trades(store, journal_path)
        src = _src_map(store)
        return [obs_of(r, bot_of_src(src.get(int(k)))) for k, r in sorted(recs.items()) if r.get("ok")]
    except Exception:
        return []


def comm_from_cash(cash_days: dict, obs: list) -> list:
    """$ a micro actually booked per day from the real balance (pure): for each day with a real cash value and the day
    before it, comm = $1.90 + (the fills' P&L at $1.90 - the real cash change) / micros traded that day. Days with no
    broker-priced trade or no micros are skipped. cash_days = {day: real cash at the day's close}."""
    by = {}
    for o in obs:
        if o.get("live_pnl") is None or not o.get("qty") or o.get("fill_src") != "broker" or o.get("exit_src") != "broker":
            continue
        x = by.setdefault(o["day"], [0.0, 0])
        x[0] += float(o["live_pnl"])
        x[1] += int(o["qty"])
    days = sorted(cash_days)
    out = []
    for a, b in zip(days, days[1:]):
        if b not in by or not by[b][1]:
            continue
        real = float(cash_days[b]) - float(cash_days[a])
        out.append({"day": b, "comm": round(COMM + (by[b][0] - real) / by[b][1], 3), "micros": by[b][1]})
    return out


def cost_stats(obs: list, bot: str = "lit", window: int = WINDOW, comm_obs: list | None = None) -> dict:
    """Execution statistics and the learned cost reserve of one bot from its last `window` broker fills (pure)."""
    B = [o for o in obs if o.get("bot") == bot and o.get("fill_src") == "broker"]
    B = sorted(B, key=lambda o: o.get("entry_t") or 0)[-int(window):]
    ent = [o["entry_slip_ticks"] for o in B if o.get("entry_slip_ticks") is not None]
    stp = [o["exit_slip_ticks"] for o in B if o.get("exit_slip_ticks") is not None and str(o.get("exit_kind") or "").upper() in ("STOP", "BE")]
    tgt = [o["exit_slip_ticks"] for o in B if o.get("exit_slip_ticks") is not None and str(o.get("exit_kind") or "").upper() == "TARGET"]
    adverse = [max(0.0, float(x)) for x in ent + stp]
    lat_r = [o["latency_route_s"] for o in B if o.get("latency_route_s") is not None]
    lat_f = [o["latency_fill_s"] for o in B if o.get("latency_fill_s") is not None]
    C = [c["comm"] for c in (comm_obs or []) if c.get("comm") is not None][-int(window):]
    p75 = pctl(adverse, 75)
    learned = len(adverse) >= MIN_OBS
    res = min(RESERVE_MAX, max(RESERVE_MIN, float(math.ceil(p75 - 1e-9)))) if learned and p75 is not None else RESERVE_MIN
    cm = _med(C)
    comm = min(COMM_MAX, max(COMM, round(cm, 2))) if C else COMM
    out = {"v": VERSION, "bot": bot, "label": BOTS.get(bot, bot), "fills": len(B), "obs": len(adverse), "min_obs": MIN_OBS,
           "window": int(window), "learned": bool(learned),
           "entry_slip_ticks_med": _f(_med(ent)), "entry_slip_ticks_p75": _f(pctl(ent, 75)),
           "stop_slip_ticks_med": _f(_med(stp)), "stop_slip_ticks_p75": _f(pctl(stp, 75)),
           "target_slip_ticks_med": _f(_med(tgt)), "adverse_p75": _f(p75),
           "latency_route_s_med": _f(_med(lat_r), 1), "latency_route_s_p75": _f(pctl(lat_r, 75), 1),
           "latency_fill_s_med": _f(_med(lat_f), 1),
           "comm_obs": len(C), "comm_med": _f(cm, 3), "assumed": {"slip_ticks": RESERVE_MIN, "comm": COMM},
           "reserve_ticks": res, "comm": comm,
           "slip_usd": round(sum(-float(x) * TICK * PV * int(o.get("qty") or 0) for o in B
                                 for x in (o.get("entry_slip_ticks"), o.get("exit_slip_ticks")) if x is not None), 2)}
    out["text"] = cost_text(out)
    return out


def cost_text(S: dict) -> str:
    if not S.get("fills"):
        return f"{S.get('label')}: no real fills yet - sizing assumes 1 tick of slippage and $1.90 a micro."
    if not S.get("learned"):
        return (f"{S.get('label')}: {S['obs']} of {S['min_obs']} fills needed before it learns - sizing assumes 1 tick and "
                f"$1.90 a micro.")
    more = S["reserve_ticks"] > RESERVE_MIN or S["comm"] > COMM
    return (f"{S.get('label')}: p75 adverse slippage {S['adverse_p75']:.1f} ticks over {S['obs']} fills -> reserve "
            f"{S['reserve_ticks']:.0f} tick{'s' if S['reserve_ticks'] != 1 else ''}, ${S['comm']:.2f} a micro"
            + (" (more conservative than assumed)" if more else " (same as assumed)"))


def load_costs(bot: str = "lit", path: str | None = None) -> dict | None:
    """The learned costs of one bot ({"reserve_ticks", "comm", ...}) from logs/learning/costs.json (env LE_LEARN_COSTS
    overrides the path). None when there is no file. Never raises."""
    p = path or os.environ.get("LE_LEARN_COSTS") or _p(None, "costs.json")
    C = _read_json(p, None)
    if not isinstance(C, dict):
        return None
    b = (C.get("bots") or {}).get(bot)
    return b if isinstance(b, dict) else None


def cash_days(store=None, bb_path: str | None = None) -> dict:
    """{day: real cash} kept from engine/broker_balance.py's state (the last cash of each day of the main account)."""
    path = _p(store, "cash.json")
    D = _read_json(path, {}) or {}
    try:
        S = _read_json(bb_path or os.path.join(ROOT, "data", "broker_balance.json"), {}) or {}
        accs = S.get("accounts") or {}
        for nm, rec in sorted(accs.items()):
            last = (rec or {}).get("last") if isinstance(rec, dict) else None
            if isinstance(last, dict) and last.get("day") and last.get("cash") is not None:
                D.setdefault(nm, {})[str(last["day"])] = float(last["cash"])
        if accs:
            _write_json(path, D)
    except Exception:
        pass
    return D


def pc_update(store=None, fa_store=None, now=None, write=True) -> dict:
    """PC: the learned costs of Zlarior and ATLAS from the fill audit store -> logs/learning/costs.json. Never raises."""
    now = int(now or time.time())
    try:
        obs = exec_obs(fa_store)
        cd = cash_days(store)
        main = max(cd.values(), key=len) if cd else {}            # the account with the most days = the 50K eval account
        co = comm_from_cash(main, [o for o in obs if o["bot"] == "lit"])
        out = {"v": VERSION, "t": now, "bots": {"lit": cost_stats(obs, "lit", comm_obs=co), "atlas": cost_stats(obs, "atlas")}}
        out["recent"] = [{k: o.get(k) for k in ("bot", "day", "entry_t", "qty", "entry_slip_ticks", "exit_kind", "exit_slip_ticks",
                                                "latency_route_s", "latency_fill_s")} for o in obs if o.get("fill_src") == "broker"][-12:][::-1]
        if write:
            _write_json(_p(store, "costs.json"), out)
        return out
    except Exception as e:
        return {"v": VERSION, "t": now, "error": f"{e.__class__.__name__}: {e}"[:200], "bots": {}}


# ================================================================================================ 2. trade review journal
def twin_lit(t: dict) -> dict:
    """A lit_live.run trade (the backtest twin) in the review shape."""
    q = int(t.get("qty") or 0)
    return {"entry_t": int(t["entry_t"]), "exit_t": _i(t.get("exit_t")), "dir": int(t["dir"]), "entry": _f(t.get("entry")),
            "exit": _f(t.get("exit_price")), "exit_kind": _kind(t.get("exit_reason")), "stop": _f(t.get("stop")),
            "target": _f(t.get("target")), "qty": q, "usd": _f(t.get("pnl")), "r": _f(t.get("pnl_r"), 3),
            "risk_pts": _f(t.get("risk_pts")), "day": t.get("day") or trading_day(t["entry_t"])}


def live_lit_paper(k, v: dict) -> dict:
    """A cloud paper ledger row (tools/cloud_monitor.py ledger) in the review shape."""
    side = str(v.get("side") or "").upper()
    return {"entry_t": int(k), "exit_t": _i(v.get("exit_ts")), "dir": 1 if side == "LONG" else -1, "entry": _f(v.get("entry_px")),
            "exit": _f(v.get("exit_px")), "exit_kind": _kind(v.get("exit")), "stop": _f(v.get("stop_px")),
            "target": _f(v.get("target_px")), "qty": int(v.get("qty") or 0), "usd": _f(v.get("usd")), "r": _f(v.get("R"), 3),
            "risk_pts": _f(v.get("risk_pts")), "day": v.get("day") or trading_day(int(k)), "src": "paper"}


def live_lit_pc(t: dict) -> dict:
    """A PC routed trade (heartbeat "acct" trades / tools/recap.finished_trades src pc) in the review shape."""
    side = str(t.get("side") or "").upper()
    return {"entry_t": int(t["entry_t"]), "exit_t": _i(t.get("exit_t")), "dir": 1 if side == "LONG" else -1, "entry": _f(t.get("entry")),
            "exit": _f(t.get("exit_px")), "exit_kind": _kind(t.get("exit")), "stop": _f(t.get("stop")), "target": _f(t.get("target")),
            "qty": int(t.get("qty") or 0), "usd": _f(t.get("pnl", t.get("usd"))), "r": _f(t.get("r"), 3), "risk_pts": _f(t.get("risk_pts")),
            "day": t.get("day") or trading_day(t["entry_t"]), "src": "pc"}


def row_second(v: dict, src: str = "paper") -> dict:
    """An engine/second.py paper ledger / run() trade row (ROW_KEYS) or an ATLAS v2 ledger row in the review shape."""
    d = int(v.get("dir") or (1 if str(v.get("side") or "").upper() == "LONG" else -1))
    return {"entry_t": int(v["entry_t"]), "exit_t": _i(v.get("exit_t")), "dir": d, "entry": _f(v.get("entry")),
            "exit": _f(v.get("exit")), "exit_kind": _kind(v.get("exit_kind")), "stop": _f(v.get("stop")), "target": _f(v.get("target")),
            "qty": int(v.get("qty") or 0), "usd": _f(v.get("usd")), "r": _f(v.get("r"), 3), "risk_pts": _f(v.get("risk_pts")),
            "day": v.get("day") or trading_day(v["entry_t"]), "src": src, "key": v.get("key"), "short": v.get("short")}


def _i(x):
    try:
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _kind(x):
    s = str(x or "").upper()
    return {"EOD": "TIME", "TIME SAFETY": "TIME", "FLAT": "TIME", "CUT_T15": "CUT", "T15": "CUT"}.get(s, s) or None


def finished(x: dict) -> bool:
    return bool(x) and x.get("exit_kind") not in (None, "", "OPEN") and x.get("exit_t") is not None


def match(live: list, twin: list, tol: int = 600) -> list:
    """Pairs (live, twin): the same entry time first, then the same side within tol seconds; the rest unpaired."""
    pairs, used = [], set()
    for l in sorted(live, key=lambda x: x["entry_t"]):
        c = [t for t in twin if id(t) not in used]
        m = next((t for t in c if t["entry_t"] == l["entry_t"] and t["dir"] == l["dir"]), None) or \
            next((t for t in c if t["dir"] == l["dir"] and abs(t["entry_t"] - l["entry_t"]) <= tol), None)
        if m is not None:
            used.add(id(m))
        pairs.append((l, m))
    pairs += [(None, t) for t in twin if id(t) not in used]
    return sorted(pairs, key=lambda p: (p[0] or p[1])["entry_t"])


def mfe_mae(x: dict, d1) -> tuple:
    """(MFE, MAE) in R of a finished trade from the 1m bars between its entry and exit (None when unknown)."""
    try:
        risk = abs(float(x["entry"]) - float(x["stop"])) if x.get("stop") is not None else float(x.get("risk_pts") or 0)
        if d1 is None or not len(d1) or not risk or x.get("exit_t") is None:
            return None, None
        seg = d1[(d1["time"] >= int(x["entry_t"])) & (d1["time"] < int(x["exit_t"]))]
        if not len(seg):
            return None, None
        e, d = float(x["entry"]), int(x["dir"])
        fav = (float(seg["high"].max()) - e) if d == 1 else (e - float(seg["low"].min()))
        adv = (e - float(seg["low"].min())) if d == 1 else (float(seg["high"].max()) - e)
        return round(max(0.0, fav) / risk, 3), round(max(0.0, adv) / risk, 3)
    except Exception:
        return None, None


def cause_of(x: dict, jrec: dict | None = None) -> tuple:
    """(cause, tags): the LIT journal's own record when there is one, else engine/lit_learn.cause_codes on the exit / R."""
    if jrec and ("cause" in jrec):
        return jrec.get("cause"), list(jrec.get("tags") or [])
    try:
        from engine.lit_learn import cause_codes
        ex = {"TIME": "EOD", "CUT": "EOD"}.get(x.get("exit_kind"), x.get("exit_kind"))
        return cause_codes({"exit": ex, "r": x.get("r"), "risk_pts": x.get("risk_pts"), "f": (jrec or {}).get("f") or {},
                            "post": (jrec or {}).get("post") or {}})
    except Exception:
        return None, []


def _usd_per_micro(t):
    q = int(t.get("qty") or 0)
    return None if not q or t.get("usd") is None else float(t["usd"]) / q


def review(bot: str, live: dict | None, twin: dict | None, d1=None, jrec: dict | None = None, checks: list | None = None,
           now=None) -> dict:
    """One review record (matched / missed / extra) of a finished trade. Pure apart from the bars it reads."""
    x = live or twin
    status = "matched" if live and twin else "extra" if live else "missed"
    keep = ("entry_t", "exit_t", "entry", "exit", "exit_kind", "stop", "target", "qty", "usd", "r")
    rec = {"v": VERSION, "key": f"{bot}|{x['day']}|{int(x['entry_t'])}|{int(x['dir'])}", "bot": bot, "label": BOTS.get(bot, bot),
           "source": (live or {}).get("src") or ("replay" if twin else None), "day": x["day"], "entry_t": int(x["entry_t"]),
           "side": "LONG" if int(x["dir"]) == 1 else "SHORT", "status": status,
           "live": {k: live.get(k) for k in keep} if live else None, "twin": {k: twin.get(k) for k in keep} if twin else None,
           "diff": None, "gap_usd": None, "gap_r": None, "exec_usd": None, "logged_at": int(now or time.time())}
    for k in ("key", "short"):
        if x.get(k):
            rec["member" if k == "key" else "member_short"] = x[k]
    if status == "matched":
        d = int(x["dir"])
        df = {"entry_s": int(live["entry_t"]) - int(twin["entry_t"]),
              "entry_ticks": _f((float(live["entry"]) - float(twin["entry"])) * d / TICK) if live.get("entry") is not None and twin.get("entry") is not None else None,
              "exit_ticks": _f((float(twin["exit"]) - float(live["exit"])) * d / TICK) if live.get("exit") is not None and twin.get("exit") is not None else None,
              "same_exit": live.get("exit_kind") == twin.get("exit_kind"), "qty": int(live.get("qty") or 0) - int(twin.get("qty") or 0),
              "exit_s": (int(live["exit_t"]) - int(twin["exit_t"])) if live.get("exit_t") and twin.get("exit_t") else None}
        rec["diff"] = df
        if live.get("usd") is not None and twin.get("usd") is not None:
            rec["gap_usd"] = round(float(live["usd"]) - float(twin["usd"]), 2)
            pm = _usd_per_micro(twin)
            if pm is not None:
                rec["exec_usd"] = round(float(live["usd"]) - pm * int(live.get("qty") or 0), 2)   # same micros: execution only
        if live.get("r") is not None and twin.get("r") is not None:
            rec["gap_r"] = round(float(live["r"]) - float(twin["r"]), 3)
        notes = []
        if df["entry_s"]:
            notes.append(f"entry {_hm(live['entry_t'])} vs the backtest's {_hm(twin['entry_t'])} ET")
        if df["entry_ticks"]:
            notes.append(f"fill {df['entry_ticks']:+.0f} ticks vs the backtest")
        if not df["same_exit"]:
            notes.append(f"exit {live.get('exit_kind')} vs the backtest's {twin.get('exit_kind')}")
        elif df["exit_ticks"]:
            notes.append(f"exit {df['exit_ticks']:+.0f} ticks vs the backtest")
        if df["qty"]:
            notes.append(f"{live.get('qty')} micros vs {twin.get('qty')} (sizing, not execution)")
        rec["notes"] = notes or ["same as the backtest"]
    elif status == "missed":
        rec["gap_usd"] = _f(-(float(twin["usd"]) if twin.get("usd") is not None else 0.0))
        rec["gap_r"] = _f(-(float(twin["r"]) if twin.get("r") is not None else 0.0), 3)
        rec["notes"] = [f"the backtest traded {twin.get('exit_kind')} {float(twin.get('r') or 0):+.2f}R; the bot did not"]
    else:
        rec["gap_usd"] = _f(live.get("usd"))
        rec["gap_r"] = _f(live.get("r"), 3)
        rec["notes"] = ["the backtest on the same bars has no trade here"]
    base = live or twin
    rec["cause"], rec["tags"] = cause_of(base, jrec)
    rec["mfe_r"], rec["mae_r"] = mfe_mae(base, d1)
    if rec["mfe_r"] is None and jrec and jrec.get("mfe") is not None:
        rec["mfe_r"], rec["mae_r"] = _f(jrec.get("mfe"), 3), _f(jrec.get("mae"), 3)
    rec["checks"] = checks
    return rec


def reviews(bot: str, live_rows: list, twin_rows: list, d1=None, journal: list | None = None, checks_fn=None,
            upto=None, now=None, since=None, live_since=None) -> list:
    """Review records of every finished trade: live rows vs their backtest twins (only finished ones). since: twins that
    entered before it are left out (the live ledger was not watching yet: not a missed trade); upto: twins that exited
    after it are left out (their session is not over); live_since: live rows before it are left out (the twin's bars do
    not reach back that far: not an extra trade). journal: LIT journal records (cause codes / MFE)."""
    L = [x for x in live_rows if finished(x) and (live_since is None or int(x["entry_t"]) >= int(live_since))]
    T = [x for x in twin_rows if finished(x) and (upto is None or int(x["exit_t"]) <= int(upto))
         and (since is None or int(x["entry_t"]) >= int(since))]
    J = {}
    for j in journal or []:
        if j.get("entry_t"):
            J[(int(j["entry_t"]), int(j.get("dir") or 0))] = j
    out = []
    for l, t in match(L, T):
        x = l or t
        jr = J.get((int(x["entry_t"]), int(x["dir"])))
        ck = None
        if checks_fn is not None:
            try:
                ck = checks_fn(x)
            except Exception:
                ck = None
        out.append(review(bot, l, t, d1, jr, ck, now))
    return out


def lit_checks(x: dict) -> list | None:
    """The LIT rule checks (engine/brain._checks via brain.replay) of the setup a trade came from. PC only (heavy)."""
    from engine import brain
    b = brain.replay(x["day"], t=int(x["entry_t"]) + 60)
    best = None
    for s in b.get("setups") or []:
        tr = s.get("trade") or {}
        if tr.get("entry_t") == int(x["entry_t"]) or (s.get("dir") == int(x["dir"]) and s.get("status") == "filled"):
            best = s
            break
    if best is None:
        return None
    return [{"key": c.get("key"), "ok": bool(c.get("ok")), "text": str(c.get("text") or "")[:140]} for c in best.get("checks") or []]


def merge(old: list, new: list, keep: int = REVIEW_KEEP) -> list:
    """The journal: one record per key; a matched record replaces an earlier missed / extra one of the same trade."""
    by = {r["key"]: r for r in old or [] if isinstance(r, dict) and r.get("key")}
    for r in new or []:
        p = by.get(r["key"])
        if p is None or p.get("status") != "matched" or r.get("status") == "matched":
            if p is not None:
                r = {**r, "logged_at": p.get("logged_at", r.get("logged_at"))}
            by[r["key"]] = r
    return sorted(by.values(), key=lambda r: r["entry_t"])[-int(keep):]


# ================================================================================================ weekly summary
def week_of(day: str) -> str:
    d = dt.date.fromisoformat(str(day))
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def weekly_summary(recs: list, week: str, bands: dict | None = None) -> dict:
    """The Mon-Fri week starting `week`: per bot the live vs backtest gap ($, R), slippage, latency, missed / extra trades
    and the expected-band verdict (bands = {bot: {"level", "text"}} from the hook). Pure."""
    mon = dt.date.fromisoformat(week)
    fri = (mon + dt.timedelta(days=4)).isoformat()
    W = [r for r in recs if week <= r["day"] <= fri]
    out = {"v": VERSION, "week": week, "to": fri, "label": f"{mon:%b %d} - {dt.date.fromisoformat(fri):%b %d}", "bots": {}}
    for bot in BOTS:
        R = [r for r in W if r["bot"] == bot]
        if not R and not (bands or {}).get(bot):
            continue
        M = [r for r in R if r["status"] == "matched"]
        X = [r for r in R if r["status"] == "missed"]
        E = [r for r in R if r["status"] == "extra"]
        lv = [r["live"] for r in R if r.get("live")]
        tw = [r["twin"] for r in R if r.get("twin")]
        s = lambda rows, k: round(sum(float(x.get(k) or 0) for x in rows), 2)
        ent = [r["diff"]["entry_ticks"] for r in M if r.get("diff") and r["diff"].get("entry_ticks") is not None]
        ext = [r["diff"]["exit_ticks"] for r in M if r.get("diff") and r["diff"].get("exit_ticks") is not None and r["diff"].get("same_exit")]
        lat = [r["diff"]["entry_s"] for r in M if r.get("diff") and r["diff"].get("entry_s") is not None]
        b = {"trades_live": len(lv), "trades_twin": len(tw), "matched": len(M), "missed": len(X), "extra": len(E),
             "live_usd": s(lv, "usd"), "twin_usd": s(tw, "usd"), "live_r": round(s(lv, "r"), 2), "twin_r": round(s(tw, "r"), 2),
             "missed_usd": round(-sum(float(r.get("gap_usd") or 0) for r in X), 2), "extra_usd": round(sum(float(r.get("gap_usd") or 0) for r in E), 2),
             "exec_usd": round(sum(float(r.get("exec_usd") or 0) for r in M), 2),
             "entry_slip_ticks_med": _f(_med(ent)), "exit_slip_ticks_med": _f(_med(ext)), "entry_delay_s_med": _f(_med(lat), 0),
             "diff_exit": sum(1 for r in M if r.get("diff") and not r["diff"].get("same_exit")),
             "causes": _count([r.get("cause") for r in R if r.get("cause")])}
        b["gap_usd"] = round(b["live_usd"] - b["twin_usd"], 2)
        b["gap_r"] = round(b["live_r"] - b["twin_r"], 2)
        bd = (bands or {}).get(bot) or {}
        b["band"] = {k: bd.get(k) for k in ("level", "text", "pct") if bd.get(k) is not None} or None
        b["inside_band"] = (None if not bd.get("level") else bd["level"] in ("good", "on_track", "ready", "collecting", "warn"))
        b["text"] = week_text(BOTS[bot], b)
        out["bots"][bot] = b
    out["head"] = "; ".join(f"{BOTS[k]} {v['text']}" for k, v in out["bots"].items()) or "No live or paper trades this week."
    return out


def _count(xs):
    c = {}
    for x in xs:
        c[x] = c.get(x, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def _usd(v):
    v = float(v or 0)
    return ("+" if v > 0 else "-" if v < 0 else "") + f"${abs(v):,.0f}"


def week_text(name, b) -> str:
    if not (b["trades_live"] or b["trades_twin"]):
        return "no trades"
    t = (f"{b['trades_live']} live vs {b['trades_twin']} backtest, {_usd(b['live_usd'])} vs {_usd(b['twin_usd'])} "
         f"(gap {_usd(b['gap_usd'])}, {b['gap_r']:+.2f}R)")
    if b["missed"]:
        t += f", {b['missed']} missed"
    if b["extra"]:
        t += f", {b['extra']} extra"
    if b.get("entry_slip_ticks_med") is not None:
        t += f", fills {b['entry_slip_ticks_med']:+.1f} ticks"
    if b.get("band"):
        t += f"; {b['band'].get('text')}"
    return t


def weekly_due(prev_week: str | None, now) -> str | None:
    """The Monday of the week to summarise when it is Sunday 17:00 ET or later (or Monday before noon, a missed Sunday)
    and that week was not pushed yet; else None."""
    e = dt.datetime.fromtimestamp(int(now), ET)
    if e.weekday() == 6 and e.hour >= 17:
        mon = e.date() - dt.timedelta(days=6)
    elif e.weekday() == 0 and e.hour < 12:
        mon = e.date() - dt.timedelta(days=7)
    else:
        return None
    w = mon.isoformat()
    return None if prev_week == w else w


def weekly_payload(W: dict, t=None) -> dict:
    from engine import push
    p = push.text_payload("Cloud", "weekly", f"Learning · week {W['label']}", ("Live vs backtest: " + W["head"])[:600],
                          key=f"learnweek:{W['week']}", t=int(t or time.time()), url="#/learning")
    p["tag"] = "le-learnweek"
    return p


# ================================================================================================ 3. suggestions
def suggestions(L: dict | None, journal: list | None, costs: dict | None = None, learn_costs: bool = False,
                advisor_store: str | None = None, advisor_tally: dict | None = None) -> list:
    """"The bot suggests" cards: the LIT learning loop's shadow knobs (observe mode) with their evidence and what they
    would have changed in $ on the journal, the cost reserve, and the discretion advisor's structure rules (engine/advisor.py:
    "would have saved / cost $X over N trades"; advice only, no approve command). Approval = an existing command; nothing is
    applied."""
    out = []
    try:
        from engine import lit_learn as LL
        L = L or {}
        J = LL.merged(journal or [])
        knobs = L.get("knobs") or {}
        mode = L.get("mode") or "observe"
        dec = {d.get("id"): d for d in L.get("decisions") or []}
        base = LL.simulate(J, {}, evals=False) if J else None
        for fam, bs in knobs.items():
            for b, k in bs.items():
                if abs(float(k.get("mult", 1.0)) - 1.0) < 1e-9 and not k.get("skip"):
                    continue
                one = LL.simulate(J, {fam: {b: k}}, evals=False) if J else None
                d = dec.get(k.get("decision")) or {}
                delta = round(float(one["net"]) - float(base["net"]), 2) if one and base else None
                out.append({"bot": "lit", "kind": "size_knob", "id": k.get("decision"), "title":
                            f"Size {LL.bucket_label(fam, b)} at {float(k.get('mult', 1.0)):g}x" + (" (skip)" if k.get("skip") else ""),
                            "since": k.get("since"), "evidence": d.get("reason"), "numbers": d.get("numbers") or None,
                            "would_usd": delta, "trades": (one or {}).get("taken"),
                            "would_text": (f"would have changed {_usd(delta)} on the {len(J)} journal trades "
                                           f"({J[0]['day']} - {J[-1]['day']})") if delta is not None and J else None,
                            "applied": mode == "apply", "approve": "python -m engine.lit_learn mode apply",
                            "undo": f"python -m engine.lit_learn revert {k.get('decision')}" if k.get("decision") else None,
                            "note": "Observe mode: nothing changes until you approve. Applying turns on every learned knob (bounded 0.5x-1.25x)."})
    except Exception as e:
        out.append({"bot": "lit", "kind": "error", "title": "Suggestions unavailable", "evidence": f"{e.__class__.__name__}: {e}"[:160]})
    for bot, c in ((costs or {}).get("bots") or {}).items():
        if c.get("learned") and (c.get("reserve_ticks", 1) > RESERVE_MIN or c.get("comm", COMM) > COMM):
            out.append({"bot": bot, "kind": "cost_reserve", "title": f"Price fills at {c['reserve_ticks']:.0f} ticks and ${c['comm']:.2f} a micro",
                        "evidence": c.get("text"), "applied": bool(learn_costs),
                        "would_text": "smaller size on the same $ risk (never larger)",
                        "approve": 'live_model.json + live_model_lit.json: lit_sizing "learn_costs": true',
                        "note": "Only makes sizing more conservative; off = today's exact sizing."})
    try:                                       # the discretion advisor's running tally per structure rule (read-only)
        from engine import advisor
        out += advisor.cards(advisor_tally, store=advisor_store)
    except Exception:
        pass
    return out


# ================================================================================================ cloud / PC hooks
def _second_bands(block):
    try:
        from engine import second_scorecard as SC
        led = {k: list(((block.get("strategies") or {}).get(k) or {}).get("ledger", {}).values()) for k in SC.all_keys()}
        ab = SC.card(led, source="paper").get("account_b") or {}
        return {"level": ab.get("kind"), "text": ab.get("text"), "pct": ab.get("pct")}
    except Exception:
        return None


def _lit_band(trades, week, today):
    try:
        from engine import health_band as HB
        B = HB.load()
        c = HB.compare(B, [{"day": t["day"], "r": t.get("r"), "usd": t.get("usd"), "t": t["entry_t"]} for t in trades], week, today) if B else None
        return {"level": c.get("level"), "text": c.get("text"), "pct": c.get("pct_r")} if c else None
    except Exception:
        return None


def cloud_hook(new_state: dict, old_state: dict, res: dict | None, second_run: dict | None, d1, now: int,
               lit_journal: list | None = None, learning: dict | None = None, lit_sizing: dict | None = None) -> dict:
    """tools/cloud_monitor.py: the review journal of the cloud (Zlarior paper ledger + the PC's routed trades vs this run's
    lit_live twin; ATLAS paper ledgers vs this run's second.run; ATLAS v2 vs its members), the weekly summary (pushed Sunday
    evening: the payload under "notices"), the suggestions, the PC's learned costs -> new_state["learning_live"]. Read-only
    towards every ledger. Never raises."""
    old = (old_state or {}).get("learning_live") or {}
    out = {"v": VERSION, "t": int(now), "reviews": list(old.get("reviews") or []), "weekly": list(old.get("weekly") or []),
           "pushed_week": old.get("pushed_week"), "notices": []}
    e = dt.datetime.fromtimestamp(int(now), ET)
    today = trading_day(now)
    over = e.hour * 60 + e.minute >= 16 * 60 + 5 or e.weekday() >= 5
    upto = int(now) if over else int(dt.datetime.combine(e.date(), dt.time(0, 0), ET).timestamp()) - 6 * 3600
    new = []
    errs = []
    try:                                       # Zlarior: paper ledger + the PC's routed trades vs the lit_live twin
        tw = [twin_lit(t) for t in (res or {}).get("trades") or [] if t.get("exit_reason") not in (None, "OPEN")]
        paper = [live_lit_paper(k, v) for k, v in (new_state.get("ledger") or {}).items()
                 if str(k).isdigit() and isinstance(v, dict) and v.get("taken") is not False]
        lo = min([t["entry_t"] for t in tw], default=None)
        first = int(new_state.get("first_run") or (old_state or {}).get("first_run") or now)
        new += reviews("lit", paper, tw, d1, lit_journal, upto=upto, now=now, since=first - 300, live_since=lo and lo - 600)
        pc = new_state.get("pc") if isinstance(new_state.get("pc"), dict) else {}
        pct = [live_lit_pc(t) for t in ((pc.get("acct") or {}).get("trades") or []) if isinstance(t, dict) and t.get("entry_t")]
        if pct:
            p0 = min(x["entry_t"] for x in pct) - 600
            for r in reviews("lit", pct, tw, d1, lit_journal, upto=upto, now=now, since=p0, live_since=lo and lo - 600):
                r["key"] = r["key"].replace("lit|", "lit_pc|", 1)
                r["source"] = "pc"
                new.append(r)
    except Exception as ex:
        errs.append(f"lit: {ex.__class__.__name__}: {ex}"[:160])
    try:                                       # ATLAS members: frozen paper ledger vs this run's second.run
        blk = new_state.get("second") or {}
        runs = (second_run or {}).get("strategies") or {}
        for k in ATLAS_KEYS:
            s = (blk.get("strategies") or {}).get(k)
            if not s or not runs:                # no fresh run of the members this time: nothing to compare with
                continue
            lv = [row_second({**v, "key": k}, "paper") for v in (s.get("ledger") or {}).values() if v.get("entry_t")]
            tw = [row_second({**t, "key": k}, "replay") for t in (runs.get(k) or {}).get("trades") or [] if t.get("entry_t")]
            f0 = int(blk.get("first_run") or now) - 300
            lo = min([t["entry_t"] for t in tw], default=None)
            for r in reviews("atlas", lv, tw, d1, None, upto=upto, now=now, since=f0,
                             live_since=lo and lo - 600) if (lv or tw) else []:
                r["key"] = r["key"].replace("atlas|", f"atlas:{k}|", 1)
                new.append(r)
    except Exception as ex:
        errs.append(f"atlas: {ex.__class__.__name__}: {ex}"[:160])
    try:                                       # ATLAS v2: its shadow ledger vs the member trade it copied (same entry)
        v2 = new_state.get("atlas_v2") or {}
        mem = {}
        for k in ATLAS_KEYS:
            for v in (((new_state.get("second") or {}).get("strategies") or {}).get(k) or {}).get("ledger", {}).values():
                if v.get("entry_t"):
                    mem.setdefault(k, []).append(row_second({**v, "key": k}, "member"))
        lv = [row_second(v, "paper") for v in (v2.get("ledger") or {}).values() if v.get("entry_t")]
        for x in lv:
            tw = [t for t in mem.get(x.get("key")) or [] if t["entry_t"] == x["entry_t"]]
            for r in reviews("atlas_v2", [x], tw, d1, None, now=now):
                if r["status"] != "missed":
                    new.append(r)
    except Exception as ex:
        errs.append(f"atlas_v2: {ex.__class__.__name__}: {ex}"[:160])
    out["reviews"] = merge(out["reviews"], new)
    # weekly summary: this week so far (display) + the Sunday push of the finished week
    try:
        wk_now = week_of(today if dt.date.fromisoformat(today).weekday() < 5 else (dt.date.fromisoformat(today) - dt.timedelta(days=2)).isoformat())

        def bands_for(week):
            fri = (dt.date.fromisoformat(week) + dt.timedelta(days=4)).isoformat()
            lt = [r["live"] | {"day": r["day"], "entry_t": r["entry_t"]} for r in out["reviews"]
                  if r["bot"] == "lit" and r.get("live") and week <= r["day"] <= fri and r.get("source") != "pc"]
            return {"lit": _lit_band(lt, week, min(fri, today)), "atlas": _second_bands(new_state.get("second") or {})}
        cur = weekly_summary(out["reviews"], wk_now, bands_for(wk_now))
        W = {w["week"]: w for w in out["weekly"] if isinstance(w, dict) and w.get("week")}
        W[cur["week"]] = cur
        due = weekly_due(out.get("pushed_week"), now)
        if due:
            fin = weekly_summary(out["reviews"], due, bands_for(due))
            fin["final"] = True
            W[due] = fin
            out["notices"].append(weekly_payload(fin, now))
            out["pushed_week"] = due
        out["weekly"] = [W[k] for k in sorted(W)][-12:]
    except Exception as ex:
        errs.append(f"weekly: {ex.__class__.__name__}: {ex}"[:160])
    adv_tally = None
    try:                                       # the discretion advisor (engine/advisor.py): structure advice scored in $, read-only
        from engine import advisor
        adv = advisor.cloud_block(new_state, old_state, d1, now)
        new_state["advisor"] = adv
        adv_tally = adv.get("tally") or {}
    except Exception as ex:
        errs.append(f"advisor: {ex.__class__.__name__}: {ex}"[:160])
    pc = new_state.get("pc") if isinstance(new_state.get("pc"), dict) else {}
    costs = (pc.get("learn") or {}).get("costs") if isinstance(pc.get("learn"), dict) else None
    out["costs"] = costs
    out["learn_costs"] = bool((lit_sizing or {}).get("learn_costs"))
    out["suggest"] = suggestions(learning, lit_journal, costs, out["learn_costs"], advisor_tally=adv_tally)
    if errs:
        out["errors"] = errs
    new_state["learning_live"] = {k: v for k, v in out.items() if k != "notices"}
    return out


def site_block(st: dict | None, n_reviews: int = 40) -> dict | None:
    """data.json "learning_live" for the phone (Zlarior / ATLAS > Results > Learning): small."""
    L = (st or {}).get("learning_live")
    if not isinstance(L, dict):
        return None
    R = L.get("reviews") or []
    per = {}
    for b in BOTS:
        rb = [r for r in R if r.get("bot") == b][-n_reviews:][::-1]
        per[b] = rb
    return {"v": VERSION, "t": L.get("t"), "costs": L.get("costs"), "learn_costs": L.get("learn_costs"),
            "weekly": (L.get("weekly") or [])[-6:][::-1], "suggest": L.get("suggest") or [], "reviews": per,
            "totals": totals(R), "errors": L.get("errors")}


def totals(R: list) -> dict:
    """All-time per bot: trades, live vs backtest $ / R and the gap."""
    out = {}
    for b in BOTS:
        rb = [r for r in R if r.get("bot") == b]
        if not rb:
            continue
        lv = [r["live"] for r in rb if r.get("live")]
        tw = [r["twin"] for r in rb if r.get("twin")]
        lu, tu = round(sum(float(x.get("usd") or 0) for x in lv), 2), round(sum(float(x.get("usd") or 0) for x in tw), 2)
        out[b] = {"reviews": len(rb), "matched": sum(1 for r in rb if r["status"] == "matched"),
                  "missed": sum(1 for r in rb if r["status"] == "missed"), "extra": sum(1 for r in rb if r["status"] == "extra"),
                  "live_usd": lu, "twin_usd": tu, "gap_usd": round(lu - tu, 2),
                  "gap_r": round(sum(float(x.get("r") or 0) for x in lv) - sum(float(x.get("r") or 0) for x in tw), 2),
                  "from": rb[0]["day"], "to": rb[-1]["day"]}
    return out


def pc_reviews(store=None, fa_store=None, now=None, checks: bool = False, write=True) -> list:
    """PC: review records of the routed Zlarior trades from the fill audit report (it already replays the twin on the
    same bars) -> logs/learning/reviews.jsonl. checks=True adds the Brain's rule checks (brain.replay, slow)."""
    from engine import fill_audit as fa
    rep = fa._read_json(fa._p(fa_store, "report.json"), None) or {}
    try:
        from engine.lit_learn import load_journal
        J = load_journal()
    except Exception:
        J = []
    Jm = {(int(j["entry_t"]), int(j.get("dir") or 0)): j for j in J if j.get("entry_t")}
    old = _jl_read(_p(store, "reviews.jsonl"))
    have = {r["key"] for r in old}
    new = []
    for row in rep.get("rows") or []:
        d = 1 if row.get("side") == "LONG" else -1
        twin = live = None
        if row.get("bt_entry") is not None:
            twin = {"entry_t": int(row["entry_t"]), "exit_t": row.get("exit_t"), "dir": d, "entry": row.get("bt_entry"),
                    "exit": row.get("bt_exit"), "exit_kind": _kind(row.get("bt_exit_reason")), "stop": row.get("bt_stop"),
                    "target": row.get("bt_target"), "qty": row.get("bt_qty"), "usd": row.get("bt_pnl"), "r": None, "day": row["day"]}
        if row["status"] in ("matched", "extra"):
            live = {"entry_t": int(row["entry_t"]), "exit_t": row.get("exit_t") or 0, "dir": d, "entry": row.get("fill_entry"),
                    "exit": row.get("live_exit"), "exit_kind": _kind(row.get("live_exit_kind")), "stop": row.get("live_stop"),
                    "target": row.get("live_target"), "qty": row.get("live_qty"), "usd": row.get("live_pnl"), "r": None,
                    "day": row["day"], "src": "pc"}
        for x in (live, twin):
            if x and x.get("entry") is not None and x.get("exit") is not None and x.get("stop") is not None:
                risk = abs(float(x["entry"]) - float(x["stop"]))
                x["r"] = round((float(x["exit"]) - float(x["entry"])) * d / risk, 3) if risk else None
                x["risk_pts"] = risk
        x = live or twin
        if x is None:
            continue
        key = f"lit_pc|{x['day']}|{int(x['entry_t'])}|{d}"
        if key in have and row["status"] != "matched":
            continue
        ck = None
        if checks:
            try:
                ck = lit_checks(x)
            except Exception:
                ck = None
        r = review("lit", live, twin, None, Jm.get((int(x["entry_t"]), d)), ck, now)
        r["key"], r["source"] = key, "pc"
        if row.get("reason"):
            r["notes"] = (r.get("notes") or []) + [str(row["reason"])[:160]]
        new.append(r)
    R = merge(old, new)
    if write and new:
        _jl_write(_p(store, "reviews.jsonl"), R)
    return R


def _jl_read(path) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def _jl_write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    os.replace(tmp, path)


def heartbeat_block(store=None) -> dict | None:
    """The heartbeat's "learn" block: the PC's learned costs (small) + its last routed-trade reviews."""
    C = _read_json(_p(store, "costs.json"), None)
    if not C:
        return None
    R = _jl_read(_p(store, "reviews.jsonl"))[-8:]
    slim = lambda r: {k: r.get(k) for k in ("key", "bot", "day", "entry_t", "side", "status", "gap_usd", "exec_usd", "cause", "notes")}
    return {"costs": {"t": C.get("t"), "bots": C.get("bots") or {}}, "recent": (C.get("recent") or [])[:6],
            "reviews": [slim(r) for r in R][::-1]}


def view(store=None) -> dict:
    """The PC dashboard's /api/next/pc/learning: costs, the PC reviews, the cloud's block when present, the switch."""
    from engine.lab_adapter import live_model
    lm = live_model()
    ls = lm.get("lit_sizing") or {}
    C = _read_json(_p(store, "costs.json"), None) or pc_update(store, write=False)
    R = _jl_read(_p(store, "reviews.jsonl"))
    try:
        from engine import lit_learn as LL
        L, J = LL.load_learning(), LL.load_journal()
    except Exception:
        L, J = None, []
    wk = {}
    for r in R:
        wk.setdefault(week_of(r["day"]), None)
    weekly = [weekly_summary(R, w) for w in sorted(wk)[-6:]][::-1]
    return {"v": VERSION, "learn_costs": bool(ls.get("learn_costs")), "costs": C, "reviews": R[-60:][::-1], "weekly": weekly,
            "totals": totals(R), "suggest": suggestions(L, J, C, bool(ls.get("learn_costs"))),
            "rule": "Learning changes nothing by itself except, with learn_costs on, a more conservative size when real fills "
                    "cost more than assumed. Entries, stops and targets never change."}


def main(argv=None) -> int:
    import sys
    a = list(argv if argv is not None else sys.argv[1:])
    cmd = a[0] if a else "show"
    if cmd == "costs":
        C = pc_update()
        for b, s in (C.get("bots") or {}).items():
            print(s.get("text"))
        return 0 if not C.get("error") else 1
    if cmd == "reviews":
        R = pc_reviews(checks="--checks" in a)
        print(f"{len(R)} review records -> {_p(None, 'reviews.jsonl')}")
        return 0
    print(json.dumps(view(), indent=1, default=str)[:20000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
