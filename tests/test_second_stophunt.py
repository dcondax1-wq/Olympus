"""Stop-hunt candidate members (paper) in engine/second.py == the research picks (research/writeups/stophunt.md).

    python -X utf8 -m tests.test_second_stophunt              # everything (~3-5 min)
    python -X utf8 -m tests.test_second_stophunt --quick      # day-end replay + paper-only + evening + scorecard
    python -X utf8 -m tests.test_second_stophunt --intraday=6 # 5m-close polls on 6 trade days per hunt (default 4)

 a. Day-end replay: every 2026 session (Jan 2 - Oct 16, the sessions of run lit_live) cut at 17:00 ET, LIT's live window
    (engine/second._window) + the 1m bars, through engine/second.run: each hunt's trades of the day == the 2026 trades of
    research/stophunt/sh_asia_resweep.json / sh_trend_idm5.json (entry time, side, exit kind, exit time, R, micros).
 b. Intraday: every 5m close (evening included) of a few trade days: no trade before its entry, OPEN between entry and
    exit with the research stop / target, the research exit after; the poll at the signal bar's close shows the signal.
 c. No look-ahead: data cut at each sampled trade's signal-bar close: the same signal (side, stop) from those bars alone,
    no trade yet.
 d. Brain: at a signal close no rule fails (✗) and the checks cover pool / depth / resweep or inducement / candle / swing;
    a day with a trade shows it with every check passed; evening polls (19:00, 23:00, 01:00 ET) give a state + brain for
    both hunts (the Asia hunt is not "off" then; at 10:00 it is off / done).
 e. Paper only: engine/stophunt.py / tools/stophunt.py import no adapter; "route" false, a candidate is never routed
    (load_cfg, set_route refused); not on account B's default list, not an ATLAS member, not in the account-B band.
 f. Without numba (blocked in a fresh process) one session gives the same trades.
 g. Scorecard: each hunt's bands pool its 2026 H2 / 2025 research trades; the dashboard block / compact carry
    "candidate" and the scorecard.
"""
from __future__ import annotations

import ast
import collections
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import second  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []
KEYS = {"sh_asia": "sh_asia_resweep", "sh_trend": "sh_trend_idm5"}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def at(d, hh, mm=0):
    return int(dt.datetime.combine(dt.date.fromisoformat(d) if isinstance(d, str) else d, dt.time(hh, mm), ET).timestamp())


def key(t):
    return (int(t["entry_t"]), int(t["dir"]))


def ex(t):
    return (str(t["exit_kind"]).upper(), int(t["exit_t"]) if t.get("exit_t") else None, round(float(t["r"]), 3), int(t["qty"]))


class Data:
    def __init__(self):
        self.df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        self.df5 = self.df5[self.df5["time"] >= at("2025-10-01", 17)].reset_index(drop=True)
        self.df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
        self.T5, self.T1 = self.df5["time"].values, self.df1["time"].values
        self.cfg = second.load_cfg()
        runs = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        self.sess = [d[0] for d in runs["days"] if "2026-01-01" <= d[0] <= "2026-10-16"]
        self.ref = {k: [t for t in json.load(open(os.path.join(ROOT, "research", "stophunt", f + ".json"), encoding="utf-8"))["trades"]
                        if "2026-01-01" <= t["day"] <= "2026-10-16"] for k, f in KEYS.items()}

    def poll(self, now, only=None):
        cfg = {**self.cfg, "strategies": {k: self.cfg["strategies"][k] for k in ([only] if only else KEYS)}}
        cut5 = self.df5.iloc[:int(np.searchsorted(self.T5 + 300, now, side="right"))]
        cut1 = self.df1.iloc[:int(np.searchsorted(self.T1 + 60, now, side="right"))]
        return second.run(cut5, one_min=cut1, now=now, cfg=cfg, lit=[])


