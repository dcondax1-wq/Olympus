"""AI watch (2026-10-22, owner: "add features that an AI trading bot needs to have"; research/writeups/ai-features.md).

What a serious automated futures bot watches about ITSELF, for LIT (MFFU 50K) and account B (ATLAS, engine/account_b.py).
Alerts are on; anything that could block an entry is OFF until the owner switches it on (live_model.json "guards").

  1. anomaly watch   ALERT ON. Each poll after routing (LiveBot._alerts_tick -> tick):
                     * bad tick / price spike on the last closed NinjaTrader 1m bar: a malformed bar (high < low, high below
                       the open / close, price <= 0), a range > max(SPIKE_K x the median range of the last 60 bars,
                       SPIKE_MIN_PTS), an open that jumps > max(SPIKE_K x median, GAP_MIN_PTS) from the previous close
                       (kind "anomaly");
                     * feed frozen MID-TRADE: LIT or account B holds a position, the market is open and the newest 1m bar
                       is > FREEZE_S old (kind "freeze", critical: repeats until "Got it" through alerts_plus.pc_conditions);
                     * slow route (latency): an entry routed > LATENCY_MAX_S after its signal bar (LIT: the 1m CISD close
                       = entry_t; account B: the 5m open) (kind "anomaly").
                     The broker-position mismatch already exists (guards reconcile, kind "unprotected").
     anomaly pause   OFF. guards "anomaly_pause": true -> no new entry (LIT and account B) for anomaly_pause_min (15) minutes
                     after a spike / bad tick, and while the feed is frozen mid-trade. Open trades keep their stop / target.
  2. drift monitor   ALERT ON. Live results vs the backtest's expected range, per strategy:
                     * LIT: the routed trades (data/lit_journal.jsonl source "pc") in the H2 band of engine/health_band
                       (bootstrap of run lit_live by sessions): below p5 -> "investigate" push, below p10 -> one "watch" push
                       a week (kind "drift");
                     * account B: its closed trades in R vs a bootstrap of the same number of trades from its research run
                       (research/runs/acctb_<plan>_<sizing>.json, 2026), same levels;
                     * execution: the fill audit's median signal -> route latency and entry slippage (logs/exec_audit/
                       summary.json) above LATENCY_MAX_S / SLIP_MAX_TICKS.
                     Reports only: it never sizes, pauses or changes a rule.
  3. loss caps       ALERT ON + BLOCK OFF. Both accounts together: today's routed P&L (LIT + account B) and this calendar
                     week's (per-day totals kept in data/ai_watch.json). Push at the caps (kind "loss_cap").
                     guards "combined_loss": true -> no new entry on either account once today <= -combined_day_usd
                     ($1,500) or the week <= -combined_week_usd ($3,000).
  4. rule-change log ALERT ON. engine/rulelog.py: who / when / why for every change of the trading files (git), and on the PC
                     a push when the rules the running bot trades change (kind "rules_change", logs/rule_changes.jsonl).
  5. readiness       the 01:40 ET pre-session push (engine/ops_checks) gets one more line from readiness_line(): today's
                     Tier-1 news, account B (name, room, problem), the blocks that are on, the auto-update state.

Switches (live_model.json "guards" or the start cfg "guards"; both OFF by default):
  "anomaly_pause": true, "anomaly_pause_min": 15         "combined_loss": true, "combined_day_usd": 1500, "combined_week_usd": 3000
Alerts: phone Settings > Alert levels (on / silent / off per kind: anomaly, freeze, drift, loss_cap, rules_change).
Everything here is failure-safe: no function raises into the bot's loop.
  python -X utf8 -m engine.ai_watch status     the PC bot's last AI-watch block (from the heartbeat file)
  python -X utf8 -m engine.ai_watch drift      the drift verdicts now (LIT from the journal, B from its state file)
Tests: tests/test_ai_features.py.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
STATE_NAME = "ai_watch.json"
JOURNAL = os.path.join(DATA, "lit_journal.jsonl")
EXEC_SUMMARY = os.path.join(ROOT, "logs", "exec_audit", "summary.json")
RUNS = os.path.join(ROOT, "research", "runs")
VERSION = 1

SPIKE_K = 8.0               # x the median 1m range of the last 60 bars
SPIKE_MIN_PTS = 60.0        # and never below this (NQ 1m ranges of 30-50 pts are normal at the 09:30 open / CPI)
GAP_MIN_PTS = 40.0          # an open this far from the previous close (consecutive 1m bars)
SPIKE_LOOKBACK = 60
FREEZE_S = 180              # newest 1m bar older than this while a trade is open
LATENCY_MAX_S = 30          # signal -> route (LIT routes ~3 s after the 1m CISD close)
SLIP_MAX_TICKS = 2.0        # median entry slippage (fill audit) worse than this
ANOMALY_KEEP = 20
DRIFT_EVERY_S = 1800
DRIFT_MIN_TRADES = 5
BOOT_REPS = 3000
GUARD_DEFAULTS = {"anomaly_pause": False, "anomaly_pause_min": 15,
                  "combined_loss": False, "combined_day_usd": 1500.0, "combined_week_usd": 3000.0}


# ============================================================================================ helpers
def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def week_of(day: str) -> str:
    d = dt.date.fromisoformat(day)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _money(x) -> str:
    x = float(x or 0)
    return ("-" if x < 0 else "+") + f"${abs(x):,.0f}"


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"), default=str)
        os.replace(tmp, path)
    except Exception:
        pass


def state_path(bot) -> str:
    """data/ai_watch.json next to data/live_state.json; another state file (test harness) gets <name>_ai.json beside it."""
    d, n = os.path.split(getattr(bot, "state_path", None) or os.path.join(DATA, "live_state.json"))
    return os.path.join(d, STATE_NAME if n == "live_state.json" else os.path.splitext(n)[0] + "_ai.json")


def _state(bot) -> dict:
    s = getattr(bot, "_ai", None)
    if not isinstance(s, dict):
        s = _read(state_path(bot), {}) or {}
        if not isinstance(s, dict):
            s = {}
        try:
            bot._ai = s
        except Exception:
            pass
    return s


def guard_cfg(bot) -> dict:
    """GUARD_DEFAULTS <- engine/guards.config (live_model.json "guards" <- start cfg "guards")."""
    try:
        from . import guards
        c = getattr(bot, "_guards_cfg", None) or guards.config(bot)
    except Exception:
        c = {}
    return {**GUARD_DEFAULTS, **{k: v for k, v in (c or {}).items() if k in GUARD_DEFAULTS}}


# ============================================================================================ 1. anomalies
def bar_anomaly(df1, k: float = SPIKE_K, min_pts: float = SPIKE_MIN_PTS, gap_pts: float = GAP_MIN_PTS) -> dict | None:
    """The last closed 1m bar of df1 (time, open, high, low, close): a malformed bar, a spike or a jump, else None. Pure."""
    try:
        if df1 is None or len(df1) < 2:
            return None
        tail = df1.tail(SPIKE_LOOKBACK + 1)
        t = [int(x) for x in tail["time"]]
        o, h, lo, c = (list(map(float, tail[x])) for x in ("open", "high", "low", "close"))
    except Exception:
        return None
    i = len(t) - 1
    bt = t[i]
    if min(o[i], h[i], lo[i], c[i]) <= 0 or h[i] < lo[i] or h[i] < max(o[i], c[i]) - 1e-9 or lo[i] > min(o[i], c[i]) + 1e-9:
        return {"id": f"badtick:{bt}", "t": bt, "what": "bad tick",
                "text": f"malformed 1m bar at {_et(bt):%H:%M} ET (O {o[i]:,.2f} H {h[i]:,.2f} L {lo[i]:,.2f} C {c[i]:,.2f})"}
    rng = sorted(h[j] - lo[j] for j in range(i))
    med = rng[len(rng) // 2] if rng else 0.0
    lim = max(k * med, float(min_pts))
    r = h[i] - lo[i]
    if r > lim:
        return {"id": f"spike:{bt}", "t": bt, "what": "price spike",
                "text": f"1m bar at {_et(bt):%H:%M} ET spans {r:,.1f} pts (median {med:,.1f}, limit {lim:,.0f})"}
    if t[i] - t[i - 1] == 60:
        gap = abs(o[i] - c[i - 1])
        glim = max(k * med, float(gap_pts))
        if gap > glim:
            return {"id": f"jump:{bt}", "t": bt, "what": "price jump",
                    "text": f"1m bar at {_et(bt):%H:%M} ET opened {gap:,.1f} pts from the previous close (limit {glim:,.0f})"}
    return None


def in_trade(bot) -> list:
    """Which accounts hold a position now: ["LIT"], ["account B"], both or []."""
    out = []
    try:
        st = getattr(bot, "state", None) or {}
        if st.get("position") or getattr(bot, "_open_routed", None) is not None:
            out.append("LIT")
    except Exception:
        pass
    b = getattr(bot, "acct_b", None)
    if b is not None and getattr(b, "open_t", None) is not None:
        out.append(getattr(b, "label", None) or "account B")
    return out


def freeze_check(bot, now, freeze_s: int = FREEZE_S) -> dict | None:
    """A position open, the market open, the newest 1m bar older than freeze_s: the feed froze mid-trade."""
    try:
        h = getattr(bot, "health", None) or {}
        if not h.get("market_open"):
            return None
        who = in_trade(bot)
        if not who:
            return None
        last = h.get("last_1m_bar_t") or h.get("last_bar_t")
        if not last:
            return None
        age = int(now) - (int(last) + 60)
        if age <= freeze_s:
            return None
        return {"id": f"freeze:{trading_day(now)}:{int(last)}", "t": int(now), "what": "feed frozen in a trade", "age_s": age,
                "text": f"newest 1m bar {age // 60} min old while {' and '.join(who)} hold{'s' if len(who) == 1 else ''} a position"}
    except Exception:
        return None


def latency_rows(bot) -> list:
    """(label, entry_t, route_t) for every routed entry in the LIT and account B ledgers."""
    out = []
    for lab, led in (("LIT", getattr(bot, "ledger", None)),
                     ("account B", getattr(getattr(bot, "acct_b", None), "ledger", None))):
        for r in led or []:
            try:
                if r.get("side") in ("buy", "sell") and r.get("entry_t") and r.get("t") and (r.get("result") or {}).get("ok") is not False:
                    out.append((r.get("strategy") or lab, int(r["entry_t"]), int(r["t"])))
            except Exception:
                continue
    return out


def latency_check(rows, now, max_s: int = LATENCY_MAX_S) -> list:
    out = []
    for lab, et_, rt in rows:
        lat = rt - et_
        if lat > max_s and 0 <= int(now) - rt <= 3600:
            out.append({"id": f"latency:{et_}", "t": rt, "what": "slow route", "lat_s": lat,
                        "text": f"{lab} entry of {_et(et_):%H:%M} ET routed {lat} s after its signal (normal ~3 s, limit {max_s} s)"})
    return out


# ============================================================================================ 3. loss caps (both accounts)
def day_totals(bot, now) -> dict:
    day = trading_day(now)
    lit = 0.0
    try:
        lit = float(bot.day_pnl_routed())
    except Exception:
        pass
    b = 0.0
    ab = getattr(bot, "acct_b", None)
    if ab is not None:
        try:
            b = float(ab.day_pnl(day))
        except Exception:
            pass
    return {"day": day, "lit": round(lit, 2), "b": round(b, 2), "total": round(lit + b, 2)}


def combined(bot, now, s: dict | None = None) -> dict:
    """{"day", "lit", "b", "total" (today), "week" (this calendar week incl. today)}."""
    s = _state(bot) if s is None else s
    d = day_totals(bot, now)
    wk = week_of(d["day"])
    past = sum(float((v or {}).get("total") or 0) for k, v in (s.get("days") or {}).items() if k != d["day"] and week_of(k) == wk)
    return {**d, "week": round(past + d["total"], 2), "iso_week": wk}


def combined_problem(bot, c: dict, now) -> str | None:
    """guards hook (OFF unless "combined_loss": true): a reason when both accounts together hit the day / week cap."""
    if not c.get("combined_loss"):
        return None
    try:
        x = combined(bot, now)
        dl, wl = float(c.get("combined_day_usd") or 1500), float(c.get("combined_week_usd") or 3000)
        if x["total"] <= -dl:
            return f"both accounts today {_money(x['total'])} reached the ${dl:,.0f} combined daily cap"
        if x["week"] <= -wl:
            return f"both accounts this week {_money(x['week'])} reached the ${wl:,.0f} combined weekly cap"
    except Exception:
        return None
    return None


def anomaly_problem(bot, c: dict, now) -> str | None:
    """guards hook (OFF unless "anomaly_pause": true): a reason while a fresh anomaly / a frozen feed in a trade is active."""
    if not c.get("anomaly_pause"):
        return None
    try:
        s = _state(bot)
        mins = float(c.get("anomaly_pause_min") or 15)
        a = s.get("pause_from") or {}
        if a.get("t") and int(now) - int(a["t"]) < mins * 60:
            return f"anomaly pause: {a.get('what')} at {_et(a['t']):%H:%M} ET (no new entry for {mins:.0f} min)"
        fz = freeze_check(bot, now)
        if fz:
            return f"anomaly pause: {fz['text']}"
    except Exception:
        return None
    return None


# ============================================================================================ 2. drift
def boot_pct(pool: list, live_sum: float, n: int, reps: int = BOOT_REPS, seed: int = 20261022) -> float | None:
    """Percentile of live_sum among `reps` sums of n draws (with replacement) from pool. Pure, seeded."""
    if not pool or n <= 0:
        return None
    import numpy as np
    rng = np.random.default_rng(seed)
    sums = np.asarray(pool, float)[rng.integers(0, len(pool), size=(reps, n))].sum(axis=1)
    return round(float((sums < live_sum).mean() * 100 + (sums == live_sum).mean() * 50), 1)


def level(p) -> str | None:
    if p is None:
        return None
    return "bad" if p < 5 else "warn" if p < 10 else "good"


def drift_lit(journal_rows=None, now=None, B=None) -> dict | None:
    """LIT's routed trades in the H2 band (engine/health_band.compare). None before the first finished session."""
    try:
        from . import health_band as HB
        B = HB.load() if B is None else B
        if not B:
            return None
        if journal_rows is None:
            journal_rows = []
            try:
                with open(JOURNAL, encoding="utf-8") as fh:
                    for ln in fh:
                        if '"source":"pc"' in ln or '"source": "pc"' in ln:
                            journal_rows.append(json.loads(ln))
            except OSError:
                pass
        _, live = HB.from_state(None, journal_rows)
        now = int(now or time.time())
        e = _et(now)
        over = e.hour * 60 + e.minute >= 16 * 60 + 5 or e.weekday() >= 5
        c = HB.compare(B, live, B.get("lit_start") or HB.LIT_START, trading_day(now), "H2", "LIT live", over)
        if not c or not c.get("trades"):
            return {"strategy": "LIT", "trades": 0, "level": None, "text": (c or {}).get("text") or "LIT live: no trade yet"}
        return {"strategy": "LIT", "trades": c.get("trades"), "sessions": c.get("sessions"), "pct": c.get("pct_r"),
                "level": c.get("level"), "text": c.get("text"), "r": c.get("r")}
    except Exception as e:
        return {"strategy": "LIT", "level": None, "error": f"{e.__class__.__name__}: {e}"}


