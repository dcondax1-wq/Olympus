# cities-giant REPORT (2026-11-21, branch night-revamp-cities on pc 7adf312d)

1. **Six arena districts** in one city (tools/world_build.py -> world.json): ZEUS Trading, Kalshi, Websites, Lab & Research, Life, Money. City radius 138 -> 166, 466 places, 5,314 data buildings, 97 app towers (tap = open the app through the warp).
2. **Websites**: every concept site is a lit building (agency/factory/sites.json, 817 today): one block per trade, hot = tall bright tower, warm = lit, not ready = scaffold. Counts only, never a business name.
3. **Payout beacon**: a gold light column over the funded account, filled to its share of the way to payout (ATLAS 93%); the Business LED ring says it when there is no live money line.
4. **Kalshi harbour**: one lit boat per Kalshi bet place, off the Kalshi shore. Account towers keep their fill-to-goal; live trades pulse their place.
5. **PC state**: "PC live · X ago" / "PC silent · last data X ago" / "PC silent · no data here yet".
6. **Phone budget**: photo poster first; on a phone the 3D builds at the first touch or 6.5 s after load (jarvis/backdrop.js rule); Save-Data or Low = the light list + "Show the 3D city". 15 draw calls (limit 60), 13,477 instances on a phone.
7. **Perf** (tools/perf_sweep.py --pages cities, phone profile, software GL; same machine): before (pc) TBT 6,100 ms, longest 2,715 ms, heap 13.0 MB, 508 KB | after TBT 4,828-6,614 ms (noisy), longest 2,650-2,973 ms, heap 12.8 MB, 499 KB. Both over the TBT / longest-task budget: what is left is ONE software-rendered GPU frame (~2.7 s on CPU), not JavaScript (JS per frame 0.3 ms median).
8. **Tests**: test_world_build 44/44, test_world_page 31/31 (pins: 6 districts, sites, poster-first rule, the stale w5 pin moved to w8).
9. Not done: reduced motion still shows the 3D (motionless, no flights) instead of skipping it: the page IS the city; Save-Data / Low skip it.

Shots (390x844 @2x): 1-skyline, 2-six-districts, 3-websites, 4-kalshi-harbour.
