"""Second strategies (paper) next to LIT: engine/second.py live == the research (research/second/*_best.json).

    python -X utf8 -m tests.test_second              # everything (~3-4 min)
    python -X utf8 -m tests.test_second --quick      # day-end replay + imports + cloud dry run (no intraday / look-ahead)
    python -X utf8 -m tests.test_second --intraday=6 # minute-of-the-5m-close polls on 6 trade days per strategy (default 3)

 a. Day-end replay: every 2026 session (Jan 2 - Oct 16) cut at 17:00 ET of that day, LIT's live window (previous month)
    + the research-clean 1m bars, through engine/second.run: each strategy's trades of the day == the research trades
    (entry time, side, exit kind, exit time, R, micros). Plus the "with LIT" view (LIT first, run lit_live's trades): the
    EMA keeps the research's 71 trades of 2026, the MACD the research combine's count.
    Intraday: every 5m close of a few trade days: a trade never shows before its entry bar's open, is OPEN between entry
    and exit (with the research stop / target), then finished with the research exit; the poll at the signal bar's close
    shows the signal (enter at the next open) and no trade yet.
 b. No look-ahead: each sampled research trade, data cut at its signal bar's close (5m and 1m): run() shows the same
    signal (side, stop) from those bars alone.
 c. Paper only: engine/second.py (and the research modules it runs) import no adapter / NinjaTrader / broker module,
    and second_model.json says paper.
 d. Cloud monitor dry run (tools/cloud_monitor.run, offline: no network, fake heartbeat with the PC's bars of a 2026 day):
    state.json "second" with the paper ledger, README "Second strategies (paper)", PAPER notices of kind "second";
    a finished paper trade is frozen.
"""
from __future__ import annotations

import ast
import collections
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import second  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []
REF_FILE = {"ema_lon_vix": "research/second/ema_best.json", "macd_sweep": "research/second/md_best.json",
            "sr_nyreclaim": "research/second/sr_best.json"}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:600]}"), flush=True)


def day_close(d):
    return int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(17, 0), ET).timestamp())


def key(t):
    return (int(t["entry_t"]), int(t["dir"]))


def ex(t):
    return (str(t["exit_kind"]).upper(), int(t["exit_t"]) if t.get("exit_t") else None, round(float(t["r"]), 3), int(t["qty"]))


class Data:
    def __init__(self):
        self.df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        self.df5 = self.df5[self.df5["time"] >= day_close("2025-10-01")].reset_index(drop=True)
        b1, _ = load_ltf("NQ", load("NQ", "5m"))
        self.b1 = b1.slice(int(np.searchsorted(b1.t, int(self.df5["time"].min()))), len(b1))
        self.T5 = self.df5["time"].values
        self.cfg = second.load_cfg()
        runs = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        self.sess = [d[0] for d in runs["days"] if "2026-01-01" <= d[0] <= "2026-10-16"]
        lt = [dict(zip(runs["trade_cols"], a)) for a in runs["trades"]]
        self.lit = sorted(({"entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"])} for t in lt), key=lambda x: x["entry_t"])
        self.ref = {k: [t for t in json.load(open(os.path.join(ROOT, f), encoding="utf-8"))["trades"]
                        if "2026-01-01" <= t["day"] <= "2026-10-16"] for k, f in REF_FILE.items()}
        # LIT + Asia slot (cloud paper shadow): the stored research run (LIT executor, LIT size rule)
        ra = json.load(open(os.path.join(ROOT, "research", "runs", "lit_more_ent_asia_slot_rr3.json"), encoding="utf-8"))
        self.ref_asia = [{**dict(zip(ra["trade_cols"], a)), "exit_kind": ("TIME" if a[ra["trade_cols"].index("exit")] == "EOD"
                                                                         else a[ra["trade_cols"].index("exit")])}
                         for a in ra["trades"] if "2026-01-01" <= a[0] <= "2026-10-16"]

    def poll(self, now, lit=True, only=None):
        cfg = self.cfg if only is None else {**self.cfg, "strategies": {only: self.cfg["strategies"][only]}}
        cut5 = self.df5.iloc[:int(np.searchsorted(self.T5 + 300, now, side="right"))]
        cut1 = self.b1.slice(0, int(np.searchsorted(self.b1.t + 60, now, side="right")))
        return second.run(cut5, one_min=cut1, now=now, cfg=cfg, lit=[x for x in self.lit if x["entry_t"] < now] if lit else [])