def b_run_id(spec: dict) -> str:
    plan = str((spec or {}).get("plan") or "builder25k").replace("builder", "")
    return f"acctb_{plan}_{(spec or {}).get('sizing') or 'need'}"


def b_pool(spec: dict, runs_dir: str = RUNS) -> list:
    """Account B's backtest R per trade (2026) from its research run; [] when the run is missing."""
    r = _read(os.path.join(runs_dir, b_run_id(spec) + ".json"))
    if not r:
        return []
    try:
        c = r["trade_cols"]
        i_d, i_r = c.index("day"), c.index("r")
        return [float(t[i_r]) for t in r["trades"] if str(t[i_d]) >= "2026-01-01" and t[i_r] is not None]
    except Exception:
        return []


def b_live_r(ab) -> list:
    """Account B's closed trades in R: pnl / (stop points x micros x $2 + $1.90 a micro). Trades without a plan are skipped."""
    out = []
    for c in list(getattr(ab, "closes", None) or []):
        try:
            pnl, et_ = float(c[2]), int(c[3]) if len(c) > 3 else None
            pv = (getattr(ab, "prov", None) or {}).get(et_) or (getattr(ab, "prov", None) or {}).get(str(et_)) or {}
            q, rp = int(pv.get("qty") or 0), float(pv.get("risk_pts") or 0)
            if q > 0 and rp > 0:
                out.append(round(pnl / (rp * q * 2.0 + 1.90 * q), 3))
        except Exception:
            continue
    return out


