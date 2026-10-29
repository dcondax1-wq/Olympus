"""The discretion advisor (owner 2026-10-28: "trade like a person, not a fixed rr ... learn how to trade"): a READ-ONLY shadow
that looks at every live / paper trade with a structure trader's eyes, writes down what each structure rule would have done
and why, and afterwards scores each piece of advice in dollars against what really happened.

It NEVER changes an order, a stop, a target or a size. The bots keep their written rules (docs/PLAYBOOK.md); the advisor is how
a rule earns a place: a running tally per rule ("breakeven on a 5m CHoCH would have saved $X over N trades"), shown as
suggestions on the Learning page (engine/live_learning.suggestions). Research on the full history is in
research/writeups/structure-management.md (tools/structure_manage.py); each rule here is the same rule as one research variant.

The rules (structure from engine/structure.Tracker on the trade's own bars, closed bars only, acting from the next 1m bar):
  be_choch     a 5m CHoCH against the trade once it was +0.75R: stop to entry + 1.25      (research choch_5m_k0.75_be)
  exit_choch   a 5m CHoCH against the trade once it was +1R: out at the next open          (choch_5m_k1.0_exit)
  trail_15m    after a 15m break in the trade's favour once +1R: stop 1 tick beyond the new protected swing (strail_15m_k1.0_any)
  trail_5m     after a 5m BOS in the trade's favour once +1R: same on 5m                   (strail_5m_k1.0_bos)
  tp_pool      take the whole trade off 1 tick before the first untaken opposing pool >= 1R away (engine/structure.pools)
  skip_htf     skip the trade when the 1h trend was against it at the entry ($0 instead)  (htf_1h_skip_against)

Scoring (after the trade is finished): the same bars walked twice by one small executor, once with the strategy's own
management (base) and once with the rule; the rule's $ = the REAL $ + (rule points - base points) x micros x $2 (the
difference method: fills, commission and the real exit stay as booked, only the rule's change is added). A rule that never
fired on a trade scores $0 there.

Stores (machine-local, logs/ is gitignored; tests pass a temp dir): <store>/<strategy>.jsonl one record per scored trade,
<store>/tally.json the running tally per strategy and rule. The cloud keeps the same block in its state ("advisor").

  python -X utf8 -m tests.test_advisor
"""
from __future__ import annotations

import json
import os
import time

import numpy as np

from engine import structure as ST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "logs", "advisor")
TICK, PV, BE_OFF = 0.25, 2.0, 1.25
VERSION = 1
KEEP = 400
STRATS = {"lit": "Zlarior", "atlas": "ATLAS", "scalp": "BLITZ"}
RULES = {
    "be_choch": {"label": "Breakeven on a 5m CHoCH against after +0.75R", "kind": "choch", "tf": "5m", "k": 0.75, "act": "be",
                 "playbook": {"lit": "Z-S3", "atlas": "A-S2", "scalp": "B-S1"}, "research": "choch_5m_k0.75_be"},
    "exit_choch": {"label": "Exit on a 5m CHoCH against after +1R", "kind": "choch", "tf": "5m", "k": 1.0, "act": "exit",
                   "playbook": {"lit": "Z-S3", "atlas": "A-S2", "scalp": "B-S1"}, "research": "choch_5m_k1.0_exit"},
    "trail_15m": {"label": "Trail to the 15m protected swing after a 15m break in favour (+1R)", "kind": "trail", "tf": "15m",
                  "k": 1.0, "kinds": "any", "playbook": {"lit": "Z-S4", "atlas": "A-S2", "scalp": "B-S1"}, "research": "strail_15m_k1.0_any"},
    "trail_5m": {"label": "Trail to the 5m protected swing after a 5m BOS in favour (+1R)", "kind": "trail", "tf": "5m", "k": 1.0,
                 "kinds": "bos", "playbook": {"lit": "Z-S4", "atlas": "A-S2", "scalp": "B-S1"}, "research": "strail_5m_k1.0_bos"},
    "tp_pool": {"label": "Take profit at the first opposing liquidity pool (>= 1.5R)", "kind": "pool", "min_r": 1.5,
                "playbook": {"lit": "Z-S2", "atlas": "A-S2", "scalp": "B-S1"}, "research": "tgt_cap_lit1h_r1.5"},
    "skip_htf": {"label": "Skip when the 1h trend is against the trade", "kind": "htf", "tf": "1h",
                 "playbook": {"lit": "Z-S1", "atlas": "A-S1", "scalp": "B-S1"}, "research": "htf_1h_skip_against"},
}
# what the research said about each rule (LIT, 2026 H1 / H2 at the LIT size rule, research/lit/structure_results.json)
RESEARCH_NOTE = "Research on LIT 2026 (tools/structure_manage.py): not adopted (see research/writeups/structure-management.md)."
RESEARCH_JSON = os.path.join(ROOT, "research", "lit", "structure_results.json")
_RN: dict = {}


