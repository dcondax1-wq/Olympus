"""The nightly self-learning loop (owner 2026-11-15: "an Olympian AI that constantly learns and improves everything",
without spending Claude usage). Runs FREE on the owner's Windows PC after the close. docs/LEARN_LOOP.md (plain words).

RESEARCH ONLY. It never trades, never routes, never changes a live setting: live_model*.json, second_model.json,
data/account_b.json and research/lit/lit_final.json are hashed before and after every run (a change = the run is marked
broken and nothing is pushed). Adoption stays a human + Claude decision (CLAUDE.md "Strategy changes").

Built on what exists (nothing re-implemented):
  (a) refresh   LIT: tools/lit_edge.evaluate (run lit_live re-walked: LIT size, the live two_week eval path, eval speed);
                the newest bars incl. the PC's NinjaTrader archive (engine/fill_audit.load_bars = TradingView exports +
                data/nt_bars merged on one basis) through engine/lit_live.run (the live loop's own twin of the last weeks).
                ATLAS: tools/atlas_deep.score (the real account-B rules, $43 25K) + engine/second.run on the same merged bars.
  (b) drift     engine/live_learning's trade reviews (logs/learning/reviews.jsonl: live / paper fills vs the backtest twin),
                its weekly summary and the learned costs, plus: does tonight's twin on the newest bars still show the trade
                each review compared against ("backtest moved")? One line a night -> research/learn/drift.jsonl.
  (c) queue     research/learn_queue.json: pre-registered experiments (written before their first run), at most NIGHT_MAX a
                night, inside a CPU budget, at below-normal priority. Judged by the project's gates:
                  LIT   tools/lit_edge.gate (more $ in 2026 H1 = pick AND H2 = check at the LIT size and on the live eval
                        path, no rise in 2-week fails, 2+ trades a week) + 2-4 trades a week + enough trades changed in each
                        half + a 200-draw shuffle placebo (p <= 0.2 in both halves); 2021-25 is a reference line (CLAUDE.md
                        LIT exception).
                  ATLAS tools/atlas_v2.verdict (better in H1 AND H2, 2025 + 2021-24 not losing, 2+ signals a week) + enough
                        trades changed. Costs are in both executors. Eval speed (p10 / f10, dec10, p15 / f15, slow_pass,
                        pass_med) is stored next to the $ for every run.
                Results are re-checked on fresh data: once every experiment has run on the current data, the oldest is
                re-run when the data or the live settings changed.
  (d) report    research/learn/summary.json (small) + research/learn/latest.md (one page) + history.jsonl; a phone line
                (the PC's private ntfy topic, tools/pc_report) ONLY when an experiment newly becomes a candidate:
                "Candidate: X, +$Y/month in both halves - review".
research/learn/ is machine-local (gitignored): the PC's auto-update needs a clean tree (docs/AUTO_UPDATE.md).

Schedule: tools/pc_report.py (the PC's 15-minute task, already installed by BOTS_BACK.bat) calls maybe_run(): weekdays
from 17:00 ET to midnight, Saturday, Sunday until 17:00 ET; once a learn day; never while a trade / bracket / pending
entry is open; only on Windows (LE_LEARN=1 forces it elsewhere, LE_LEARN=0 turns it off). It starts one detached child
(below-normal priority, no window, one thread for numpy) and returns at once.

    python -X utf8 -m engine.learn_loop status          # what ran, the queue, the candidates
    python -X utf8 -m engine.learn_loop run [--budget S] [--max N] [--force]   # one night by hand (--force: skip the clock guard)
    python -X utf8 -m engine.learn_loop guard           # would it run now, and why not
    python -X utf8 -m tests.test_learn_loop             # fast checks (no data run)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
VERSION = 1
QUEUE_PATH = os.path.join(ROOT, "research", "learn_queue.json")
OUT_DIR = os.path.join(ROOT, "research", "learn")              # gitignored (machine-local)
PROTECTED = ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json", "data/account_b.json",
             "research/lit/lit_final.json")
DATA_FILES = ("data/NQ_5m.csv", "data/NQ_1m.csv", "data/nt_bars/NQ_5m.csv", "data/nt_bars/NQ_1m.csv",
              "data/nt_bars/MNQ_5m.csv", "data/nt_bars/MNQ_1m.csv")
NIGHT_MAX = 2                         # experiments a night
BUDGET_S = 1800                       # the child's soft budget (checked between steps); hard stop at 2x
WEEKDAY_FROM = 17 * 60                # ET minute: weekdays from 17:00 (after the 16:00 close and the 17:00 pause)
SUNDAY_UNTIL = 17 * 60                # Sunday: until 17:00 ET (Globex opens 18:00)
STALE_LOCK_S = 3 * 3600
MAX_TRIES = 3                         # starts a day (a crashing child is not restarted every 15 minutes)
PLACEBO_N = 200
PLACEBO_MAX = 0.2
MIN_HIT = {"H1": 5, "H2": 3}          # trades the rule must change in each 2026 half to be trusted
TPW = (2.0, 4.0)                      # CLAUDE.md frequency: 2-4 trades a week
DRIFT_WEEKS = 4
STATUSES = ("candidate", "rejected", "error", "pending")


# ================================================================================================ small helpers
def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, default=str, separators=None if indent else (",", ":"))
    from .fsutil import replace as _rep       # retried on a Windows / OneDrive lock (tests.test_selfheal)
    _rep(tmp, path)


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, default=str, separators=(",", ":")) + "\n")


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def learn_day(now) -> str:
    """The learn day = the ET calendar date (one run per date)."""
    return _et(now).strftime("%Y-%m-%d")


def _num(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _money(x) -> str:
    x = float(x or 0)
    return f"{'+' if x >= 0 else '-'}${abs(x):,.0f}"


# ================================================================================================ the guard
def window_ok(now) -> tuple:
    """(ok, why): weekdays from 17:00 ET, Saturday, Sunday until 17:00 ET."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    wd = e.weekday()
    if wd <= 4:
        return (True, "after the close") if m >= WEEKDAY_FROM else (False, "before 17:00 ET on a trading day")
    if wd == 5:
        return True, "Saturday"
    return (True, "Sunday before the open") if m < SUNDAY_UNTIL else (False, "Sunday after 17:00 ET (the week opens at 18:00)")