def drift_b(ab, runs_dir: str = RUNS) -> dict | None:
    if ab is None:
        return None
    try:
        R = b_live_r(ab)
        pool = b_pool(getattr(ab, "spec", None) or {}, runs_dir)
        lab = getattr(ab, "label", None) or "Account B"
        if len(R) < DRIFT_MIN_TRADES or not pool:
            why = "no research run" if not pool else f"{len(R)} trade{'s' if len(R) != 1 else ''} (needs {DRIFT_MIN_TRADES})"
            return {"strategy": lab, "trades": len(R), "level": None, "text": f"{lab}: too early to judge ({why})"}
        p = boot_pct(pool, sum(R), len(R))
        lv = level(p)
        txt = (f"{lab}: {sum(R):+.1f}R in {len(R)} trades, p{p:.0f} of the backtest "
               + ("(inside the expected range)" if lv == "good" else "(low end: watch)" if lv == "warn" else "(below p5: investigate)"))
        return {"strategy": lab, "trades": len(R), "pct": p, "level": lv, "r": round(sum(R), 2), "text": txt,
                "run": b_run_id(getattr(ab, "spec", None) or {})}
    except Exception as e:
        return {"strategy": "Account B", "level": None, "error": f"{e.__class__.__name__}: {e}"}


def drift_exec(summary: dict | None = None) -> dict | None:
    """The fill audit's medians: signal -> route latency and entry slippage."""
    S = _read(EXEC_SUMMARY) if summary is None else summary
    if not isinstance(S, dict):
        return None
    tot = S.get("totals") if isinstance(S.get("totals"), dict) else S
    lat, slip, n = tot.get("latency_s_med"), tot.get("entry_slip_ticks_med"), tot.get("trades")
    if lat is None and slip is None:
        return None
    bad = [x for x in ((f"median route latency {lat:.0f} s" if lat is not None and lat > LATENCY_MAX_S else None),
                       (f"median entry slippage {slip:.1f} ticks" if slip is not None and slip > SLIP_MAX_TICKS else None)) if x]
    return {"strategy": "Execution", "level": "warn" if bad else "good", "latency_s_med": lat, "slip_ticks_med": slip, "matched": n,
            "text": ("Execution drift: " + ", ".join(bad)) if bad else
                    f"Execution in line (median latency {lat if lat is not None else '-'} s, slippage {slip if slip is not None else '-'} ticks)"}


