"""Phone screenshots (390 x 844, 2x) of the K8 day dashboard (day-kalshi 2026-11-20), made by the test harness tests/kalshi_k8_dash.cjs on
its sample PC cards + the test fixture tests/fixtures/k8_plan_sample.json (NOT real numbers):
  kalshi-k8-paper.png   the Kalshi page's K8 card, paper, Mon 11-23 05:20 ET, edge health from Kalshi's results (no own bets yet)
  kalshi-k8-live.png    the same card LIVE with a bet log (Mon 11-23 05:20 ET, gold DOWN "now")
  dionysus-k8.png       the Dionysus desk's "K8 today" panel
Run under the browser lock:  flock -w 2400 /tmp/olympus_browser.lock python research/kalshi_k8_day/shots.py
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "research", "handoff", "2026-11-20", "kalshi")

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "tests.test_kalshi_k8_dash"], cwd=ROOT, env={**os.environ, "K8_SHOTS": OUT})
    print("shots in", OUT, sorted(f for f in os.listdir(OUT) if f.endswith(".png")))
    sys.exit(r.returncode)