def _has_position(x, depth=0) -> bool:
    """Any truthy "position" / "open_routed" in the bot's snapshot (LIT, ATLAS account B, BLITZ account C)."""
    if depth > 4:
        return False
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("position", "open_routed") and v:
                return True
            if isinstance(v, (dict, list)) and k not in ("log", "ledger", "trades", "history", "seen"):
                if _has_position(v, depth + 1):
                    return True
    elif isinstance(x, list):
        return any(_has_position(v, depth + 1) for v in x[:50])
    return False


def _http_get(url, timeout=4.0):
    if os.environ.get("LE_PR_NO_NET") == "1" or os.environ.get("LE_LEARN_NO_HTTP") == "1":
        return None
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read(2_000_000).decode("utf-8", "replace"))
    except Exception:
        return None


def trade_open(root: str = ROOT, port: int = 8766, http=None, now=None) -> str | None:
    """Why the bot is NOT flat (None = flat). The running server's state first (engine/autoupdate.flat_reason + any
    account's position), else the files (engine/autoupdate.files_flat_reason). Unsure = not flat."""
    get = http or _http_get
    snap = get(f"http://127.0.0.1:{int(port)}/api/live/state")
    if isinstance(snap, dict):
        try:
            from .autoupdate import flat_reason
            r = flat_reason(snap.get("state"), snap.get("open_routed"), None, bool(snap.get("running")))
        except Exception:
            r = None
        if r:
            return r
        if _has_position(snap):
            return "a position is open (bot state)"
        return None
    try:
        from .autoupdate import files_flat_reason
        return files_flat_reason(root, now)
    except Exception as e:
        return f"cannot tell if flat ({e.__class__.__name__})"


def _lock_path(out_dir):
    return os.path.join(out_dir, "running.json")


def _pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return code.value == 259                                      # STILL_ACTIVE
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def guard(now=None, out_dir: str = OUT_DIR, root: str = ROOT, env=None, open_fn=None, force=False) -> tuple:
    """(ok, why) for tonight's run: switch, platform, clock window, once a learn day, not already running, flat."""
    e = os.environ if env is None else env
    now = int(now if now is not None else time.time())
    sw = str(e.get("LE_LEARN", "")).strip()
    if sw == "0":
        return False, "switched off (LE_LEARN=0)"
    if os.name != "nt" and sw != "1" and not force:
        return False, "runs on the Windows PC only (LE_LEARN=1 forces it)"
    if not force:
        ok, why = window_ok(now)
        if not ok:
            return False, why
        st = _read_json(os.path.join(out_dir, "state.json"), {}) or {}
        if st.get("day") == learn_day(now):
            return False, "already ran today"
        if (st.get("tries") or {}).get(learn_day(now), 0) >= MAX_TRIES:
            return False, f"started {MAX_TRIES} times today without finishing: see research/learn/learn.log"
    lk = _read_json(_lock_path(out_dir), None)
    if isinstance(lk, dict) and now - int(lk.get("t") or 0) < STALE_LOCK_S and _pid_alive(lk.get("pid")):
        return False, "already running"
    why = (open_fn or (lambda: trade_open(root, now=now)))()
    if why:
        return False, f"skipped: {why}"
    return True, "ok"


# ================================================================================================ safety
def protected_hashes(root: str = ROOT) -> dict:
    out = {}
    for rel in PROTECTED:
        p = os.path.join(root, rel)
        try:
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[rel] = None
    return out


def data_key(root: str = ROOT) -> str:
    """Changes when the bars (exports or the NinjaTrader archive) or the live settings change: results go stale."""
    h = hashlib.sha1()
    for rel in DATA_FILES:
        p = os.path.join(root, rel)
        try:
            s = os.stat(p)
            h.update(f"{rel}:{s.st_size}:{int(s.st_mtime)}".encode())
        except OSError:
            h.update(f"{rel}:-".encode())
    for rel, v in sorted(protected_hashes(root).items()):
        h.update(f"{rel}:{v}".encode())
    return h.hexdigest()[:16]


def lower_priority():
    """Below-normal CPU priority for this process (Windows BELOW_NORMAL, else nice 10). Never raises."""
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
        else:
            os.nice(10)
    except Exception:
        pass