def drift_notices(drifts: list, s: dict, now) -> list:
    """bad -> one push per (strategy, trade count); warn -> one push per strategy per week."""
    from . import push
    out = []
    wk = week_of(trading_day(now))
    for d in drifts or []:
        if not d or d.get("level") not in ("bad", "warn"):
            continue
        nm = str(d.get("strategy") or "?")
        key = (f"ai:drift:{nm}:{d.get('trades')}:bad" if d["level"] == "bad" else f"ai:drift:{nm}:{wk}:warn")
        if key in (s.get("sent") or []):
            continue
        s.setdefault("sent", []).append(key)
        title = (f"Drift: {nm} below the expected range" if d["level"] == "bad" else f"Drift watch: {nm}")
        body = d.get("text", "") + (" Nothing was changed: check the trades in the app (Data > Performance) before acting."
                                    if d["level"] == "bad" else " Reports only.")
        out.append(push.text_payload("PC", "drift", title, body, key=key, t=int(now), url="#/aiwatch"))
    return out


# ============================================================================================ 4. rule changes (runtime)
def rules_snapshot(bot=None) -> dict:
    """What the running bot trades: live_model.json lit / lit_sizing / guards / model + second_model.json account_b and the
    strategies' on / route. Never raises."""
    out = {}
    try:
        from .lab_adapter import live_model
        lm = live_model()
        out["model"] = lm.get("model")
        out["lit"] = lm.get("lit")
        out["lit_sizing"] = {k: v for k, v in (lm.get("lit_sizing") or {}).items() if k != "eval_start"}
        out["guards"] = lm.get("guards") or {}
    except Exception:
        pass
    try:
        cfg = (getattr(bot, "cfg", None) or {}) if bot is not None else {}
        for k in ("model_params", "lit_sizing", "guards"):
            if cfg.get(k):
                out["start_cfg." + k] = cfg[k]
    except Exception:
        pass
    try:
        sm = _read(os.path.join(ROOT, "second_model.json"), {}) or {}
        out["second"] = {"account_b": sm.get("account_b"),
                         "strategies": {k: {"on": v.get("on", True), "route": v.get("route", False)}
                                        for k, v in (sm.get("strategies") or {}).items() if isinstance(v, dict)}}
    except Exception:
        pass
    return json.loads(json.dumps(out, default=str))