# ------------------------------------------------------------------------------------------------ a. day-end replay
def day_end(D):
    print("a. day-end replay, every 2026 session", flush=True)
    t0 = time.time()
    got, errs, brains = collections.defaultdict(list), [], collections.defaultdict(list)
    for d in D.sess:
        r = D.poll(at(d, 17))
        for k, s in r["strategies"].items():
            if s.get("error") or (s.get("brain") or {}).get("error"):
                errs.append((d, k, s.get("error") or s["brain"]["error"]))
            td = [t for t in s["trades"] if t["day"] == d]
            got[k] += td
            if td:
                brains[k].append((d, s.get("brain") or {}))
    out = {}
    for k, ref in D.ref.items():
        g = {key(t): t for t in got[k]}
        same, miss, wrong = 0, [], []
        for w in ref:
            t = g.pop(key(w), None)
            if t is None:
                miss.append((w["day"], w["entry_t"]))
            elif ex(t) == ex(w) and abs(t["stop"] - w["stop"]) < 1e-6 and abs(t["target"] - w["target"]) < 0.011:
                same += 1
            else:
                wrong.append((w["day"], ex(t), ex(w)))
        extra = [(t["day"], t["entry_t"]) for t in g.values()]
        out[k] = (same, len(ref))
        check(f"{k} ({KEYS[k]}): day-end replay {same}/{len(ref)} research trades of 2026 identical (missing {len(miss)}, "
              f"extra {len(extra)}, exit differs {len(wrong)})", same == len(ref) and not extra and not [e for e in errs if e[1] == k],
              {"missing": miss[:5], "extra": extra[:5], "wrong": wrong[:5], "errors": errs[:3]})
        bad = [(d, b.get("first_fail"), len(b.get("checks") or [])) for d, b in brains[k]
               if (b.get("focus") or {}).get("kind") != "trade" or b.get("first_fail") or len(b.get("checks") or []) < 6]
        check(f"{k}: brain on the {len(brains[k])} trade days: today's trade in focus, every rule check passed",
              brains[k] and not bad, bad[:5])
    print(f"   ({time.time() - t0:.0f}s)", flush=True)
    return out


# ------------------------------------------------------------------------------------------------ b. intraday
def intraday(D, n_days):
    print(f"b. intraday: every 5m close of {n_days} trade days per hunt", flush=True)
    t0 = time.time()
    for k, ref in D.ref.items():
        days = sorted({t["day"] for t in ref})
        pick = [days[int(i)] for i in np.linspace(0, len(days) - 1, n_days)] if n_days < len(days) else days
        bad, n_polls, sig_seen, n_open = [], 0, 0, 0
        for d in pick:
            W = [t for t in ref if t["day"] == d]
            a = at(dt.date.fromisoformat(d) - dt.timedelta(days=1), 18)
            first = min(t["signal_t"] for t in W)
            for now in range(max(a + 300, first - 1800), at(d, 16) + 1, 300):
                if not (D.T5 == now - 300).any():
                    continue
                n_polls += 1
                s = D.poll(now, only=k)["strategies"][k]
                tt = {key(t): t for t in s["trades"] if t["day"] == d}
                for w in W:
                    t = tt.pop(key(w), None)
                    if now == w["signal_t"]:
                        sg = (s.get("state") or {}).get("signal")
                        if sg and int(sg["dir"]) == int(w["dir"]) and abs(float(sg["stop"]) - float(w["stop"])) < 1e-6:
                            sig_seen += 1
                        elif not any(int(x["entry_t"]) < now and x["day"] == d for x in s["trades"]):
                            bad.append((d, now, "no signal at the signal bar's close", s.get("state")))
                    if now <= w["entry_t"]:
                        if t is not None:
                            bad.append((d, now, "trade before its entry bar"))
                        continue
                    if t is None:
                        if now >= w["entry_t"] + 300:
                            bad.append((d, now, "missing after its entry"))
                        continue
                    done = now >= int(w["exit_t"])
                    if done and ex(t) != ex(w):
                        bad.append((d, now, ex(t), ex(w)))
                    if not done:
                        n_open += 1
                        if t["exit_kind"] != "OPEN":
                            bad.append((d, now, "finished before the research exit", ex(t), ex(w)))
                        elif abs(t["stop"] - w["stop"]) > 1e-6 or abs(t["target"] - w["target"]) > 0.011:
                            bad.append((d, now, "open trade stop / target differ"))
                        elif (s.get("state") or {}).get("stage") != "in_trade":
                            bad.append((d, now, "state not in_trade while OPEN", s.get("state")))
                if tt:
                    bad.append((d, now, "extra trade", list(tt)))
        check(f"{k}: intraday {n_polls} polls on {len(pick)} trade days: OPEN between entry and exit ({n_open} polls), research "
              f"exit after, signal shown at {sig_seen} signal-bar closes", not bad and sig_seen > 0, bad[:6])
    print(f"   ({time.time() - t0:.0f}s)", flush=True)


