"""Order latency chain of the PC bot: where the seconds go from the bar close to the order line (big-execution 2026-11-26).
Research only: the real engine.live.LiveBot in research/speed/replay_harness.py (paper adapter, frozen clock, LE_BarFeed-
format files that grow bar by bar), with LIT and ATLAS (account B). Every order the bot hands its adapter is stamped with
the wall time since its poll started; ATLAS's own model run (engine.second.run at the 5m open) is timed.

    python -X utf8 research/latency/chain.py --days 2026-11-06,2026-11-17,2026-11-18 [--offset 2.0] [--out f.json]
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "speed"))

import replay_harness as RH  # noqa: E402

REC = {"poll0": None, "poll_t": None, "sends": [], "second_runs": []}


def install():
    from engine import live, second
    orig_poll = live.LiveBot.poll_once

    def poll_once(self, *a, **k):
        REC["poll0"], REC["poll_t"] = time.perf_counter(), float(self.clock())
        return orig_poll(self, *a, **k)
    live.LiveBot.poll_once = poll_once
    orig_send = live.PaperAdapter.send

    def send(self, action):
        who = "LIT"
        for fr in inspect.stack()[1:8]:
            if fr.filename.endswith("account_b.py"):
                who = "ATLAS"
                break
            if fr.filename.endswith("multi_account.py"):
                who = "LIT extra"
                break
        if REC["poll0"] is not None and action.get("side") in ("buy", "sell"):
            REC["sends"].append({"who": who, "poll_t": REC["poll_t"], "entry_t": action.get("entry_t"),
                                 "ms_in_poll": round((time.perf_counter() - REC["poll0"]) * 1000, 1), "side": action.get("side")})
        return orig_send(self, action)
    live.PaperAdapter.send = send
    orig_run = second.run

    def run(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig_run(*a, **k)
        finally:
            if any(fr.function == "entry" and fr.filename.endswith("account_b.py") for fr in inspect.stack()[1:4]):
                REC["second_runs"].append(round((time.perf_counter() - t0) * 1000, 1))
    second.run = run


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", default="2026-11-06,2026-11-17,2026-11-18")
    ap.add_argument("--offset", type=float, default=2.0)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    install()
    extra = {"account_b": {"account": "SimATLAS", "plan": "builder25k", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"],
                           "sizing": "need", "eval_start": "2026-11-02"}}
    res = RH.run(a.days.split(","), offset=a.offset, cfg_extra=extra)
    s = RH.summary(res)
    rows = res["rows"]
    five = [r for r in rows if int(r["t"]) % 300 == int(a.offset)]           # polls right after a 5m close
    stage_b = [r["stages"].get("ATLAS (account B)") for r in five if r["stages"].get("ATLAS (account B)") is not None]
    out = {"days": res["days"], "offset_s": a.offset, "polls": s["polls"], "errors": res["n_errors"],
           "poll_wall_median_ms": s["wall_median_ms"], "poll_wall_p90_ms": s["wall_p90_ms"],
           "poll_wall_5m_median_ms": statistics.median([r["wall_ms"] for r in five]) if five else None,
           "atlas_stage_5m_median_ms": statistics.median(stage_b) if stage_b else None,
           "atlas_model_run_ms": REC["second_runs"], "sends": REC["sends"],
           "ledger_atlas": res.get("ledger_atlas"), "ledger": res.get("ledger"),
           "stages_5m": sorted(((k, statistics.median([r["stages"][k] for r in five if k in r["stages"]]))
                                for k in {k for r in five for k in r["stages"]}), key=lambda x: -x[1])[:15]}
    print(json.dumps({k: v for k, v in out.items() if k not in ("ledger", "ledger_atlas")}, indent=1)[:4000])
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