def research_note(rid: str) -> str:
    """What the research said about the rule's variant (LIT size rule, 2026 H1 / H2 change vs live, 2021-25 reference)."""
    var = (RULES.get(rid) or {}).get("research")
    if "R" not in _RN:
        try:
            with open(RESEARCH_JSON, encoding="utf-8") as fh:
                _RN["R"] = json.load(fh)
        except (OSError, ValueError):
            _RN["R"] = {}
    R = _RN["R"]
    o, b = R.get(var), R.get("live")
    if not o or not b:
        return RESEARCH_NOTE
    try:
        d = {s: o["lit"][s]["net"] - b["lit"][s]["net"] for s in ("H1", "H2", "2021-25")}
        return (f"Research on the real LIT trades (run {var}): 2026 H1 {d['H1']:+,.0f} $, H2 {d['H2']:+,.0f} $ vs live "
                f"(2021-25 reference {d['2021-25']:+,.0f} $); not adopted (research/writeups/structure-management.md).")
    except (KeyError, TypeError):
        return RESEARCH_NOTE


# ================================================================================================ bars + structure
def _rows(x):
    return ST.as_rows(x)


def _arr(rows):
    A = np.array(rows, dtype=float) if rows else np.zeros((0, 5))
    return A[:, 0].astype(np.int64), A[:, 1], A[:, 2], A[:, 3], A[:, 4]


def frames_events(b1: list, t_end: int | None = None) -> dict:
    """{tf: structure.frame_events} for 1m / 5m / 15m / 1h built from 1m rows (closed bars up to t_end)."""
    rows = [r for r in b1 if t_end is None or r[0] + 60 <= t_end]
    out = {}
    if not rows:
        return out
    out["1m"] = ST.frame_events(*_arr(rows), 60)
    for tf in ("5m", "15m", "1h"):
        R = ST.resample(rows, ST.TF_SECS[tf], 60)
        if R:
            out[tf] = ST.frame_events(*_arr(R), ST.TF_SECS[tf])
    return out


# ================================================================================================ the executor
def _manage_spec(strategy: str, trade: dict) -> dict:
    """The strategy's own post-fill management (the base walk)."""
    if strategy == "scalp":
        return {"be_r": None, "trail_r": (1.0, 1.5), "max_bars": 30, "tcheck": None}
    if strategy == "atlas":
        key = str(trade.get("key") or "")
        if key.startswith("ema"):
            return {"be_r": 1.0, "trail_r": None, "max_bars": None, "tcheck": None}
        return {"be_r": None, "trail_r": None, "max_bars": None, "tcheck": (15, 0.3, 0.5)}
    return {"be_r": 1.0, "trail_r": None, "max_bars": None, "tcheck": (15, 0.3, 0.5)}