def rules_step(bot, s: dict, now, snap: dict | None = None) -> list:
    """Compare the running rules with the last seen; a change -> logs/rule_changes.jsonl + a push. First call = baseline."""
    from . import push, rulelog
    snap = rules_snapshot(bot) if snap is None else snap
    prev = s.get("rules_snap")
    s["rules_snap"] = snap
    if prev is None or prev == snap:
        return []
    ch = rulelog.diff(prev, snap)
    if not ch:
        return []
    who = rulelog.head_commit()
    row = {"t": int(now), "changes": ch[:40], "commit": who, "src": "pc"}
    rulelog.append_runtime(row, path=s.get("_rule_log_path"))
    s.setdefault("rule_changes", []).append({"t": int(now), "changes": ch[:6], "commit": who})
    s["rule_changes"] = s["rule_changes"][-10:]
    head = "; ".join(ch[:3]) + (f" (+{len(ch) - 3} more)" if len(ch) > 3 else "")
    by = f" Commit {who.get('sha', '')[:7]} by {who.get('who', '?')}: {who.get('why', '')[:80]}." if who else ""
    return [push.text_payload("PC", "rules_change", "Trading rules changed on the PC", f"{head}.{by}"[:600],
                              key=f"ai:rules:{int(now)}", t=int(now), url="#/aiwatch")]