# ------------------------------------------------------------------------------------------------ c. no look-ahead
def lookahead(D, n=20):
    print(f"c. no look-ahead: {n} trades per hunt, data cut at the signal bar's close", flush=True)
    for k, ref in D.ref.items():
        idx = np.linspace(0, len(ref) - 1, min(n, len(ref))).astype(int)
        bad, nb = [], 0
        for i in idx:
            w = ref[i]
            r = D.poll(int(w["signal_t"]), only=k)["strategies"][k]
            sg = (r.get("state") or {}).get("signal")
            b = r.get("brain") or {}
            ok = bool(sg) and int(sg["dir"]) == int(w["dir"]) and abs(float(sg["stop"]) - float(w["stop"])) < 1e-6 \
                and not any(key(t) == key(w) for t in r["trades"])
            if not ok:
                bad.append((w["day"], w["signal_t"], sg, (r.get("state") or {}).get("text")))
            names = {c["k"] for c in b.get("checks") or []}
            if (b.get("focus") or {}).get("kind") != "signal" or b.get("first_fail") or not {"pool", "depth", "disp", "mss"} <= names \
                    or not (names & {"rs", "pre"}) or not b.get("plan"):
                nb += 1
                bad.append(("brain", w["day"], b.get("focus"), b.get("first_fail"), sorted(names)))
        check(f"{k}: {len(idx) - len(bad) + nb}/{len(idx)} signals found from the bars up to the signal bar alone (same side and "
              f"stop, no trade yet); brain at the signal: no ✗, pool / depth / resweep-or-inducement / candle / swing checks + plan "
              f"({len(idx) - nb}/{len(idx)})", not bad, bad[:4])


# ------------------------------------------------------------------------------------------------ d. evening
def evening(D):
    print("d. evening hours: states and brains 18:00-02:00 ET", flush=True)
    for d in ("2026-10-14", "2026-09-17", "2026-06-10"):
        prev = dt.date.fromisoformat(d) - dt.timedelta(days=1)
        rows = []
        for now in (at(prev, 19), at(prev, 23), at(d, 1), at(d, 10)):
            r = D.poll(now)
            for k in KEYS:
                s = r["strategies"][k]
                rows.append((k, _hm(now), (s.get("state") or {}).get("stage"), bool(s.get("brain")), s.get("error")))
        ok = all(st not in (None, "error") and br and not er for _, _, st, br, er in rows)
        asia_eve = [st for k, h, st, _, _ in rows if k == "sh_asia" and h in ("19:00", "23:00", "01:00")]
        asia_day = [st for k, h, st, _, _ in rows if k == "sh_asia" and h == "10:00"]
        check(f"session {d}: 19:00 / 23:00 / 01:00 / 10:00 ET polls give a state + brain for both hunts; Asia hunt live in the evening "
              f"({', '.join(asia_eve)}), {asia_day[0]} at 10:00", ok and "off" not in asia_eve and asia_day[0] in ("off", "done", "in_trade"), rows)


def _hm(t):
    return dt.datetime.fromtimestamp(t, ET).strftime("%H:%M")


# ------------------------------------------------------------------------------------------------ e. paper only
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