def walk(rows: list, i0: int, d: int, entry: float, stop: float, target: float | None, spec: dict, rule: dict | None = None,
         ev: dict | None = None, pool: float | None = None, flat_mod: int = 955, secs: int = 60) -> dict:
    """One trade on 1m rows from bar i0 (the fill bar), real prices. spec = the strategy's management; rule = one advisor rule
    (None = base). Stop before target inside a bar; a moved stop fills at min(stop, open) - 1 tick; decisions at a bar's close
    act from the next bar. Returns {"pts", "kind", "t_exit", "mfe_r", "fired": [advice events]}."""
    risk = (entry - stop) * d
    if risk <= 0:
        return {"pts": 0.0, "kind": "BAD", "t_exit": None, "mfe_r": 0.0, "fired": []}
    cur, mfe, be_done, moved, cut = stop * d, 0.0, False, False, None
    tg = target * d if target is not None else None
    if rule and rule["kind"] == "pool" and pool is not None:
        tg = min(tg, pool * d - TICK) if tg is not None else pool * d - TICK
    e = entry * d
    fired = []
    cur_ev = None
    if rule and rule["kind"] in ("choch", "trail") and ev and rule["tf"] in ev:
        E = ev[rule["tf"]]
        cur_ev = [E, int(np.searchsorted(E["known_t"], int(rows[i0][0]), side="right"))]
    day0 = ST.trading_day(int(rows[i0][0]))
    best = e
    k = i0
    n = len(rows)
    kind, px = None, None
    while k < n:
        t, o, h, l, c = rows[k]
        if ST.trading_day(int(t)) != day0:
            k -= 1
            px, kind = rows[k][4] * d - TICK, "EOD"
            break
        o_d, h_d, l_d, c_d = (o, h, l, c) if d == 1 else (-o, -l, -h, -c)
        if cut:
            px, kind = o_d - TICK, cut
            break
        if l_d <= cur:
            px = (min(cur, o_d) if moved else cur) - TICK
            kind = "TRAIL" if moved and cur > e + BE_OFF + 1e-9 else ("BE" if (be_done or moved) and cur >= e else "STOP")
            break
        mfe = max(mfe, (h_d - e) / risk)
        best = max(best, h_d)
        if tg is not None and h_d >= tg:
            px, kind = tg, ("POOL" if rule and rule["kind"] == "pool" and tg < (target * d if target is not None else 1e18) else "TARGET")
            break
        if spec.get("be_r") is not None and not be_done and h_d >= e + spec["be_r"] * risk:
            cur = max(cur, e + BE_OFF)
            be_done = True
        if spec.get("trail_r") and mfe >= spec["trail_r"][0]:
            lv = best - spec["trail_r"][1] * risk
            if lv > cur:
                cur, moved = lv, True
        mod = ST.et_mod(int(t))
        if mod >= flat_mod and mod < 1080:
            px, kind = c_d - TICK, "EOD"
            break
        if spec.get("max_bars") and k - i0 + 1 >= spec["max_bars"]:
            px, kind = c_d - TICK, "TIME"
            break
        tc = spec.get("tcheck")
        if tc and not be_done and k - i0 + 1 == tc[0] and mfe < tc[2] and c_d < e - tc[1] * risk:
            cut = "CUT"
            k += 1
            continue
        if cur_ev is not None:
            E, p = cur_ev
            q = int(np.searchsorted(E["known_t"], int(t) + secs, side="right"))
            for i in range(p, q):
                dr, kd = int(E["dir"][i]), int(E["kind"][i])
                if rule["kind"] == "choch" and dr == -d and kd == 2 and mfe >= rule["k"]:
                    lvl = float(E["level"][i])
                    if rule["act"] == "exit":
                        cut = "CHOCH"
                        fired.append({"t": int(t) + secs, "action": "EXIT", "price": round(c, 2),
                                      "why": f"5m CHoCH {'down' if dr < 0 else 'up'} through {lvl:,.2f} after +{mfe:.2f}R: out at the next open"})
                    elif e + BE_OFF > cur:
                        if c_d <= e + BE_OFF:
                            cut = "CHOCH_BE"
                        else:
                            cur, moved = e + BE_OFF, True
                        fired.append({"t": int(t) + secs, "action": "BE", "price": round((e + BE_OFF) * d, 2),
                                      "why": f"5m CHoCH {'down' if dr < 0 else 'up'} through {lvl:,.2f} after +{mfe:.2f}R: stop to entry + 1.25"})
                elif rule["kind"] == "trail" and dr == d and (rule.get("kinds") == "any" or kd == 1) and mfe >= rule["k"]:
                    lv = float(E["prot"][i]) * d - TICK
                    if lv > cur and lv < c_d:
                        cur, moved = lv, True
                        fired.append({"t": int(t) + secs, "action": "TRAIL", "price": round(lv * d, 2),
                                      "why": f"{rule['tf']} {'BOS' if kd == 1 else 'CHoCH'} {'up' if dr > 0 else 'down'} through "
                                             f"{float(E['level'][i]):,.2f}: stop to the new protected swing {float(E['prot'][i]):,.2f}"})
            cur_ev[1] = max(p, q)
            if cut:
                k += 1
                continue
        k += 1
    if kind is None:
        last = rows[-1]
        px, kind = (last[4] * d), "OPEN"
        k = n - 1
    if rule and rule["kind"] == "pool" and kind == "POOL":
        fired.append({"t": int(rows[k][0]) + secs, "action": "TP", "price": round(px * d, 2),
                      "why": f"took profit 1 tick before the opposing pool {pool:,.2f}"})
    return {"pts": round(px - e, 4), "kind": kind, "t_exit": int(rows[k][0]) + secs, "mfe_r": round(mfe, 3), "fired": fired}


