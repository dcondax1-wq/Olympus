"""Holodeck data (owner 2026-10-29: "a main feature that allows me to see exactly chart fills, very high quality and 3D, where
I can see what every bot is thinking"). One JSON answer per trading day, the contract the 3D page draws (web_next):

  {"v": 1, "kind": "le-holo", "t", "day", "live", "bars": {"1m", "5m"}, "bots", "fills", "trades", "orders", "thoughts",
   "levels", "structure", "now", "errors"}

  GET /api/next/holo?day=YYYY-MM-DD   that session (18:00 ET the evening before -> 17:00 ET); no day = today's
  GET /api/next/holo/days             the last 30 trading days with trades or fills, newest first (n_trades, real $)
  phone(bot) / hist(bot)              holo.json (today, <= PHONE_MAX) and holo_hist.json (the last HIST_DAYS days' trades,
                                      <= HIST_MAX) for the phone, shipped by engine/live_publish.Publisher.extra()

Where every number comes from (read-only; nothing here starts, arms, routes, sizes or changes anything):
  real fills    the NinjaTrader adapters' legs (bot.adapter, bot.acct_b.adapter, bot.acct_c.adapter: legs + history; the
                entry fill_px / fill_mtime = NinjaTrader's own order-state file time, scale-in adds), the archived leg views
                and NinjaTrader order states of engine/fill_audit (logs/exec_audit/legs.json, orders.jsonl: stop / target
                fill prices and times) and the adapters' outgoing\\ folder now. A refused entry is never a fill
                (engine/ninjatrader.entry_never_placed): it is an order REJECTED with NinjaTrader's reason.
  routed rows   the bots' ledgers: LIT's (bot.ledger; logs/exec_audit/ledger.jsonl for past days), account B's (ATLAS) and
                account C's (BLITZ) in memory or their state files (data/live_state_acctb.json / _acctc.json).
  model         the LIT backtest of that day on the same bars (engine/lit_live.run + engine/brain.build, as fill_audit does)
                gives each real fill its model price + slippage in ticks (+ = worse for us), the setup (sweep, inducement,
                displacement, CISD), the levels and the thought log; a day without real fills shows the model's trades as
                real=false (src "model"). ATLAS paper trades (bot.second), BLITZ paper trades (bot.blitz) are real=false,
                src "paper".
  thoughts      the narrator's feed (logs/narrator/<day>.jsonl + today's memory), the Brain's thought log (data/brain/
                <day>.jsonl or the replay) and the order events, time-ordered.
build() never raises: a broken part becomes [] / null and a line in "errors". Mounted by server.py with one include line.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time

from fastapi import APIRouter
from fastapi.responses import Response

from . import narrator as N

router = APIRouter()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
VERSION, KIND = 1, "le-holo"
TICK, PV = 0.25, 2.0
BOTS = {"lit": ("Zlarior", "#4f9bff"), "atlas": ("ATLAS", "#ff9a3d"), "blitz": ("BLITZ", "#b388ff")}
STRAT_BOT = {"lit": "lit", "atlas": "atlas", "scalp": "blitz", "blitz": "blitz", "sys": "sys"}
LEVELS = ("info", "good", "warn", "bad", "dim")

# hooks (tests point them at temp folders / fake bars; None = the real default)
STORE = None                 # logs/exec_audit (engine/fill_audit.STORE)
NARR_DIR = None              # logs/narrator
BRAIN_DIR = None             # data/brain
STATE_PATH = None            # data/live_state.json (account B / C state files sit next to it)
FRAMES = None                # callable -> (d5, d1) frames; None = engine/fill_audit.load_bars (TradingView CME + data/nt_bars)
CSV_FALLBACK = True          # False: never read data/ bars (tests)
LIVE_REPLAY = False          # True: also replay today's LIT backtest from the frames (the PC has the Brain for today)
_MX = threading.RLock()
_MODEL: dict = {}            # day -> (sig, model dict): a finished day with the same bars is never replayed twice
_STRUCT: dict = {}


def _g(obj, name, default=None):
    """getattr that never raises (a broken bot / adapter property reads as missing)."""
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    from .live import BOT
    return BOT


def _now(bot) -> int:
    try:
        return int(bot.clock())
    except Exception:
        return int(time.time())


def _f(v, d=2):
    try:
        x = float(v)
        return None if x != x else round(x, d)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _err(errors: list, part: str, e: Exception):
    errors.append(f"{part}: {e.__class__.__name__}: {e}"[:200])


def _store():
    if STORE:
        return STORE
    from . import fill_audit as FA
    return FA.STORE


def _comm() -> float:
    try:
        from .sizing import LIVE_COMM
        return float(LIVE_COMM)
    except Exception:
        return 1.90


def session_bounds(day: str):
    """(18:00 ET the evening before, 17:00 ET) of trading day `day`."""
    d = dt.date.fromisoformat(day)
    p = d - dt.timedelta(days=1)
    t0 = int(dt.datetime(p.year, p.month, p.day, 18, 0, tzinfo=N.ET).timestamp())
    t1 = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=N.ET).timestamp())
    return t0, t1


def _ticks(a, b, d):
    """(a - b) in ticks in direction d (+ = a is worse for us when a is what we paid and b the model's price)."""
    return round((float(a) - float(b)) * d / TICK, 2) + 0.0


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


_FC: dict = {}


def _cached_file(path, loader, default):
    """loader(path) cached by the file's (mtime, size): holo_hist builds 10 days from the same archives."""
    try:
        st = os.stat(path)
    except OSError:
        return default
    k = (st.st_mtime_ns, st.st_size)
    with _MX:
        hit = _FC.get(path)
        if hit and hit[0] == k:
            return hit[1]
    val = loader(path)
    with _MX:
        if len(_FC) > 64:
            _FC.clear()
        _FC[path] = (k, val)
    return val


def _jl(path) -> list:
    return list(_cached_file(path, _jl_read, []))


def _rjson(path, default):
    v = _cached_file(path, lambda p: _read_json(p, None), None)
    return default if v is None else v


def _jl_read(path) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        continue
    except (FileNotFoundError, OSError):
        pass
    return out


_PX = re.compile(r"(?<![\d.,$])(\d{2},\d{3}(?:\.\d{1,2})?|\d{5}(?:\.\d{1,2})?)(?![\d,])")
_USD = re.compile(r"[+-]?\$\s?[+-]?[\d,]+(?:\.\d+)?")


def _first_px(text):
    """The first NQ-like price (5 digits, e.g. 30,747.25) in a sentence; $ amounts are never a price."""
    m = _PX.search(_USD.sub(" ", str(text or "")))
    return _f(m.group(1).replace(",", "")) if m else None


# ============================================================================================ bars
def _rows(df) -> list:
    if df is None or not len(df):
        return []
    v = df["volume"] if "volume" in df.columns else [0] * len(df)
    return [[int(t), float(o), float(h), float(l), float(c), int(x or 0)]
            for t, o, h, l, c, x in zip(df["time"], df["open"], df["high"], df["low"], df["close"], v)]


def _frames():
    if FRAMES is not None:
        return FRAMES()
    if not CSV_FALLBACK:
        return None, None
    from . import fill_audit as FA
    return FA.load_bars()


def _bot_rows(bot, t0, t1):
    """The bot's own feed (5m bars_tail, the 1m LIT store) inside [t0, t1)."""
    b5, b1 = [], []
    try:
        for r in _g(bot, "bars_tail", None) or []:
            if isinstance(r, dict):
                t = _i(r.get("time"))
                row = [t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r.get("volume") or 0)]
            else:
                t = _i(r[0])
                row = [t] + [float(x) for x in r[1:5]] + [int(r[5]) if len(r) > 5 and r[5] is not None else 0]
            if t is not None and t0 <= t < t1:
                b5.append(row)
    except Exception:
        b5 = []
    st = _g(bot, "_lit_1m_store", None)
    if st is not None:
        try:
            b1 = _rows(st[(st["time"] >= t0) & (st["time"] < t1)])
        except Exception:
            b1 = []
    return b5, b1


def day_bars(bot, day: str, live: bool) -> dict:
    """{"1m", "5m", "source"}: the bot's own NinjaTrader bars when they cover the session, else the TradingView CME exports
    merged with the PC's archive data/nt_bars (engine/fill_audit.load_bars; futures only, never Yahoo)."""
    t0, t1 = session_bounds(day)
    b5, b1 = _bot_rows(bot, t0, t1)
    covers = bool(b1) and (live or b1[0][0] <= t0 + 3 * 3600)
    if covers:
        return {"1m": b1, "5m": b5 or _agg5(b1), "source": "bot"}
    d5, d1 = _frames()
    r1 = _rows(d1[(d1["time"] >= t0) & (d1["time"] < t1)]) if d1 is not None and len(d1) else []
    r5 = _rows(d5[(d5["time"] >= t0) & (d5["time"] < t1)]) if d5 is not None and len(d5) else []
    if not r1 and b1:
        r1 = b1
    return {"1m": r1, "5m": r5 or _agg5(r1) or b5, "source": "data" if r1 or r5 else "none"}


def _agg5(b1) -> list:
    out = {}
    for t, o, h, l, c, v in b1:
        k = t - t % 300
        x = out.get(k)
        if x is None:
            out[k] = [k, o, h, l, c, v]
        else:
            x[2], x[3], x[4], x[5] = max(x[2], h), min(x[3], l), c, x[5] + v
    return [out[k] for k in sorted(out)]


# ============================================================================================ the LIT model of a day
def _params():
    try:
        from . import fill_audit as FA
        return FA._params()
    except Exception:
        return {}


