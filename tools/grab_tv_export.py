"""Copy the newest TradingView 'Download chart data' file from Downloads into data/tv_exports/<name>.csv and print its range.
Usage: python tools/grab_tv_export.py NQ1_5m_chunk_2026-08-24
"""
import glob
import os
import shutil
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DL = os.path.join(os.path.expanduser("~"), "Downloads")

name = sys.argv[1]
time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 3)
files = [f for f in glob.glob(os.path.join(DL, "*")) if os.path.isfile(f) and f.lower().endswith((".csv", ".tmp"))]
newest = max(files, key=os.path.getmtime)
age = time.time() - os.path.getmtime(newest)
if age > 60:
    sys.exit(f"{name}: STALE - newest download is {age:.0f}s old, the export did not happen; nothing copied")
dst = os.path.join(HERE, "data", "tv_exports", name + ".csv")
os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copy2(newest, dst)
d = pd.read_csv(dst)
t = pd.to_datetime(d["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
vol = "Volume" in d.columns
print(f"{name}: {len(d)} bars {t.min():%Y-%m-%d %H:%M} -> {t.max():%Y-%m-%d %H:%M} ET | volume={vol} | src age {age:.0f}s")