# ================================================================================================ one trade
def _first_pool(b1: list, trade: dict, d: int, entry: float, risk: float, min_r: float) -> tuple:
    """(price, label) of the nearest untaken opposing pool >= min_r R from the entry, known before the fill."""
    t0 = int(trade["entry_t"])
    rows = [r for r in b1 if r[0] + 60 <= t0 and r[0] >= t0 - 3 * 86400]
    b5 = ST.resample(rows, 300, 60)
    if not b5:
        return None, None
    h1 = ST.Tracker(3600)
    for r in ST.resample(rows, 3600, 60):
        h1.push(*r)
    P = ST.pools(b5, now=t0, h1_swings=list(h1.swings), price=entry)
    side = "buy" if d == 1 else "sell"
    best = None
    for p in P:
        if p["swept"] or p["side"] != side:
            continue
        dist = (p["price"] - entry) * d
        if dist >= min_r * risk and (best is None or dist < best[0]):
            best = (dist, p["price"], p["label"])
    return (best[1], best[2]) if best else (None, None)


def score_trade(strategy: str, trade: dict, b1, rules: tuple | None = None) -> dict | None:
    """The advice record of one FINISHED trade (review shape: entry_t, exit_t, dir, entry, stop, target, qty, usd, exit_kind),
    from 1m bars covering the trade (plus history before it for the structure). None when the bars do not cover it."""
    rows = _rows(b1)
    try:
        et, d = int(trade["entry_t"]), int(trade["dir"])
        entry, stop = float(trade["entry"]), float(trade["stop"])
        tgt = float(trade["target"]) if trade.get("target") is not None else None
        qty = int(trade.get("qty") or 0)
        usd = float(trade.get("usd") or 0.0)
    except (KeyError, TypeError, ValueError):
        return None
    if not rows or qty <= 0:
        return None
    i0 = next((i for i, r in enumerate(rows) if r[0] + 60 > et), None)
    if i0 is None or rows[i0][0] > et + 120:
        return None
    t_end = int(trade.get("exit_t") or 0) or None
    if t_end is None or rows[-1][0] + 60 < t_end:
        return None
    day_end = max((r[0] for r in rows[i0:] if ST.trading_day(int(r[0])) == ST.trading_day(et)), default=rows[-1][0]) + 60
    ev = frames_events([r for r in rows if r[0] >= et - 6 * 86400], day_end)
    spec = _manage_spec(strategy, trade)
    risk = (entry - stop) * d
    seg = [r for r in rows[i0:] if r[0] < day_end]
    base = walk(seg, 0, d, entry, stop, tgt, spec)
    rec = {"key": f"{strategy}|{trade.get('day') or ST.trading_day(et)}|{et}|{d}", "strategy": strategy, "day": trade.get("day") or ST.trading_day(et),
           "entry_t": et, "exit_t": t_end, "dir": d, "entry": entry, "stop": stop, "target": tgt, "qty": qty, "usd": round(usd, 2),
           "exit_kind": trade.get("exit_kind"), "base": {"kind": base["kind"], "pts": base["pts"], "mfe_r": base["mfe_r"]},
           "advice": [], "t": int(time.time()), "v": VERSION, "src": trade.get("src"), "member": trade.get("key")}
    for rid in rules or tuple(RULES):
        R = RULES[rid]
        if R["kind"] == "htf":
            tr = ST.trend_at(ev.get("1h") or {"known_t": np.zeros(0, np.int64), "dir": np.zeros(0)}, et)
            fire = tr == -d
            delta = -usd if fire else 0.0
            rec["advice"].append({"rule": rid, "fired": bool(fire), "delta_usd": round(delta, 2), "alt_usd": round(usd + delta, 2),
                                  "events": [{"t": et, "action": "SKIP", "price": round(entry, 2),
                                              "why": f"1h trend {'down' if tr < 0 else 'up'} against the {'long' if d > 0 else 'short'}"}] if fire else [],
                                  "playbook": R["playbook"].get(strategy)})
            continue
        pool = lab = None
        if R["kind"] == "pool":
            pool, lab = _first_pool(rows, trade, d, entry, risk, R["min_r"])
            if pool is None:
                rec["advice"].append({"rule": rid, "fired": False, "delta_usd": 0.0, "alt_usd": round(usd, 2), "events": [],
                                      "playbook": R["playbook"].get(strategy)})
                continue
        alt = walk(seg, 0, d, entry, stop, tgt, spec, R, ev, pool)
        fired = bool(alt["fired"])
        delta = (alt["pts"] - base["pts"]) * PV * qty if fired else 0.0
        a = {"rule": rid, "fired": fired, "delta_usd": round(delta, 2), "alt_usd": round(usd + delta, 2), "alt_kind": alt["kind"],
             "events": alt["fired"][:4], "playbook": R["playbook"].get(strategy)}
        if lab:
            a["pool"] = {"price": pool, "label": lab}
        rec["advice"].append(a)
    return rec