def model_day(day: str, errors: list | None = None, now: int | None = None) -> dict | None:
    """The LIT backtest of trading day `day` on the frames' bars (up to `now` for today): {"trades", "setups", "levels",
    "log"}, cached by the bars it saw. None without bars."""
    errors = errors if errors is not None else []
    try:
        d5, d1 = _frames()
        if d5 is None or not len(d5):
            return None
        from . import fill_audit as FA
        end = FA._ts(day, 16, 5)
        if now is not None:
            end = min(end, int(now) - int(now) % 60)
        a0 = FA._ts(day, 2, 0) - 8 * 3600
        a5 = d5[(d5["time"] >= a0) & (d5["time"] < end)]
        a1 = d1[(d1["time"] >= a0) & (d1["time"] < end)] if d1 is not None and len(d1) else None
        if len(a5) < 12:
            return None
        P = _params()
        sig = (FA._phash(P), len(a5), int(a5["time"].max()), 0 if a1 is None else len(a1), 0 if a1 is None or not len(a1) else int(a1["time"].max()))
        with _MX:
            hit = _MODEL.get(day)
            if hit and hit[0] == sig:
                return hit[1]
        from . import brain as BR, lit_live
        keep: dict = {}
        cut1 = d1[d1["time"] < end] if d1 is not None and len(d1) else None
        r = lit_live.run(d5[d5["time"] < end], P, one_min=cut1, now=end, keep=keep)
        b = BR.build(r, P, end, keep=keep, mode="replay")
        M, C = keep.get("M"), keep.get("C") or []
        trades = []
        for t in r.get("trades") or []:
            if t.get("day") != day:
                continue
            row = {k: t.get(k) for k in ("entry_t", "exit_t", "dir", "entry", "exit_price", "stop", "target", "qty", "pnl", "pnl_r",
                                         "exit_reason", "risk_pts", "risk_usd", "target_label", "entry_kind", "swept", "sweep_ext")}
            row["be_t"] = FA._bt_be_time(t, d1)
            trades.append(row)
        levels = []
        try:
            from . import lit_brief
            last = int(_g(M, "n_closed", M.n)) - 1
            k = int(M.day_of[last])
            for lv in lit_brief.level_map(M, k, last, end):
                levels.append({"bot": "lit", "px": _f(lv.get("price")), "label": lv.get("label"), "t0": _i(lv.get("known_t")),
                               "t1": None, "taken_t": _i(lv.get("taken_t")) if lv.get("taken") else None, "kind": lv.get("kind"),
                               "side": lv.get("side")})
        except Exception as e:
            _err(errors, "model levels", e)
        setups = []
        for s in b.get("setups") or []:
            s = dict(s)
            s["detail"] = _cand_detail(M, C, s.get("id"))
            setups.append(s)
        out = {"trades": trades, "setups": setups, "levels": levels, "log": b.get("log") or [], "error": b.get("error")}
        with _MX:
            if len(_MODEL) > 40:
                _MODEL.clear()
            _MODEL[day] = (sig, out)
        return out
    except Exception as e:
        _err(errors, "model", e)
        return None


_LIVE_TRY: dict = {}
LIVE_RETRY_S = 300


def _live_model(day, brain, now, errors):
    """Today: the replay only for what the Brain cannot say (a setup's sweep / inducement / displacement times, the model
    trade's exact exit): re-run when the Brain shows a setup the cached replay does not have, at most every LIVE_RETRY_S."""
    need = {s.get("id") for s in brain.get("setups") or [] if isinstance(s, dict) and s.get("id")}
    with _MX:
        hit = _MODEL.get(day)
    have = {s.get("id") for s in (hit[1].get("setups") or [])} if hit else set()
    closed = {int(s["trade"]["entry_t"]) for s in brain.get("setups") or [] if isinstance(s, dict) and isinstance(s.get("trade"), dict)
              and s["trade"].get("entry_t") and str(s["trade"].get("exit") or "OPEN").upper() != "OPEN"}
    have_closed = {int(t["entry_t"]) for t in (hit[1].get("trades") or []) if t.get("exit_t")} if hit else set()
    if not need or (hit and need <= have and closed <= have_closed):
        return hit[1] if hit else None
    if now - _LIVE_TRY.get(day, 0) < LIVE_RETRY_S:
        return hit[1] if hit else None
    _LIVE_TRY[day] = now
    return model_day(day, errors, now=now) or (hit[1] if hit else None)


def _cand_detail(M, C, sid) -> dict | None:
    """Sweep / inducement / displacement / CISD times of one Brain setup ("<i>:<dir>") from lit.candidates()."""
    try:
        i, d = (int(x) for x in str(sid).split(":"))
        c = next((c for c in C if int(c.get("i", -1)) == i and int(c.get("dir", 0)) == d), None)
        if c is None:
            return None
        T = M.t
        ext_i, sw_i = int(c["ext_i"]), int(c["sweep_i"])
        lo, hi = min(ext_i, i), i
        disp_i = max(range(lo, hi + 1), key=lambda j: abs(float(M.c[j]) - float(M.o[j]))) if hi >= lo else i
        idm = [(float(a), int(b)) for a, b in (c.get("idm_a") or []) if int(b) > 0]
        idm_i = sw_i - min(idm)[1] if idm else None
        return {"t_sweep": int(T[sw_i]), "t_ext": int(T[ext_i]), "sweep_ext": _f(abs(float(c["ext_d"]))),
                "t_idm": int(T[idm_i]) if idm_i is not None and 0 <= idm_i < len(T) else None, "idm_n": _i(c.get("ind_n")),
                "t_disp": int(T[disp_i]), "disp_atr": _f(c.get("disp")), "t_cisd": int(T[i]) + 300, "cisd": _f(abs(float(c["ref_d"]))),
                "depth_atr": _f(c.get("depth_atr")), "swept_px": {str(k): _f(abs(float(v))) for k, v in (c.get("sw") or {}).items()}}
    except Exception:
        return None


def lit_setup(s: dict | None, levels: list, trade_sweep_ext=None) -> dict | None:
    """The contract's "setup" from a Brain setup (+ its candidate detail)."""
    if not isinstance(s, dict):
        return None
    det = s.get("detail") or {}
    swept = []
    t_c = det.get("t_cisd") or _i(s.get("t")) or 0
    want = "H" if int(s.get("dir") or 0) == -1 else "L"
    for nm in s.get("swept") or []:
        c = [lv for lv in levels or [] if lv.get("label") == nm]
        side = [lv for lv in c if str(lv.get("side") or want)[:1].upper() == want] or c
        taken = [lv for lv in side if lv.get("taken_t") and int(lv["taken_t"]) <= t_c]
        lv = max(taken, key=lambda z: int(z["taken_t"])) if taken else (side[0] if side else {})
        swept.append({"px": lv.get("px"), "label": nm, "t": lv.get("taken_t")})
    notes = [c.get("text") for c in s.get("checks") or [] if isinstance(c, dict) and c.get("text")]
    if s.get("status_text"):
        notes.insert(0, s["status_text"])
    return {"kind": "LIT", "id": s.get("id"), "dir": s.get("dir"), "t_sweep": det.get("t_sweep") or s.get("t"),
            "sweep_ext": _f(trade_sweep_ext) or det.get("sweep_ext") or _f(s.get("ext")), "t_ext": det.get("t_ext"), "swept": swept,
            "t_idm": det.get("t_idm"), "t_disp": det.get("t_disp"), "t_cisd": det.get("t_cisd") or _i(s.get("t")),
            "cisd": det.get("cisd") or _f(s.get("cisd")), "plan": s.get("plan"), "status": s.get("status"), "notes": notes[:12]}


# ============================================================================================ real routed trades
def _accounts(bot) -> list:
    """[(bot key, account object or None, adapter, ledger rows, label)] of LIT's account, account B (ATLAS), account C (BLITZ)."""
    out = []
    try:
        acct = bot._push_account() if callable(_g(bot, "_push_account", None)) else None
    except Exception:
        acct = None
    ad = _g(bot, "adapter", None)
    out.append(("lit", bot, ad, list(_g(bot, "ledger", None) or []), acct or _g(ad, "account", None)))
    for key, attr in (("atlas", "acct_b"), ("blitz", "acct_c")):
        A = _g(bot, attr, None)
        if A is not None:
            out.append((key, A, _g(A, "adapter", None), list(_g(A, "ledger", None) or []),
                        _g(A, "name", None) or _g(A, "label", None)))
    return out


def _state_path(bot):
    return STATE_PATH or _g(bot, "state_path", None) or os.path.join(DATA, "live_state.json")


def _disk_ledgers(bot) -> dict:
    """bot key -> ledger rows kept on disk: LIT's archive (logs/exec_audit/ledger.jsonl), account B / C state files."""
    out = {"lit": _jl(os.path.join(_store(), "ledger.jsonl"))}
    base, ext = os.path.splitext(_state_path(bot))
    for key, suf in (("atlas", "_acctb"), ("blitz", "_acctc")):
        out[key] = list((_rjson(base + suf + (ext or ".json"), {}) or {}).get("ledger") or [])
    return out


def _rkey(r) -> str:
    return json.dumps([r.get("t"), r.get("side"), r.get("entry_t"), r.get("stop"), r.get("reason"), r.get("src")], default=str)


def _orders_raw(bot, accts) -> dict:
    """order id -> {"first", "state", "filled", "avg", "mtime"}: logs/exec_audit/orders.jsonl + each adapter's outgoing\\ now."""
    rows = {}

    def put(oid, st, seen=None):
        if not oid:
            return
        old = rows.get(oid)
        first = min(x for x in (seen, st.get("mtime"), (old or {}).get("first")) if x) if any((seen, st.get("mtime"), (old or {}).get("first"))) else None
        if old and old.get("state") == "FILLED" and st.get("state") != "FILLED":
            old["first"] = first
            return
        rows[oid] = {"state": st.get("state"), "filled": _i(st.get("filled")) or 0, "avg": _f(st.get("avg")), "mtime": st.get("mtime"),
                     "first": first}
    for r in _jl(os.path.join(_store(), "orders.jsonl")):
        if isinstance(r, dict) and r.get("id"):
            put(r["id"], r, r.get("seen"))
    try:
        from tools import fill_audit as tfa
        folders = {_g(ad, "folder", None) for _k, _a, ad, _l, _n in accts if ad is not None}
        for fo in folders:
            if fo and os.path.isdir(os.path.join(fo, "outgoing")):
                with _MX:
                    hit = _OUT.get(fo)
                if hit and time.time() - hit[0] < OUT_TTL_S:
                    cur = hit[1]
                else:
                    cur = tfa.read_outgoing(fo)
                    with _MX:
                        _OUT[fo] = (time.time(), cur)
                for oid, st in cur.items():
                    put(oid, st)
    except Exception:
        pass
    return rows


