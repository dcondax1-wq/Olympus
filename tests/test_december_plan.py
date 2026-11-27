"""December money plan (tools/december_plan.py -> tools/web_public/nq/december.json + docs/DECEMBER_PLAN.md). Offline, no network.

  a. calendar: Dec 2026 = 22 sessions (21 full + Thu 12-24 half day halt 13:15), Fri 12-25 closed, Thu 12-31 full day
  b. roll Thu 12-10 (MNQ 12-26 -> 03-27) flagged on that day only; CPI the same morning
  c. news: NFP 12-04, FOMC 12-09 (+ press), CPI 12-10, FOMC minutes 12-30 = high with a LIT flat time 5 min before; PPI no pause
  d. forecast view: by-month-end % read from pass_cum / payout_cum at the right session; median day mapped through closures
  e. k7: Christmas squeeze line (last trade Mon 12-21 -> only Thu 12-24 left); offline falls back to the last file's rows
  f. public-safe: no account number fields (l4) in the JSON; markdown builds; paper_only
    python -X utf8 -m tests.test_december_plan
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import december_plan as D  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        FAILS.append(name)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        old = D.OUT, D.FORECAST, D.FORECAST_CUM
        D.FORECAST_CUM = os.path.join(tmp, "none.json")
        D.OUT, D.FORECAST = os.path.join(tmp, "dec.json"), os.path.join(tmp, "fc.json")
        cum = [min(100.0, 3.0 * k) for k in range(1, 41)]
        json.dump({"made": "2026-11-26 18:10 UTC", "engine": "test", "accounts": {
            "fresh25": {"stage": "eval", "state": {"profit": 19.0, "room": 996.0},
                        "2026-like": {"pass_cum": cum, "fail_cum": [1.0] * 40, "pass_med_sessions": 10, "pass_pct": 80, "fail_pct": 10},
                        "2021-25-like": {"pass_cum": [0.0] * 40, "fail_cum": [0.0] * 40}},
            "atlas": {"stage": "funded", "state": {"profit": 401.0, "room": 1000.0},
                      "2026-like": {"payout_cum": cum, "first_payout_med_sessions": 23}, "2021-25-like": {"payout_cum": [0.0] * 40}}}},
                  open(D.FORECAST, "w"))
        json.dump({"k7_src_rows": [{"id": "atlas", "nm": "ATLAS 25K funded", "lf": "2026-11-25", "dl": "2026-12-01", "hard": "2026-12-02",
                                    "on": True, "l4": "9999"}]}, open(D.OUT, "w"))
        doc = D.build("2026-12", offline=True, today=dt.date(2026, 11, 27))
        D.OUT, D.FORECAST, D.FORECAST_CUM = old
    days = {r["day"]: r for r in doc["days"]}
    s = doc["summary"]
    check("a 22 sessions, 21 full + 1 half", s["sessions"] == 22 and s["full_days"] == 21 and s["half_days"] == 1, s)
    check("a 12-24 half day 13:15, 12-25 closed, 12-31 open", days["2026-12-24"]["halt"] == "13:15" and days["2026-12-25"]["market"] == "closed"
          and days["2026-12-31"]["market"] == "open")
    check("a 12-24 entry cut 13:00 / flat 13:10", "13:00" in days["2026-12-24"]["bots"] and "13:10" in days["2026-12-24"]["bots"], days["2026-12-24"]["bots"])
    check("b roll 12-10 only", [d for d, r in days.items() if r["roll"]] == ["2026-12-10"] and "03-27" in days["2026-12-10"]["bots"])
    hi = s["news_high"]
    check("c high news list", any("2026-12-04 08:30" in x for x in hi) and any("2026-12-09 14:00" in x for x in hi)
          and any("2026-12-10 08:30" in x for x in hi) and any("2026-12-30 14:00" in x for x in hi), hi)
    check("c LIT flat 5 min before NFP", "LIT flat by 08:25" in days["2026-12-04"]["bots"], days["2026-12-04"]["bots"])
    check("c PPI no pause", "no pause" in days["2026-12-15"]["bots"], days["2026-12-15"]["bots"])
    acc = {a["key"]: a for a in doc["accounts"]}
    S = D.sessions(dt.date(2026, 11, 27), 40)
    k_end = sum(1 for d in S if d <= dt.date(2026, 12, 31))
    check("d sessions 11-27..12-31 = 24 (Fri 11-27, Mon 11-30 + 22)", k_end == 24, k_end)
    check("d pass by Dec 31 = pass_cum[k_end-1]", acc["fresh25"]["2026-like"]["pass_by_month_end_pct"] == min(100.0, 3.0 * k_end))
    check("d median pass day = session 10 = Thu Dec 10", acc["fresh25"]["2026-like"]["median_pass_day"] == "2026-12-10",
          acc["fresh25"]["2026-like"]["median_pass_day"])
    check("d ATLAS payout median day = session 23 = Wed Dec 30", doc["atlas_payout"]["forecast_median_day"] == "2026-12-30",
          doc["atlas_payout"]["forecast_median_day"])
    check("d ATLAS: $949 to the MFFU minimum, $1,699 to the $1,000 goal", "$949" in doc["atlas_payout"]["min_route"]
          and "$1,699" in doc["atlas_payout"]["goal_route"])
    check("e Christmas squeeze: only 12-24 left", "2026-12-24" in doc["k7"]["christmas_squeeze"], doc["k7"].get("christmas_squeeze"))
    check("e offline k7 rows from the last file", doc["k7"]["accounts"][0]["safe_by"] == "2026-12-01" and doc["k7_src"] == "last december.json")
    txt = json.dumps(doc)
    check("f no account number field (l4) anywhere, even when the source row had one", '"l4"' not in txt and "9999" not in txt)
    md = D.markdown(doc)
    check("f markdown builds + paper_only", doc["paper_only"] and "# December 2026 money plan" in md and "Christmas" in md and len(txt) > 1000)
    check("d forecast run 18:10 UTC 11-26 (13:10 ET, Thanksgiving already halted) -> session 1 = 11-27", D.first_session("2026-11-26 18:10 UTC") == dt.date(2026, 11, 27))
    check("d forecast run 05:35 UTC 11-27 (00:35 ET) -> session 1 = 11-27", D.first_session("2026-11-27 05:35 UTC") == dt.date(2026, 11, 27))
    check("d forecast run 22:00 UTC 11-27 (17:00 ET, over) -> Mon 11-30", D.first_session("2026-11-27 22:00 UTC") == dt.date(2026, 11, 30))
    print(f"\ndecember_plan: {'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
