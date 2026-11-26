"""Order-flow learning loop (research/orderflow/DESIGN3.md "The learning loop", frozen 327619a1). Paper research only: it never
changes LIT, ATLAS, a size or a live file. Every night:
  1. log   - for each LIT / ATLAS signal on a tick day: the order-flow state at entry (v2 + v3 features, OF1's absorbed read at the
             sweep) and the outcome -> of_signals.jsonl (append-only, one row per (bot, entry time)).
  2. learn - per bot, per reading (each feature split at its frozen median + 3 named readings: absorbed / cascade / flow_with):
             wins on each side, Wilson 90% intervals, one-sided permutation p, BH at q 0.10, older vs newer half.
  3. placebo - the same on outcome labels shuffled once (seed = the night's date); its lead count is printed next to the real one.
  4. words  - too few / nothing / watching / lead ("OF said absorbed at the sweep: 7 of 9 won, too few to act").
  5. journal - research/learn/journal.json via engine/market_learn.update_journal (key of|<bot>|<reading>, lens "order flow");
             of_learn_state.json carries the newest line for the Brain's Order Flow room (engine/brain_feed.of_bot).
Cloud: python -X utf8 research/orderflow/of_learn.py [--src DIR]      PC: engine/tickrec.autopilot -> run(out_dir=logs/orderflow,
journal=None) (the PC never writes a tracked file).      Proof: python -X utf8 research/orderflow/of_learn.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT_CLOUD = os.path.join(ROOT, "research", "learn")
JOURNAL = os.path.join(OUT_CLOUD, "journal.json")
SIGNALS, STATE = "of_signals.jsonl", "of_learn_state.json"
MIN_SIDE, MIN_MEDIAN, N_PERM, Q, Z90 = 20, 20, 2000, 0.10, 1.6449
NAMED = {"absorbed": "absorbed at the sweep", "cascade": "stops ran and were absorbed (K4 > 0)",
         "flow_with": "the last 15 min of flow was with the trade (A2 > 0)"}
BOTS = {"LIT": "lit", "ATLAS": "atlas"}


def _mod(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


F_ = None


def _fwd():
    global F_
    if F_ is None:
        F_ = _mod("of_forward.py", "of_forward_learn")
    return F_


# ------------------------------------------------------------------------------------------------ 1. log
def _jl(p):
    out = []
    try:
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def _clean(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 5)


def signal_rows(R, lit, atlas):
    """[row] for every LIT / ATLAS signal on a tick day of R (summaries as of_battery._from_bytes)."""
    F = _fwd()
    B, M = F.B, F.M
    days = sorted(d for d, x in R.items() if int(x["meta"].get("rows", 0)) >= B.MIN_ROWS)
    D, ctx = {}, {}

    def day(d):
        if d not in D:
            D[d] = B.Day(d, R[d])
            ctx[d] = M.Ctx(D[d])
        return D[d], ctx[d]
    dset = set(days)
    out = []
    for bot, src in (("LIT", lit or []), ("ATLAS", atlas or [])):
        for s in src:
            t_in = int(s["tn"] if bot == "LIT" else s["entry_t"])
            d_ = B.et_day(t_in)
            if d_ not in dset:
                continue
            Dy, cx = day(d_)
            i = Dy.row_of_t.get(t_in)
            if i is None or i < 7:
                continue
            dd = int(s["dir"])
            if bot == "LIT":
                ext = Dy.row_of_t.get(int(s["te"]))
            else:
                w = Dy.bars.iloc[i - 6:i]
                ext = int(w.low.idxmin() if dd == 1 else w.high.idxmax())
            if ext is None:
                continue
            f = F.all_features(cx, i, dd, ext, None)
            z = Dy.zone(int(Dy.bars.at[ext, "t"]), dd)
            absorbed = None if z is None or z[0] <= 0 else bool(z[1] * dd < 0 and abs(z[1]) >= B.ABS_SHARE * z[0])
            sides = (Dy.meta.get("sides") or {})
            out.append({"bot": bot, "t": t_in, "day": d_, "d": dd, "pnl": round(float(s["pnl"]), 2),
                        "R": _clean(s.get("R")), "won": bool(float(s["pnl"]) > 0), "absorbed": absorbed,
                        "quote_rule": sides.get("quote_rule"), "f": {k: _clean(v) for k, v in f.items()}})
    return out


def log(rows, path):
    """Append rows whose (bot, t) is not logged yet. -> the full log."""
    have = _jl(path)
    keys = {(r["bot"], int(r["t"])) for r in have}
    new = [r for r in rows if (r["bot"], int(r["t"])) not in keys]
    if new:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for r in sorted(new, key=lambda r: (r["t"], r["bot"])):
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    return sorted(have + new, key=lambda r: (r["t"], r["bot"])), len(new)


# ------------------------------------------------------------------------------------------------ 2. learn
def wilson(k, n, z=Z90):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def _perm_p(a_mask, won, rid, n_perm=N_PERM):
    """One-sided: P(win rate A - win rate B >= observed) under shuffled outcome labels."""
    na, nb = int(a_mask.sum()), int((~a_mask).sum())
    if na == 0 or nb == 0:
        return 1.0
    w = won.astype(float)
    obs = w[a_mask].mean() - w[~a_mask].mean()
    rng = np.random.default_rng(zlib.crc32(rid.encode()))
    tot = w.sum()
    n = len(w)
    hits = 0
    for _ in range(n_perm):
        idx = rng.permutation(n)[:na]
        sa = w[idx].sum()
        if sa / na - (tot - sa) / nb >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def readings(rows, medians):
    """{reading id: (A mask, known mask, label A, label B)} for one bot's rows."""
    out = {}
    ab = np.array([r["absorbed"] for r in rows], dtype=object)
    known = np.array([a is not None for a in ab])
    out["absorbed"] = (np.array([a is True for a in ab]), known, "absorbed", "not absorbed")
    for nm, feat in (("cascade", "K4"), ("flow_with", "A2")):
        v = np.array([np.nan if r["f"].get(feat) is None else r["f"][feat] for r in rows], float)
        out[nm] = (v > 0, np.isfinite(v), "yes", "no")
    for feat, med in sorted(medians.items()):
        v = np.array([np.nan if r["f"].get(feat) is None else r["f"][feat] for r in rows], float)
        out[f"{feat}"] = (v >= med, np.isfinite(v), f">= {med:.3g}", f"< {med:.3g}")
    return out