_OUT: dict = {}
OUT_TTL_S = 15.0             # NinjaTrader's outgoing folder read at most every 15 s (holo_hist builds 10 days at once)


def _legs(accts, bot) -> dict:
    """bot key -> {entry_t -> [leg, ...]} from the adapters (legs + history) and the archived views (LIT)."""
    out = {}
    for key, _A, ad, _l, _n in accts:
        seen = {}
        for lg in list(_g(ad, "legs", None) or []) + list(_g(ad, "history", None) or []):
            if isinstance(lg, dict) and lg.get("entry_id"):
                old = seen.get(lg["entry_id"])
                if old is None or int(lg.get("filled") or 0) >= int(old.get("filled") or 0):
                    seen[lg["entry_id"]] = lg
        if key == "lit":
            for eid, lg in (_rjson(os.path.join(_store(), "legs.json"), {}) or {}).items():
                if isinstance(lg, dict) and eid not in seen:
                    seen[eid] = {**lg, "entry_id": eid}
        for lg in seen.values():
            if lg.get("entry_t") is not None:
                out.setdefault(key, {}).setdefault(int(lg["entry_t"]), []).append(lg)
    return out


def _src_of(adapter_name, account) -> tuple:
    """(real, src) of a fill reported by this adapter on this account."""
    a = str(adapter_name or "").lower()
    if a.startswith("ninja"):
        try:
            from .ninjatrader import is_sim
            return True, ("sim" if is_sim(str(account or "")) else "ninjatrader")
        except Exception:
            return True, "ninjatrader"
    return False, "paper"


def _exit_kind(reason) -> str:
    r = str(reason or "").upper()
    if r in ("KILL", "KILL SWITCH", "FLATTEN", "FLAT_SAFETY", "SAFETY"):
        return "flatten"
    if r in ("TARGET", "BANK"):
        return "target"
    if r in ("STOP", "BE"):
        return "stop"
    return "exit"


def real_trades(bot, day: str, now: int, errors: list, accts=None) -> dict:
    """{"fills", "trades", "orders", "thoughts", "entries"}: every routed entry of `day` on the bots' accounts."""
    t0, t1 = session_bounds(day)
    accts = accts if accts is not None else _accounts(bot)
    disk = {}
    try:
        disk = _disk_ledgers(bot)
    except Exception as e:
        _err(errors, "ledgers on disk", e)
    try:
        orders = _orders_raw(bot, accts)
    except Exception as e:
        _err(errors, "order states", e)
        orders = {}
    try:
        legs = _legs(accts, bot)
    except Exception as e:
        _err(errors, "legs", e)
        legs = {}
    fills, trades, orders_out, thoughts, entries = [], [], [], [], set()
    comm = _comm()
    for key, A, ad, mem_rows, acct_name in accts + [(k, None, None, [], None) for k in ("atlas", "blitz") if k not in {a[0] for a in accts}]:
        rows, have = [], set()
        for r in list(mem_rows) + list(disk.get(key) or []):
            if not isinstance(r, dict) or r.get("t") is None:
                continue
            k_ = _rkey(r)
            if k_ in have:
                continue
            have.add(k_)
            rows.append(r)
        rows = [r for r in rows if N.trading_day(int(r.get("entry_t") or r["t"])) == day]
        by = {}
        for r in rows:
            et_ = _i(r.get("entry_t"))
            if et_ is None:
                continue
            x = by.setdefault(et_, {"entries": [], "mods": [], "exits": [], "adds": []})
            s = r.get("side")
            {"buy": x["entries"], "sell": x["entries"], "modify": x["mods"], "exit": x["exits"], "add": x["adds"]}.get(s, []).append(r)
        for et_, x in sorted(by.items()):
            try:
                tr = _one_real(key, A, ad, acct_name, et_, x, legs.get(key, {}).get(et_, []), orders, now, comm, fills, orders_out,
                               thoughts)
                if tr:
                    trades.append(tr)
                    entries.add((key, et_))
            except Exception as e:
                _err(errors, f"{key} trade {et_}", e)
        try:      # order events in the narrator's words (sent / refused / filled / BE / exit with real $)
            bk = "scalp" if key == "blitz" else key
            srt = sorted(rows, key=lambda r: r["t"])
            groups = [(bk, [r for r in srt if not (key == "lit" and r.get("src"))])]
            if key == "lit":                         # ATLAS members routed on LIT's own account
                groups.append(("atlas", [r for r in srt if r.get("src")]))
            who = acct_name or next((str((r.get("result") or {}).get("account")) for r in srt
                                     if isinstance(r.get("result"), dict) and r["result"].get("account")), "")
            for strat, rs in groups:
                for m in N._route_rows(rs, strat, who, paper=False):
                    thoughts.append(_thought_of(m))
        except Exception as e:
            _err(errors, f"{key} order events", e)
    return {"fills": fills, "trades": trades, "orders": orders_out, "thoughts": thoughts, "entries": entries}


