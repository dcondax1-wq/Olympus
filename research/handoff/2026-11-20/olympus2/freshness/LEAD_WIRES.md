# Data freshness: lead wires (day-archive, 2026-11-20)

## 1. tools/build_web_dashboard.py (lead-only): refresh the CRONOS-era files at every build
Insert right BEFORE the "# Pinakes: catalogue every table in the built site" block (so Pinakes catalogues the fresh files):
```python
    # Data freshness (day-archive 2026-11-20): Pantheon + Fates were CRONOS jobs writing a `cronos` branch that no longer exists on
    # dcondax1-wq/Olympus, so they froze on Nov 3. tools/site_refresh.py rebuilds them into the site (about 2.5 min, never fatal,
    # never writes the checkout). Fates reads today's state from the PC's public status post.
    try:
        import subprocess
        rr = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "site_refresh.py"), "--site", out], capture_output=True, text=True, timeout=1200)
        print((rr.stdout or "").rstrip() or f"  refresh: rc={rr.returncode}")
    except Exception as e:  # noqa: BLE001
        print(f"  refresh: skipped ({e})")
```
Test: `python tests/run_area.py olympus --only site_refresh` (5/5, no network).

## 2. Decisions (owner / lead), not code
- **The PC has been silent since 9:30 ET today** (board: "STALE, PC SILENT", 5 h at 14:20 ET). Pages now show its last real
  numbers with their age instead of demo, but the owner should check the PC / bot.
- **Odeon trades (Trading reels, Journal, Kronos, NQ's past days) stop at Oct 28.** The newer real trades exist only in the PC's
  day packs (`engine/datapipe.py` -> a `data` branch), which this repo does not have. Either let the PC push its `data` branch to
  dcondax1-wq/Olympus (then `python tools/odeon_export.py` picks them up via `tools/live_trades.py`), or accept the label: Kronos and
  Journal now say "As of Oct 28: the site's trade list ends there".
- **GitHub Actions on dcondax1-wq/Olympus**: cronos.yml, datacity.yml, kalshicity.yml wrote the `cronos` / `datacity` branches. They
  are not running here (no such branches): Data City (Nov 10) and Kalshi City (Nov 5) are also frozen (Cities / Kalshi teams' data).
  Enable the workflows on this repo, or add their builders to tools/site_refresh.py.
- **plutus/roadmap.json** (Nov 4; Hera's 12-month plan, Ledger's plan check, Demeter's typical dates) is a research model that still
  plans BLITZ and an ATLAS eval. Hera now labels it "16 days old" and shows the real accounts above it ("First payouts, now"). A new
  model run with today's accounts (ATLAS funded, Zlarior 50K + 25K #2 evals, no BLITZ) is a money-model change: owner's call.

## 3. sw.js
Not needed: changed files are app JS with bumped ?v= (hera a1dgi, kronos a3, journal j1ge) and network-first data.
