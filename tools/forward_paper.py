"""FORWARD-PAPER harness (big-forward 2026-11-26; rules pre-registered in research/forward/DESIGN.md). PAPER RESEARCH ONLY:
never trades, sizes, arms or edits a live file. Each watched lead is a pure function over the bars (standalone) or over the
live twin's trades (skip / size rules); it is scored on sessions it has never seen against its OWN backtest band, so it can
graduate (status `promote` -> the lead writes an owner yes/no card with the full proof) or be dropped (`demoted`).

    python -X utf8 tools/forward_paper.py                 # nightly: forward events on the newest sessions -> research/forward/
    python -X utf8 tools/forward_paper.py --bands         # (re)compute every rule's frozen backtest band first (bands.json)
    python -X utf8 tools/forward_paper.py --only ict_ote_dol,atlas_skip_news   [--dry-run: print, write nothing]
    python -X utf8 tools/forward_paper.py --report        # the table from forward.json, nothing run

Outputs: research/forward/forward.json (rules, band, forward n / mean / sum / z / days in, status, events),
research/forward/bands.json (band per rule; recomputed only with --bands or when missing / the rule changed),
research/forward/journal.jsonl (ONE line per rule per ISO week, re-runs replace that week's line, never duplicate).
Nightly step: tools/learn_night.py step "forward" (skip with --skip forward). Tests: python -X utf8 -m tests.test_forward_paper.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import logging
import math
import os
import sys
import time
import zoneinfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_DIR = os.path.join(ROOT, "research", "forward")
STATE = os.path.join(OUT_DIR, "forward.json")
BANDS = os.path.join(OUT_DIR, "bands.json")
JOURNAL = os.path.join(OUT_DIR, "journal.jsonl")
NY = zoneinfo.ZoneInfo("America/New_York")
BT_FROM = "2021-11-01"
BT_TO = "2026-11-20"                      # the last session every seed study used
FWD_FROM = "2026-11-23"                   # the first session after it (DESIGN.md "Forward window")
PROMOTE_N, PROMOTE_Z, DEMOTE_N, DEMOTE_Z, DEMOTE_SUM = 20, -1.0, 10, -2.0, -8.0
TIER1 = ("FOMC rate decision", "CPI", "PPI", "Non-Farm")
SB_HOURS = (3, 10, 14)
ATLAS_COST_PTS = 0.25 + 1.90 / 2.0        # 1 tick slip + $1.90 a micro, in NQ points (atlas_health cost model)
PROTECTED = ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json")
_C: dict = {}


# ================================================================================================ small helpers
def _hour(ts):
    return dt.datetime.fromtimestamp(int(ts), NY).hour


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=float)
        fh.write("\n")
    os.replace(tmp, path)


def _hash(paths):
    h = hashlib.sha256()
    for p in paths:
        try:
            h.update(open(os.path.join(ROOT, p), "rb").read())
        except OSError:
            h.update(b"-")
    return h.hexdigest()[:16]


def ev(day, t, value, **kw):
    return {"day": str(day), "t": int(t), "v": round(float(value), 4), **kw}


# ================================================================================================ shared sources (lazy)
def tier1_days():
    if "t1" not in _C:
        import pandas as pd
        e = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
        e = e[(e["impact"] == "high") & e["event"].apply(lambda s: any(str(s).startswith(k) for k in TIER1))]
        _C["t1"] = set(e["date"].astype(str))
    return _C["t1"]


def ict():
    if "ict" not in _C:
        sys.path.insert(0, os.path.join(ROOT, "research", "ictlab"))
        import ict_lab as L1
        import ict_lab2 as L2
        B = L1.load()
        C = L1.build_ctx(B)
        L2.indicators(B)
        L2.build_ctx2(B, C)
        _C["ict"] = (L1, L2, B, C)
    return _C["ict"]


def lit_run(extra=None, since=BT_FROM):
    """The LIT engine as the live twin runs it (tools/livegap.lit_twin), with optional parameter overrides."""
    key = ("lit", json.dumps(extra or {}, sort_keys=True), since)
    if key not in _C:
        logging.disable(logging.WARNING)
        from engine import lit
        from tools import lit_final as F
        from tools import lit_rev_exit as R
        c = R.cx()
        M = c["M"]
        ss = [str(d) for d, s, e in M.days if str(d) >= since]
        P = {**lit.DEFAULTS, **R.LIVE, **(extra or {})}
        Mm, Cm = F.market(P["ref"], P["extra_boxes"])
        T = lit.run_x(Mm, Cm, P, ss, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
        out = []
        for t in T:
            q = int(t.get("qty") or 0)
            risk = abs(t["entry_px"] - t["stop_px"])
            if q <= 0 or risk <= 0:
                continue
            out.append({"day": str(t["day"]), "entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "exit": t.get("exit"),
                        "r": float(t["pnl"]) / (risk * 2.0 * q)})
        _C[key] = out
    return _C[key]


def atlas_band_trades():
    if "atl_bt" not in _C:
        logging.disable(logging.WARNING)
        import atlas_health as AH
        _C["atl_bt"] = [{"day": t["day"], "entry_t": t["entry_t"], "dir": t["dir"], "r": float(t["R"])} for t in AH.stream()]
    return _C["atl_bt"]


def atlas_forward_trades(since):
    key = ("atl_fw", since)
    if key not in _C:
        logging.disable(logging.WARNING)
        from tools import livegap as G
        _C[key] = [{"day": t["day"], "entry_t": t["entry_t"], "dir": t["dir"],
                    "r": float(t["r"]) - ATLAS_COST_PTS / max(1e-9, float(t["risk"]))}
                   for t in G.atlas_twin(since) if not t.get("one_position_skip")]
    return _C[key]


def structure_tags(rows):
    if "stx" not in _C:
        sys.path.insert(0, os.path.join(ROOT, "research", "structure"))
        import study as ST
        _C["stx"] = (ST, ST.context())
    ST, X = _C["stx"]
    return ST.tag_trades(X, [{**r, "pillar": "lit", "span": None, "usd": 0.0} for r in rows])


# ================================================================================================ the rules
def _ict_stand(stand_key, gate, a, z):
    L1, L2, B, C = ict()
    fn = {k: f for k, _, _, f, *_ in (list(L1.STAND) + list(L2.STAND))}[stand_key]
    out = []
    for sd, i0, i1 in B["sess"]:
        sd = str(sd)
        if not (a <= sd <= z):
            continue
        tr = L1.first_fill(B, i0, i1, fn(B, i0, i1, C[sd]))
        if not tr or not gate(L1, B, C, sd, tr):
            continue
        q = L1.P.qty(tr["stop_pts"])
        if q <= 0:
            continue
        out.append(ev(sd, tr["t_in"], (tr["pts"] * L1.PTV - L1.FEE) / (tr["stop_pts"] * L1.PTV), side=tr["side"], exit=tr["exit"]))
    return out


def r_ict_ote_dol(a, z):
    return _ict_stand("S_OTE", lambda L1, B, C, sd, tr: L1.has(L1.features(B, C, tr["i_in"], tr["side"], tr["entry"], tr["entry"]),
                                                                ["F_DOL"]), a, z)


def r_ict_mmbm_week(a, z):
    return _ict_stand("S_MMBM", lambda L1, B, C, sd, tr: C[sd].get("wbias") is not None and C[sd]["wbias"] == tr["side"], a, z)


def _atlas(a, z):
    T = atlas_band_trades() if z <= BT_TO else atlas_forward_trades(a)
    return [t for t in T if a <= t["day"] <= z]


def r_atlas_skip_news(a, z):
    t1 = tier1_days()
    return [ev(t["day"], t["entry_t"], -t["r"]) for t in _atlas(a, z) if t["day"] in t1]


def r_atlas_half_off_sb(a, z):
    return [ev(t["day"], t["entry_t"], -0.5 * t["r"]) for t in _atlas(a, z) if _hour(t["entry_t"]) not in SB_HOURS]


def r_blitz_v1_noise(a, z):
    if "bz" not in _C:
        sys.path.insert(0, os.path.join(ROOT, "research", "blitzv2"))
        cwd = os.getcwd()
        try:
            import blitzv2 as BV          # needs numba (tools/blitz25k_lib)
            B5 = BV.N.bars(5)
            _C["bz"] = BV.sim(B5, BV.V["V1 noise-area exit (band/VWAP, no clock, no trail)"])
        finally:
            os.chdir(cwd)
    return [ev(t["day"], t["entry_t"], float(t["pnl_pm"]) / float(t["risk_pm"]), side=int(t["dir"]))
            for t in _C["bz"] if a <= str(t["day"]) <= z and t.get("risk_pm")]


L11 = {"max_per_day": 2, "second": {"after": ["STOP"], "side": "any", "cool": 0, "r_stop": None, "r_take": None,
                                    "new_level": False, "q": None, "m": 1.0}}


def r_lit_second_after_stop(a, z):
    base = {t["entry_t"] for t in lit_run(None, BT_FROM)}
    return [ev(t["day"], t["entry_t"], t["r"], side=t["dir"]) for t in lit_run(L11, BT_FROM)
            if a <= t["day"] <= z and t["entry_t"] not in base]


def r_lit_x15_extreme(a, z):
    rows = [t for t in lit_run(None, BT_FROM) if a <= t["day"] <= z]
    R = {t["entry_t"]: t["r"] for t in rows}
    return [ev(g["day"], g["entry_t"], 0.5 * R[g["entry_t"]], pos=round(float(g["pos"]), 3))
            for g in structure_tags(rows) if g["pos"] < 0.2]


# ---------------------------------------------------------------------------------------------- S1 forward hold-out
# research/regime2026/DESIGN_forward.md: "ATLAS only when S1 (realized range above its 1-year median) is ON", judged on
# sessions from FWD_FROM only, re-judge 2027-02-26 / >= 60 sessions.
S1_FILE = os.path.join(ROOT, "research", "regime2026", "s1_forward.json")
S1_REJUDGE, S1_NEED = "2027-02-26", 60
ASIA_KZ = [[1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]


def s1_series():
    if "s1" not in _C:
        sys.path.insert(0, os.path.join(ROOT, "research", "regime2026"))
        import regime as RG
        s = RG.rules(RG.daily(), 1)["S1_RV"]
        _C["s1"] = {str(k): bool(v) for k, v in s.items()}
    return _C["s1"]


def r_atlas_s1_gate(a, z):
    """Band / forward events at the harness's 1-tick ATLAS cost (comparable to the other ATLAS rules). NOTE: at 1 tick the
    S1-OFF trades were slightly positive (band mu < 0); S1 helped only at the calibrated 12-tick fills, which
    s1_forward() judges (DESIGN_forward.md)."""
    S = s1_series()
    return [ev(t["day"], t["entry_t"], -t["r"], s1=False) for t in _atlas(a, z) if not S.get(t["day"], False)]


def asia_paper(since):
    """The litasia Asia-slot variant's Asia trades (18:00-02:00 ET entries) through the twin LIT engine; r and r at +2 ticks."""
    from tools import lit_more_entries as LM
    P = LM.P_of("full", 2, None, 1.0, {"per_session": [[[1080, 120], [120, 1080]], 1], "second": {}, "kz": ASIA_KZ})
    out = []
    for t in lit_run(P, since):
        h = dt.datetime.fromtimestamp(int(t["entry_t"]), NY)
        m = h.hour * 60 + h.minute
        if m >= 1080 or m < 120:
            out.append(t)
    return out


