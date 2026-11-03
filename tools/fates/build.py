"""FATES build: the Monte Carlo of the owner's evals and money -> tools/web_public/fates/fates.json + jarvis.json.

    python -X utf8 -m tools.fates.build                       # full build (1,000 futures a scenario, 400 drawn as threads)
    python -X utf8 -m tools.fates.build --n 200 --threads 80 --out <dir> --live <saved live.json> --no-fetch

Scenarios (each on the 2026 sample and the 2021-25 sample; the Jul-Oct 2026 check as numbers only):
  eval:zlarior   this eval of Zlarior (LIT) on the MFFU Builder 50K, from today's live state
  eval:atlas     this eval of ATLAS on the MFFU Builder 25K, from today's live state
  money          6 account slots on the same futures (tools/rd_money.py's plan, research/writeups/2026-11-03-money-plan.md):
                 1 Zlarior 50K (today's eval), 2 ATLAS 25K (today's eval), 3 Zlarior on the free MFFU 25K ($63, a week
                 later), 4-6 Zlarior copies on other firms' 50Ks (MFFU 50K rules as the proxy, $130 an eval), a week apart.
                 A book of N accounts = the first N slots.
Deterministic: the seed fixes every future. Paper only: reads the replays and the live feed, writes the two JSON files.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.fates import export as EX  # noqa: E402
from tools.fates import live as LV  # noqa: E402
from tools.fates import sim as SI  # noqa: E402
from tools.fates import sources as SO  # noqa: E402
from tools.fates.rules import load_rules  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public", "fates")
SEED = 23
EVAL_H = 60                    # sessions simulated for this eval (about 3 months)
MONEY_H = 252                  # 12 months
GOAL = 10_000.0                # the money page's "Road to $10K"
OTHER_FIRM_50K = 130.0         # LucidPro / FundedNext 50K eval, the money plan's price
PERIODS_THREADS = ("2026", "2021-25")
PERIODS_ALL = ("2026", "2021-25", "H2")


def start_of(b: dict) -> SI.Start:
    last = SO.as_date(b["last_trade"]) if b.get("last_trade") else None
    return SI.Start(profit=b["profit"], peak=b["peak"], floor=b["floor"], session=int(b["session"]),
                    days_traded=1 if b["session"] > 0 else 0, last_trade=last)


def slots_for(lit50, lit25, atlas, live) -> list[SI.Slot]:
    R50, R25 = load_rules("builder50k"), load_rules("builder25k")
    other = dataclasses.replace(R50, name="Other firm 50K (MFFU 50K rules as the proxy)", price=OTHER_FIRM_50K)
    return [SI.Slot(lit50, R50, "Zlarior · MFFU 50K", start=start_of(live["bots"]["zlarior"])),
            SI.Slot(atlas, R25, "ATLAS · MFFU 25K", start=start_of(live["bots"]["atlas"])),
            SI.Slot(lit25, R25, "Zlarior · MFFU 25K #2", offset=5),
            SI.Slot(lit50, other, "Zlarior · 50K firm #1", offset=10),
            SI.Slot(lit50, other, "Zlarior · 50K firm #2", offset=15),
            SI.Slot(lit50, other, "Zlarior · 50K firm #3", offset=20)]


def build(n: int = 1000, n_threads: int = 400, seed: int = SEED, live_path: str | None = None, fetch: bool = True,
          periods=PERIODS_ALL, log=print) -> dict:
    t0 = time.time()
    live = LV.read_live(live_path, LV.LIVE_URL if fetch else None)
    lit50, lit25, atlas = SO.LitSource("builder50k"), SO.LitSource("builder25k"), SO.AtlasSource()
    S = lit50.sessions()
    cal = LV.calendar(SO.as_date(live["first_session"]), MONEY_H)
    slots = slots_for(lit50, lit25, atlas, live)
    doc = {"v": 1, "app": "fates", "built": dt.datetime.now().isoformat(timespec="seconds"), "t": int(time.time()), "seed": seed,
           "paths": n, "threads": n_threads, "today": cal[0].isoformat(), "live": live,
           "calendar": [d.isoformat() for d in cal], "periods": {}, "scenarios": {},
           "replay": lit50.check_against_replay(),
           "notes": ["Futures = real market days of the sample drawn a week (5 sessions) at a time; each bot sized by its live rules.",
                     "MFFU rules: end-of-day trailing floor (open losses count), soft daily loss, target, 7 quiet days close the "
                     "account (the owner's 1-MNQ keep-alive on quiet day 6 is assumed; without it see no_keepalive).",
                     "The 2021-25 sample is LIT's untuned past: a much weaker edge. Quote 2026 with that warning.",
                     "Money: $ to the owner (80% of payouts) net of every eval bought; today's two evals are already paid.",
                     "Paper only: nothing here trades or changes a live setting."]}
    for pi, per in enumerate(periods):
        D = SO.period_dates(S, per)
        a, z, label = SO.PERIODS[per]
        doc["periods"][per] = {"label": label, "from": D[0], "to": D[-1], "days": len(D)}
        ps = seed + 1000 * pi
        PE = SI.bootstrap(len(D), n, EVAL_H, seed=ps)
        PM = SI.bootstrap(len(D), n, MONEY_H, seed=ps + 1)
        log(f"[{per}] {len(D)} real days; money futures ...")
        R = SI.run_money(slots, D, PM, cal)
        log(f"[{per}] money done ({time.time() - t0:.0f}s)")
        if per in PERIODS_THREADS:
            doc["scenarios"][f"money:{per}"] = EX.money_block(per, slots, R, cal, GOAL, n_threads)
        else:
            doc["scenarios"][f"money:{per}"] = {"kind": "money", "period": per, "horizon": MONEY_H, "goal": GOAL, "summary_only": True,
                                                "slots": [{"label": s.label} for s in slots],
                                                "books": {str(k): SI.money_summary(R, list(range(k)), cal, GOAL) for k in range(1, len(slots) + 1)}}
        for j, (src, key) in enumerate(((lit50, "zlarior"), (atlas, "atlas"))):
            R_ = slots[j].rules
            st = start_of(live["bots"][key])
            res = SI.run_eval(src, R_, st, D, PE, cal)
            res["cal"] = cal
            noka = SI.run_eval(src, R_, st, D, PE, cal, keepalive=False)
            fresh_r = SI.run_eval(src, R_, SI.Start(last_trade=cal[0]), D, PE, cal)
            fresh = {k: v for k, v in SI.eval_summary(fresh_r, SI.Start(), R_, cal).items() if k != "pass_hist"}
            block = EX.eval_block(src, per, R_, st, live["bots"][key], res, noka, fresh, EX.single_money(R, j, cal, GOAL),
                                  n_threads if per in PERIODS_THREADS else 0, EVAL_H)
            if per not in PERIODS_THREADS:
                block.pop("bands")
                block["threads"] = {"o": "", "b": []}
                block["summary_only"] = True
            doc["scenarios"][f"eval:{key}:{per}"] = block
            s = block["summary"]
            log(f"[{per}] {src.name}: pass {s['pass']}% fail {s['fail']}% open {s['open']}% p10/f10 {s['p10']}/{s['f10']} "
                f"median {s['pass_med']} sessions; fresh p10/f10 {fresh['p10']}/{fresh['f10']}")
    doc["headline"] = EX.headline(doc)
    doc["build_seconds"] = round(time.time() - t0)
    return doc


def write(doc: dict, out_dir: str = WEB, name: str = "fates.json", jarvis: bool = True) -> int:
    os.makedirs(out_dir, exist_ok=True)
    bad = EX.validate(doc)
    if bad:
        raise SystemExit("FATES JSON failed its checks: " + "; ".join(bad))
    size = EX.dump(doc, os.path.join(out_dir, name))
    if jarvis:
        with open(os.path.join(out_dir, "jarvis.json"), "w", encoding="utf-8") as fh:
            json.dump(EX.jarvis_card(doc), fh, separators=(",", ":"))
    return size


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--threads", type=int, default=400)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=WEB)
    ap.add_argument("--name", default="fates.json")
    ap.add_argument("--live", default=None, help="a saved live.json instead of the published feed")
    ap.add_argument("--no-fetch", action="store_true", help="never fetch the feed (fallback numbers unless --live)")
    ap.add_argument("--no-jarvis", action="store_true")
    a = ap.parse_args(argv)
    doc = build(a.n, a.threads, a.seed, a.live, not a.no_fetch)
    size = write(doc, a.out, a.name, not a.no_jarvis)
    print(f"-> {os.path.join(a.out, a.name)} ({size / 1e3:.0f} KB, {doc['build_seconds']}s)")


if __name__ == "__main__":
    main()