# ================================================================================================ the open trade (live advice)
def advise_open(strategy: str, pos: dict, b1, now: int | None = None) -> list:
    """What each structure rule would say about an OPEN trade right now (advice only), newest first. pos = {entry_t, dir,
    entry, stop, target}."""
    rows = _rows(b1)
    if not rows or not pos or pos.get("entry_t") is None:
        return []
    try:
        et, d, entry, stop = int(pos["entry_t"]), int(pos["dir"]), float(pos["entry"]), float(pos.get("stop0") or pos["stop"])
        tgt = float(pos["target"]) if pos.get("target") is not None else None
    except (KeyError, TypeError, ValueError):
        return []
    if now is not None:
        rows = [r for r in rows if r[0] + 60 <= int(now)]
    i0 = next((i for i, r in enumerate(rows) if r[0] + 60 > et), None)
    if i0 is None:
        return []
    ck = (strategy, et, d, entry, stop, len(rows), rows[-1][0])
    if _OPEN.get("k") == ck:
        return _OPEN["v"]
    ev = frames_events([r for r in rows if r[0] >= et - 6 * 86400], None)
    spec = _manage_spec(strategy, pos)
    out = []
    for rid in ("be_choch", "exit_choch", "trail_15m", "trail_5m"):
        R = RULES[rid]
        w = walk(rows[i0:], 0, d, entry, stop, tgt, spec, R, ev)
        for f in w["fired"]:
            out.append({**f, "rule": rid, "label": R["label"], "playbook": R["playbook"].get(strategy)})
    out.sort(key=lambda x: -x["t"])
    _OPEN.update(k=ck, v=out[:6])
    return out[:6]