# ================================================================================================ the rule language (no eval)
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
       "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def rule_errors(rule) -> list:
    """A rule = a list of steps {"feature", "op" (< <= > >= == != true false), "value" | "h1_q" (a quantile picked on
    2026 H1), "mult" (0-1.5)}; the first step that matches sets the size multiplier, none = x1."""
    errs = []
    if not isinstance(rule, list) or not rule:
        return ["rule must be a non-empty list"]
    for i, s in enumerate(rule):
        if not isinstance(s, dict) or not s.get("feature"):
            errs.append(f"step {i}: needs a feature")
            continue
        op = s.get("op")
        if op not in OPS and op not in ("true", "false"):
            errs.append(f"step {i}: bad op {op!r}")
        if op in OPS and "value" not in s and "h1_q" not in s:
            errs.append(f"step {i}: needs value or h1_q")
        if "h1_q" in s and not (0.0 < float(s["h1_q"]) < 1.0):
            errs.append(f"step {i}: h1_q must be in (0, 1)")
        m = _num(s.get("mult"))
        if m is None or not (0.0 <= m <= 1.5):
            errs.append(f"step {i}: mult must be 0..1.5")
    return errs


def resolve(rule, quantile_fn) -> list:
    """The rule with every h1_q replaced by its value (quantile_fn(feature, q) on 2026 H1 only)."""
    out = []
    for s in rule:
        s = dict(s)
        if "h1_q" in s and "value" not in s:
            s["value"] = round(float(quantile_fn(s["feature"], float(s["h1_q"]))), 6)
        out.append(s)
    return out


def rule_mult(rule, row) -> float:
    """Size multiplier of one trade (row = its facts known at the entry). Missing facts -> x1."""
    for s in rule:
        v = (row or {}).get(s["feature"])
        op = s["op"]
        if op in ("true", "false"):
            if v is None:
                continue
            if bool(v) == (op == "true"):
                return float(s["mult"])
            continue
        if isinstance(s.get("value"), str):
            if v is not None and OPS[op](str(v), s["value"]):
                return float(s["mult"])
            continue
        x = _num(v)
        if x is None:
            continue
        if OPS[op](x, float(s["value"])):
            return float(s["mult"])
    return 1.0


# ================================================================================================ the gates (pure)
def judge_lit(s: dict, base: dict, hits: dict, placebo: dict | None) -> dict:
    """The LIT verdict from tools/lit_edge.short(o, base) `s`, the base short `base`, the trades changed per half and the
    shuffle placebo. LIT exception (CLAUDE.md): picked on 2026 H1, checked on H2; 2021-25 a reference line, never a gate."""
    from tools import lit_edge as E
    why = []
    if hits.get("H1", 0) < MIN_HIT["H1"] or hits.get("H2", 0) < MIN_HIT["H2"]:
        why.append(f"too few trades changed ({hits.get('H1', 0)} in Jan-Jun, {hits.get('H2', 0)} in Jul-Oct)")
    if not E.gate(s):
        for h, nm in (("H1", "Jan-Jun (pick)"), ("H2", "Jul-Oct (check)")):
            if s["d_lit"][h] <= 0:
                why.append(f"{nm}: {_money(s['d_lit'][h])} at the LIT size")
            if s["d_eval"][h] <= 0:
                why.append(f"{nm}: {_money(s['d_eval'][h])} on the eval path")
            if s["d_f10"][h] > 0:
                why.append(f"{nm}: 2-week fails +{s['d_f10'][h]} pts")
    tpw_hi = max(TPW[1], max(base["lit"][h]["tpw"] for h in ("H1", "H2")))
    for h in ("H1", "H2"):
        t = s["lit"][h]["tpw"]
        if not (TPW[0] <= t <= tpw_hi + 1e-9):
            why.append(f"{h}: {t} trades a week (needs {TPW[0]:g}-{tpw_hi:g})")
    if placebo is not None and not why:
        bad = [h for h in ("H1", "H2") if float(placebo.get(h, 1.0)) > PLACEBO_MAX]
        if bad:
            why.append("not better than the same sizes shuffled at random (" +
                       ", ".join(f"{h} p {placebo[h]}" for h in bad) + ")")
    usd = {h: round(s["lit"][h]["per_month"] - base["lit"][h]["per_month"]) for h in ("H1", "H2", "2021-25")}
    usd_ev = {h: round(s["eval"][h]["per_month"] - base["eval"][h]["per_month"]) for h in ("H1", "H2")}
    status = "candidate" if not why and placebo is not None else "rejected"
    return {"status": status, "why": "; ".join(why) or "better in Jan-Jun and Jul-Oct, eval fails not up, 2+ trades a week, beats random",
            "usd_month": min(usd["H1"], usd["H2"]), "usd_month_by": usd, "eval_usd_month_by": usd_ev}


def judge_atlas(v: dict, o: dict, base: dict, hits: dict) -> dict:
    """The ATLAS verdict from tools/atlas_v2.verdict `v` (H1 pick, H2 check, 2025 + 2021-24 reference tier, 2+ a week)."""
    why = []
    if hits.get("H1", 0) < MIN_HIT["H1"] or hits.get("H2", 0) < MIN_HIT["H2"]:
        why.append(f"too few trades changed ({hits.get('H1', 0)} in Jan-Jun, {hits.get('H2', 0)} in Jul-Oct)")
    if not v.get("h1"):
        why.append("not better in Jan-Jun (pick)")
    if not v.get("h2"):
        why.append("not better in Jul-Oct (check)")
    if v.get("ref") == "-":
        why.append("2021-25 worse than today")
    if not v.get("freq"):
        why.append("fewer than 2 signals a week")
    usd = {h: round(float(o[h]["per_month"]) - float(base[h]["per_month"])) for h in o if h in base}
    return {"status": "candidate" if not why else "rejected",
            "why": "; ".join(why) or "better in Jan-Jun and Jul-Oct, 2021-25 holds, 2+ signals a week",
            "usd_month": min(usd.get("H1", 0), usd.get("H2", 0)), "usd_month_by": usd}