def _one_real(key, A, ad, acct_name, et_, x, legs, orders, now, comm, fills, orders_out, thoughts) -> dict | None:
    if not x["entries"]:
        return None
    oks = [e for e in x["entries"] if (e.get("result") or {}).get("ok") is not False]
    e = (oks or x["entries"])[-1]
    res = e.get("result") or {}
    d = 1 if e.get("side") == "buy" else -1
    side = "BUY" if d == 1 else "SELL"
    acct = res.get("account") or acct_name
    real, src = _src_of(res.get("adapter") or _g(ad, "name", None), acct)
    bot_key = "atlas" if key == "lit" and e.get("src") else key
    t_route = int(e["t"])
    if not legs:
        legs = _legs_from_orders(orders, et_, e)
    filled_legs = [lg for lg in legs if int(lg.get("filled") or 0) > 0 and lg.get("fill_px") is not None]
    rlegs = [lg for lg in (res.get("legs") or []) if isinstance(lg, dict) and int(lg.get("filled") or 0) > 0 and lg.get("fill_px") is not None]
    ent_ord = [orders.get(lg.get("entry_id")) for lg in legs if orders.get(lg.get("entry_id"))]
    if not oks:
        from .ninjatrader import entry_never_placed
        never = True
        if ad is not None:
            try:
                never = entry_never_placed(ad, et_, res, now)
            except Exception:
                never = not filled_legs
        if never or not (filled_legs or rlegs):
            orders_out.append({"t": t_route, "t_end": t_route, "bot": bot_key, "acct": acct, "type": "MARKET", "side": side,
                               "px": _f(e.get("entry")), "qty": _i(e.get("qty")) or 0, "state": "REJECTED",
                               "why": str(res.get("error") or "refused")[:200], "entry_t": et_})
            return None
    model_entry = _f(e.get("entry"))
    tid = f"{bot_key}:{et_}"
    efills = []
    src_legs = filled_legs or rlegs
    for n, lg in enumerate(src_legs):
        st = orders.get(lg.get("entry_id")) or {}
        t = lg.get("fill_mtime") or st.get("mtime") or t_route
        efills.append({"id": lg.get("entry_id") or f"{tid}:E{n}", "t": round(float(t), 3), "px": float(lg["fill_px"]),
                       "qty": int(lg["filled"]), "side": side, "kind": "entry", "bot": bot_key, "acct": acct, "real": real, "src": src,
                       "model_px": model_entry, "slip_ticks": _ticks(lg["fill_px"], model_entry, d) if model_entry is not None else None,
                       "trade": tid})
    if not efills:
        st = next((o for o in ent_ord if o.get("state") == "FILLED" and o.get("avg")), None)
        if st:
            efills.append({"id": f"{tid}:E", "t": round(float(st.get("mtime") or t_route), 3), "px": float(st["avg"]),
                           "qty": int(st.get("filled") or e.get("qty") or 0), "side": side, "kind": "entry", "bot": bot_key, "acct": acct,
                           "real": real, "src": src, "model_px": model_entry,
                           "slip_ticks": _ticks(st["avg"], model_entry, d) if model_entry is not None else None, "trade": tid})
        elif oks and not real and model_entry is not None:      # the paper adapter fills at the model price
            efills.append({"id": f"{tid}:E", "t": float(t_route), "px": model_entry, "qty": int(e.get("qty") or 0), "side": side,
                           "kind": "entry", "bot": bot_key, "acct": acct, "real": False, "src": "paper", "model_px": model_entry,
                           "slip_ticks": 0.0, "trade": tid})
    orders_out.append({"t": t_route, "t_end": int(min(f["t"] for f in efills)) if efills else None, "bot": bot_key, "acct": acct,
                       "type": "MARKET", "side": side, "px": model_entry, "qty": _i(e.get("qty")) or 0,
                       "state": "FILLED" if efills else ("WORKING" if oks else "REJECTED"), "why": e.get("strategy") or e.get("reason"),
                       "entry_t": et_})
    if not efills:
        return None
    fills.extend(efills)
    # scale-in adds (the adapter's legs)
    for lg in legs:
        for a in lg.get("adds") or []:
            if int(a.get("filled") or 0) > 0 and a.get("fill_px") is not None:
                st = orders.get(a.get("id")) or {}
                fills.append({"id": a.get("id"), "t": round(float(st.get("mtime") or a.get("sent_at") or t_route), 3),
                              "px": float(a["fill_px"]), "qty": int(a["filled"]), "side": side, "kind": "add", "bot": bot_key, "acct": acct,
                              "real": real, "src": src, "model_px": None, "slip_ticks": None, "trade": tid})
    qty = sum(f["qty"] for f in fills if f["trade"] == tid and f["kind"] in ("entry", "add"))
    e_px = sum(f["px"] * f["qty"] for f in efills) / max(1, sum(f["qty"] for f in efills))
    e_t = min(f["t"] for f in efills)
    stop0 = _f(next((lg.get("stop0") for lg in legs if lg.get("stop0") is not None), None)) or _f(e.get("stop"))
    target = _f(next((lg.get("target") for lg in legs if lg.get("target") is not None), None)) or _f(e.get("target"))
    path = [[round(e_t, 3), stop0]] if stop0 is not None else []
    for m in sorted(x["mods"], key=lambda r: r["t"]):
        if (m.get("result") or {}).get("ok") is not False and m.get("stop") is not None and (not path or path[-1][1] != _f(m["stop"])):
            path.append([int(m["t"]), _f(m["stop"])])
    cur = _f(next((lg.get("stop") for lg in legs if lg.get("stop") is not None), None))
    if cur is not None and path and path[-1][1] != cur:
        path.append([int(now), cur])
    t_prot = round(e_t, 3)
    stop_ids = [lg.get("stop_id") for lg in legs if lg.get("stop_id")]
    tgt_ids = [lg.get("target_id") for lg in legs if lg.get("target_id")]
    # exits: the stop / target order filled at NinjaTrader, else the bot's exit row (a CLOSEPOSITION: no broker price)
    xf = []
    for ids, kind, ref in ((stop_ids, "stop", None), (tgt_ids, "target", target)):
        for oid in ids:
            st = orders.get(oid) or {}
            if st.get("state") == "FILLED" and st.get("avg"):
                mpx = (path[-1][1] if path else None) if kind == "stop" else ref
                xf.append({"id": oid, "t": round(float(st.get("mtime") or now), 3), "px": float(st["avg"]),
                           "qty": int(st.get("filled") or qty), "side": "SELL" if d == 1 else "BUY", "kind": kind, "bot": bot_key,
                           "acct": acct, "real": real, "src": src, "model_px": mpx,
                           "slip_ticks": _ticks(mpx, st["avg"], d) if mpx is not None else None, "trade": tid})
    xr = sorted(x["exits"], key=lambda r: r["t"])
    reason = (xr[-1].get("reason") if xr else None)
    if not xf and xr:
        r = xr[-1]
        rr = r.get("result") or {}
        fpx = next((_f(lg.get("fill_px")) for lg in rr.get("legs") or [] if isinstance(lg, dict) and lg.get("fill_px")), None)
        kind = _exit_kind(r.get("reason"))
        mpx = (path[-1][1] if path else None) if kind == "stop" else target if kind == "target" else None
        px = fpx if fpx is not None else (_px_from_pnl(r.get("pnl"), e_px, d, qty, comm) if r.get("pnl") is not None else mpx)
        if px is not None and rr.get("ok") is not False:
            xf.append({"id": f"{tid}:X", "t": float(int(r.get("exit_t") or r["t"]) if not fpx else r["t"]), "px": round(px, 2),
                       "qty": int(r.get("qty") or qty), "side": "SELL" if d == 1 else "BUY", "kind": kind, "bot": bot_key, "acct": acct,
                       "real": real and fpx is not None, "src": src if fpx is not None else ("paper" if not real else "model"),
                       "model_px": mpx, "slip_ticks": _ticks(mpx, px, d) if mpx is not None and fpx is not None else None, "trade": tid})
    fills.extend(xf)
    x_t = max(f["t"] for f in xf) if xf else None
    x_q = sum(f["qty"] for f in xf)
    x_px = (sum(f["px"] * f["qty"] for f in xf) / x_q) if x_q else None
    if xf and not reason:
        reason = "BE" if xf[0]["kind"] == "stop" and len(path) > 1 else xf[0]["kind"].upper()
    usd = None
    if x_px is not None:
        usd = round(sum((x_px - f["px"]) * d * PV * f["qty"] for f in fills if f["trade"] == tid and f["kind"] in ("entry", "add"))
                    - comm * qty, 2)
    elif xr and xr[-1].get("pnl") is not None:
        usd = _f(xr[-1]["pnl"])
    risk_usd = round(abs(e_px - stop0) * PV * qty, 2) if stop0 is not None else None
    r_mult = round((x_px - e_px) * d / abs(e_px - stop0), 3) if (x_px is not None and stop0 and abs(e_px - stop0) > 0) else None
    # the bracket orders (one segment per stop price)
    for n, (t, px) in enumerate(path):
        nxt = path[n + 1][0] if n + 1 < len(path) else None
        end = nxt or x_t
        filled_here = nxt is None and xf and xf[0]["kind"] == "stop"
        orders_out.append({"t": int(t if n else t_prot), "t_end": int(end) if end else None, "bot": bot_key, "acct": acct, "type": "STOP",
                           "side": "SELL" if d == 1 else "BUY", "px": px, "qty": qty,
                           "state": "FILLED" if filled_here else ("CANCELLED" if end else "WORKING"),
                           "why": (f"replaced: stop moved to {N.px(path[n + 1][1])}" if nxt else ("stop" if n == 0 else "stop (moved)")),
                           "entry_t": et_})
    if target is not None:
        hit = bool(xf) and xf[0]["kind"] == "target"
        orders_out.append({"t": int(t_prot), "t_end": int(x_t) if x_t else None, "bot": bot_key, "acct": acct, "type": "LIMIT",
                           "side": "SELL" if d == 1 else "BUY", "px": target, "qty": qty,
                           "state": "FILLED" if hit else ("CANCELLED" if x_t else "WORKING"), "why": "target", "entry_t": et_})
    return {"id": tid, "bot": bot_key, "acct": acct, "real": real, "src": src, "side": "LONG" if d == 1 else "SHORT", "qty": qty,
            "entry": {"t": round(e_t, 3), "px": round(e_px, 2)},
            "exit": {"t": x_t, "px": round(x_px, 2), "reason": reason} if x_px is not None else None,
            "stop_path": path, "target": target, "risk_usd": risk_usd, "usd": usd, "r": r_mult, "model": None,
            "setup": {"kind": str(e.get("strategy") or e.get("src") or ("LIT" if bot_key == "lit" else bot_key)).upper() if bot_key != "lit" else "LIT",
                      "t_sweep": None, "sweep_ext": None, "swept": [], "t_idm": None, "t_disp": None, "t_cisd": None, "cisd": None,
                      "notes": [n for n in (e.get("strategy"), e.get("reason")) if n]},
            "entry_t": et_, "dir": d, "routed_t": t_route, "_src": e.get("src")}


def _legs_from_orders(orders: dict, et_: int, e: dict) -> list:
    """No leg of this entry is known (an account B / C day before a restart): its brackets from NinjaTrader's archived order
    states, by the order ids LE<entry_t><tag><N|M><E|S|T> (tools/fill_audit.parse_oid)."""
    try:
        from tools import fill_audit as tfa
    except Exception:
        return []
    by = {}
    for oid, st in orders.items():
        p = tfa.parse_oid(oid)
        if p and int(p["entry_t"]) == int(et_):
            by.setdefault(oid[:-1], {})[p["leg"]] = st
    out = []
    for base, x in sorted(by.items()):
        en = x.get("entry") or {}
        out.append({"entry_id": base + "E", "stop_id": base + "S", "target_id": base + "T", "entry_t": int(et_),
                    "filled": int(en.get("filled") or 0) if en.get("state") in ("FILLED", "PARTFILLED") else 0, "fill_px": en.get("avg"),
                    "fill_mtime": en.get("mtime"), "stop0": _f(e.get("stop")), "target": _f(e.get("target")), "from_orders": True})
    return out


def _px_from_pnl(pnl, e_px, d, qty, comm):
    try:
        q = max(1, int(qty or 1))
        return e_px + d * ((float(pnl) / q) + comm) / PV
    except Exception:
        return None


# ============================================================================================ model / paper trades
def _model_trade(t, bot="lit", src="model", setup=None, acct=None) -> tuple:
    """A model (backtest) or paper trade as the contract's trade + its fills (real=false)."""
    d = int(t.get("dir") or 1)
    et_ = int(t["entry_t"])
    tid = f"{bot}:{et_}:{src}"
    q = int(t.get("qty") or 0)
    entry, stop = _f(t.get("entry")), _f(t.get("stop"))
    x_px = _f(t.get("exit_price") if t.get("exit_price") is not None else t.get("exit"))
    reason = t.get("exit_reason") or t.get("exit_kind")
    open_ = str(reason or "").upper() == "OPEN" or x_px is None or t.get("exit_t") is None
    side = "BUY" if d == 1 else "SELL"
    fills = [{"id": f"{tid}:E", "t": float(et_), "px": entry, "qty": q, "side": side, "kind": "entry", "bot": bot, "acct": acct,
              "real": False, "src": src, "model_px": entry, "slip_ticks": 0.0, "trade": tid}]
    path = [[et_, stop]] if stop is not None else []
    be_t = _i(t.get("be_t"))
    if be_t and stop is not None and entry is not None:
        be_px = None
        if str(reason).upper() == "BE" and x_px is not None:
            be_px = round(x_px + d * TICK, 2)          # the model books BE with 1 tick of slippage
        else:
            try:
                be_px = round(entry + d * float((_params().get("be_off")) or 1.25), 2)
            except Exception:
                be_px = None
        if be_px is not None:
            path.append([be_t, be_px])
    stop_now = _f(t.get("stop_now"))
    if stop_now is not None and path and stop_now != path[-1][1]:
        path.append([int(t.get("last") or t.get("exit_t") or et_), stop_now])
    if not open_:
        kind = _exit_kind(reason)
        fills.append({"id": f"{tid}:X", "t": float(int(t["exit_t"])), "px": x_px, "qty": q, "side": "SELL" if d == 1 else "BUY",
                      "kind": kind, "bot": bot, "acct": acct, "real": False, "src": src, "model_px": x_px, "slip_ticks": 0.0, "trade": tid})
    usd = _f(t.get("pnl") if t.get("pnl") is not None else t.get("usd"))
    risk = _f(t.get("risk_usd")) or (round(abs(entry - stop) * PV * q, 2) if entry is not None and stop is not None and q else None)
    r = _f(t.get("pnl_r") if t.get("pnl_r") is not None else t.get("r"), 3)
    tr = {"id": tid, "bot": bot, "acct": acct, "real": False, "src": src, "side": "LONG" if d == 1 else "SHORT", "qty": q,
          "entry": {"t": et_, "px": entry}, "exit": None if open_ else {"t": int(t["exit_t"]), "px": x_px, "reason": reason},
          "stop_path": path, "target": _f(t.get("target")), "risk_usd": risk, "usd": usd, "r": r,
          "model": {"entry_t": et_, "entry": entry, "exit_t": None if open_ else int(t["exit_t"]), "exit": None if open_ else x_px, "usd": usd},
          "setup": setup, "entry_t": et_, "dir": d}
    return tr, fills