_OPEN: dict = {}


def cached_open_advice(strategy: str, entry_t: int) -> list:
    """The last advise_open() result for this open trade (no work: the narrator on the poll thread reads it)."""
    k = _OPEN.get("k")
    return list(_OPEN.get("v") or []) if k and k[0] == strategy and k[1] == int(entry_t) else []


# ================================================================================================ store + tally
def _p(store, name):
    return os.path.join(store or STORE, name)


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


def tally(records: list) -> dict:
    """{rule: {n, fired, saved, cost, net, better, worse, text}} over scored trade records of one strategy."""
    out = {}
    for rid, R in RULES.items():
        A = [a for r in records for a in r.get("advice") or [] if a.get("rule") == rid]
        fired = [a for a in A if a.get("fired")]
        saved = sum(a["delta_usd"] for a in fired if a["delta_usd"] > 0)
        cost = sum(a["delta_usd"] for a in fired if a["delta_usd"] < 0)
        net = saved + cost
        verb = "saved" if net > 0 else ("cost" if net < 0 else "changed")
        txt = (f"{R['label']}: would have {verb} ${abs(net):,.0f} over {len(A)} trades (fired on {len(fired)}: "
               f"+${saved:,.0f} / -${abs(cost):,.0f})") if A else f"{R['label']}: no trades scored yet"
        out[rid] = {"n": len(A), "fired": len(fired), "saved": round(saved, 2), "cost": round(cost, 2), "net": round(net, 2),
                    "better": sum(1 for a in fired if a["delta_usd"] > 0), "worse": sum(1 for a in fired if a["delta_usd"] < 0),
                    "text": txt, "label": R["label"], "research": R["research"]}
    return out


def update(strategy: str, trades: list, b1, store: str | None = None, write: bool = True) -> dict:
    """Score every finished trade not scored yet (key = strategy|day|entry_t|dir), append to <store>/<strategy>.jsonl and
    rewrite <store>/tally.json. Returns {"new": n, "tally": {...}}. Never raises."""
    try:
        path = _p(store, f"{strategy}.jsonl")
        old = _jl_read(path)
        have = {r.get("key") for r in old}
        new = []
        for t in trades or []:
            if not t or t.get("exit_kind") in (None, "", "OPEN") or t.get("exit_t") is None:
                continue
            key = f"{strategy}|{t.get('day') or ST.trading_day(int(t['entry_t']))}|{int(t['entry_t'])}|{int(t['dir'])}"
            if key in have:
                continue
            r = score_trade(strategy, t, b1)
            if r is not None:
                new.append(r)
                have.add(key)
        recs = (old + new)[-KEEP:]
        T = tally(recs)
        if write and new:
            _jl_write(path, recs)
            allt = _read_json(_p(store, "tally.json"), {}) or {}
            allt[strategy] = {"t": int(time.time()), "n_trades": len(recs), "rules": T}
            _write_json(_p(store, "tally.json"), allt)
        return {"new": len(new), "tally": T, "n_trades": len(recs)}
    except Exception as e:
        return {"new": 0, "tally": {}, "error": f"{e.__class__.__name__}: {e}"[:200]}


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


def load_tally(store: str | None = None) -> dict:
    return _read_json(_p(store, "tally.json"), {}) or {}