# ============================================================================================ the tick
def tick(bot, now=None, send=None, df1=None, path: str | None = None) -> list:
    """Once per poll after routing (the real bot: LiveBot._alerts_tick). Returns the payloads sent. Never raises."""
    out = []
    try:
        now = int(now or time.time())
        s = _state(bot)
        if send is None:
            from . import alerts_plus
            send = alerts_plus.pc_send
        from . import push
        sent = s.setdefault("sent", [])
        notes = []
        # 1. anomalies
        if df1 is None:
            try:
                sym = (getattr(bot, "cfg", None) or {}).get("sym", "NQ")
                df1 = (getattr(bot, "_nt_last", None) or {}).get((sym, "1m"))
            except Exception:
                df1 = None
        found = []
        a = bar_anomaly(df1)
        if a and int(now) - int(a["t"]) <= 600:
            found.append(a)
            if a["id"] not in sent:
                s["pause_from"] = {"t": int(now), "what": a["what"], "id": a["id"]}
        found += latency_check(latency_rows(bot), now)
        fz = freeze_check(bot, now)
        s["freeze"] = fz
        for x in found:
            if x["id"] in sent:
                continue
            sent.append(x["id"])
            s.setdefault("anomalies", []).append({k: x.get(k) for k in ("id", "t", "what", "text")})
            c = guard_cfg(bot)
            tail = (f" New entries paused {int(c['anomaly_pause_min'])} min (anomaly_pause on)." if c.get("anomaly_pause") and x["what"] != "slow route"
                    else " Alert only: nothing was blocked.")
            notes.append(push.text_payload("PC", "anomaly", f"Anomaly: {x['what']}", x["text"] + "." + tail, key=f"ai:{x['id']}", t=now,
                                           url="#/aiwatch"))
        if fz and fz["id"] not in sent:
            sent.append(fz["id"])
            s.setdefault("anomalies", []).append({k: fz.get(k) for k in ("id", "t", "what", "text")})
        s["anomalies"] = (s.get("anomalies") or [])[-ANOMALY_KEEP:]
        # 3. loss caps (both accounts)
        x = combined(bot, now, s)
        s.setdefault("days", {})[x["day"]] = {"lit": x["lit"], "b": x["b"], "total": x["total"]}
        s["days"] = {k: s["days"][k] for k in sorted(s["days"])[-21:]}
        s["loss"] = x
        c = guard_cfg(bot)
        for lab, v, cap, k in (("today", x["total"], float(c["combined_day_usd"]), f"ai:loss:day:{x['day']}"),
                               ("this week", x["week"], float(c["combined_week_usd"]), f"ai:loss:week:{x['iso_week']}")):
            if v <= -cap and k not in sent:
                sent.append(k)
                notes.append(push.text_payload("PC", "loss_cap", f"Both accounts {_money(v)} {lab}",
                                               f"LIT {_money(x['lit'])}, account B {_money(x['b'])} today; the combined {lab} cap is ${cap:,.0f}. "
                                               + ("New entries on both accounts are blocked (combined_loss on)." if c.get("combined_loss")
                                                  else "Alert only (combined_loss off): the bot keeps trading."), key=k, t=now, url="#/aiwatch"))
        # 2. drift (every 30 min, or when a trade closed)
        nclose = len([r for r in getattr(bot, "ledger", None) or [] if r.get("side") == "exit"]) + \
            len(getattr(getattr(bot, "acct_b", None), "closes", None) or [])
        if now - int(s.get("drift_t") or 0) >= DRIFT_EVERY_S or nclose != s.get("drift_n"):
            s["drift_t"], s["drift_n"] = now, nclose
            dr = [drift_lit(now=now), drift_b(getattr(bot, "acct_b", None)), drift_exec()]
            s["drift"] = [d for d in dr if d]
            notes += drift_notices(s["drift"], s, now)
        # 4. rules
        try:
            notes += rules_step(bot, s, now)
        except Exception as e:
            s["rules_error"] = f"{e.__class__.__name__}: {e}"[:160]
        s["sent"] = sent[-300:]
        s["t"] = now
        for p in notes:
            try:
                send(p)
            except Exception:
                pass
            out.append(p)
        _write(path or state_path(bot), {k: v for k, v in s.items() if not k.startswith("_")})
    except Exception as e:
        try:
            bot._note_error(f"ai watch failed: {e.__class__.__name__}: {e}")
        except Exception:
            pass
    return out