def _match(model_trades: list, real: list) -> list:
    """[(model, real|None)]: same entry_t first, then the same side within 10 minutes (engine/fill_audit._match); a paper
    trade of an ATLAS member prefers the real trade routed for that member (its "src" key)."""
    used, out = set(), []
    for m in model_trades:
        c = [r for r in real if id(r) not in used]
        if m.get("_key"):
            c = [r for r in c if r.get("_src") in (None, m["_key"])]
            c.sort(key=lambda r: r.get("_src") != m["_key"])
        hit = next((r for r in c if int(r["entry_t"]) == int(m["entry_t"])), None) or \
            next((r for r in c if r["dir"] == int(m["dir"]) and abs(int(r["entry_t"]) - int(m["entry_t"])) <= 600), None)
        if hit is not None:
            used.add(id(hit))
        out.append((m, hit))
    return out


def _attach_model(tr, m, fills, mfills):
    """The model's prices on a real trade (+ its fills' model_px / slip_ticks where the outcome is the same)."""
    d = tr["dir"]
    x = _f(m.get("exit_price") if m.get("exit_price") is not None else m.get("exit"))
    tr["model"] = {"entry_t": int(m["entry_t"]), "entry": _f(m.get("entry")), "exit_t": _i(m.get("exit_t")), "exit": x,
                   "usd": _f(m.get("pnl") if m.get("pnl") is not None else m.get("usd"))}
    same = lambda a, b: {"BE": "STOP", "BANK": "TARGET"}.get(str(a or "").upper(), str(a or "").upper()) == \
        {"BE": "STOP", "BANK": "TARGET"}.get(str(b or "").upper(), str(b or "").upper())
    for f in fills:
        if f["trade"] != tr["id"]:
            continue
        if f["kind"] == "entry" and m.get("entry") is not None:
            f["model_px"] = _f(m["entry"])
            f["slip_ticks"] = _ticks(f["px"], m["entry"], d)
        elif f["kind"] in ("stop", "target", "exit", "flatten") and x is not None and tr.get("exit") and \
                same(tr["exit"].get("reason") or f["kind"], m.get("exit_reason") or m.get("exit_kind")):
            f["model_px"] = x
            if f.get("real"):
                f["slip_ticks"] = _ticks(x, f["px"], d)


def _model_limits(setups: dict, now: int) -> list:
    """Each armed LIT setup's limit as the model's order ("model": true, acct null: LIT routes at market on the 1m CISD; the
    limit is the backtest's level, live 30 min): FILLED when the setup filled, CANCELLED when it expired, WORKING while armed."""
    out = []
    for s in setups.values():
        pl = (s or {}).get("plan") if isinstance(s, dict) else None
        if not isinstance(pl, dict) or pl.get("limit") is None or not pl.get("armed_t"):
            continue
        st = str(s.get("status") or "")
        tr = s.get("trade") if isinstance(s.get("trade"), dict) else {}
        state = "FILLED" if st == "filled" or tr.get("entry_t") else "WORKING" if st in ("armed", "tapped") and int(pl.get("expires_t") or 0) > now \
            else "CANCELLED"
        end = _i(tr.get("entry_t")) if state == "FILLED" else (None if state == "WORKING" else _i(pl.get("expires_t")))
        out.append({"t": int(pl["armed_t"]), "t_end": end, "bot": "lit", "acct": None, "type": "LIMIT",
                    "side": "SELL" if int(s.get("dir") or 0) == -1 else "BUY", "px": _f(pl["limit"]), "qty": _i(tr.get("qty")) or 0,
                    "state": state, "why": f"model limit (LIT setup {s.get('id')}, not routed): {s.get('status_text') or st}"[:200],
                    "model": True, "stop": _f(pl.get("stop")), "target": _f(pl.get("target"))})
    return out


def _atlas_paper(bot, day) -> list:
    """ATLAS members' paper trades of `day` (bot.second; candidates and Zlarior's own variants left out)."""
    out = []
    sec = _g(bot, "second", None) or {}
    for k, s in (sec.get("strategies") or {}).items():
        if not isinstance(s, dict) or s.get("on") is False or s.get("candidate") or str(k).startswith(("lit", "scalp")):
            continue
        for t in s.get("trades") or []:
            if isinstance(t, dict) and t.get("entry_t") and (t.get("day") or N.trading_day(int(t["entry_t"]))) == day:
                out.append({**t, "_key": k, "_short": s.get("short") or k, "_label": s.get("label") or k})
    return out


def _blitz_paper(bot, day) -> list:
    S = _g(bot, "blitz", None)
    if not isinstance(S, dict):
        return []
    out = []
    for led, tag in (("ledger", "25K eval"), ("ledger50", "50K + LIT")):
        for r in S.get(led) or []:
            if isinstance(r, dict) and r.get("entry_t") and r.get("exit_kind") != "SKIP" and \
                    (r.get("day") or N.trading_day(int(r["entry_t"]))) == day:
                out.append({**r, "_tag": tag})
    return out


def _paper_setup(kind, t, notes=()) -> dict:
    return {"kind": kind, "t_sweep": _i(t.get("hunt_t")), "sweep_ext": None, "swept": [{"px": _f(t.get("pool_px")), "label": "pool"}] if t.get("pool_px") else [],
            "t_idm": None, "t_disp": None, "t_cisd": _i(t.get("signal_t")), "cisd": None, "notes": [n for n in notes if n]}


# ============================================================================================ thoughts / levels / now
def _thought_of(m: dict) -> dict:
    lvl = m.get("level") if m.get("level") in LEVELS else "info"
    px = next((_f(m.get(k)) for k in ("fill", "px", "price", "limit", "stop") if _f(m.get(k)) is not None), None)
    if px is None:
        px = _first_px(m.get("text"))
    return {"t": int(m.get("t") or 0), "bot": STRAT_BOT.get(m.get("strat"), "sys"), "stage": m.get("kind"),
            "title": str(m.get("title") or "")[:120], "text": str(m.get("text") or "")[:400], "level": lvl, "px": px,
            "key": m.get("key"), "_et": _i(m.get("entry_t"))}


_BRAIN_TITLE = {"sweep": "Level swept", "box": "Session box closed", "cisd": "5m CISD", "armed": "Setup armed", "expired": "Setup expired",
                "rejected": "Setup rejected", "blocked": "Setup skipped", "stage": "Now", "entry": "Model entry", "exit": "Model exit",
                "tapped": "Limit tapped", "trade": "In trade"}


def _brain_thought(r: dict, setups: dict) -> dict:
    k, txt = str(r.get("kind") or ""), str(r.get("text") or "")
    lvl = {"armed": "good", "entry": "good", "expired": "warn", "rejected": "dim", "blocked": "dim", "box": "dim", "stage": "dim"}.get(k, "info")
    if k == "sweep" and "✗" in txt:
        lvl = "dim"
    if k == "exit":
        lvl = "good" if "+" in txt.split("$")[-1][:2] else "warn"
    sid = str(r.get("key") or "").split(":", 1)[1] if ":" in str(r.get("key") or "") else ""
    s = setups.get(sid) or {}
    px = None
    if k == "armed":
        px = _f((s.get("plan") or {}).get("limit"))
    elif k in ("cisd", "rejected", "blocked"):
        px = _f(s.get("cisd"))
    if px is None:
        px = _first_px(txt)
    return {"t": int(r.get("t") or 0), "bot": "lit", "stage": r.get("stage") if k == "stage" else k, "title": _BRAIN_TITLE.get(k, k.capitalize() or "Brain"),
            "text": txt.replace("Now: ", "", 1)[:400], "level": lvl, "px": px, "key": "lit:" + str(r.get("key"))}


def _narr_rows(day: str, live: bool) -> list:
    rows = _jl(os.path.join(NARR_DIR or N.LOG_DIR, f"{day}.jsonl"))
    if live:
        try:
            have = {m.get("key") for m in rows}
            rows += [m for m in N.NARRATOR.feed(N.KEEP) if N.trading_day(m.get("t") or 0) == day and m.get("key") not in have]
        except Exception:
            pass
    return [m for m in rows if isinstance(m, dict) and N.trading_day(int(m.get("t") or 0)) == day]


def _levels_live(bot, day, t0) -> list:
    out = []
    b = _g(bot, "brain", None) or {}
    for lv in b.get("levels") or []:
        if isinstance(lv, dict) and lv.get("price") is not None:
            out.append({"bot": "lit", "px": _f(lv.get("price")), "label": lv.get("label"), "t0": _hm_t(day, t0, lv.get("known_hm")), "t1": None,
                        "taken_t": _i(lv.get("taken_t")) if lv.get("taken") else None, "kind": lv.get("kind"), "side": lv.get("side")})
    return out