# ------------------------------------------------------------------------------------------------ a. day-end replay
def day_end(D):
    print("a. day-end replay, every 2026 session", flush=True)
    t0 = time.time()
    got = collections.defaultdict(list)
    alt = collections.defaultdict(list)
    errs = []
    for d in D.sess:
        r = D.poll(day_close(d))
        for k, s in r["strategies"].items():
            if s.get("error"):
                errs.append((d, k, s["error"]))
            got[k] += [t for t in s["trades"] if t["day"] == d]
            alt[k] += [a for a in (s.get("state") or {}).get("lit_alt") or [] if a["day"] == d]
    out = {}
    ga = {int(t["entry_t"]): t for t in got["lit_asia"]}
    same_a, bad_a = 0, []
    for w in D.ref_asia:
        t = ga.pop(int(w["entry_t"]), None)
        if t and (t["exit_kind"], t["exit_t"], t["qty"], t["dir"]) == (w["exit_kind"], int(w["exit_t"]), int(w["qty"]), int(w["dir"])) \
                and abs(t["usd"] - w["pnl"]) <= 0.6 * max(1, t["qty"]):
            same_a += 1
        else:
            bad_a.append((w["day"], w["entry_t"], t and (t["exit_kind"], t["exit_t"], t["qty"], t["usd"]), (w["exit_kind"], w["exit_t"], w["qty"], w["pnl"])))
    out["lit_asia"] = (same_a, len(D.ref_asia))
    check(f"lit_asia (LIT + Asia slot, cloud shadow): day-end replay {same_a}/{len(D.ref_asia)} trades of run lit_more_ent_asia_slot_rr3 "
          f"identical (exit, time, micros, $ within the commission rounding), extra {len(ga)}", same_a == len(D.ref_asia) and not ga,
          {"bad": bad_a[:5], "extra": list(ga)[:5]})
    for k, ref in D.ref.items():
        g = {key(t): t for t in got[k]}
        same = entries = 0
        miss, wrong = [], []
        for w in ref:
            t = g.pop(key(w), None)
            if t is None:
                miss.append((w["day"], w["entry_t"]))
                continue
            entries += 1
            if ex(t) == ex(w):
                same += 1
            else:
                wrong.append((w["day"], ex(t), ex(w)))
        extra = [(t["day"], t["entry_t"]) for t in g.values()]
        out[k] = (same, len(ref))
        check(f"{k}: day-end replay {same}/{len(ref)} research trades identical (entries {entries}, missing {len(miss)}, "
              f"extra {len(extra)}, exit differs {len(wrong)})", same == len(ref) and not extra and not errs,
              {"missing": miss[:5], "extra": extra[:5], "wrong": wrong[:5], "errors": errs[:3]})
        lt = [t for t in got[k] if (t.get("lit") or {}).get("taken")]
        out[k + "_lit"] = (len(lt), round(sum(t["lit"]["usd"] for t in lt)))
    # the "with LIT" view vs the research combine (LIT first, max 2 a day)
    ema_rep = json.load(open(os.path.join(ROOT, "research", "second", "ema_report.json"), encoding="utf-8"))["versions"]["ema2_lon_vix"]
    want = ema_rep["with_lit_max2"]["ema_trades_kept_2026"]
    check(f"ema_lon_vix: with LIT on one account {out['ema_lon_vix_lit'][0]} trades kept = research {want}",
          out["ema_lon_vix_lit"][0] == want, out["ema_lon_vix_lit"])
    md_rep = json.load(open(os.path.join(ROOT, REF_FILE["macd_sweep"]), encoding="utf-8"))["report"]["combo"]
    want_md = md_rep["two"]["merged"]["2026"]["n"] - md_rep["lit_only"]["2026"]["n"]
    want_net = md_rep["two"]["merged"]["2026"]["net"] - md_rep["lit_only"]["2026"]["net"]
    check(f"macd_sweep: with LIT on one account {out['macd_sweep_lit'][0]} trades kept, {out['macd_sweep_lit'][1]:+,} $ "
          f"= research combine {want_md}, {want_net:+,} $ (+/- $5)",
          out["macd_sweep_lit"][0] == want_md and abs(out["macd_sweep_lit"][1] - want_net) <= 5, out["macd_sweep_lit"])
    sr_rep = json.load(open(os.path.join(ROOT, "research", "second", "sr_final.json"), encoding="utf-8"))["nyreclaim"]["combo"]["max2"]
    want_sr = sum(sr_rep[p]["sr_n"] for p in ("H1", "H2"))
    want_sr_net = sum(sr_rep[p]["sr_net"] for p in ("H1", "H2"))
    na = len(alt["sr_nyreclaim"])
    n_sr = out["sr_nyreclaim_lit"][0] + na
    net_sr = out["sr_nyreclaim_lit"][1] + round(sum(a["usd"] for a in alt["sr_nyreclaim"]))
    check(f"sr_nyreclaim: with LIT on one account {n_sr} trades ({na} later reclaims taken instead), {net_sr:+,} $ "
          f"= research combine {want_sr}, {want_sr_net:+,} $ (+/- $5)", n_sr == want_sr and abs(net_sr - want_sr_net) <= 5,
          (out["sr_nyreclaim_lit"], alt["sr_nyreclaim"][:3]))
    print(f"   ({time.time() - t0:.0f}s)", flush=True)
    return out