def pc_atlas_real():
    """day -> ATLAS's real live $ (PC day folders: exit rows of bot atlas, mode live)."""
    import glob
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "pc_days", "*", "trades.jsonl.gz"))):
        for r in (json.loads(x) for x in gzip.open(p, "rt")):
            if r.get("bot") == "atlas" and r.get("side") == "exit" and r.get("mode") == "live" and r.get("pnl") is not None:
                d = os.path.basename(os.path.dirname(p))
                out[d] = round(out.get(d, 0.0) + float(r["pnl"]), 2)
    return out


def s1_forward(days, path=None, say=print):
    """research/regime2026/s1_forward.json: one row per forward session + the re-judge state (DESIGN_forward.md)."""
    S = s1_series()
    tw, tw1 = {}, {}
    from tools import livegap as G
    for t in G.atlas_twin(FWD_FROM):
        if t.get("one_position_skip"):
            continue
        risk = max(1e-9, float(t["risk"]))
        tgt = str(t.get("exit", "")).upper() == "TARGET"
        r12 = float(t["r"]) - (12 * 0.25 + (0 if tgt else 2 * 0.25) + 1.90 / 2.0) / risk   # atlas2's calibrated fills (judged)
        tw.setdefault(t["day"], []).append(round(r12, 4))
        tw1.setdefault(t["day"], []).append(round(float(t["r"]) - ATLAS_COST_PTS / risk, 4))
    try:
        A = {}
        for t in asia_paper(FWD_FROM):
            A.setdefault(t["day"], []).append(t)
    except Exception as e:  # noqa: BLE001
        A, say_err = {}, f"{e.__class__.__name__}: {e}"
        say(f"s1_forward: Asia paper skipped ({say_err})")
    real = pc_atlas_real()
    rows = []
    for d in days:
        if d < FWD_FROM:
            continue
        ar = [round(float(t["r"]), 4) for t in A.get(d, [])]
        rows.append({"day": d, "s1": S.get(d), "atlas_real_usd": real.get(d), "atlas_twin_r": tw.get(d, []),
                     "atlas_twin_r_1tick": tw1.get(d, []), "asia_paper_r": ar})
    on = [r for x in rows if x["s1"] for r in x["atlas_twin_r"]]
    off = [r for x in rows if x["s1"] is False for r in x["atlas_twin_r"]]
    n = len(rows)
    mean = lambda v: round(sum(v) / len(v), 4) if v else None  # noqa: E731
    tot, kept = round(sum(on) + sum(off), 3), round(sum(on), 3)
    due = n >= S1_NEED and (days[-1] if days else "") >= S1_REJUDGE
    checks = {"off_trades_ge_10": len(off) >= 10, "off_sum_lt_0": sum(off) < 0,
              "on_mean_gt_off_mean": (mean(on) or -9) > (mean(off) if off else 9),
              "keeps_80pct": (kept >= 0.8 * tot) if tot > 0 else (kept >= tot)}
    doc = {"design": "research/regime2026/DESIGN_forward.md", "fwd_from": FWD_FROM,
           "costs": "atlas_twin_r = calibrated fills (entry 12 ticks, stop / market exit 2, target 0, $1.90), JUDGED; atlas_twin_r_1tick = recorded only", "rejudge": S1_REJUDGE, "need_sessions": S1_NEED,
           "sessions": n, "progress": f"{n} / {S1_NEED} sessions", "due": due,
           "atlas_twin": {"on_n": len(on), "on_sum_r": round(sum(on), 3), "on_mean_r": mean(on), "off_n": len(off),
                          "off_sum_r": round(sum(off), 3), "off_mean_r": mean(off), "ungated_sum_r": tot},
           "checks": checks, "verdict": (("ADOPT-CANDIDATE (owner card)" if all(checks.values()) else "REJECTED") if due else "watching"),
           "rows": rows}
    _write(path or S1_FILE, doc)
    try:
        from engine import market_learn as ML
        obs = [{"key": "regime2026|s1_forward", "pillar": "atlas", "lens": "forward hold-out",
                "noticed": (f"S1 forward test (ATLAS only when the 20-day range is above its 1-year median): {n}/{S1_NEED} sessions, "
                            f"re-judge {S1_REJUDGE}; twin ATLAS on S1-ON days {len(on)} trades {round(sum(on), 2)}R, on S1-OFF days "
                            f"{len(off)} trades {round(sum(off), 2)}R"),
                "evidence": {"n": n, "on_n": len(on), "off_n": len(off)},
                "status": "watching" if not due else ("adopted-needs-owner-yes" if all(checks.values()) else "rejected")}]
        J, _ = ML.update_journal(ML.journal_doc(ML.JOURNAL), obs)
        ML._write_json(ML.JOURNAL, J)
    except Exception as e:  # noqa: BLE001
        say(f"s1_forward: journal not updated ({e.__class__.__name__})")
    say(f"s1_forward: {doc['progress']}, ON {len(on)} trades {round(sum(on), 2)}R / OFF {len(off)} trades {round(sum(off), 2)}R -> {doc['verdict']}")
    return doc