def _hm_t(day, t0, hm):
    """'03:00' on the session of `day` (18:00 the evening before -> 17:00) -> unix; None when unknown."""
    try:
        h, m = (int(x) for x in str(hm).split(":"))
        d = dt.date.fromisoformat(day)
        if h >= 17:                                 # 17:00-18:00: yesterday's close (a level known before the session)
            d = d - dt.timedelta(days=1)
        return int(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=N.ET).timestamp())
    except Exception:
        return t0


def _levels_atlas_blitz(bot, day, t0, t1) -> list:
    out = []
    sec = _g(bot, "second", None) or {}
    for k, s in (sec.get("strategies") or {}).items():
        if not isinstance(s, dict) or s.get("on") is False or s.get("candidate") or str(k).startswith(("lit", "scalp")):
            continue
        for x in ((s.get("brain") or {}).get("levels") or []):
            if isinstance(x, dict) and x.get("px") is not None:
                out.append({"bot": "atlas", "px": _f(x.get("px")), "label": f"{s.get('short') or k} {x.get('name') or 'S/R'}", "t0": t0,
                            "t1": None, "taken_t": None, "stage": x.get("stage")})
    S = _g(bot, "blitz", None)
    try:
        if isinstance(S, dict) and S.get("eng"):
            from . import blitz as BZ
            b = (BZ.compact(S, n=40) or {}).get("band") or {}
            if b.get("o0") is not None and b.get("date") == day:
                rows = [r for r in b.get("checks") or [] if r.get("up") is not None]
                for n, r in enumerate(rows):
                    nxt = int(rows[n + 1]["t"]) if n + 1 < len(rows) else None
                    for nm, px in (("band up", r["up"]), ("band low", r["lo"])):
                        out.append({"bot": "blitz", "px": _f(px), "label": f"BLITZ {nm} {r.get('hm') or ''}".strip(), "t0": int(r["t"]),
                                    "t1": nxt, "taken_t": None})
                out.append({"bot": "blitz", "px": _f(b["o0"]), "label": "BLITZ 09:30 open", "t0": _hm_t(day, t0, "09:30"), "t1": t1,
                            "taken_t": None})
    except Exception:
        pass
    return out


def _now_panels(bot, now, lv=None) -> dict | None:
    """The thinking panels exactly as the Live View shows them (lv = a liveview view()/phone_view() already built)."""
    from . import liveview_api as LV
    try:
        if not isinstance(lv, dict) or "strategies" not in lv:
            st = _g(bot, "state", None) or {}
            price = _f(st.get("price"))
            lv = {"strategies": {"lit": LV.lit_layer(bot, now, price)}}
            try:
                lv["strategies"].update(LV.atlas_layer(bot, now, [], now, price))
            except Exception:
                pass
            try:
                bl = LV.blitz_layer(bot, now, price)
                if bl:
                    lv["strategies"]["scalp"] = bl
            except Exception:
                pass
            try:                                       # the structure line, the playbook rule, the open trade's advice
                lv["structure"] = LV.structure_block(bot, now, price)
                LV._structure_notes(lv, bot, now)
            except Exception:
                pass
        S = lv.get("strategies") or {}
        at = S.get("atlas") or {}
        sc = S.get("scalp") or {}
        return {"lit": (S.get("lit") or {}).get("thinking"),
                "atlas": {"members": [{k: m.get(k) for k in ("key", "short", "stage", "text", "first_fail", "checks", "window")}
                                      for m in at.get("members") or [] if isinstance(m, dict) and not m.get("candidate")],
                          "rule": at.get("rule"), "structure": at.get("structure_note"), "account": at.get("account")} if at else None,
                "blitz": sc.get("thinking") if isinstance(sc.get("thinking"), dict) else ({"headline": sc.get("text")} if sc else None)}
    except Exception:
        return None


def _structure(bot, day, live, now, bars, lv, errors):
    try:
        if live:
            if isinstance(lv, dict) and lv.get("structure") is not None:
                return lv["structure"]
            from . import liveview_api as LV
            return LV.structure_block(bot, now)
        b1 = bars.get("1m") or []
        if not b1:
            return None
        t_end = int(b1[-1][0]) + 60
        with _MX:
            hit = _STRUCT.get(day)
            if hit and hit[0] == (len(b1), t_end):
                return hit[1]
        from . import structure as ST
        d5, d1 = _frames()
        r1 = _rows(d1[(d1["time"] >= t_end - 12 * 86400) & (d1["time"] < t_end)])[-6000:] if d1 is not None and len(d1) else b1
        r5 = _rows(d5[(d5["time"] >= t_end - 15 * 86400) & (d5["time"] < t_end)]) if d5 is not None and len(d5) else bars.get("5m") or []
        A = ST.analyze([r[:5] for r in r1], [r[:5] for r in r5], t_end, None)
        out = ST.block_from(A, t_end, float(b1[-1][4]))
        with _MX:
            if len(_STRUCT) > 20:
                _STRUCT.clear()
            _STRUCT[day] = ((len(b1), t_end), out)
        return out
    except Exception as e:
        _err(errors, "structure", e)
        return None


# ============================================================================================ the whole answer
def _ninja(ad) -> bool:
    return ad is not None and str(_g(ad, "name", "") or "").lower().startswith("ninja")


def _bots(bot) -> dict:
    try:
        acct = bot._push_account() if callable(_g(bot, "_push_account", None)) else None
    except Exception:
        acct = None
    ad = _g(bot, "adapter", None)
    cfg = _g(bot, "cfg", None) or {}
    ab, ac = _g(bot, "acct_b", None), _g(bot, "acct_c", None)
    lit_real = str(cfg.get("adapter") or _g(ad, "name", "") or "paper").lower().startswith("ninja")

    def plan_of(A):
        try:
            return str((_g(A, "spec", None) or {}).get("plan_label") or (_g(A, "spec", None) or {}).get("plan") or "")
        except Exception:
            return ""
    c_real = False
    try:
        c_real = ac is not None and not (ac.disabled_reason() if callable(_g(ac, "disabled_reason", None)) else True)
    except Exception:
        c_real = False
    return {"lit": {"name": BOTS["lit"][0], "color": BOTS["lit"][1], "account": acct or _g(ad, "account", None), "real": lit_real,
                    "plan": "LIT method · MFFU eval"},
            "atlas": {"name": BOTS["atlas"][0], "color": BOTS["atlas"][1], "account": _g(ab, "name", None) if ab is not None else None,
                      "real": ab is not None and _ninja(_g(ab, "adapter", None)), "plan": plan_of(ab) or "EMA · MACD · S/R (paper)"},
            "blitz": {"name": BOTS["blitz"][0], "color": BOTS["blitz"][1], "account": _g(ac, "name", None) if ac is not None else None,
                      "real": bool(c_real) and _ninja(_g(ac, "adapter", None)), "plan": plan_of(ac) or "scalper · PAPER shadow"}}


def _empty(now, day, why) -> dict:
    try:
        t = int(now or time.time())
    except Exception:
        t = int(time.time())
    try:
        d = str(dt.date.fromisoformat(str(day))) if day else N.trading_day(t)
    except Exception:
        d = N.trading_day(t)
    t0, t1 = session_bounds(d)
    return {"v": VERSION, "kind": KIND, "t": t, "day": d, "live": d == N.trading_day(t), "t0": t0, "t1": t1, "bars": {"1m": [], "5m": []},
            "bots": {k: {"name": v[0], "color": v[1], "account": None, "real": False, "plan": ""} for k, v in BOTS.items()},
            "fills": [], "trades": [], "orders": [], "thoughts": [], "levels": [], "structure": None, "now": None, "errors": [why[:200]]}


def build(bot, day: str | None = None, now: int | None = None, lv: dict | None = None) -> dict:
    """The Holodeck answer for trading day `day` (default today's). lv: the Live View answer already built this minute (the
    publisher's phone_view), reused for the thinking panels and the structure. Never raises."""
    try:
        return _build(bot, day, now, lv)
    except Exception as e:
        return _empty(now, day, f"build: {e.__class__.__name__}: {e}")