# ================================================================================================ the runners (real data)
class Ctx:
    """Lazy, shared within one night: the bases are computed once."""

    def __init__(self):
        self.c = {}

    def lit_base(self):
        if "lit" not in self.c:
            from tools import lit_edge as E
            o, U, L = E.evaluate()
            self.c["lit"] = (o, U, L, E.short(o))
        return self.c["lit"]

    def atlas_base(self):
        if "atlas" not in self.c:
            from tools import atlas_deep as D
            D.V2.install()
            U = D.A.account_units(D.A.BASE)
            F = D.feats(U)
            o = D.score(D.V_of({}))
            self.c["atlas"] = (o, U, F)
        return self.c["atlas"]


EV_KEYS = ("p10", "f10", "dec10", "p15", "f15", "slow_pass", "pass_med")


def _lit_head(s) -> dict:
    L, E_ = s["lit"], s["eval"]
    out = {h: {k: L[h][k] for k in ("n", "tpw", "pf", "net", "per_month", "dd")} for h in L}
    for h in E_:
        out[h]["eval"] = {k: E_[h].get(k) for k in ("net", "per_month") + EV_KEYS}
    return out


def _atlas_head(o) -> dict:
    keys = ("n", "tpw", "pf", "net", "per_month", "dd", "sig_tpw", "dead10", "mp_net_less_fees") + EV_KEYS
    return {h: {k: o[h].get(k) for k in keys} for h in o}


def _span_lit(day):
    return "H1" if "2026-01-01" <= day <= "2026-06-30" else "H2" if day >= "2026-07-01" else "2021-25"


def run_lit_tilt(exp, C: Ctx) -> dict:
    from tools import lit_edge as E
    o0, U0, L0, s0 = C.lit_base()
    rule = resolve(exp["rule"], E.h1_cut)
    intel = E.ctx()["intel"]
    mfn = lambda t, row: rule_mult(rule, row)                                       # noqa: E731
    o, U, L = E.evaluate(mfn=mfn)
    s = E.short(o, o0)
    hits = {}
    for t in E.ctx()["T"]:
        if rule_mult(rule, intel.get(int(t["entry_t"]), {})) != 1.0:
            sp = _span_lit(t["day"])
            hits[sp] = hits.get(sp, 0) + 1
    pre = judge_lit(s, s0, hits, None)
    plc = None
    if not pre["why"].startswith("too few") and E.gate(s):
        plc = E.placebo(U, L0, n=PLACEBO_N)
    v = judge_lit(s, s0, hits, plc) if plc is not None else pre
    return {"rule": rule, "hits": hits, "placebo": plc, "head": _lit_head(s), "base": _lit_head(s0),
            "d_lit": s["d_lit"], "d_eval": s["d_eval"], "d_f10": s["d_f10"], "d_p10": s["d_p10"], **v}


def run_atlas_tilt(exp, C: Ctx) -> dict:
    from tools import atlas_deep as D
    o0, U, F = C.atlas_base()
    rows = [f for f in F if f.get("span") == "H1"]

    def q(feature, qq):
        import numpy as np
        v = [_num(f.get(feature)) for f in rows]
        v = [x for x in v if x is not None]
        return float(np.quantile(v, qq))
    rule = resolve(exp["rule"], q)
    name = f"learn_{exp['id']}"
    D._UM[name] = D.um_from(F, U, lambda f: rule_mult(rule, f))
    hits = {}
    for f in F:
        if rule_mult(rule, f) != 1.0:
            hits[f.get("span")] = hits.get(f.get("span"), 0) + 1
    o = D.score(D.V_of({"um": name}))
    v = D.V2.verdict(o, o0, "tilt")
    return {"rule": rule, "hits": hits, "verdict_v2": v, "head": _atlas_head(o), "base": _atlas_head(o0),
            **judge_atlas(v, o, o0, hits)}


RUNNERS = {"lit_tilt": run_lit_tilt, "atlas_tilt": run_atlas_tilt}