def crit_conditions(bot, now=None) -> list:
    """For alerts_plus.pc_conditions: the feed frozen mid-trade is critical (repeats until "Got it")."""
    try:
        fz = freeze_check(bot, int(now or time.time()))
        if fz:
            return [{"id": fz["id"], "kind": "freeze", "title": "FEED FROZEN in a trade",
                     "body": fz["text"] + ". The broker stop / target still protect it; check NinjaTrader's chart and connection now."}]
    except Exception:
        pass
    return []


def hb_block(bot, now=None) -> dict | None:
    """The heartbeat / live.json "ai" block (small). None before the first tick."""
    try:
        s = getattr(bot, "_ai", None)
        if not isinstance(s, dict) or not s.get("t"):
            return None
        c = guard_cfg(bot)
        ab = getattr(bot, "acct_b", None)
        bi = None
        if ab is not None:
            try:
                ev = ab.eval_view()
                bi = {"label": getattr(ab, "label", None), "account": getattr(ab, "name", None), "room": ev.get("room"),
                      "status": ev.get("status"), "problem": getattr(ab, "problem", None)}
            except Exception:
                bi = {"label": getattr(ab, "label", None), "problem": "no eval view"}
        return {"v": VERSION, "t": s.get("t"), "anomalies": (s.get("anomalies") or [])[-6:], "freeze": s.get("freeze"),
                "drift": s.get("drift") or [], "loss": s.get("loss"), "rule_changes": (s.get("rule_changes") or [])[-5:],
                "switches": {k: c.get(k) for k in GUARD_DEFAULTS}, "acct_b": bi, "rule_log": rule_log_compact(bot)}
    except Exception:
        return None


def rule_log_compact(bot=None, n: int = 5, every_s: int = 3600) -> list:
    """The last n commits that changed a trading file (engine/rulelog.history), refreshed hourly: for the phone."""
    try:
        c = getattr(bot, "_ai_rl", None) if bot is not None else None
        if c and time.time() - c[0] < every_s:
            return c[1]
        from . import rulelog
        H = [{"when": h["when"][:16], "who": h["who"], "why": h["why"][:120],
              "changes": [x for v in h["files"].values() for x in v][:4], "n": h["n"]} for h in rulelog.history(15)[:n]]
        if bot is not None:
            try:
                bot._ai_rl = (time.time(), H)
            except Exception:
                pass
        return H
    except Exception:
        return []