RULES = {
    "atlas_s1_gate": {"kind": "skip", "bot": "ATLAS", "fn": r_atlas_s1_gate, "source": "research/regime2026/DESIGN_forward.md",
                      "desc": "ATLAS only when S1 (20-day NQ range above its 1-year median) is ON: skip the S1-OFF trades",
                      "code": ["research/regime2026/regime.py"]},
    "ict_ote_dol": {"kind": "standalone", "bot": "-", "fn": r_ict_ote_dol, "source": "research/writeups/ict-lab-2026-11-25.md",
                    "desc": "ICT OTE 70.5% of the 09:30-10:00 leg, only when the PDH/PDL draw agrees (ICT lab G3)",
                    "code": ["research/ictlab/ict_lab.py", "tools/popular_ict.py"]},
    "ict_mmbm_week": {"kind": "standalone", "bot": "-", "fn": r_ict_mmbm_week, "source": "research/writeups/ict-lab2-2026-11-25.md",
                      "desc": "MMBM / MMSM only with the weekly bias", "code": ["research/ictlab/ict_lab2.py", "research/ictlab/ict_lab.py"]},
    "atlas_skip_news": {"kind": "skip", "bot": "ATLAS", "fn": r_atlas_skip_news, "source": "research/writeups/news-playbook-2026-11-26.md",
                        "desc": "skip ATLAS on Tier-1 days (FOMC / CPI / PPI / NFP)", "code": ["data/news/events.csv"]},
    "atlas_half_off_sb": {"kind": "size x0.5", "bot": "ATLAS", "fn": r_atlas_half_off_sb, "source": "owner card atlas-sb-half",
                          "desc": "ATLAS x0.5 outside Silver Bullet hours (03 / 10 / 14 ET)", "code": []},
    "blitz_v1_noise": {"kind": "standalone", "bot": "BLITZ", "fn": r_blitz_v1_noise, "source": "research/writeups/blitz-v2-2026-11-26.md",
                       "desc": "BLITZ V1 noise-area exit (band / VWAP, no clock, no trail), 5m", "code": ["research/blitzv2/blitzv2.py"]},
    "lit_second_after_stop": {"kind": "standalone", "bot": "LIT", "fn": r_lit_second_after_stop,
                              "source": "research/writeups/more-trades-2026-11-25.md",
                              "desc": "LIT L11: the extra 2nd trade of a day, only after a STOP", "code": ["engine/lit.py"]},
    "lit_x15_extreme": {"kind": "size x1.5", "bot": "LIT", "fn": r_lit_x15_extreme, "source": "research/writeups/structure-2026-11-24.md",
                        "desc": "LIT x1.5 when the entry sits in the 20% of the day's range on its side (structure F3)",
                        "code": ["engine/lit.py", "research/structure/study.py"]},
}