# ================================================================================================ (a) refresh, (b) drift
def refresh(C: Ctx, root: str = ROOT) -> dict:
    """The live strategies' backtests on the newest data, and the live loop's twin on the newest bars (incl. the PC's
    NinjaTrader archive). Each part soft: an error is recorded, the rest still runs."""
    out = {}
    try:
        out["lit"] = _lit_head(C.lit_base()[3])
    except Exception as e:
        out["lit_error"] = f"{e.__class__.__name__}: {e}"[:200]
    try:
        out["atlas"] = _atlas_head(C.atlas_base()[0])
    except Exception as e:
        out["atlas_error"] = f"{e.__class__.__name__}: {e}"[:200]
    try:
        from engine import fill_audit as fa, lit_live
        d5, d1 = fa.load_bars()
        last = int(d5["time"].max())
        exp_last = None
        try:
            import pandas as pd
            exp_last = int(pd.read_csv(os.path.join(root, "data", "NQ_5m.csv"), usecols=["time"])["time"].max())
        except Exception:
            pass
        r = lit_live.run(d5, fa._params(), one_min=d1, now=last + 300)
        T = [{"day": t.get("day"), "entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "pnl": _num(t.get("pnl")),
              "exit": t.get("exit_reason"), "qty": t.get("qty")} for t in r.get("trades") or []]
        out["lit_recent"] = {"bars_to": _et(last).strftime("%Y-%m-%d %H:%M"),
                             "exports_to": _et(exp_last).strftime("%Y-%m-%d %H:%M") if exp_last else None,
                             "nt_days": (round((last - exp_last) / 86400, 1) if exp_last and last > exp_last else 0),
                             "trades": T[-30:], "n": len(T), "net": round(sum(t["pnl"] or 0 for t in T), 2)}
        C.c["recent_lit"] = T
        try:
            from engine import second
            s = second.run(d5, one_min=d1, now=last + 300, lit=r.get("trades"))
            out["atlas_recent"] = {k: {"n": len(v.get("trades") or []),
                                       "net": round(sum(float(x.get("usd") or 0) for x in v.get("trades") or []), 2)}
                                   for k, v in (s.get("strategies") or {}).items() if v.get("on", True)}
        except Exception as e:
            out["atlas_recent_error"] = f"{e.__class__.__name__}: {e}"[:200]
    except Exception as e:
        out["recent_error"] = f"{e.__class__.__name__}: {e}"[:200]
    return out


def drift(C: Ctx | None = None, store: str | None = None, today: str | None = None) -> dict:
    """Live vs the backtest twin: engine/live_learning's reviews of the last DRIFT_WEEKS weeks, its learned costs, and
    whether tonight's twin still has the trades the reviews compared against."""
    from engine import live_learning as LL
    R = LL._jl_read(LL._p(store, "reviews.jsonl"))
    today = today or dt.date.today().isoformat()
    mon = dt.date.fromisoformat(LL.week_of(today))
    weeks = [(mon - dt.timedelta(days=7 * i)).isoformat() for i in range(DRIFT_WEEKS)][::-1]
    W = [LL.weekly_summary(R, w) for w in weeks]
    bots = {}
    for w in W:
        for b, x in (w.get("bots") or {}).items():
            a = bots.setdefault(b, {"live_usd": 0.0, "twin_usd": 0.0, "matched": 0, "missed": 0, "extra": 0, "exec_usd": 0.0, "weeks": 0})
            for k in ("live_usd", "twin_usd", "exec_usd"):
                a[k] = round(a[k] + float(x.get(k) or 0), 2)
            for k in ("matched", "missed", "extra"):
                a[k] += int(x.get(k) or 0)
            a["weeks"] += 1
    flags = []
    for b, a in bots.items():
        a["gap_usd"] = round(a["live_usd"] - a["twin_usd"], 2)
        nm = LL.BOTS.get(b, b)
        if a["missed"] + a["extra"] >= 2:
            flags.append(f"{nm}: {a['missed']} missed / {a['extra']} extra trades vs the backtest in {DRIFT_WEEKS} weeks")
        if a["gap_usd"] <= -300:
            flags.append(f"{nm}: live {_money(a['gap_usd'])} behind the backtest in {DRIFT_WEEKS} weeks")
    costs = {}
    for b in ("lit", "atlas"):
        c = LL.load_costs(b, os.path.join(store, "costs.json") if store else None)
        if c:
            costs[b] = {k: c.get(k) for k in ("fills", "learned", "reserve_ticks", "comm", "adverse_p75", "text")}
            if c.get("learned") and float(c.get("reserve_ticks") or 1) > 1:
                flags.append(f"{LL.BOTS.get(b, b)}: real fills cost {c['reserve_ticks']:.0f} ticks (the backtest assumes 1)")
    moved = []
    fresh = (C.c.get("recent_lit") if C else None)
    if fresh is not None:
        fm = {(t["day"], t["dir"]): t for t in fresh}
        days = {t["day"] for t in fresh}
        for r in R:
            tw = r.get("twin")
            if r.get("bot") != "lit" or not tw or r.get("day") not in days:
                continue
            d = 1 if r.get("side") == "LONG" else -1
            f = fm.get((r["day"], d))
            if f is None:
                moved.append({"day": r["day"], "side": r.get("side"), "what": "tonight's backtest has no trade here"})
            elif tw.get("usd") is not None and f.get("pnl") is not None and abs(float(tw["usd"]) - float(f["pnl"])) > 1.0:
                moved.append({"day": r["day"], "side": r.get("side"), "what": f"backtest $ {float(tw['usd']):+,.0f} -> {float(f['pnl']):+,.0f}"})
        if moved:
            flags.append(f"the backtest moved on {len(moved)} reviewed trade(s) (new bars / data revision)")
    return {"weeks": weeks, "bots": bots, "costs": costs, "moved": moved[:10], "reviews": len(R), "flags": flags,
            "level": "watch" if flags else "ok"}