def estimate(rows, medians, won=None, pnl=None):
    """Per reading: counts, Wilson intervals, p, halves. won / pnl override (placebo)."""
    won = np.array([r["won"] for r in rows], bool) if won is None else won
    pnl = np.array([r["pnl"] for r in rows], float) if pnl is None else pnl
    n = len(rows)
    old = np.arange(n) < (n + 1) // 2
    res = {}
    for rid, (a, known, la, lb) in readings(rows, medians).items():
        A, Bm = a & known, (~a) & known
        na, nb = int(A.sum()), int(Bm.sum())
        ka, kb = int(won[A].sum()), int(won[Bm].sum())
        e = {"id": rid, "label_a": la, "label_b": lb, "n_a": na, "won_a": ka, "n_b": nb, "won_b": kb,
             "ci_a": wilson(ka, na), "ci_b": wilson(kb, nb),
             "usd_a": round(float(pnl[A].mean()), 1) if na else None, "usd_b": round(float(pnl[Bm].mean()), 1) if nb else None}
        e["diff"] = round(ka / na - kb / nb, 3) if na and nb else None
        e["p"] = round(_perm_p(A[known], won[known], rid), 4) if na and nb else 1.0
        halves = []
        for h in (old, ~old):
            ha, hb = A & h, Bm & h
            halves.append(None if not ha.sum() or not hb.sum() else float(won[ha].mean() - won[hb].mean()))
        e["halves"] = [None if x is None else round(x, 3) for x in halves]
        res[rid] = e
    return res


def bh(p, q=Q):
    p = np.asarray(p, float)
    m = len(p)
    if not m:
        return np.zeros(0, bool)
    o = np.argsort(p)
    th = q * np.arange(1, m + 1) / m
    ok = p[o] <= th
    k = int(np.max(np.where(ok)[0])) + 1 if ok.any() else 0
    out = np.zeros(m, bool)
    out[o[:k]] = True
    return out


def statuses(res):
    ids = list(res)
    disc = bh([res[i]["p"] for i in ids])
    for i, ok in zip(ids, disc):
        e = res[i]
        if e["n_a"] < MIN_SIDE or e["n_b"] < MIN_SIDE:
            e["status"] = "too few"
        elif e["p"] >= 0.10:
            e["status"] = "nothing"
        elif ok and all(h is not None and h > 0 for h in e["halves"]):
            e["status"] = "lead"
        else:
            e["status"] = "watching"
    return res