# ---------------------------------------------------------------------------------------------- idea mill adapter
def ideamill_rules():
    """Every idea mill idea at its paper gate (G3 / D, or the confirm track at 'paper') -> a standalone rule (auto)."""
    out = {}
    ids = set()
    S = _read(os.path.join(ROOT, "research", "ideamill", "summary.json"), {})
    cf = S.get("confirm_track") or {}
    if isinstance(cf, dict) and cf.get("verdict") == "paper" and cf.get("named"):
        ids.add(cf["named"])
    for s in S.get("v3_survivors") or []:
        if isinstance(s, dict) and s.get("id"):
            ids.add(s["id"])
    p = os.path.join(ROOT, "research", "ideamill", "trials.jsonl.gz")
    if os.path.exists(p):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if '"gate"' in line and ('"G3"' in line or '"D"' in line):
                        t = json.loads(line)
                        if t.get("gate") in ("G3", "D") and t.get("id"):
                            ids.add(t["id"])
        except Exception:  # noqa: BLE001
            pass
    for iid in sorted(ids):
        out["ideamill:" + iid] = {"kind": "standalone", "bot": "-", "fn": _idea_fn(iid), "source": "research/ideamill (paper gate)",
                                  "desc": f"idea mill idea {iid}", "code": ["research/ideamill/grammar.py"]}
    return out