# ================================================================================================ (c) the queue
def load_queue(path: str = QUEUE_PATH) -> tuple:
    """(experiments, errors). Invalid entries are left out (and named)."""
    Q = _read_json(path, None)
    if not isinstance(Q, dict) or not isinstance(Q.get("experiments"), list):
        return [], ["queue missing or not {experiments: [...]}"]
    out, errs, seen = [], [], set()
    for e in Q["experiments"]:
        if not isinstance(e, dict) or not e.get("id"):
            errs.append("an experiment without an id")
            continue
        er = []
        if e["id"] in seen:
            er.append("duplicate id")
        if e.get("kind") not in RUNNERS:
            er.append(f"unknown kind {e.get('kind')!r}")
        if e.get("bot") not in ("lit", "atlas"):
            er.append("bot must be lit or atlas")
        er += rule_errors(e.get("rule"))
        for k in ("title", "hypothesis", "judged_by", "registered"):
            if not e.get(k):
                er.append(f"needs {k}")
        if er:
            errs.append(f"{e['id']}: " + "; ".join(er))
            continue
        seen.add(e["id"])
        if e.get("on", True):
            out.append(e)
    return out, errs


def exp_hash(e) -> str:
    return hashlib.sha1(json.dumps({k: e.get(k) for k in ("kind", "bot", "rule")}, sort_keys=True).encode()).hexdigest()[:12]


def pick(queue: list, results: dict, dkey: str, n: int = NIGHT_MAX) -> list:
    """Tonight's experiments: never run (or changed) first, in queue order; then stale ones (run on older data / older
    live settings), oldest first. Up-to-date results are not re-run."""
    new, stale = [], []
    for e in queue:
        r = results.get(e["id"])
        if not r or r.get("hash") != exp_hash(e) or r.get("status") == "error" and r.get("tries", 0) < 3:
            new.append(e)
        elif r.get("data_key") != dkey:
            stale.append((r.get("t") or 0, e))
    stale.sort(key=lambda x: x[0])
    return (new + [e for _, e in stale])[:max(0, int(n))]


# ================================================================================================ (d) outputs
def phone_line(c: dict) -> str:
    return f"Candidate: {c['title']}, {_money(c.get('usd_month'))}/month in both halves - review"


def push_phone(text: str, title: str = "OLYMPUS learn", env=None, http=None) -> tuple:
    """One push on the PC's private ntfy topic (tools/pc_report config, outside the repo). (sent, why). Never raises."""
    try:
        e = os.environ if env is None else env
        if e.get("LE_PR_NO_NET") == "1" and http is None:
            return False, "network off (tests)"
        sys.path.insert(0, ROOT) if ROOT not in sys.path else None
        from tools import pc_report as PR
        cfg = PR.load_cfg(env)
        if not cfg.get("on") or not cfg.get("topic"):
            return False, "no private alert topic on this PC"
        return PR.ntfy_post(cfg["ntfy"], cfg["topic"], text, title=title, priority="default", tags="brain", http=http)
    except Exception as ex:
        return False, f"{ex.__class__.__name__}: {str(ex)[:80]}"


def _row_text(r) -> str:
    by = r.get("usd_month_by") or {}
    parts = [f"Jan-Jun {_money(by.get('H1'))}/mo", f"Jul-Oct {_money(by.get('H2'))}/mo"]
    ref = by.get("2021-25") if "2021-25" in by else by.get("2021-24")
    if ref is not None:
        parts.append(f"{'2021-25' if '2021-25' in by else '2021-24'} {_money(ref)}/mo")
    return ", ".join(parts)


def build_summary(now, took, refresh_blk, drift_blk, ran, results, queue, q_errs, protected_ok, pushed, errors) -> dict:
    cands = [{"id": k, "title": v.get("title"), "bot": v.get("bot"), "usd_month": v.get("usd_month"), "since": v.get("since")}
             for k, v in results.items() if v.get("status") == "candidate"]
    qids = [e["id"] for e in queue]
    return {"v": VERSION, "kind": "le-learn", "t": int(now), "day": learn_day(now), "took_s": round(took, 1),
            "paper_only": True, "protected_ok": protected_ok,
            "refresh": refresh_blk, "drift": drift_blk,
            "ran": [{"id": r["id"], "status": r.get("status"), "usd_month": r.get("usd_month"), "why": r.get("why")} for r in ran],
            "queue": {"n": len(qids), "done": sum(1 for i in qids if i in results and results[i].get("status") in ("candidate", "rejected")),
                      "errors": q_errs[:10]},
            "candidates": cands, "pushed": pushed, "errors": errors[:10],
            "rule": "Research only: nothing here changes a live setting. A candidate is reviewed by the owner + Claude, then "
                    "built and re-tested in the run library before anything is switched."}


