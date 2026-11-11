#!/bin/bash
# Full team C harvest (public read-only API, polite, resumable: finished series are skipped). About 2 hours.
cd "$(dirname "$0")/../.."
python3 -u research/kalshi_edge_C/harvest_c.py --group weather_main,weather_rep,weather_low
python3 -u research/kalshi_edge_C/harvest_c.py --group index,econ,other
python3 -u research/kalshi_edge_C/harvest_c.py --group index --backfill-since 2026-03-01 --near 0.012
python3 -u research/kalshi_edge_C/harvest_c.py --group weather_main --backfill-since 2026-06-01
echo HARVEST DONE