def _build(bot, day, now, lv) -> dict:
    t_start = time.perf_counter()
    errors: list = []
    try:
        now = int(now or _now(bot))
    except Exception:
        now = int(time.time())
    today = N.trading_day(now)
    try:
        day = str(dt.date.fromisoformat(str(day))) if day else today
    except Exception:
        errors.append(f"bad day {day!r}: today's session instead")
        day = today
    live = day == today
    t0, t1 = session_bounds(day)
    out = {"v": VERSION, "kind": KIND, "t": now, "day": day, "live": live, "t0": t0, "t1": t1, "bars": {"1m": [], "5m": []},
           "bots": {}, "fills": [], "trades": [], "orders": [], "thoughts": [], "levels": [], "structure": None, "now": None,
           "errors": errors}
    try:
        out["bots"] = _bots(bot)
    except Exception as e:
        _err(errors, "bots", e)
        out["bots"] = {k: {"name": v[0], "color": v[1], "account": None, "real": False, "plan": ""} for k, v in BOTS.items()}
    bars = {"1m": [], "5m": []}
    try:
        bars = day_bars(bot, day, live)
        out["bars"] = {"1m": bars["1m"], "5m": bars["5m"]}
        out["bars_source"] = bars.get("source")
    except Exception as e:
        _err(errors, "bars", e)
    # 1. real fills (adapters, archives, ledgers)
    R = {"fills": [], "trades": [], "orders": [], "thoughts": [], "entries": set()}
    try:
        R = real_trades(bot, day, now, errors)
    except Exception as e:
        _err(errors, "real trades", e)
    fills, trades, orders, thoughts = R["fills"], R["trades"], R["orders"], R["thoughts"]
    # 2. the LIT model of the day: past days from the bars (replay), today from the Brain
    M = None
    brain = _g(bot, "brain", None) if live else None
    if not live or LIVE_REPLAY:
        M = model_day(day, errors, now=now if live else None)
    elif isinstance(brain, dict):
        M = _live_model(day, brain, now, errors)
    setups = {}
    lit_levels = []
    if M:
        setups = {s.get("id"): s for s in M.get("setups") or []}
        lit_levels = M.get("levels") or []
    if live and isinstance(brain, dict):
        for s in brain.get("setups") or []:
            if isinstance(s, dict) and s.get("id"):
                setups[s["id"]] = {**s, "detail": (setups.get(s["id"]) or {}).get("detail")}
        try:
            lit_levels = _levels_live(bot, day, t0) or lit_levels
        except Exception as e:
            _err(errors, "levels", e)
    out["levels"] = list(lit_levels)
    try:
        out["levels"] += _levels_atlas_blitz(bot, day, t0, t1) if live else []
    except Exception as e:
        _err(errors, "levels atlas/blitz", e)
    model_lit = list((M or {}).get("trades") or [])
    if live and isinstance(brain, dict):            # the Brain's trades the replay does not have yet (no exact exit time)
        for s in brain.get("setups") or []:
            tr = (s or {}).get("trade") if isinstance(s, dict) else None
            if isinstance(tr, dict) and tr.get("entry_t") and not any(int(m["entry_t"]) == int(tr["entry_t"]) for m in model_lit):
                plan = s.get("plan") or {}
                ex = str(tr.get("exit") or "")
                xp = plan.get("target") if ex in ("TARGET", "BANK") else plan.get("stop") if ex == "STOP" else None
                model_lit.append({"entry_t": int(tr["entry_t"]), "dir": s.get("dir"), "entry": tr.get("entry"), "stop": plan.get("stop"),
                                  "target": plan.get("target"), "qty": tr.get("qty"), "pnl": tr.get("pnl"), "pnl_r": tr.get("r"),
                                  "exit_reason": ex or "OPEN", "exit_price": xp, "exit_t": None, "sweep_ext": s.get("ext")})
        bt = brain.get("trade") if isinstance(brain.get("trade"), dict) else None
        if bt and bt.get("entry_t") and not any(int(m["entry_t"]) == int(bt["entry_t"]) for m in model_lit):
            model_lit.append({"entry_t": int(bt["entry_t"]), "dir": bt.get("dir"), "entry": bt.get("entry"), "stop": bt.get("stop0") or bt.get("stop"),
                              "target": bt.get("target"), "qty": bt.get("qty"), "exit_reason": "OPEN", "exit_price": None, "exit_t": None,
                              "stop_now": bt.get("stop")})
    try:
        setup_by_entry = {}
        for s in setups.values():
            tr = (s or {}).get("trade") if isinstance(s, dict) else None
            if isinstance(tr, dict) and tr.get("entry_t"):
                setup_by_entry[int(tr["entry_t"])] = s
        lit_real = [t for t in trades if t["bot"] == "lit"]
        for m, rt in _match(model_lit, lit_real):
            stp = lit_setup(setup_by_entry.get(int(m["entry_t"])), lit_levels, m.get("sweep_ext"))
            if rt is not None:
                _attach_model(rt, m, fills, [])
                if stp:
                    rt["setup"] = stp
            else:
                tr, ff = _model_trade(m, "lit", "model", stp)
                trades.append(tr)
                fills.extend(ff)
        for rt in lit_real:
            if rt.get("setup", {}).get("t_cisd") is None:
                s = setup_by_entry.get(int(rt["entry_t"]))
                if s:
                    rt["setup"] = lit_setup(s, lit_levels)
    except Exception as e:
        _err(errors, "LIT model", e)
    try:
        orders += _model_limits(setups, now)
    except Exception as e:
        _err(errors, "LIT model limits", e)
    # 3. ATLAS / BLITZ paper ledgers (real=false), matched to their real account trades when routed
    try:
        real_at = [t for t in trades if t["bot"] == "atlas" and t.get("src") != "model"]
        for m, rt in _match(_atlas_paper(bot, day), real_at):
            stp = _paper_setup(str(m.get("setup") or m.get("_label") or "ATLAS"), m, [m.get("_label"), m.get("note")])
            if rt is not None:
                _attach_model(rt, {**m, "exit_reason": m.get("exit_kind")}, fills, [])
                if not rt["setup"].get("t_cisd"):
                    rt["setup"] = {**stp, "notes": stp["notes"] + rt["setup"].get("notes", [])}
                continue
            tr, ff = _model_trade({**m, "exit_reason": m.get("exit_kind")}, "atlas", "paper", stp)
            tr["id"] = f"atlas:{m['_key']}:{int(m['entry_t'])}"
            for f in ff:
                f["trade"] = tr["id"]
                f["id"] = f["id"].replace("atlas:", f"atlas:{m['_key']}:", 1)
            trades.append(tr)
            fills.extend(ff)
    except Exception as e:
        _err(errors, "ATLAS paper", e)
    try:
        real_bz = [t for t in trades if t["bot"] == "blitz"]
        for m, rt in _match(_blitz_paper(bot, day), real_bz):
            mm = {**m, "exit_reason": m.get("exit_kind"), "exit_t": m.get("exit_t") if m.get("exit_kind") not in (None, "OPEN") else None}
            if rt is not None:
                _attach_model(rt, mm, fills, [])
                continue
            stp = {"kind": "BLITZ", "t_sweep": None, "sweep_ext": None, "swept": [], "t_idm": None, "t_disp": None,
                   "t_cisd": _i(m.get("entry_t")), "cisd": None, "notes": [f"PAPER {m.get('_tag')}"]}
            tr, ff = _model_trade(mm, "blitz", "paper", stp)
            tr["id"] = f"blitz:{m.get('_tag', '').split()[0]}:{int(m['entry_t'])}"
            for f in ff:
                f["trade"] = tr["id"]
                f["id"] = tr["id"] + (":E" if f["kind"] == "entry" else ":X")
            trades.append(tr)
            fills.extend(ff)
    except Exception as e:
        _err(errors, "BLITZ paper", e)
    # 4. thoughts: narrator + Brain log + order events + model events
    try:
        narr = [_thought_of(m) for m in _narr_rows(day, live)]
        keys = {x.get("key") for x in narr}
        thoughts = [x for x in thoughts if x.get("key") not in keys]       # the narrator already told these order events
        logs = []
        if live and isinstance(brain, dict):
            logs = list(brain.get("log") or [])          # the newest rows; the day's file has the rest
        try:
            from . import brain as BR
            have = {r.get("key") for r in logs if isinstance(r, dict)}
            logs += [r for r in BR.read_day_log(day, BRAIN_DIR or BR.BRAIN_DIR, keep=2000) if r.get("key") not in have]
        except Exception:
            pass
        if not logs and M:
            logs = M.get("log") or []
        bt_ = [_brain_thought(r, setups) for r in logs if isinstance(r, dict) and r.get("key")]
        # the Brain's / narrator's "model entry / exit" rows of a trade that was routed: the real fills tell it
        real_lit = [t for t in trades if t["bot"] == "lit" and t.get("real")]
        model_ts = {t["entry_t"] for t in real_lit} | {int(t["model"]["entry_t"]) for t in real_lit if t.get("model")} | \
            {int(t["model"]["exit_t"]) for t in real_lit if t.get("model") and t["model"].get("exit_t")}
        bt_ = [x for x in bt_ if x["key"] not in keys]

        def routed_model_row(x):
            k_ = str(x.get("key") or "")
            return x["bot"] == "lit" and (k_.startswith("lit:entry:") or k_.startswith("lit:exit:")) and _i(k_.rsplit(":", 1)[-1]) in model_ts
        allt = [x for x in narr + thoughts + bt_ if not routed_model_row(x)]
        # an entry / exit message without a price: anchored at its trade's fill
        by_et = {(t["bot"], int(t["entry_t"])): t for t in trades if t.get("entry_t") is not None}
        for x in allt:
            tr_ = by_et.get((x["bot"], x.get("_et"))) if x.get("_et") else None
            if tr_ and x["stage"] == "exit" and (tr_.get("exit") or {}).get("px") is not None:
                x["px"] = tr_["exit"]["px"]
            elif tr_ and x["px"] is None:
                x["px"] = tr_["entry"]["px"]
        allt = [{k: v for k, v in x.items() if k != "_et"} for x in allt]
        allt = [x for x in allt if t0 - 3600 <= int(x["t"]) <= t1 + 3600]
        seen, uniq = set(), []
        for x in sorted(allt, key=lambda x: (x["t"], x["bot"])):
            k = x.get("key") or (x["t"], x["bot"], x["title"], x["text"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(x)
        out["thoughts"] = uniq
    except Exception as e:
        _err(errors, "thoughts", e)
        out["thoughts"] = sorted([{k: v for k, v in x.items() if k != "_et"} for x in thoughts], key=lambda x: x["t"])
    for tr in trades:
        tr.pop("entry_t", None)
        tr.pop("dir", None)
        tr.pop("routed_t", None)
        tr.pop("_src", None)
        tr.setdefault("src", "model")
    out["fills"] = sorted(fills, key=lambda f: (f["t"], f["id"]))
    out["trades"] = sorted(trades, key=lambda t: (t["entry"]["t"] or 0, t["id"]))
    out["orders"] = sorted([{k: v for k, v in o.items() if k != "entry_t"} for o in orders], key=lambda o: (o["t"] or 0))
    out["structure"] = _structure(bot, day, live, now, bars, lv, errors)
    if live:
        try:
            out["now"] = _now_panels(bot, now, lv)
        except Exception as e:
            _err(errors, "now", e)
    out["build_ms"] = int((time.perf_counter() - t_start) * 1000)
    return out


# ============================================================================================ days list
def days(bot, n: int = 30, now: int | None = None) -> list:
    """The last n trading days with trades or fills, newest first: [{"day", "n_trades", "real_n", "real_usd", "model_n", "model_usd"}].
    Real = the bots' routed ledgers (memory + disk); model = engine/fill_audit's replay cache (logs/exec_audit) and the 2026
    LIT run (research/runs/lit_live.json)."""
    now = int(now or _now(bot))
    out: dict = {}
    try:
        led = _disk_ledgers(bot)
        for key, _A, _ad, rows, _n in _accounts(bot):
            led[key] = list(led.get(key) or []) + list(rows)
        for key, rows in led.items():
            seen = set()
            for r in rows:
                if not isinstance(r, dict) or r.get("t") is None or r.get("entry_t") is None:
                    continue
                k_ = _rkey(r)
                if k_ in seen:
                    continue
                seen.add(k_)
                d = N.trading_day(int(r["entry_t"]))
                x = out.setdefault(d, {"day": d, "n_trades": 0, "real_n": 0, "real_usd": 0.0, "model_n": 0, "model_usd": 0.0, "_e": set()})
                if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok") is not False and (key, r["entry_t"]) not in x["_e"]:
                    x["_e"].add((key, r["entry_t"]))
                    x["real_n"] += 1
                if r.get("side") == "exit" and r.get("pnl") is not None:
                    x["real_usd"] += float(r["pnl"])
    except Exception:
        pass
    try:
        rc = _rjson(os.path.join(_store(), "replay_cache.json"), {}) or {}
        for d, v in rc.items():
            ts = (v or {}).get("trades") or []
            if ts:
                x = out.setdefault(d, {"day": d, "n_trades": 0, "real_n": 0, "real_usd": 0.0, "model_n": 0, "model_usd": 0.0, "_e": set()})
                x["model_n"] = len(ts)
                x["model_usd"] = round(sum(float(t.get("pnl") or 0) for t in ts), 2)
    except Exception:
        pass
    if CSV_FALLBACK:
        try:
            r = _rjson(os.path.join(ROOT, "research", "runs", "lit_live.json"), {}) or {}
            cols = r.get("trade_cols") or []
            for t in r.get("trades") or []:
                row = dict(zip(cols, t))
                d = str(row.get("day") or "")
                if d and d not in out:
                    out[d] = {"day": d, "n_trades": 0, "real_n": 0, "real_usd": 0.0, "model_n": 1, "model_usd": _f(row.get("pnl")) or 0.0, "_e": set()}
        except Exception:
            pass
    rows = []
    for d, x in out.items():
        if d > N.trading_day(now):
            continue
        x.pop("_e", None)
        x["n_trades"] = x["real_n"] or x["model_n"]
        x["real_usd"] = round(x["real_usd"], 2)
        if x["n_trades"]:
            rows.append(x)
    rows.sort(key=lambda x: x["day"], reverse=True)
    return rows[:max(1, int(n))]


# ============================================================================================ phone files
PHONE_FILE, HIST_FILE = "holo.json", "holo_hist.json"
PHONE_MAX = 300 * 1024
HIST_MAX = 400 * 1024
HIST_DAYS = 10
HIST_EVERY_S = 600
HIST_PAD_S = 45 * 60
_HIST = {"t": 0.0, "key": None, "val": None, "ms": None}


def _size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), default=str))