def markdown(S: dict, results: dict, queue: list) -> str:
    L = [f"# Nightly learning - {S['day']}", "",
         "Research only. The bot's settings are never changed by this; a candidate is something to review.", "",
         "| What | Result |", "|---|---|"]
    rf = S.get("refresh") or {}
    lit = rf.get("lit") or {}
    if lit.get("H2"):
        L.append(f"| Zlarior backtest (newest data) | Jan-Jun {_money(lit['H1']['net'])} ({_money(lit['H1']['per_month'])}/mo), "
                 f"Jul-Oct {_money(lit['H2']['net'])} ({_money(lit['H2']['per_month'])}/mo), PF {lit['H2']['pf']}, "
                 f"{lit['H2']['tpw']} trades/wk; 50K eval 2-week pass/fail {lit['H2']['eval']['p10']}/{lit['H2']['eval']['f10']}% |")
    at = rf.get("atlas") or {}
    if at.get("H2"):
        L.append(f"| ATLAS backtest (newest data) | Jan-Jun {_money(at['H1']['net'])}, Jul-Oct {_money(at['H2']['net'])} "
                 f"({_money(at['H2']['per_month'])}/mo), 25K 2-week pass {at['H2']['p10']}% |")
    lr = rf.get("lit_recent") or {}
    if lr:
        L.append(f"| Newest bars | to {lr.get('bars_to')} ET ({lr.get('nt_days', 0)} days from NinjaTrader); live-loop twin "
                 f"{lr.get('n', 0)} trades {_money(lr.get('net'))} in its window |")
    d = S.get("drift") or {}
    L.append(f"| Live vs backtest ({DRIFT_WEEKS} weeks) | " + ("; ".join(d.get("flags") or []) or "in line (no drift flagged)") + " |")
    for r in S.get("ran") or []:
        x = results.get(r["id"]) or {}
        L.append(f"| Tonight: {x.get('title') or r['id']} | **{r.get('status')}**: {x.get('why')} ({_row_text(x)}) |")
    q = S.get("queue") or {}
    L.append(f"| Queue | {q.get('done', 0)} of {q.get('n', 0)} judged on current data; {len(S.get('candidates') or [])} candidate(s) |")
    L += ["", "## Every experiment", "", "| Experiment | Status | $ a month (pick / check) | Why |", "|---|---|---|---|"]
    for e in queue:
        x = results.get(e["id"]) or {}
        L.append(f"| {e['title']} | {x.get('status', 'pending')} | {_row_text(x) if x.get('usd_month_by') else '-'} | {x.get('why', 'not run yet')} |")
    if S.get("candidates"):
        L += ["", "## Next step", "", "1. Tell Claude: \"review the learn candidates\" (it re-tests them in the run library "
                                      "and nothing changes until you say yes)."]
    if S.get("errors"):
        L += ["", "Errors: " + "; ".join(S["errors"])]
    return "\n".join(L) + "\n"


# ================================================================================================ one night
def run(budget_s: float = BUDGET_S, n_max: int = NIGHT_MAX, out_dir: str = OUT_DIR, root: str = ROOT, now=None,
        queue_path: str = QUEUE_PATH, runners: dict | None = None, refresh_fn=None, drift_fn=None, push_fn=None,
        write: bool = True) -> dict:
    """One night: refresh, drift, up to n_max queued experiments within budget_s, summary + one-pager, a phone line for a
    NEW candidate. Never edits a protected file (checked)."""
    t0 = time.monotonic()
    now = int(now if now is not None else time.time())
    RN = runners or RUNNERS
    h0 = protected_hashes(root)
    dkey = data_key(root)
    C = Ctx()
    errors = []
    st = _read_json(os.path.join(out_dir, "state.json"), {}) or {}
    results = st.get("results") or {}
    if write:
        _write_json(_lock_path(out_dir), {"pid": os.getpid(), "t": now})
    try:
        try:
            rf = (refresh_fn or refresh)(C) if refresh_fn is not False else {}
        except Exception as e:
            rf, _ = {}, errors.append(f"refresh: {e.__class__.__name__}: {e}"[:200])
        try:
            dr = (drift_fn or drift)(C) if drift_fn is not False else {}
        except Exception as e:
            dr, _ = {}, errors.append(f"drift: {e.__class__.__name__}: {e}"[:200])
        queue, q_errs = load_queue(queue_path)
        ran, new_cands = [], []
        for e in pick(queue, results, dkey, n_max):
            if time.monotonic() - t0 > budget_s:
                errors.append(f"budget reached before {e['id']}")
                break
            prev = results.get(e["id"]) or {}
            t1 = time.monotonic()
            try:
                r = RN[e["kind"]](e, C)
                r = {k: v for k, v in r.items()}
            except Exception as ex:
                r = {"status": "error", "why": f"{ex.__class__.__name__}: {ex}"[:200], "tries": int(prev.get("tries") or 0) + 1}
            r.update(id=e["id"], title=e["title"], bot=e["bot"], hash=exp_hash(e), data_key=dkey, t=now,
                     took_s=round(time.monotonic() - t1, 1), judged_by=e.get("judged_by"))
            if r.get("status") == "candidate":
                r["since"] = prev.get("since") if prev.get("status") == "candidate" else now
                if prev.get("status") != "candidate":
                    new_cands.append(r)
            results[e["id"]] = r
            ran.append(r)
            if write:
                _write_json(os.path.join(out_dir, "results", f"{e['id']}.json"), r, indent=1)
        h1 = protected_hashes(root)
        ok = h1 == h0
        if not ok:
            errors.append("a protected live file changed during the run: results not trusted, nothing pushed")
        pushed = []
        if ok:
            for c in new_cands:
                line = phone_line(c)
                sent, why = (push_fn or push_phone)(line)
                pushed.append({"id": c["id"], "line": line, "sent": bool(sent), "why": why})
        took = time.monotonic() - t0
        S = build_summary(now, took, rf, dr, ran, results, queue, q_errs, ok, pushed, errors)
        if write:
            st.update(v=VERSION, day=learn_day(now), t=now, results=results, data_key=dkey)
            _write_json(os.path.join(out_dir, "state.json"), st)
            _write_json(os.path.join(out_dir, "summary.json"), S, indent=1)
            with open(os.path.join(out_dir, "latest.md"), "w", encoding="utf-8") as fh:
                fh.write(markdown(S, results, queue))
            _append(os.path.join(out_dir, "history.jsonl"), {"t": now, "day": S["day"], "ran": S["ran"], "cands": len(S["candidates"]),
                                                            "lit_h2_month": ((rf.get("lit") or {}).get("H2") or {}).get("per_month"),
                                                            "atlas_h2_month": ((rf.get("atlas") or {}).get("H2") or {}).get("per_month")})
            if dr:
                _append(os.path.join(out_dir, "drift.jsonl"), {"t": now, "level": dr.get("level"), "flags": dr.get("flags"), "bots": dr.get("bots")})
        return S
    finally:
        if write:
            try:
                os.remove(_lock_path(out_dir))
            except OSError:
                pass


