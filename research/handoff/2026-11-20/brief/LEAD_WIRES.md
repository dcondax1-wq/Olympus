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
- Fresh VIX / VXN in the cloud: the files end 2026-10-16 (brief flags it in `data.stale`). Worth a lead look: the
  CBOE refresh (engine/news.py `_cboe_daily`) is PC-side; until VIX reaches the cloud, LIT's target lines in the brief
  use the Oct-16 close.
- Smoke: 7/8 here; the red one is `tests.test_zenith_mode` = `No module named 'playwright'` (Python Playwright is not
  installed in this container; browser suite, untouched by this branch).