def _idea_fn(iid):
    def f(a, z):
        sys.path.insert(0, os.path.join(ROOT, "research", "ideamill"))
        import grammar as G
        I = next(I for I in G.ideas() if I["id"] == iid)
        key = ("idx", I["tf"])
        if key not in _C:
            _C[key] = G.context(I["tf"])
        X = _C[key]
        d, r, _ = G.run_idea(X, I)
        days = X["udays"]
        return [ev(days[k], 0, rr) for k, rr in zip(d, r) if a <= str(days[k]) <= z]
    return f


def all_rules():
    R = dict(RULES)
    try:
        R.update(ideamill_rules())
    except Exception:  # noqa: BLE001
        pass
    return R


# ================================================================================================ scoring
def band_of(E):
    v = [e["v"] for e in E]
    n = len(v)
    mu = sum(v) / n if n else 0.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1)) if n > 1 else 0.0
    return {"n_bt": n, "mu": round(mu, 4), "sd": round(sd, 4), "sum_bt": round(sum(v), 2),
            "days": [E[0]["day"], E[-1]["day"]] if E else None}


def score(E, band):
    """Forward events vs the band -> n, mean, sum, z, status (DESIGN.md bars)."""
    v = [e["v"] for e in E]
    n = len(v)
    s = sum(v)
    m = s / n if n else None
    z = None
    if n and band and band.get("sd"):
        z = round((m - band["mu"]) / (band["sd"] / math.sqrt(n)), 2)
    if s <= DEMOTE_SUM or (n >= DEMOTE_N and z is not None and z <= DEMOTE_Z):
        st = "demoted"
    elif n >= PROMOTE_N and z is not None and z >= PROMOTE_Z and s > 0:
        st = "promote"
    else:
        st = "watching"
    return {"n": n, "mean": round(m, 4) if m is not None else None, "sum": round(s, 2), "z": z, "status": st}