# ================================================================================================ the hook + the child
def spawn(budget_s: int = BUDGET_S, out_dir: str | None = None) -> int | None:
    """Start tonight's run as a detached, low-priority child with no window (it outlives the 15-minute task)."""
    try:
        import subprocess
        od = out_dir or OUT_DIR
        os.makedirs(od, exist_ok=True)
        log = open(os.path.join(od, "learn.log"), "a", encoding="utf-8")
        cmd = [sys.executable, "-X", "utf8", "-m", "engine.learn_loop", "run", "--budget", str(int(budget_s)), "--from-hook"]
        if out_dir:
            cmd += ["--out", od]
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8"}
        kw = {"cwd": ROOT, "stdout": log, "stderr": log, "stdin": subprocess.DEVNULL, "env": env}
        if os.name == "nt":
            base = 0x00004000 | 0x08000000 | 0x00000200          # BELOW_NORMAL | CREATE_NO_WINDOW | NEW_PROCESS_GROUP
            try:
                return subprocess.Popen(cmd, creationflags=base | 0x01000000, **kw).pid   # + BREAKAWAY_FROM_JOB
            except OSError:
                return subprocess.Popen(cmd, creationflags=base, **kw).pid
        kw["start_new_session"] = True
        kw["preexec_fn"] = lambda: os.nice(10)
        return subprocess.Popen(cmd, **kw).pid
    except Exception:
        return None


def maybe_run(now_s=None, say=print, env=None, out_dir: str = OUT_DIR, spawn_fn=None, open_fn=None) -> int | None:
    """tools/pc_report.py's 15-minute hook: start tonight's learning run once when the guard allows. Never raises."""
    try:
        e = os.environ if env is None else env
        if e.get("LE_PR_NO_NET") == "1" and spawn_fn is None:
            return None                                   # the PC report's tests: never start a real child
        ok, why = guard(now_s, out_dir, env=e, open_fn=open_fn)
        if not ok:
            return None
        pid = (spawn_fn or spawn)(BUDGET_S, None if out_dir == OUT_DIR else out_dir)
        if pid:
            t = int(now_s if now_s is not None else time.time())
            _write_json(_lock_path(out_dir), {"pid": pid, "t": t, "by": "hook"})
            sp = os.path.join(out_dir, "state.json")
            st = _read_json(sp, {}) or {}
            d = learn_day(t)
            st["tries"] = {d: int((st.get("tries") or {}).get(d, 0)) + 1}      # a child that keeps crashing stops after MAX_TRIES
            _write_json(sp, st)
            say(f"  [OK]  nightly learning started (research only, low priority, pid {pid})")
        return pid
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] nightly learning skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


def status(out_dir: str = OUT_DIR) -> dict:
    st = _read_json(os.path.join(out_dir, "state.json"), {}) or {}
    q, errs = load_queue()
    R = st.get("results") or {}
    return {"last_day": st.get("day"), "queue": [{"id": e["id"], "status": (R.get(e["id"]) or {}).get("status", "pending"),
                                                 "usd_month": (R.get(e["id"]) or {}).get("usd_month"),
                                                 "why": (R.get(e["id"]) or {}).get("why")} for e in q],
            "queue_errors": errs}


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="engine.learn_loop", description="The nightly self-learning loop (research only).")
    ap.add_argument("cmd", choices=("run", "status", "guard"), nargs="?", default="status")
    ap.add_argument("--budget", type=float, default=BUDGET_S)
    ap.add_argument("--max", type=int, default=NIGHT_MAX)
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--force", action="store_true", help="skip the clock / once-a-day guard (never the flat check)")
    ap.add_argument("--from-hook", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(a.out), indent=1))
        return 0
    if a.cmd == "guard":
        print(guard(out_dir=a.out, force=a.force))
        return 0
    if not a.from_hook:
        ok, why = guard(out_dir=a.out, force=True if a.force else False, env={**os.environ, "LE_LEARN": os.environ.get("LE_LEARN") or "1"})
        if not ok:
            print(f"not now: {why}")
            return 0
    lower_priority()
    hard = threading.Timer(max(60.0, 2 * a.budget), lambda: os._exit(3))       # a hard stop at twice the budget
    hard.daemon = True
    hard.start()
    S = run(budget_s=a.budget, n_max=a.max, out_dir=a.out)
    print(json.dumps({k: S[k] for k in ("day", "took_s", "ran", "candidates", "protected_ok", "errors")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