def cards(T: dict | None = None, store: str | None = None) -> list:
    """Suggestion cards for engine/live_learning.suggestions: one per strategy and rule that fired at least once. Advice only:
    no approve command (a rule goes live only after research passes every gate and the owner approves)."""
    T = T if T is not None else load_tally(store)
    out = []
    for strat, blk in (T or {}).items():
        rules = (blk or {}).get("rules") or {}
        for rid, x in sorted(rules.items(), key=lambda kv: -abs(float(kv[1].get("net") or 0))):
            if not x.get("fired"):
                continue
            out.append({"bot": "lit" if strat == "lit" else ("atlas" if strat == "atlas" else strat), "kind": "advisor", "id": f"advisor:{strat}:{rid}",
                        "title": f"{STRATS.get(strat, strat)}: {x['label']}", "evidence": research_note(rid),
                        "would_usd": x.get("net"), "trades": x.get("n"),
                        "would_text": x.get("text"), "applied": False, "approve": None,
                        "note": "Discretion advisor (read-only shadow): it never changes an order. A rule that keeps saving money "
                                "goes back to research before anything changes."})
    return out


# ================================================================================================ cloud hook (live_learning)
CLOUD_KEEP = 120


def _slim(r: dict) -> dict:
    return {"key": r["key"], "day": r["day"], "entry_t": r["entry_t"], "dir": r["dir"], "usd": r["usd"], "member": r.get("member"),
            "advice": [{"rule": a["rule"], "fired": a["fired"], "delta_usd": a["delta_usd"],
                        "why": (a.get("events") or [{}])[0].get("why") if a.get("fired") else None} for a in r.get("advice") or []]}


def cloud_block(new_state: dict, old_state: dict | None, d1, now: int, keep: int = CLOUD_KEEP) -> dict:
    """tools/cloud_monitor.py (via engine/live_learning.cloud_hook): score the finished Zlarior paper trades (the cloud's LIT
    ledger) and the ATLAS members' paper trades on the cloud's 1m bars (the PC's pushed NinjaTrader bars); slim records kept
    in the state ("advisor"), the tally per strategy. Read-only towards every ledger."""
    from engine import live_learning as LL
    old = (old_state or {}).get("advisor") or {}
    recs = {k: list(v) for k, v in (old.get("records") or {}).items() if isinstance(v, list)}
    b1 = ST.as_rows(d1) if d1 is not None else []
    trades = {"lit": [], "atlas": []}
    for k, v in (new_state.get("ledger") or {}).items():
        if str(k).isdigit() and isinstance(v, dict) and v.get("taken") is not False:
            try:
                trades["lit"].append(LL.live_lit_paper(k, v))
            except Exception:
                pass
    for k in LL.ATLAS_KEYS:
        s = ((new_state.get("second") or {}).get("strategies") or {}).get(k) or {}
        for v in (s.get("ledger") or {}).values():
            if isinstance(v, dict) and v.get("entry_t"):
                try:
                    trades["atlas"].append(LL.row_second({**v, "key": k}, "paper"))
                except Exception:
                    pass
    for strat, T in trades.items():
        R = recs.setdefault(strat, [])
        have = {r.get("key") for r in R}
        for t in T:
            if t.get("exit_kind") in (None, "", "OPEN") or t.get("exit_t") is None:
                continue
            key = f"{strat}|{t.get('day') or ST.trading_day(int(t['entry_t']))}|{int(t['entry_t'])}|{int(t['dir'])}"
            if key in have:
                continue
            r = score_trade(strat, t, b1)
            if r is not None:
                R.append(_slim(r))
                have.add(key)
        recs[strat] = R[-keep:]
    return {"v": VERSION, "t": int(now), "records": recs,
            "tally": {s: {"t": int(now), "n_trades": len(r), "rules": tally(r)} for s, r in recs.items() if r}}


# ================================================================================================ PC hook (narrator.tick)
_PC = {"last": None, "seen": None, "store": None}