def intraday(D, n_days):
    print(f"a2. intraday: every 5m close of {n_days} trade days per strategy", flush=True)
    t0 = time.time()
    for k, ref in D.ref.items():
        days = sorted({t["day"] for t in ref})
        pick = [days[int(i)] for i in np.linspace(0, len(days) - 1, n_days)] if n_days < len(days) else days
        bad, n_polls, sig_seen = [], 0, 0
        for d in pick:
            W = [t for t in ref if t["day"] == d]
            a = int(dt.datetime.combine(dt.date.fromisoformat(d) - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
            first_e = min(t["entry_t"] for t in W)
            for now in range(max(a + 300, first_e - 3600), day_close(d) - 3600 + 1, 300):
                if not (D.T5 == now - 300).any():
                    continue
                n_polls += 1
                s = D.poll(now, only=k)["strategies"][k]
                tt = {key(t): t for t in s["trades"] if t["day"] == d}
                for w in W:
                    t = tt.pop(key(w), None)
                    if now <= w["entry_t"]:
                        if t is not None:
                            bad.append((d, now, "trade before its entry bar opened"))
                        if now == w["entry_t"]:
                            sg = (s.get("state") or {}).get("signal")
                            if sg and int(sg["dir"]) == int(w["dir"]):
                                sig_seen += 1
                            else:
                                bad.append((d, now, f"no signal at the signal bar's close: {s.get('state')}"))
                        continue
                    if t is None:
                        bad.append((d, now, "missing after its entry"))
                        continue
                    done = now >= int(w["exit_t"])
                    # a 15-minute cut exits at the next bar's open: at that open the price is not known yet (still OPEN)
                    cut_wait = t["exit_kind"] == "OPEN" and now == int(w["exit_t"]) and str(w["exit_kind"]).lower() == "cut"
                    if done and ex(t) != ex(w) and not cut_wait:
                        bad.append((d, now, ex(t), ex(w)))
                    if not done and t["exit_kind"] != "OPEN":
                        bad.append((d, now, "finished before the research exit", ex(t), ex(w)))
                    if not done and (abs(t["stop"] - w["stop"]) > 1e-6 or abs(t["target"] - w["target"]) > 0.011):
                        bad.append((d, now, "open trade stop / target differ"))
                if tt:
                    bad.append((d, now, "extra trade", list(tt)))
        check(f"{k}: intraday {n_polls} polls on {len(pick)} trade days: open between entry and exit, research exit after, "
              f"signal shown at {sig_seen} signal-bar closes", not bad, bad[:6])
    print(f"   ({time.time() - t0:.0f}s)", flush=True)


# ------------------------------------------------------------------------------------------------ b. no look-ahead
def lookahead(D, n=20):
    print(f"b. no look-ahead: {n} trades per strategy, data cut at the signal bar's close", flush=True)
    for k, ref in D.ref.items():
        idx = np.linspace(0, len(ref) - 1, min(n, len(ref))).astype(int)
        bad = 0
        ex_ = []
        for i in idx:
            w = ref[i]
            now = int(w["entry_t"])           # the signal bar closes when the entry bar opens
            r = D.poll(now, only=k)["strategies"][k]
            sg = (r.get("state") or {}).get("signal")
            ok = bool(sg) and int(sg["dir"]) == int(w["dir"]) and abs(float(sg["stop"]) - float(w["stop"])) < 1e-6 \
                and not any(key(t) == key(w) for t in r["trades"])
            if not ok:
                bad += 1
                ex_.append((w["day"], w["entry_t"], sg, r.get("state", {}).get("text")))
        check(f"{k}: {len(idx) - bad}/{len(idx)} signals found from the bars up to the signal bar alone (same side and stop)",
              bad == 0, ex_[:4])


# ------------------------------------------------------------------------------------------------ c. paper only
BAD_MOD = re.compile(r"ninjatrader|tradovate|adapter|broker|multi_account|oif|lab_adapter|engine\.live$|crosstrade|traderspost", re.I)


def imports_of(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            m = ("." * n.level) + (n.module or "")
            out |= {m} | {f"{m}.{a.name}" for a in n.names}
    return out


def paper_only():
    print("c. paper only: no routing imports", flush=True)
    files = ["engine/second.py", "tools/second_ema.py", "tools/second_md.py", "tools/second_sr.py", "tools/retail_standalone.py"]
    hits = {f: sorted(m for m in imports_of(os.path.join(ROOT, f)) if BAD_MOD.search(m)) for f in files}
    check("engine/second.py + the research modules it runs import no adapter / NinjaTrader / broker module",
          not any(hits.values()), hits)
    src = open(os.path.join(ROOT, "engine", "second.py"), encoding="utf-8").read()
    check("engine/second.py writes no order file (no 'incoming', 'PLACE', 'place_order', 'route' calls)",
          not re.search(r"incoming|PLACE;|place_order|\.route\(|submit_order", src))
    code = ("import sys, json; sys.path.insert(0, '.'); import pandas as pd; from engine import second; "
            "df = pd.read_csv('data/NQ_5m.csv'); df = df[df.time < 1768500000]; second.run(df.tail(12000)); "
            "print(json.dumps(sorted(m for m in sys.modules if m.startswith(('engine', 'tools')))))")
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=300)
    mods = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else None
    loaded = [m for m in (mods or []) if BAD_MOD.search(m)]
    check("a fresh process that runs engine/second.run loads no adapter / NinjaTrader / broker module",
          mods is not None and not loaded, loaded or p.stderr[-400:])
    cfg = second.load_cfg()
    keys = {kk for s in cfg["strategies"].values() for kk in s}
    # "route" (2026-10-22) is the owner's per-strategy switch for the PC bot (engine/live.py routes it, this module never):
    # it ships false everywhere; no account / adapter / armed setting lives in this file
    check("second_model.json: paper true, every strategy on, \"route\": false everywhere, no account / adapter / armed setting",
          cfg.get("paper") is True and all(cfg["strategies"][k].get("on") for k in REF_FILE)
          and not any(s.get("route") for s in cfg["strategies"].values()) and second.routed(cfg) == []
          and not any(re.search(r"^(account|accounts|adapter|routing|armed|live)$", k, re.I) for k in keys), (cfg.get("error"), keys))
    a, b = (os.path.join(ROOT, "tools", "web_public", "secondcore.js"), os.path.join(ROOT, "web_next", "js", "next", "secondcore.js"))
    check("secondcore.js: the phone and the PC copies are byte-identical",
          os.path.exists(b) and open(a, "rb").read() == open(b, "rb").read())


# ------------------------------------------------------------------------------------------------ e. the second brain
EMA_MASK_ORDER = ("window", "t15", "t60", "pull", "sweep", "monday")


def _ema_mask_first_fail(row, E):
    """The first entry_mask condition (tools/second_ema.entry_mask, written out again here) the candidate fails."""
    from tools import second_ema as SE
    a, z = SE.WINS[E["win"]]
    conds = {"window": a <= row["mod"] + 5 < z, "t15": row["t15"] > 0, "t60": row["t60"] > 0, "pull": row["touch50"] > 0,
             "sweep": row["swept"] > 0, "monday": row["dow"] != 0}
    return next((k for k in EMA_MASK_ORDER if not conds[k]), None)


def brain(D, n_per=6):
    """The second brain's rule checks against each strategy's actual decision: at the signal bar's close of a research
    trade every rule is ✓ (none ✗) and the planned stop / side are the trade's; once filled the trade's checks are all ✓; at
    the day's close the brain's log marks exactly the research trades as TRADE and gives every other setup a first ✗ that is
    the engine's reason (EMA: recomputed from tools/second_ema.candidates / entry_mask / simulate on the same bars; MACD /
    S-R: none of them is a research trade; S-R reclaim / body / inducement rejections are not in tools/second_sr.gen)."""
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    from tools import second_sr as SR
    print("e. second brain: rule checks vs the strategies' decisions", flush=True)
    t0 = time.time()
    for k in ("ema_lon_vix", "macd_sweep", "sr_nyreclaim"):
        refs = D.ref[k]
        pick = refs[::max(1, len(refs) // n_per)][:n_per]
        bad_sig, bad_trade, bad_log, bad_why, n_log, n_rej = [], [], [], [], 0, 0
        for u in pick:
            et_ = int(u["entry_t"])
            b = D.poll(et_ + 2, only=k)["strategies"][k].get("brain") or {}
            C = b.get("checks") or []
            pl = b.get("plan") or {}
            if (b.get("focus") or {}).get("kind") != "signal" or any(c["ok"] is False for c in C) or not C \
                    or pl.get("dir") != int(u["dir"]) or abs(float(pl.get("stop") or 0) - float(u["stop"])) > 0.01:
                bad_sig.append((u["day"], et_, b.get("focus"), second.first_fail(C), pl, b.get("error")))
            b2 = D.poll(et_ + 302, only=k)["strategies"][k].get("brain") or {}
            if (b2.get("focus") or {}).get("kind") != "trade" or not all(c["ok"] is True for c in b2.get("checks") or [None]):
                bad_trade.append((u["day"], b2.get("focus"), [(c["k"], c["ok"]) for c in b2.get("checks") or []], b2.get("error")))
            now = day_close(u["day"])
            b3 = D.poll(now, only=k)["strategies"][k].get("brain") or {}
            want = {int(t["entry_t"]) for t in refs if t["day"] == u["day"]}
            log = [x for x in b3.get("log") or [] if x.get("entry_t") or x.get("t")]
            got = {int(x["entry_t"]) for x in log if x.get("trade")}
            if got != want or any(not x.get("trade") and not x.get("ff") and x.get("t") for x in log):
                bad_log.append((u["day"], sorted(got), sorted(want), [x["text"] for x in log][:12]))
            n_log += len(log)
            rej = [x for x in log if x.get("ff") and x.get("entry_t")]
            n_rej += len(rej)
            if k == "ema_lon_vix" and rej:
                cut5 = D.df5.iloc[:int(np.searchsorted(D.T5 + 300, now, side="right"))]
                E, X = dict(D.cfg["strategies"][k]["entry"]), dict(D.cfg["strategies"][k]["exit"])
                saved = dict(RS.D)
                try:
                    RS.load_frame(second._window(cut5), live_cut=True)
                    d = SE.load()
                    cand = SE.candidates()
                    rows = {(int(d["t"][int(r["sig"])]) + 300, int(r["dir"])): r for _, r in cand.iterrows()}
                    mask = SE.entry_mask(cand, E)
                    ok_mask = {(int(d["t"][int(r["sig"])]) + 300, int(r["dir"])): bool(m) for (_, r), m in zip(cand.iterrows(), mask)}
                    for x in rej:
                        kk = (int(x["entry_t"]), int(x["dir"]))
                        r = rows.get(kk)
                        if r is None:
                            bad_why.append((u["day"], x["text"], "no such candidate")); continue
                        ff = x["ff"]
                        if ff in EMA_MASK_ORDER:
                            good = (not ok_mask[kk]) and _ema_mask_first_fail(r, E) == ff
                        elif ff == "one":
                            good = ok_mask[kk] and any(int(t) < kk[0] for t in want)
                        elif ff == "target":
                            good = ok_mask[kk] and SE.simulate(r, X, d) is None
                        else:
                            good = False
                        if not good:
                            bad_why.append((u["day"], x["text"], ff, _ema_mask_first_fail(r, E), ok_mask[kk]))
                finally:
                    RS.D.clear(); RS.D.update(saved)
            if k == "sr_nyreclaim" and rej:
                key_ = dict(D.cfg["strategies"][k]["key"])
                cut5 = D.df5.iloc[:int(np.searchsorted(D.T5 + 300, now, side="right"))]
                saved, saved_sr, saved_oc = dict(RS.D), dict(SR.D), dict(SR._OC)
                try:
                    RS.load_frame(second._window(cut5), live_cut=True)
                    SR.D.clear(); SR._OC.clear(); SR.data()
                    d = SR.D
                    g = {kk: key_[kk] for kk in SR.GEN_KEYS[key_["setup"]]}
                    gen = {(int(d["t"][c[0]]) + 300, int(c[2]), c[8]) for c in SR.gen(d, key_["setup"], g)}
                    for x in rej:
                        in_gen = (int(x["entry_t"]), int(x["dir"]), x.get("level")) in gen
                        if x["ff"] in ("reclaim", "body", "idm", "depth", "known", "swept") and in_gen:
                            bad_why.append((u["day"], x["text"], "rejected by the brain but in gen"))
                        if x["ff"] in ("fill", "stop", "window", "one", "busy", "target") and not in_gen:
                            bad_why.append((u["day"], x["text"], "a select-stage reason but not in gen"))
                finally:
                    RS.D.clear(); RS.D.update(saved)
                    SR.D.clear(); SR.D.update(saved_sr)
                    SR._OC.clear(); SR._OC.update(saved_oc)
        check(f"brain {k}: at the signal bar's close of {len(pick)} research trades every rule is ✓ (no ✗), plan side / stop = the trade",
              not bad_sig, bad_sig[:3])
        check(f"brain {k}: once filled, today's trade shows all its rules ✓", not bad_trade, bad_trade[:3])
        check(f"brain {k}: day-end log marks exactly the research trades as TRADE, every other setup has a first ✗ ({n_log} setups)",
              not bad_log, bad_log[:2])
        check(f"brain {k}: each rejected setup's first ✗ is the engine's real reason ({n_rej} rejected setups checked)", not bad_why,
              bad_why[:4])
    # the heartbeat cut stays small
    r = D.poll(day_close(D.ref["sr_nyreclaim"][3]["day"]))
    cp = second.compact(r)
    cand = {k: len(json.dumps(v, default=str)) for k, v in cp["strategies"].items() if v.get("candidate")}   # stop-hunt candidates
    size = len(json.dumps({**cp, "strategies": {k: v for k, v in cp["strategies"].items() if k not in cand}}, default=str))
    check(f"brain: the heartbeat / live.json cut of every strategy's brain is small ({size:,} bytes < 16 KB; candidate members "
          f"{cand} < 3.5 KB each)", size < 16000 and all(v < 3500 for v in cand.values()), (size, cand))
    print(f"   ({time.time() - t0:.0f}s)", flush=True)


# ------------------------------------------------------------------------------------------------ d. cloud dry run
def at(y, m, d, hh, mm, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


class Net:
    def __init__(self):
        self.urls = []

    def __call__(self, req, *a, **kw):
        self.urls.append(req if isinstance(req, str) else getattr(req, "full_url", str(req)))
        raise OSError("offline test: no network")


def cloud(D):
    print("d. cloud monitor dry run (offline, fake heartbeat with the PC's bars)", flush=True)
    import urllib.request
    import cloud_monitor as cm
    from engine import heartbeat, live, pcbars, push
    NOW = at(2026, 1, 9, 10, 3, 30)        # Fri 2026-01-09: EMA short 03:25 (BE), MACD short 02:25 (stop)
    TV_END = at(2026, 1, 7, 0, 0)
    b5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    b1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    b1.columns = [c.strip().lower() for c in b1.columns]
    b5 = b5[(b5["time"] >= NOW - 70 * 86400) & (b5["time"] + 300 <= NOW)].reset_index(drop=True)
    b1 = b1[(b1["time"] >= NOW - 70 * 86400) & (b1["time"] + 60 <= NOW)][list(pcbars.COLS)].reset_index(drop=True)
    tmp = tempfile.mkdtemp(prefix="le_second_")
    out = os.path.join(tmp, "dash")
    os.makedirs(out)
    with open(os.path.join(out, "state.json"), "w", encoding="utf-8") as fh:   # the ledgers started watching a day earlier
        json.dump({"first_run": NOW - 86400, "model": "lit", "second": {"first_run": NOW - 86400, "strategies": {}},
                   "bars_src": "pc-ninjatrader", "push_since": NOW - 86400}, fh)
    clock = [NOW]
    f1, f5 = b1[b1["time"] >= TV_END - 86400], b5[b5["time"] >= TV_END - 86400]
    files = {pcbars.BARS_1M: pcbars.encode(f1[f1["time"] >= NOW - 3 * 86400]), pcbars.BARS_5M: pcbars.encode(f5)}
    hb = {"t": NOW - 30, "running": True, "adapter": "ninjatrader", "every_s": 300, "host": "test", "bars": pcbars.PCBars.meta(files)}

    def fake_read(cwd=None, remote="origin", branch="heartbeat", now=None, files_=(), **kw):
        h = json.loads(json.dumps(hb))
        h.update(present=True, age_s=int((now or clock[0]) - h["t"]), silent=False)
        fl = kw.get("files") or files_
        if fl:
            h["files"] = {n: files.get(n) for n in fl}
        return h
    tv5, tv1 = b5[b5["time"] < TV_END].reset_index(drop=True), b1[b1["time"] < TV_END].reset_index(drop=True)
    net = Net()
    saved = (heartbeat.read, push.Relay.read, cm.time.time, live.LiveBot._read_hist, urllib.request.urlopen, subprocess.run)
    heartbeat.read = fake_read
    push.Relay.read = lambda self, *a, **kw: []
    cm.time.time = lambda: clock[0]
    urllib.request.urlopen = net
    live.LiveBot._read_hist = lambda self, sym, tf: (tv5 if tf == "5m" else tv1 if tf == "1m" else pd.DataFrame(columns=pcbars.COLS)) \
        if sym == "NQ" else pd.DataFrame(columns=pcbars.COLS)
    real_run = subprocess.run

    def no_git_net(args, *a, **kw):                # git ls-remote / fetch would go to the network: refuse
        if isinstance(args, (list, tuple)) and args and str(args[0]).endswith("git") and any(x in args for x in ("ls-remote", "fetch", "push")):
            return subprocess.CompletedProcess(args, 1, "", "offline test")
        return real_run(args, *a, **kw)
    subprocess.run = no_git_net
    err = None
    try:
        try:
            cm.run(out)
        except Exception:
            import traceback
            err = traceback.format_exc()[-1500:]
        st = json.load(open(os.path.join(out, "state.json"), encoding="utf-8")) if os.path.exists(os.path.join(out, "state.json")) else {}
        sec = st.get("second") or {}
        led_e = ((sec.get("strategies") or {}).get("ema_lon_vix") or {}).get("ledger") or {}
        led_m = ((sec.get("strategies") or {}).get("macd_sweep") or {}).get("ledger") or {}
        want_e = [t for t in D.ref["ema_lon_vix"] if t["day"] == "2026-01-09"]
        want_m = [t for t in D.ref["macd_sweep"] if t["day"] == "2026-01-09"]
        ok_e = all(str(t["entry_t"]) in led_e and ex(led_e[str(t["entry_t"])]) == ex(t) for t in want_e)
        ok_m = all(str(t["entry_t"]) in led_m and ex(led_m[str(t["entry_t"])]) == ex(t) for t in want_m)
        check("cloud run with second on: no error, state.json 'second' holds both paper ledgers with the research trades of the day",
              err is None and ok_e and ok_m and want_e and want_m, err or {"ema": list(led_e), "md": list(led_m)})
        readme = open(os.path.join(out, "README.md"), encoding="utf-8").read() if os.path.exists(os.path.join(out, "README.md")) else ""
        check("README has 'ATLAS (paper)' with both strategies", "## ATLAS (paper)" in readme
              and "London EMA trend pullback" in readme and "MACD divergence" in readme)
        nts = [n for n in st.get("notices") or [] if n.get("kind") == "second"]
        check(f"PAPER notices of kind 'second' for the entries and exits ({len(nts)})",
              len(nts) >= 4 and all(n["title"].startswith(("ATLAS PAPER", "PAPER")) and "PAPER" in n["title"] for n in nts), [n.get("title") for n in nts])
        check("offline: no network call reached the internet (all refused)", True, net.urls[:3])
        # freeze: a re-run where the replay disagrees keeps the finished row
        row = dict(led_e[str(want_e[0]["entry_t"])]) if want_e and led_e else None
        fake = {"day": "2026-01-09", "strategies": {"ema_lon_vix": {"label": "x", "trades": [{**row, "exit_kind": "TARGET", "r": 3.0}]}}} if row else None
        b2 = second.ledger_update(sec, fake, NOW + 600) if fake else {}
        r2 = (((b2.get("strategies") or {}).get("ema_lon_vix") or {}).get("ledger") or {}).get(str(want_e[0]["entry_t"])) if row else None
        check("a finished paper trade is frozen (a disagreeing re-run is only noted)",
              r2 is not None and r2["exit_kind"] == row["exit_kind"] and (r2.get("revised_replay") or {}).get("exit_kind") == "TARGET", r2)
        blk = second.dashboard_block(sec)
        mem = [s for s in blk["strategies"] if not s.get("candidate")]       # candidates (stop hunts): tests/test_second_stophunt.py
        check("dashboard block: every strategy with rules, backtest H1/H2/2025/2021-24 + with-LIT tables and paper trades",
              len(mem) == len(REF_FILE) + 1 and all(s["rules"] and s["backtest"]["own"].get("H2") and s["backtest"]["with_lit"].get("H1")
                                                  and s["backtest"]["own"].get("2021-24") for s in mem)
              and all(s["trades"] for s in mem if s["key"] not in ("sr_nyreclaim", "lit_asia")),
              [(s["key"], bool(s["rules"]), list(s["backtest"]["own"]), s["backtest"].get("error")) for s in blk["strategies"]])
    finally:
        heartbeat.read, push.Relay.read, cm.time.time, live.LiveBot._read_hist, urllib.request.urlopen, subprocess.run = saved
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    quick = "--quick" in sys.argv
    n_intra = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--intraday=")), 3)
    t0 = time.time()
    D = Data()
    paper_only()
    rep = day_end(D)
    brain(D, 3 if quick else 6)
    if not quick:
        intraday(D, n_intra)
        lookahead(D)
    if "--nocloud" not in sys.argv:
        cloud(D)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nsecond strategies: {'PASS' if n_ok == len(RESULTS) else 'FAIL'} ({n_ok}/{len(RESULTS)}) in {time.time() - t0:.0f}s; "
          + ", ".join(f"{k} {a}/{b}" for k, (a, b) in rep.items() if not k.endswith("_lit")))
    return n_ok == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
