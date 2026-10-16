"""Build the historical high-impact US event calendar used by backtests: data/news/events.csv

Sources
  CPI, Employment Situation (NFP), PPI release dates: bls.gov release archives
      https://www.bls.gov/bls/news-release/cpi.htm | empsit.htm | ppi.htm   (all released 08:30 ET)
  FOMC decisions: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm  (statement 14:00 ET, presser 14:30 ET)
Optional: data/news/user_events.csv (date,time_et,event[,impact]) is merged in (e.g. a calendar you exported elsewhere).
python build_news.py
"""
import os
import re
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "news")
os.makedirs(OUT_DIR, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

# release dates read from the BLS archive pages (Oct 2023 -> Oct 2026); 2025 dates reflect the shutdown delays
CPI = """2023-10-12 2023-11-14 2023-12-12 2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11
2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11
2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18 2026-01-13 2026-02-13 2026-03-11 2026-04-10 2026-05-12 2026-06-10
2026-07-14 2026-08-12 2026-09-11""".split()
NFP = """2023-10-06 2023-11-03 2023-12-08 2024-01-05 2024-02-02 2024-03-08 2024-04-05 2024-05-03 2024-06-07 2024-07-05
2024-08-02 2024-09-06 2024-10-04 2024-11-01 2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06
2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16 2026-01-09 2026-02-11 2026-03-06 2026-04-03 2026-05-08 2026-06-05
2026-07-02 2026-08-07 2026-09-04 2026-10-02""".split()
PPI = """2023-10-11 2023-11-15 2023-12-13 2024-01-12 2024-02-16 2024-03-14 2024-04-11 2024-05-14 2024-06-13 2024-07-12
2024-08-13 2024-09-12 2024-10-11 2024-11-14 2024-12-12 2025-01-14 2025-02-13 2025-03-13 2025-04-11 2025-05-15 2025-06-12
2025-07-16 2025-08-14 2025-09-10 2025-11-25 2026-01-14 2026-01-30 2026-02-27 2026-03-18 2026-04-14 2026-05-13 2026-06-11
2026-07-15 2026-08-13 2026-09-10""".split()

MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}
ABBR = {m[:3]: i for m, i in MONTHS.items()}


def fomc_dates():
    html = urllib.request.urlopen(urllib.request.Request(
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", headers=UA), timeout=30).read().decode("utf-8", "ignore")
    out = []
    parts = re.split(r"(\d{4}) FOMC Meetings", html)
    for k in range(1, len(parts) - 1, 2):
        year, body = int(parts[k]), parts[k + 1]
        for mon, day in re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', body, re.S):
            mon, day = mon.strip(), day.strip()
            if "notation" in day.lower() or "unscheduled" in day.lower() or "cancel" in day.lower():
                continue
            nums = re.findall(r"\d+", day)
            if not nums:
                continue
            last_mon = mon.split("/")[-1]
            m = MONTHS.get(last_mon) or ABBR.get(last_mon[:3])
            if not m:
                continue
            sep = "*" in day
            out.append((f"{year}-{m:02d}-{int(nums[-1]):02d}", sep))
    return sorted(set(out))


def main():
    rows = []
    rows += [(d, "08:30", "CPI (consumer inflation)", "high", "bls.gov") for d in CPI]
    rows += [(d, "08:30", "Non-Farm Payrolls (jobs report)", "high", "bls.gov") for d in NFP]
    rows += [(d, "08:30", "PPI (producer inflation)", "medium", "bls.gov") for d in PPI]
    try:
        for d, sep in fomc_dates():
            rows.append((d, "14:00", "FOMC rate decision" + (" + projections" if sep else ""), "high", "federalreserve.gov"))
            rows.append((d, "14:30", "FOMC press conference", "high", "federalreserve.gov"))
    except Exception as e:
        print("FOMC fetch failed:", e)
    df = pd.DataFrame(rows, columns=["date", "time_et", "event", "impact", "source"])
    user = os.path.join(OUT_DIR, "user_events.csv")
    if os.path.exists(user):
        u = pd.read_csv(user)
        u.columns = [c.strip().lower() for c in u.columns]
        u["impact"] = u.get("impact", "high")
        u["source"] = "user_events.csv"
        u["time_et"] = u["time_et"].astype(str).str.slice(0, 5)
        df = pd.concat([df, u[["date", "time_et", "event", "impact", "source"]]])
    df = df.drop_duplicates(["date", "time_et", "event"]).sort_values(["date", "time_et"])
    df.to_csv(os.path.join(OUT_DIR, "events.csv"), index=False)
    print(f"{len(df)} events  {df.date.min()} -> {df.date.max()}")
    print(df.groupby("event").size().to_string())


if __name__ == "__main__":
    main()