def words(bot, e):
    name = NAMED.get(e["id"])
    if e["id"] == "absorbed":
        head = f"OF said absorbed at the sweep: {e['won_a']} of {e['n_a']} won; not absorbed: {e['won_b']} of {e['n_b']}"
    elif name:
        head = f"OF {name}: {e['won_a']} of {e['n_a']} won; otherwise {e['won_b']} of {e['n_b']}"
    else:
        head = f"OF {e['id']} {e['label_a']}: {e['won_a']} of {e['n_a']} won; {e['label_b']}: {e['won_b']} of {e['n_b']}"
    tail = {"too few": "too few to act", "nothing": f"no difference (p {e['p']:.2f})",
            "watching": f"watching (p {e['p']:.3f}, not past the many-tests check)",
            "lead": f"LEAD (p {e['p']:.4f}, both halves agree): next = a pre-registered battery test, nothing changes yet"}[e["status"]]
    return f"{'Zlarior' if bot == 'LIT' else 'ATLAS'}: {head}, {tail}"


# ------------------------------------------------------------------------------------------------ run
def run(R=None, lit=None, atlas=None, out_dir=None, journal=JOURNAL, today=None, src=None, write=True, say=print) -> dict:
    F = _fwd()
    out_dir = out_dir or OUT_CLOUD
    today = today or dt.date.today().isoformat()
    if R is None:
        R = F.B.find_days(src)
    if not any(int(x["meta"].get("rows", 0)) >= F.B.MIN_ROWS for x in R.values()):
        say("of_learn: no order-flow tick days yet (waiting for the PC's summaries); nothing logged")
        return {"date": today, "signals": {}, "added": 0, "line": None, "waiting": True}
    if lit is None:
        try:
            lit, _ = F.B.lit_trades()
        except Exception:  # noqa: BLE001
            lit = []
    if atlas is None:
        try:
            atlas, _ = F.B.atlas_md()
        except Exception:  # noqa: BLE001
            atlas = []
    sig_p, st_p = os.path.join(out_dir, SIGNALS), os.path.join(out_dir, STATE)
    rows_new = signal_rows(R, lit, atlas)
    if write:
        allrows, added = log(rows_new, sig_p)
    else:
        allrows, added = sorted(rows_new, key=lambda r: (r["t"], r["bot"])), len(rows_new)
    try:
        state = json.load(open(st_p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        state = {}
    meds = state.setdefault("medians", {})
    out = {"date": today, "signals": {}, "added": added, "bots": {}, "placebo_leads": {}, "real_leads": {}}
    obs, lines = [], []
    feats = list(F.M.FEATURES) + list(F.V3.FEATURES_V3)
    try:
        from engine import market_learn as ML
        prev = ML.current_status(ML.journal_doc(journal)) if journal else {}
    except Exception:  # noqa: BLE001
        ML, prev = None, {}
    for bot in ("LIT", "ATLAS"):
        rows = [r for r in allrows if r["bot"] == bot]
        out["signals"][bot] = len(rows)
        if not rows:
            continue
        if bot not in meds and len(rows) >= MIN_MEDIAN:                 # frozen once, never moved
            first = rows                                                    # every signal logged that night
            m = {}
            for f in feats:
                v = np.array([np.nan if r["f"].get(f) is None else r["f"][f] for r in first], float)
                v = v[np.isfinite(v)]
                if len(v) >= MIN_MEDIAN and np.ptp(v) > 0:
                    m[f] = round(float(np.median(v)), 5)
            meds[bot] = {"since": today, "n": len(rows), "m": m}
        med = (meds.get(bot) or {}).get("m", {})
        res = statuses(estimate(rows, med))
        rng = np.random.default_rng(zlib.crc32(f"{today}|{bot}".encode()))
        perm = rng.permutation(len(rows))
        won_p = np.array([r["won"] for r in rows], bool)[perm]
        pnl_p = np.array([r["pnl"] for r in rows], float)[perm]
        plc = statuses(estimate(rows, med, won_p, pnl_p))
        nl, npl = sum(e["status"] == "lead" for e in res.values()), sum(e["status"] == "lead" for e in plc.values())
        out["real_leads"][bot], out["placebo_leads"][bot] = nl, npl
        chance = npl >= nl and nl > 0
        out["bots"][bot] = {k: v for k, v in res.items() if k in NAMED or v["status"] in ("watching", "lead")}
        for rid, e in res.items():
            key = f"of|{bot}|{rid}"
            was = (prev.get(key) or {}).get("status")
            keep = rid in NAMED or e["status"] in ("watching", "lead") or was in ("watching", "lead")
            if not keep:
                continue
            st = {"too few": "watching", "nothing": "rejected", "watching": "watching", "lead": "confirmed"}[e["status"]]
            txt = words(bot, e) + (" - but the shuffled-label placebo found as many: no better than chance" if chance and e["status"] == "lead" else "")
            obs.append({"key": key, "pillar": BOTS[bot], "lens": "order flow", "noticed": txt, "status": st,
                        "evidence": {"n": e["n_a"] + e["n_b"], "won_a": e["won_a"], "n_a": e["n_a"], "won_b": e["won_b"],
                                     "n_b": e["n_b"], "p": e["p"], "ci_a": e["ci_a"], "ci_b": e["ci_b"], "of_status": e["status"]}})
            if rid == "absorbed" or e["status"] == "lead":
                lines.append(txt)
    best = sorted((e for b in out["bots"].values() for e in b.values()), key=lambda e: e["p"])
    out["line"] = (lines[0] if lines else (f"order-flow learner: {sum(out['signals'].values())} signals logged, nothing to say yet"))
    out["leads"] = [f"{b}|{k}" for b, x in out["bots"].items() for k, e in x.items() if e["status"] == "lead"]
    out["best"] = [{k: e[k] for k in ("id", "n_a", "won_a", "n_b", "won_b", "p", "status")} for e in best[:5]]
    say(f"of_learn {today}: signals {out['signals']} (+{added}); leads real {out['real_leads']} vs placebo {out['placebo_leads']}; {out['line']}")
    if write:
        os.makedirs(out_dir, exist_ok=True)
        state.update(last=out, line=out["line"], updated=today)
        with open(st_p, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, default=str)
        if journal and ML is not None and obs and os.path.exists(os.path.dirname(journal)):
            J, new = ML.update_journal(ML.journal_doc(journal), obs, today=today)
            with open(journal, "w", encoding="utf-8") as fh:
                json.dump(J, fh, indent=1)
            out["journal_added"] = len(new)
    out["obs"] = obs
    return out


def pc_nightly(root: str = ROOT, now: dt.datetime | None = None) -> dict:
    """The PC's nightly call (engine/tickrec.autopilot): its own summaries + replays -> logs/orderflow (untracked). Never raises."""
    try:
        if os.environ.get("LE_OFLEARN") == "0":
            return {"off": True}
        today = (now or dt.datetime.now()).date().isoformat()
        try:
            if json.load(open(os.path.join(root, "logs", "orderflow", STATE), encoding="utf-8")).get("updated") == today:
                return {"skipped": "already ran today"}
        except Exception:  # noqa: BLE001
            pass
        F = _fwd()
        R = F.B.find_days(os.path.join(root, "logs", "datapipe", "days"))
        if not R:
            return {"skipped": "no order-flow summaries yet"}
        r = run(R=R, out_dir=os.path.join(root, "logs", "orderflow"), journal=None,
                today=today, say=lambda *_: None)
        return {"line": r["line"], "signals": r["signals"], "leads": r["leads"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {str(e)[:100]}"}


def selftest() -> bool:
    """Fast proof on a small planted world (the full chain proof is tests/test_oflearn.py)."""
    import tempfile
    S = _mod("of_sim.py", "of_sim_learn")
    W = S.world(30, "planted", seed=11)
    with tempfile.TemporaryDirectory() as td:
        jp = os.path.join(td, "journal.json")
        r1 = run(R=W["R"], lit=W["lit"][:20], atlas=[], out_dir=td, journal=jp, today="2026-11-26")
        r2 = run(R=W["R"], lit=W["lit"], atlas=W["atlas"], out_dir=td, journal=jp, today="2026-11-27")
        J = json.load(open(jp))
        ab = r2["bots"]["LIT"]["absorbed"]
        ok = (r1["signals"]["LIT"] == 20 and r2["added"] > 0 and ab["n_a"] + ab["n_b"] > 30 and ab["won_a"] / max(1, ab["n_a"]) > ab["won_b"] / max(1, ab["n_b"])
              and any(e["key"] == "of|LIT|absorbed" for e in J) and "OF said absorbed" in r2["line"])
    print("of_learn selftest:", "OK" if ok else "FAIL", "|", r2["line"])
    return bool(ok)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    run(src=a.src)
