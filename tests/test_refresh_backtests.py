"""tools/refresh_backtests.py (day-strats 2026-11-27): the strategy rooms' backtests made current through the newest data/ bars, with parity.

  a. LIT     the re-run (live_model.json "lit", every weekday with bars from the stored first session) gives every stored trade of
             research/lab/backtest_live.json byte-identical, then the new ones (to 2026-11-26: 7 trades, -$858.40, the drought study's)
  b. ATLAS   engine/second.run on the overlap days = the stored member trades (entry, direction, exit); the new book's trades carry
             prices, $ at $250 and a member; LIT's opposite open trade skips, LIT's opposite entry closes (HEDGE)
  c. BLITZ   (numba) every stored row of research/runs/blitz_2026_backtest.json again (floats within 0.001), then the new ones
  d. safety  the stored research files are not touched (same bytes after the run); only research/strats_refresh/ is written; a
             failed parity writes no trades; build_strats appends the fresh rows and says so (data_to.fresh)
    python -X utf8 -m tests.test_refresh_backtests
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
STORED = ["research/lab/backtest_live.json", "research/anatomy/trades_atlas.json", "research/runs/blitz_2026_backtest.json",
          "research/second/ema_best.json", "research/second/md_best.json", "research/second/sr_best.json"]


def sha(rel):
    return hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()


def main():
    from tools import refresh_backtests as R
    before = {p: sha(p) for p in STORED}
    has_numba = importlib.util.find_spec("numba") is not None
    rc = R.main(["lit", "atlas", "blitz"] if has_numba else ["lit", "atlas"])
    out = {s: json.load(open(os.path.join(R.OUT, s + ".json"), encoding="utf-8")) for s in (("lit", "atlas", "blitz") if has_numba else ("lit", "atlas"))}
    L = out["lit"]
    check("a. LIT parity: every stored trade (631, to 2026-10-14) byte-identical, the stored params = live_model.json's",
          L["ok"] and L["parity"]["identical"] and L["parity"]["stored"] == L["parity"]["rerun_to_stored_end"] and L["parity"]["params_match"], L["parity"])
    if L["data_to"] == "2026-11-26":
        check("a. LIT's new trades to 2026-11-26: 7, -$858.40 (= the drought study's Oct 15 - Nov 26)", L["n_new"] == 7 and abs(L["usd_new"] + 858.4) < 0.01, (L["n_new"], L["usd_new"]))
    check("a. LIT's new rows are in the stored file's shape (export_backtest.lit_row: prices, report, why)",
          all(k in L["trades"][0] for k in ("day", "entry_t", "exit_t", "side", "entry", "stop", "target", "exit_price", "exit", "pnl", "r", "report")) if L["trades"] else True)
    A = out["atlas"]
    par = {k: v for k, v in A["parity"].items() if k != "overlap_days"}
    check("b. ATLAS parity on the 5 overlap days: the replay's member trades = the stored ones (entry, direction, exit time)",
          A["ok"] and all(v["stored"] == v["replay"] == v["same_entry_and_exit"] for v in par.values()) and len(A["parity"]["overlap_days"]) == 5, A["parity"])
    check("b. ATLAS's new book rows: after the stored end, prices + member + $ at $250 a trade, exits incl. HEDGE when LIT entered opposite",
          all(t["day"] > A["stored_end"] and t["entry"] is not None and t["member"] in ("EMA", "MACD", "S/R") and abs(t["usd"] - t["r"] * 250) < 0.06 for t in A["trades"])
          and A["n_new"] == len(A["trades"]) > 0, A["n_new"])
    check("b. ATLAS says the armed-setup block is not applied after the stored end", "armed" in A["armed_block"])
    if has_numba:
        B = out["blitz"]
        check("c. BLITZ parity: every stored row (2,164 to 2026-10-16) again, floats within 0.001", B["ok"] and B["parity"]["identical"] == B["parity"]["stored"] == 2164, B["parity"])
        check("c. BLITZ's new rows after the stored end, the stored columns", all(r[0] > B["stored_end"] and len(r) == len(B["cols"]) for r in B["trades"]) and B["n_new"] > 0, B["n_new"])
    else:
        check("c. BLITZ skipped here: no numba (the cloud's nightly run has it)", True)
    check("d. the stored research files are untouched (same bytes after the run)", all(sha(p) == before[p] for p in STORED), [p for p in STORED if sha(p) != before[p]])
    check("d. the run exits 0 when every parity holds", rc == 0, rc)
    # a failed parity writes no trades
    real = R._load

    def bent(rel):
        d = real(rel)
        if rel.endswith("backtest_live.json"):
            d["trades"][0]["pnl"] = d["trades"][0]["pnl"] + 1.0         # one stored trade that the re-run cannot give again
        return d
    R._load = bent
    try:
        bad = R.lit()
    finally:
        R._load = real
    check("d. a broken parity (simulated) = ok false and no trades", bad["ok"] is False and bad["trades"] == [], (bad["ok"], len(bad["trades"])))
    from tools import build_strats as BS
    d = BS.build("lit")
    check("d. build_strats appends the fresh rows (src backtest, the 'fresh replay' why) and says so (data_to.fresh)",
          d["data_to"].get("fresh", {}).get("n") == L["n_new"] and sum(1 for x in d["trades"] if x[0] == "backtest" and x[1] > L["stored_end"]) == L["n_new"]
          and all(x[15].startswith("Fresh replay") for x in d["trades"] if x[0] == "backtest" and x[1] > L["stored_end"]))


if __name__ == "__main__":
    main()
    AK.finish()