def _windows(out) -> list:
    """[(a, z)] the trading windows of a day (each trade / armed setup / order ±30 min) for trimming the 1m bars."""
    w = []
    for tr in out.get("trades") or []:
        a = (tr.get("setup") or {}).get("t_sweep") or tr["entry"]["t"]
        z = (tr.get("exit") or {}).get("t") or out.get("t")
        w.append((int(min(a, tr["entry"]["t"])) - 1800, int(z) + 1800))
    for o in out.get("orders") or []:
        w.append((int(o["t"]) - 1800, int(o.get("t_end") or o["t"]) + 1800))
    return w


def phone(bot, now: int | None = None, lv: dict | None = None) -> dict:
    """holo.json: today's Holodeck for the phone (<= PHONE_MAX bytes: the 1m bars are trimmed to the trading windows ±30 min
    first, then thinned; every fill / trade / thought is kept). Never raises."""
    try:
        v = build(bot, None, now, lv=lv)
        if _size(v) > PHONE_MAX:
            v["trimmed"] = True
            ws = _windows(v)
            last = (v["bars"]["1m"] or [[0]])[-1][0]
            keep = [b for b in v["bars"]["1m"] if any(a <= b[0] <= z for a, z in ws) or b[0] >= last - 3 * 3600]
            v["bars"]["1m"] = keep
        while _size(v) > PHONE_MAX and len(v["bars"]["1m"]) > 120:
            v["bars"]["1m"] = v["bars"]["1m"][-max(120, len(v["bars"]["1m"]) * 2 // 3):]
            v["trimmed"] = True
        if _size(v) > PHONE_MAX and isinstance(v.get("structure"), dict):
            v["structure"] = {k: v["structure"].get(k) for k in ("summary", "per_strategy", "trend", "t") if k in v["structure"]}
            v["trimmed"] = True
        if _size(v) > PHONE_MAX:
            v["levels"] = [x for x in v["levels"] if x.get("bot") != "blitz"] + [x for x in v["levels"] if x.get("bot") == "blitz"][-20:]
        v["bytes"] = _size(v)
        return v
    except Exception as e:
        return {"v": VERSION, "kind": KIND, "t": int(now or time.time()), "error": f"{e.__class__.__name__}: {e}"[:200]}


def _hist_key(bot):
    """Changes when a trade closes / a fill lands (a cheap look at the ledgers' lengths and exits)."""
    try:
        k = [len(_g(bot, "ledger", None) or [])]
        for a in ("acct_b", "acct_c"):
            A = _g(bot, a, None)
            k.append(len(_g(A, "ledger", None) or []) if A is not None else -1)
        b = _g(bot, "brain", None) or {}
        k.append(sum(1 for s in b.get("setups") or [] if isinstance(s, dict) and (s.get("trade") or {}).get("exit")))
        S = _g(bot, "blitz", None)
        k.append(len((S or {}).get("ledger") or []) if isinstance(S, dict) else -1)
        return tuple(k)
    except Exception:
        return None


def hist(bot, now: int | None = None, force: bool = False) -> dict:
    """holo_hist.json: the last HIST_DAYS trading days' trades (fills, stop paths, setups, the thoughts inside each trade and
    a 1m bar window of the trade ±45 min), <= HIST_MAX bytes. Cached: rebuilt at most every HIST_EVERY_S or when a trade
    closes / an order is routed. Never raises."""
    now = int(now or _now(bot))
    key = (_hist_key(bot), N.trading_day(now))
    with _MX:
        if not force and _HIST["val"] is not None and (_HIST["key"] == key and now - _HIST["t"] < HIST_EVERY_S):
            return _HIST["val"]
        if not force and _HIST["val"] is not None and now - _HIST["t"] < 60:
            return _HIST["val"]                     # at most one rebuild a minute even while trades close
    t_s = time.perf_counter()
    try:
        ds = []
        d = dt.date.fromisoformat(N.trading_day(now))
        while len(ds) < HIST_DAYS:
            d -= dt.timedelta(days=1)
            if d.weekday() < 5:
                ds.append(d.isoformat())
        days_out = []
        for day in ds:
            v = build(bot, day, now)
            b1 = v["bars"]["1m"]
            trs = []
            for tr in v["trades"]:
                a = int(min((tr.get("setup") or {}).get("t_sweep") or tr["entry"]["t"], tr["entry"]["t"])) - HIST_PAD_S
                z = int((tr.get("exit") or {}).get("t") or tr["entry"]["t"]) + HIST_PAD_S
                trs.append({**tr, "fills": [f for f in v["fills"] if f["trade"] == tr["id"]],
                            "thoughts": [x for x in v["thoughts"] if a <= x["t"] <= z and x["bot"] in (tr["bot"], "sys")],
                            "win": [a, z]})
            if not trs:
                continue
            ws = sorted(t["win"] for t in trs)
            merged = []
            for a, z in ws:
                if merged and a <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], z)
                else:
                    merged.append([a, z])
            bars = [b for b in b1 if any(a <= b[0] <= z for a, z in merged)]
            days_out.append({"day": day, "trades": trs, "bars_1m": bars, "real": any(t.get("real") for t in trs),
                             "usd": round(sum(float(t.get("usd") or 0) for t in trs), 2), "errors": v.get("errors") or []})
        out = {"v": VERSION, "kind": "le-holo-hist", "t": now, "days": days_out}
        # size: older days' bars go to 5m first, then the oldest days' bars, then their thoughts
        i = len(days_out) - 1
        while _size(out) > HIST_MAX and i >= 0:
            dd = days_out[i]
            if dd.get("bars_1m") and not dd.get("bars_5m"):
                dd["bars_5m"] = _agg5([b if len(b) > 5 else b + [0] for b in dd.pop("bars_1m")])
                dd["bars_1m"] = []
            i -= 1
        i = len(days_out) - 1
        while _size(out) > HIST_MAX and i >= 0:
            for tr in days_out[i]["trades"]:
                tr["thoughts"] = [x for x in tr["thoughts"] if x["level"] != "dim"][:20]
            days_out[i]["bars_5m"] = []
            i -= 1
        out["trimmed"] = _size(out) > HIST_MAX or any(("bars_5m" in d_) for d_ in days_out)
        out["build_ms"] = int((time.perf_counter() - t_s) * 1000)
        out["bytes"] = _size(out)
        with _MX:
            _HIST.update(t=now, key=key, val=out, ms=out["build_ms"])
        return out
    except Exception as e:
        return {"v": VERSION, "kind": "le-holo-hist", "t": now, "days": [], "error": f"{e.__class__.__name__}: {e}"[:200]}


# ============================================================================================ routes
@router.get("/api/next/holo")
def r_holo(day: str = ""):
    try:
        return _J(build(_bot(), day or None))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)


@router.get("/api/next/holo/days")
def r_days(n: int = 30):
    try:
        bot = _bot()
        return _J({"t": _now(bot), "days": days(bot, n)})
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)
