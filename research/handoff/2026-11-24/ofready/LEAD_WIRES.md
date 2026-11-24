# day-ofready: lead wires (after hours, with a red team; nothing below touches the trade path)

New files (no bot file imports them): `engine/ofsum.py` (PC: tick day -> 3 small files), `research/orderflow/of_battery.py`
(the pre-registered battery, `research/orderflow/DESIGN.md` @ bc2e5e68f), `tests/test_ofready.py` (4/4, synthetic only;
added to `tests/run_area.py` area `pc`). Smoke 11/11.

## Why not the git `data` branch
`engine/datapipe.py` push is OFF (backup repo is PUBLIC, no push sign-in). The live path is `engine/datafeed.py`: the cloud asks
over ntfy, the PC answers with ONE signed zip <= 1.85 MB, <= 8 answers a day (ntfy 250 msgs/day/IP; status posts use ~210),
attachments kept 3 h, requests reach back DAYS_BACK = 60 days, EXTRAS files capped at 200 KB each.
Order-flow summary = ~55 KB a CME/ET day (synthetic 300k trades: bars 8 KB, footprint 46 KB, meta 1 KB; real NQ RTH ranges are
wider, so budget ~60-120 KB) -> 15-30 days per answer: 60 days = 2-4 answers, one evening.

## W1 (PC builds the summaries) - engine/tickrec.py autopilot(), right after its ingest step
```python
        try:                                    # day-ofready: per-day order-flow summaries for the cloud (read-only, cheap, idempotent)
            from . import ofsum
            ofsum.build(days_back=400)          # writes logs/datapipe/days/<day>/of/NQ_{bars5m,fp5m}.csv.gz + NQ_meta.json
        except Exception:
            pass
```
autopilot already runs only outside 02:00-16:05 ET from the 15-min report task. First run ~1 s a day of ticks, then only new days.

## W2 (PC sends them, days <= 60 back) - engine/datafeed.py
```python
EXTRAS = ("review.json", "proposals.jsonl", "learn.json",
          "of/NQ_bars5m.csv.gz", "of/NQ_fp5m.csv.gz", "of/NQ_meta.json")      # day-ofready: order-flow summaries
DAY_FILE = re.compile(r"^days/(\d{4}-\d{2}-\d{2})/(manifest\.json|trades\.jsonl\.gz|fills\.jsonl\.gz|review\.json|proposals\.jsonl|learn\.json|gaps\.json|"
                      r"of/NQ_(?:bars5m|fp5m)\.csv\.gz|of/NQ_meta\.json|"
                      r"bars/(?:MNQ|NQ|MES|ES|GC|MGC|SI|SIL)_(?:1m|5m)\.csv\.gz)$")
```
The PC and the cloud must land this together (an old cloud refuses a bundle with an unknown name: the Nov 20 fills.jsonl outage).
`extract()` already creates the `of/` subfolder. The comment above DAY_FILE names `tests/test_datafeed_names.py`, which does not
exist: add an `of/` name check to `tests/test_datafeed.py` instead. Note: a tick-day file is an ET calendar day and the datafeed folder
is a CME day with the same date; the battery only uses the ET file's own bars, so that is fine.

## W3 (later, only for backfill days older than 60) - a request flag `"what": "of"`
`parse_request` keeps `what`; with it `since` may reach back 400 days, and `build()` packs only `of/*` + a minimal manifest for each
day that has `logs/datapipe/days/<day>/of/NQ_meta.json` (no bars, trades, fills, gaps). `tools/data_pull.py --latest --of` sends it.
Not needed for the first look if the 40 days are all within 60 days.

## W4 (cloud runs it) - tools/data_pull.py --latest, at the end
`python -X utf8 research/orderflow/of_battery.py` (prints "waiting: N of 40" and exits 0 until there are 40 days; runs each look
once: 40 / 60 / 120-or-`--final`). Needs the bars too (LIT replay): the same pull brings them.

## Privacy / licence
Only 5-minute aggregates of public market data (volume by price and side, signed big-print volume): no account, balance, path or
bot data. Raw ticks and single trades never leave the PC. The ntfy topic is public (name in the repo) and keeps an attachment
3 h; aggregated derived data is the low-risk end of CME redistribution terms, but it is still exchange-derived: if the owner
wants zero exposure, keep W2 off and run the battery on the PC (`of_battery.py --ticks` or `--src logs/datapipe/days`), which
pushes nothing and sends one ntfy line.