def paper_only(D):
    print("e. paper only", flush=True)
    files = ["engine/stophunt.py", "tools/stophunt.py"]
    hits = {f: sorted(m for m in imports_of(os.path.join(ROOT, f)) if BAD_MOD.search(m)) for f in files}
    check("engine/stophunt.py + tools/stophunt.py import no adapter / NinjaTrader / broker module", not any(hits.values()), hits)
    raw = json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))
    S = raw["strategies"]
    check("second_model.json: sh_asia / sh_trend on, \"route\": false, candidate, $500, their research params / rules / labels",
          all(S[k].get("on") is True and S[k].get("route") is False and S[k].get("candidate") is True and S[k].get("usd") == 500
              and S[k]["params"] == json.load(open(os.path.join(ROOT, "research", "stophunt", f + ".json")))["params"]
              and S[k]["rules"] and S[k]["kind"] == "stop_hunt" for k, f in KEYS.items())
          and S["sh_asia"]["label"] == "Asia resweep hunt" and S["sh_trend"]["label"] == "Trend inducement hunt"
          and raw.get("account_b") is None, {k: {kk: S[k].get(kk) for kk in ("on", "route", "candidate", "label")} for k in KEYS})
    forced = json.loads(json.dumps(raw))
    for k in KEYS:
        forced["strategies"][k]["route"] = True
    tmp = os.path.join(ROOT, "data", "_test_second_sh.json")
    try:
        json.dump(forced, open(tmp, "w", encoding="utf-8"))
        c2 = second.load_cfg(tmp)
        json.dump(raw, open(tmp, "w", encoding="utf-8"), indent=1)
        r = second.set_route("sh_asia", True, path=tmp, selftest=lambda: (True, "ok"))
        check("a candidate is never routed: load_cfg forces \"route\" false, set_route --route sh_asia on is refused",
              not any(c2["strategies"][k]["route"] for k in KEYS) and second.routed(c2) == [] and not r["ok"] and "candidate" in r["error"], r)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    from engine import account_b as AB, second_scorecard as SC
    src = open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read()
    check("not on account B's default list, not an ATLAS member, not in the account-B scorecard pool",
          "sh_asia" not in src and "sh_trend" not in src and not set(KEYS) & set(second.ATLAS_KEYS)
          and not set(KEYS) & {m if isinstance(m, str) else (m or {}).get("key") for m in second.atlas_info().get("members") or []} and not set(KEYS) & set(SC.KEYS) and set(KEYS) <= set(SC.CANDIDATES))
    code = ("import sys, json; sys.path.insert(0, '.'); import pandas as pd; from engine import second; "
            "df = pd.read_csv('data/NQ_5m.csv'); df = df[df.time < 1768500000]; c = second.load_cfg(); "
            "c['strategies'] = {k: c['strategies'][k] for k in ('sh_asia', 'sh_trend')}; second.run(df.tail(12000), cfg=c); "
            "print(json.dumps(sorted(m for m in sys.modules if m.startswith(('engine', 'tools')))))")
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=600)
    mods = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else None
    loaded = [m for m in (mods or []) if BAD_MOD.search(m)]
    check("a fresh process that runs the two hunts loads no adapter / NinjaTrader / broker module",
          mods is not None and not loaded and "tools.stophunt" in mods, loaded or p.stderr[-400:])


# ------------------------------------------------------------------------------------------------ f. without numba
def no_numba(D):
    print("f. without numba", flush=True)
    d = "2026-01-16"
    now = at(d, 17)
    code = ("import sys, json; sys.modules['numba'] = None; sys.path.insert(0, '.'); import pandas as pd, numpy as np; "
            "from engine import second; import engine.stophunt as E; assert not hasattr(E.njit, '__module__') or 'numba' not in str(E.njit.__module__); "
            f"now = {now}; df5 = pd.read_csv('data/NQ_5m.csv'); df5 = df5[(df5.time + 300 <= now) & (df5.time >= now - 80 * 86400)]; "
            "df1 = pd.read_csv('data/NQ_1m.csv'); df1 = df1[(df1.time + 60 <= now) & (df1.time >= now - 80 * 86400)]; c = second.load_cfg(); "
            "c['strategies'] = {k: c['strategies'][k] for k in ('sh_asia', 'sh_trend')}; r = second.run(df5, one_min=df1, now=now, cfg=c); "
            "print(json.dumps({k: [[t['entry_t'], t['dir'], t['exit_kind'], t['exit_t'], round(t['r'], 3), t['qty']] for t in s['trades']] "
            "for k, s in r['strategies'].items()}))")
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=900)
    got = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else None
    r = D.poll(now)
    want = {k: [[t["entry_t"], t["dir"], t["exit_kind"], t["exit_t"], round(t["r"], 3), t["qty"]] for t in s["trades"]] for k, s in r["strategies"].items()}
    check(f"numba blocked: the {d} poll gives the same trades of the window ({sum(len(v) for v in want.values())})",
          got == want and want, (got, want) if p.returncode == 0 else p.stderr[-600:])