def sessions_since(a):
    import pandas as pd
    d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time"])
    et = pd.to_datetime(d["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
    day = (et + pd.Timedelta(hours=6))
    days = sorted({x for x, w in zip(day.dt.strftime("%Y-%m-%d"), day.dt.dayofweek) if w < 5})
    return [x for x in days if x >= a], (days[-1] if days else None)


def run(only=None, bands=False, dry=False, say=print, rules=None, today=None):
    t0 = time.time()
    before = _hash(PROTECTED)
    R = rules if rules is not None else all_rules()
    if only:
        R = {k: v for k, v in R.items() if k in only}
    B = _read(BANDS, {})
    S = _read(STATE, {"rules": {}})
    fwd_days, data_end = sessions_since(FWD_FROM) if rules is None else (today or ([], None))
    out_rules = dict(S.get("rules") or {})
    for rid, r in R.items():
        sig = _hash(r.get("code") or []) + "|" + r["desc"]
        row = {"id": rid, "kind": r["kind"], "bot": r["bot"], "desc": r["desc"], "source": r["source"], "fwd_from": FWD_FROM}
        try:
            if bands or rid not in B or B[rid].get("sig") != sig:
                Eb = r["fn"](BT_FROM, BT_TO)
                B[rid] = {**band_of(Eb), "sig": sig, "built": dt.date.today().isoformat()}
            Ef = r["fn"](FWD_FROM, "9999-12-31")
            sc = score(Ef, B[rid])
            row.update(band={k: B[rid][k] for k in ("n_bt", "mu", "sd", "sum_bt", "days")}, **sc,
                       days_in=len(fwd_days), events=Ef[-60:], error=None)
        except Exception as e:  # noqa: BLE001
            old = out_rules.get(rid) or {}
            row.update({k: old.get(k) for k in ("band", "n", "mean", "sum", "z", "days_in", "events")},
                       status="error", error=f"{e.__class__.__name__}: {e}"[:300])
        out_rules[rid] = row
        say(f"{rid:24s} {row['status']:9s} band mu {((row.get('band') or {}).get('mu'))} sd {((row.get('band') or {}).get('sd'))} "
            f"n_bt {((row.get('band') or {}).get('n_bt'))} | forward n {row.get('n')} mean {row.get('mean')} sum {row.get('sum')} "
            f"z {row.get('z')} days {row.get('days_in')}" + (f" | {row['error']}" if row.get("error") else ""))
    doc = {"v": 1, "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "design": "research/forward/DESIGN.md",
           "fwd_from": FWD_FROM, "data_end": data_end, "forward_sessions": len(fwd_days),
           "bars": {"promote": f"n >= {PROMOTE_N} and z >= {PROMOTE_Z} and sum > 0",
                    "demote": f"(n >= {DEMOTE_N} and z <= {DEMOTE_Z}) or sum <= {DEMOTE_SUM} R"},
           "rules": out_rules, "note": "Paper research only: a 'promote' is a request for an owner yes/no card, never a live change."}
    after = _hash(PROTECTED)
    if after != before:
        doc["ALARM"] = "a live model file changed during the run (forward_paper never writes one)"
        say("ALARM: live model files changed during the run")
    if not dry:
        _write(BANDS, B)
        _write(STATE, doc)
        journal(doc)
        if rules is None and (not only or "atlas_s1_gate" in only):
            try:
                doc["s1_forward"] = {k: v for k, v in s1_forward(fwd_days, say=say).items() if k != "rows"}
            except Exception as e:  # noqa: BLE001
                say(f"s1_forward failed: {e.__class__.__name__}: {e}")
        if rules is None:                  # the Brain's "What the bots learned" page reads it (big-learnview): rebuild, soft
            try:                           # big-setupscore: the LIT setup score's pool + holdout verdict first (soft, ~5 s)
                import setupscore_build
                setupscore_build.main([])
            except Exception as e:  # noqa: BLE001
                say(f"setup score pool not rebuilt: {e.__class__.__name__}: {e}")
            try:                           # the NQ Replay Theater's day files (tools/build_replay.py, ~6 s, the last 35 days)
                import build_replay
                build_replay.main([])
            except Exception as e:  # noqa: BLE001
                say(f"replay days not rebuilt: {e.__class__.__name__}: {e}")
            try:
                import build_brain_learn
                build_brain_learn.main([])
            except Exception as e:  # noqa: BLE001
                say(f"brain/learn.json not rebuilt: {e.__class__.__name__}: {e}")
    say(f"forward: {len(out_rules)} rules, {len(fwd_days)} forward sessions (data to {data_end}), {time.time() - t0:.0f}s")
    return doc


def journal(doc, path=None):
    """One line per rule per ISO week of the data end; a re-run replaces that week's line (no duplicates)."""
    path = path or JOURNAL
    de = doc.get("data_end")
    if not de:
        return []
    y, w, _ = dt.date.fromisoformat(de).isocalendar()
    week = f"{y}-W{w:02d}"
    old = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = [json.loads(x) for x in fh if x.strip()]
    keep = [x for x in old if x.get("week") != week]
    new = [{"week": week, "data_end": de, "rule": rid, "status": r.get("status"), "n": r.get("n"), "mean": r.get("mean"),
            "sum": r.get("sum"), "z": r.get("z"), "band_mu": (r.get("band") or {}).get("mu"), "error": r.get("error")}
           for rid, r in sorted(doc["rules"].items())]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for x in keep + new:
            fh.write(json.dumps(x) + "\n")
    return new


def report(say=print):
    S = _read(STATE, None)
    if not S:
        say("no research/forward/forward.json yet: run python -X utf8 tools/forward_paper.py")
        return
    say(f"forward from {S['fwd_from']}, data to {S['data_end']}, {S['forward_sessions']} forward sessions")
    for rid, r in S["rules"].items():
        b = r.get("band") or {}
        say(f"{rid:24s} {r.get('status'):9s} backtest {b.get('mu')}R x{b.get('n_bt')} | forward {r.get('mean')}R x{r.get('n')} "
            f"sum {r.get('sum')} z {r.get('z')}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", action="store_true", help="recompute every band")
    ap.add_argument("--only", default="", help="comma list of rule ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    if a.report:
        return report()
    run(only={x for x in a.only.split(",") if x} or None, bands=a.bands, dry=a.dry_run)


if __name__ == "__main__":
    main()