def _ledger_trades(bot) -> list:
    """Zlarior's finished routed trades from the bot's ledger (entry rows + exit rows) in the review shape."""
    rows = [r for r in list(getattr(bot, "ledger", None) or []) if isinstance(r, dict) and r.get("t") and not r.get("src")]
    ent = {}
    out = []
    for r in rows:
        if r.get("side") in ("buy", "sell"):
            ent[int(r.get("entry_t") or r["t"])] = r
        elif r.get("side") == "exit":
            et = r.get("entry_t")
            e = ent.get(int(et)) if et is not None else (list(ent.values())[-1] if ent else None)
            if not e:
                continue
            res = e.get("result") or {}
            fill = next((x.get("fill_px") for x in (res.get("legs") or []) if isinstance(x, dict) and x.get("fill_px") is not None), None)
            out.append({"entry_t": int(e.get("entry_t") or e["t"]), "exit_t": int(r.get("exit_t") or r["t"]), "dir": 1 if e.get("side") == "buy" else -1,
                        "entry": fill or e.get("entry") or e.get("price"), "stop": e.get("stop"), "target": e.get("target"),
                        "qty": e.get("qty"), "usd": r.get("pnl"), "exit_kind": r.get("reason") or "EXIT", "src": "pc"})
    return out


def _second_trades(bot) -> list:
    S = getattr(bot, "second", None) or {}
    out = []
    for k, s in ((S.get("strategies") or {}) if isinstance(S, dict) else {}).items():
        for t in (s or {}).get("trades") or []:
            if isinstance(t, dict) and t.get("entry_t") and t.get("exit_kind") not in (None, "OPEN"):
                out.append({**t, "key": k, "usd": t.get("usd", t.get("pnl_usd")), "qty": t.get("qty") or 1})
    return out


def _blitz_trades(bot) -> list:
    S = getattr(bot, "blitz", None) or {}
    out = []
    for r in (S.get("ledger") or []) if isinstance(S, dict) else []:
        if isinstance(r, dict) and r.get("entry_t") and r.get("exit_kind") not in (None, "OPEN") and r.get("exit_t"):
            out.append({**r, "qty": r.get("qty") or 1})
    return out


def _key(strategy: str, t: dict) -> str:
    return f"{strategy}|{t.get('day') or ST.trading_day(int(t['entry_t']))}|{int(t['entry_t'])}|{int(t['dir'])}"


def pc_tick(bot, now=None, store: str | None = None) -> dict | None:
    """engine/narrator.tick hook (PC): once per new 1m bar, score every finished Zlarior / ATLAS / BLITZ trade not scored yet on
    the bot's own 1m store (NinjaTrader bars, 12 days). The bars are only converted when there is a new finished trade (the
    scored keys are kept in memory). Read-only towards the bot. Never raises."""
    try:
        st = getattr(bot, "_lit_1m_store", None)
        if st is None or not len(st):
            return None
        last = int(st["time"].iloc[-1])
        if _PC["last"] == last:
            return None
        _PC["last"] = last
        if _PC.get("seen") is None or _PC.get("store") != store:
            _PC["seen"] = {s: {r.get("key") for r in _jl_read(_p(store, f"{s}.jsonl"))} for s in STRATS}
            _PC["store"] = store
        todo = {}
        for strat, fn in (("lit", _ledger_trades), ("atlas", _second_trades), ("scalp", _blitz_trades)):
            try:
                tr = fn(bot)
            except Exception:
                tr = []
            new = [t for t in tr if t.get("exit_kind") not in (None, "", "OPEN") and t.get("exit_t") is not None
                   and t.get("entry_t") is not None and _key(strat, t) not in _PC["seen"][strat]]
            if new:
                todo[strat] = new
        if not todo:
            return {}
        t0 = min(int(t["entry_t"]) for v in todo.values() for t in v) - 7 * 86400
        b1 = ST.as_rows(st[st["time"] >= t0])
        out = {}
        for strat, tr in todo.items():
            out[strat] = update(strat, tr, b1, store)
            for t in tr:                         # scored, or too old for the 12-day store: never retried every bar
                if out[strat].get("new") or int(t["exit_t"]) < last - 86400:
                    _PC["seen"][strat].add(_key(strat, t))
        return out
    except Exception:
        return None