# ------------------------------------------------------------------------------------------------ g. scorecard + blocks
def scorecard(D):
    print("g. scorecard bands + dashboard / compact blocks", flush=True)
    from engine import second_scorecard as SC
    d = SC.load()
    for k, f in KEYS.items():
        T = json.load(open(os.path.join(ROOT, "research", "stophunt", f + ".json"), encoding="utf-8"))["trades"]
        n2 = sum(1 for t in T if "2026-07-01" <= t["day"] <= "2026-12-31")
        n5 = sum(1 for t in T if "2025-01-01" <= t["day"] <= "2025-12-31")
        b = (d or {}).get("bands", {}).get(k) or {}
        check(f"{k}: scorecard bands pool its 2026 H2 ({n2}) and 2025 ({n5}) research trades",
              (b.get("expected") or {}).get("n_pool") == n2 and (b.get("bad_year") or {}).get("n_pool") == n5,
              (b.get("expected") or {}).get("n_pool"))
    nb = d["bands"][SC.ACCT_B]["expected"]["n_pool"]
    check("the account-B band still pools only EMA + MACD + S/R", nb == sum(d["bands"][k]["expected"]["n_pool"] for k in SC.KEYS), nb)
    r = D.poll(at("2026-01-07", 17))
    st = second.ledger_update(None, r, at("2026-01-06", 17))
    blk = second.dashboard_block(st)
    sc = {s["key"]: s for s in blk["strategies"]}
    ok = all(sc[k]["candidate"] and sc[k].get("scorecard") and sc[k]["backtest"]["own"].get("H2") and sc[k]["backtest"]["own"].get("2026")
             and (sc[k]["backtest"].get("atlas_eval") or {}).get("atlas_plus", {}).get("H2") and sc[k]["rules"] and sc[k]["brain"] for k in KEYS)
    check("dashboard block: both hunts flagged candidate, with scorecard, research numbers (H1 / H2 / 2026 / 2025 / 2021-24), "
          "ATLAS 25K eval paths, rules and brain", ok, {k: (sc[k].get("candidate"), bool(sc[k].get("scorecard")), list(sc[k]["backtest"]["own"]),
                                                          sc[k]["backtest"].get("error")) for k in KEYS})
    cp = second.compact(r)
    led = [v for v in ((st["strategies"].get("sh_asia") or {}).get("ledger") or {}).values()]
    check("compact (heartbeat / live.json) carries both hunts with candidate + brain; the cloud ledger records the paper trade",
          all(cp["strategies"][k].get("candidate") and cp["strategies"][k].get("brain") for k in KEYS) and led
          and len(json.dumps(cp)) < 40000, (len(json.dumps(cp)), len(led)))
    lines = "\n".join(second.readme_lines(st))
    check("README section lists both hunts as candidate ATLAS members", "Asia resweep hunt" in lines and "candidate ATLAS member" in lines)


def main():
    quick = "--quick" in sys.argv
    nd = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--intraday=")), 4)
    t0 = time.time()
    D = Data()
    out = day_end(D)
    if not quick:
        intraday(D, nd)
        lookahead(D)
    evening(D)
    paper_only(D)
    if not quick:
        no_numba(D)
    scorecard(D)
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} checks passed ({time.time() - t0:.0f}s): replay " +
          ", ".join(f"{k} {a}/{b}" for k, (a, b) in out.items()))
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
