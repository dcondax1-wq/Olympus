"""python -m tools.datacity [--full] [--heartbeat] [--no-web] [--no-run] [--fixture] [--out DIR]"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.datacity import learn, report  # noqa: E402

ap = argparse.ArgumentParser(prog="python -m tools.datacity", description="OLYMPUS DATA CITY: the NQ data machine (research only)")
ap.add_argument("--full", action="store_true", help="rebuild the event table from scratch")
ap.add_argument("--heartbeat", action="store_true", help="first append the PC's NinjaTrader 5m bars (heartbeat / dashboard branches)")
ap.add_argument("--out", default=learn.OUT, help="output folder (default research/datacity)")
ap.add_argument("--no-web", action="store_true", help="do not copy city.json / jarvis.json next to the page")
ap.add_argument("--no-run", action="store_true", help="do not store the run in research/runs")
ap.add_argument("--fixture", action="store_true", help="also rewrite the page's demo fixture from this run")
a = ap.parse_args()
files = learn.run(full=a.full, heartbeat=a.heartbeat, out=a.out, web=None if a.no_web else learn.WEB, store_run=not a.no_run)
if a.fixture:
    learn.write_json(os.path.join(learn.WEB, "fixture.json"), report.fixture(files["city.json"]))