# ============================================================================================ 5. readiness + weekly lines
def news_today(now, events=None) -> list:
    """Today's Tier-1 (high impact) releases 01:00-16:00 ET: ["08:30 CPI", ...]."""
    try:
        if events is None:
            from . import news
            events = news.historical_events(("high",))
        day = _et(now).strftime("%Y-%m-%d")
        return [f"{e.get('time_et') or _et(e['t']).strftime('%H:%M')} {e.get('event')}" for e in events
                if _et(e["t"]).strftime("%Y-%m-%d") == day and 1 <= _et(e["t"]).hour < 16][:4]
    except Exception:
        return []


def readiness_line(hb: dict | None, now, events=None) -> str:
    """One more line for the 01:40 ET pre-session push: news, account B, blocks on, AI-watch state, auto-update."""
    parts = []
    nw = news_today(now, events)
    parts.append("News: " + ", ".join(nw) if nw else "No Tier-1 news today")
    ai = (hb or {}).get("ai") if isinstance((hb or {}).get("ai"), dict) else None
    if ai:
        b = ai.get("acct_b")
        if b:
            if b.get("problem"):
                parts.append(f"{b.get('label') or 'Account B'}: {str(b['problem'])[:80]}")
            else:
                parts.append(f"{b.get('label') or 'Account B'} room ${float(b.get('room') or 0):,.0f} ({b.get('status') or '?'})")
        on = [k for k, v in (ai.get("switches") or {}).items() if v is True]
        parts.append("Blocks on: " + ", ".join(on) if on else "AI watch: alerts only")
        if ai.get("freeze"):
            parts.append("FEED FROZEN in a trade")
    try:
        from . import autoupdate
        u = autoupdate.status()
        if u.get("result") in ("failed", "rolled_back"):
            parts.append(f"auto-update {u['result']}")
    except Exception:
        pass
    return ". ".join(parts) + "."


def weekly_line(hb: dict | None) -> str:
    """For the Sunday weekly push: the drift verdicts and this week's anomalies / rule changes."""
    ai = (hb or {}).get("ai") if isinstance((hb or {}).get("ai"), dict) else None
    if not ai:
        return ""
    bits = []
    for d in ai.get("drift") or []:
        if d.get("level"):
            bits.append(f"{d.get('strategy')} {'in range' if d['level'] == 'good' else 'watch' if d['level'] == 'warn' else 'INVESTIGATE'}"
                        + (f" (p{d['pct']:.0f})" if d.get("pct") is not None else ""))
    n_a = len(ai.get("anomalies") or [])
    n_r = len(ai.get("rule_changes") or [])
    if n_a:
        bits.append(f"{n_a} anomal{'y' if n_a == 1 else 'ies'} logged")
    if n_r:
        bits.append(f"{n_r} rule change{'s' if n_r != 1 else ''}")
    return ("Self-review: " + "; ".join(bits) + ".") if bits else ""


def ops_checks(hb: dict | None, now) -> list:
    """Extra rows for the health screen (engine/ops_checks.run_checks): account B readiness."""
    ai = (hb or {}).get("ai") if isinstance((hb or {}).get("ai"), dict) else None
    b = (ai or {}).get("acct_b")
    if not b:
        return []
    if b.get("problem"):
        return [{"key": "acct_b", "name": "Account B", "level": "bad", "text": str(b["problem"])[:160],
                 "fix": "Check the account Name in NinjaTrader (Control Center > Accounts) and second_model.json account_b."}]
    room = b.get("room")
    lvl = "warn" if room is not None and float(room) < 400 else "ok"
    return [{"key": "acct_b", "name": "Account B", "level": lvl,
             "text": f"{b.get('label') or 'Account B'} on {b.get('account') or '?'}: room ${float(room or 0):,.0f}, {b.get('status') or '?'}",
             "fix": "Room under $400: one stop-out can end it." if lvl == "warn" else ""}]


# ============================================================================================ CLI
def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="python -m engine.ai_watch")
    ap.add_argument("what", choices=("status", "drift"), nargs="?", default="status")
    a = ap.parse_args(argv)
    if a.what == "drift":
        print(json.dumps([drift_lit(), drift_exec()], indent=1, default=str))
        return 0
    hb = _read(os.path.join(ROOT, "logs", "heartbeat_last.json"), {}) or {}
    print(json.dumps((hb.get("payload") or hb).get("ai"), indent=1, default=str))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
