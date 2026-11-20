# LEAD_WIRES (day-brief, 2026-11-20): exact edits only the lead makes

Branch `day-brief`. Nothing below touches the bot (engine/*, server.py, live_model*.json untouched).

## 1. Cloud build: `tools/build_web_dashboard.py`, inside the `if os.environ.get("LE_DASH_BUILD") == "1":` block
Find:
```python
            from tools import nqdash_export as _nqx            # night-nqdash2: business/payday.json + nq/news_week.json
            _nqx.main([])
        except Exception as _dash_err:  # noqa: BLE001
            print(f"[dash_build] skipped: {_dash_err.__class__.__name__}: {_dash_err}")
```
Replace with (own try, so a brief failure never skips the others and vice versa):
```python
            from tools import nqdash_export as _nqx            # night-nqdash2: business/payday.json + nq/news_week.json
            _nqx.main([])
        except Exception as _dash_err:  # noqa: BLE001
            print(f"[dash_build] skipped: {_dash_err.__class__.__name__}: {_dash_err}")
        try:                                                    # day-brief 2026-11-20: nq/brief.json (docs/BRIEF.md)
            from tools import premarket_brief as _pmb
            _pmb.main([])
        except Exception as _brief_err:  # noqa: BLE001
            print(f"[premarket_brief] skipped: {_brief_err.__class__.__name__}: {_brief_err}")
```
Checked: `python -c "from tools import premarket_brief as p; p.main([])"` from the repo root writes the file in ~1 s,
stdlib only (no pandas), reads engine/live_board + engine/cme_calendar + engine/guards + engine/multi_account read-only.
The nq/ folder is already copied to the site by the same build (`"nq"` is in the app list), so `<site>/nq/brief.json` is live.

## 2. `engine/generated_files.py` GENERATED: add one line after the `nq/news_week.json` line
```python
    "tools/web_public/nq/brief.json",     # tools/premarket_brief.py (cloud build, day-brief 2026-11-20)
```
(Without it, a PC build or a test that runs the tool would leave a tracked file changed and block the PC's auto-update.)

## 3. `tests/run_area.py`: add the suite to the nq area (after the `nqdeep` line)
```python
AREAS["nq"].append("premarket_brief")       # day-brief 2026-11-20: nq/brief.json contract + pre-registered bias (tools/premarket_brief.py)
```
Run: `python -X utf8 -m tests.test_premarket_brief` (74 checks, ~3 s).

## 4. STATE.md line (Live now / notes)
- Premarket brief (day-brief 2026-11-20, docs/BRIEF.md, research/writeups/premarket-brief-2026-11-20.md): cloud build writes
  nq/brief.json (levels PDH/PDL/PDC/ONH/ONL/PWH/PWL + LIT's target lines, gap, ATR, VIX/VXN band, Tier-1/2 news with what
  each bot does, each bot's window today + setup in plain words, recap + yesterday's recap). Day bias pre-registered
  (B1 overnight drift, B2 fade yesterday): NO better than a coin (B1 47% of 442 days 2021-25, 59% of 69 H1, 45% of 56 H2)
  -> shown grey as context only; the bots ignore it.

## 5. Not done here (owned by others)
- Showing it: day-nqdash3 (nq/, trading/) and day-arenas (helios/) read `tools/web_public/nq/brief.json` per docs/BRIEF.md.
- VIX / VXN: this branch carries pc's fresh CBOE closes (to 2026-11-19); the brief flags any close older than 4 days in `data.stale`.
- Smoke: 7/8 here; the red one is `tests.test_zenith_mode` = `No module named 'playwright'` (Python Playwright is not
  installed in this container; browser suite, untouched by this branch).

# ROUND 2: weekly review (ZEUS this week), 2026-11-20

Changed (all on day-brief): `tools/weekly_review.py` (extra blocks, cloud trade list, no churn, Friday-morning session count),
new `tools/week_more.py`, `tools/web_public/business/week.html` + `week.js` (v=4), `tools/web_public/business/week.json`
(this week's real data, built from the PC's status post), new test `tests/test_week_more.py` (35/35), existing
`tests/test_weekly_review.py` still 35/35. Screenshot: `research/handoff/2026-11-20/brief/week_review_2026-11-20.png`
(full page, 390 px @2x) + `week_review_top.png`.

## 6. Cloud build: run the weekly review too (the PC writes week.json but cannot push; the site only had a Claude-committed copy)
In the same `LE_DASH_BUILD == "1"` block, after the premarket_brief try (item 1):
```python
        try:                                                    # day-brief round 2: business/week.json from the PC's status post
            from tools import weekly_review as _wr
            _wr.write(_wr.build())
        except Exception as _wr_err:  # noqa: BLE001
            print(f"[weekly_review] skipped: {_wr_err.__class__.__name__}: {_wr_err}")
```
~4 s (ntfy read + the two twin replays). `write()` now skips the rewrite when only `built` changed. week.json is already
in engine/generated_files.py GENERATED (the PC's Friday ops task keeps rewriting it there).

## 7. tests/run_area.py: add to the money area (next to weekly_review)
```python
AREAS["money"].append("week_more")          # day-brief 2026-11-20: weekly review round 2 (twins, best/worst, K8, calendar, weekend)
```

## 8. sw.js (yours): week.js went v=3 -> v=4 in week.html; bump the business cache entry if sw.js lists week.js / week.html.

## Facts worth knowing
- Thanksgiving Thu Nov 26 is NOT a CME closure: engine/cme_calendar (= the bots) and 5 years of NQ bars say NQ trades
  until a 13:00 ET halt (the bots stop new trades 12:45); Fri Nov 27 halts 13:15. The page says so ("the stock market is
  closed; NQ trades until 13:00 ET").
- This week vs the twin: Zlarior matched its twin (Nov 16 long, -1.01R both). ATLAS matched on Nov 18 (MACD short, -1.04R);
  ATLAS's twin also had a +6.87R EMA short on Nov 17 08:20, before the funded account was issued (Nov 17 20:26 ET):
  shown as "not live yet", not "missed".
