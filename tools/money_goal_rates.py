"""The $ a month per funded account type for the "Road to $10K / Z06" card (engine/money_goal.py), read from the stored
research files and written to research/second/money_goal_rates.json (the cloud's sparse checkout has research/second/*.json,
not research/lit/*.json, so the card reads this small copy; tests/test_money_goal.py checks it still equals the sources).

Every number is the H2 2026 (Jul-Oct, the check half) rate for a FUNDED account at the live funded sizing, $ a month to the
owner after the firm's split, net of fees (one-time evals, $0 activation: nothing recurring). H1 and a bad-year reference
(2021-25 / 2021-24) ride along for the honest line.

  lit_b50    MFFU Builder 50K, Zlarior    research/lit/uprisk_wincap.json  builder50k.cap1500_p60_mw2000 (the live funded preset:
                                          60% of the room, <= $1,500, a winner <= $2,000; research/writeups/uprisk.md)
  atlas_b25  MFFU Builder 25K, ATLAS      research/second/atlas_funded.json configs.live (research/writeups/atlas-funded.md)
  lit_l50    LucidPro 50K, Zlarior        research/lit/funded_combo.json t15_be_off lucid_pro_50k funded (= the live LIT without
                                          scale-in; funded 60% / <= $800 / winner <= $1,500 = engine/multi_account preset)
  lit_fn50   FundedNext Rapid Daily 50K   research/lit/funded_combo.json t15_be_off fn_rapid_daily_50k funded (40% / <= $800)

    python -X utf8 tools/money_goal_rates.py          rebuild the file (after one of the studies above is re-run)
    python -X utf8 tools/money_goal_rates.py --check  compare the file with the sources (exit 1 when they differ)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "second", "money_goal_rates.json")
WINCAP = os.path.join(ROOT, "research", "lit", "uprisk_wincap.json")
ATLAS = os.path.join(ROOT, "research", "second", "atlas_funded.json")
COMBO = os.path.join(ROOT, "research", "lit", "funded_combo.json")


def _j(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def build() -> dict:
    """-> the rates block from the four stored studies (raises when a source is missing: run it on the PC / a full checkout)."""
    w = _j(WINCAP)["wincap"]["builder50k"]["cap1500_p60_mw2000"]
    at = _j(ATLAS)["configs"]["live"]
    plans = {p["id"]: p["results"]["funded"] for p in _j(COMBO)["t15_be_off"]["plans"]}
    lu, fn = plans["lucid_pro_50k"], plans["fn_rapid_daily_50k"]
    return {
        "v": 1, "built": dt.date.today().isoformat(), "span": "H2",
        "what": "$ a month to you per FUNDED account, 2026 Jul-Oct (H2, the check half), live funded sizing, after the firm's split, "
                "net of fees (one-time evals, $0 activation). Not a promise: 2026 is one good year; ref = 2021-25 / 2021-24.",
        "types": {
            "lit_b50": {"usd_month": w["H2"]["per_month"], "usd_month_h1": w["H1"]["per_month"], "usd_month_ref": w["REF"]["per_month"],
                        "ref_span": "2021-25", "src": "research/lit/uprisk_wincap.json builder50k.cap1500_p60_mw2000",
                        "writeup": "research/writeups/uprisk.md"},
            "atlas_b25": {"usd_month": at["H2"]["per_month"], "usd_month_h1": at["H1"]["per_month"], "usd_month_ref": at["2021-24"]["per_month"],
                          "ref_span": "2021-24", "src": "research/second/atlas_funded.json configs.live",
                          "writeup": "research/writeups/atlas-funded.md"},
            "lit_l50": {"usd_month": lu["H2"]["net_per_month"], "usd_month_h1": lu["H1"]["net_per_month"],
                        "usd_month_ref": lu["2021-25"]["net_per_month"], "ref_span": "2021-25",
                        "src": "research/lit/funded_combo.json t15_be_off lucid_pro_50k funded", "writeup": "research/writeups/lit-funded-combo.md"},
            "lit_fn50": {"usd_month": fn["H2"]["net_per_month"], "usd_month_h1": fn["H1"]["net_per_month"],
                         "usd_month_ref": fn["2021-25"]["net_per_month"], "ref_span": "2021-25",
                         "src": "research/lit/funded_combo.json t15_be_off fn_rapid_daily_50k funded", "writeup": "research/writeups/lit-funded-combo.md"},
        },
    }


def same(a: dict, b: dict) -> bool:
    """The stored file equals a fresh build (the build day aside)."""
    return {k: v for k, v in (a or {}).items() if k != "built"} == {k: v for k, v in (b or {}).items() if k != "built"}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    new = build()
    if "--check" in argv:
        try:
            old = _j(OUT)
        except Exception:
            old = None
        ok = same(old, new)
        print("money_goal_rates.json matches the sources" if ok else "money_goal_rates.json differs from the sources: rebuild it")
        return 0 if ok else 1
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(new, fh, indent=1)
        fh.write("\n")
    print("wrote", os.path.relpath(OUT, ROOT), {k: v["usd_month"] for k, v in new["types"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
