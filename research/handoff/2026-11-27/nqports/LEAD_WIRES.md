# day-nqports (2026-11-27): MARKET PORTS on nq/ - lead wires

Built: one section `#ports` on nq/ (after the December card, jump link "Market"), five cards, code-split (ports.js added near the section or
when idle; ports.css non-blocking). Data: `tools/web_public/nq/ports.json` (4 KB) from `tools/nq_ports.py`.

## 1. Site build: run the builder (cloud side)
After `tools/context_refresh.py` (it refreshes CBOE_vol_1d / GEX_1d / VIX / VXN) and the bars import, in the site build:

    python tools/nq_ports.py            # ~2.5 s; fetches the CFTC weeks (free public API, no key) and caches them in data/cot/nq_tff.json
    python tools/nq_ports.py --offline  # no network: the cached COT weeks (every other section is local files)

Inputs: data/NQ_5m.csv (sessions + base rates), NQ_1d / ES_1d (ES vs NQ), CBOE_vol_1d / VIX_1d / VXN_1d / GEX_1d, data/news/events.csv,
engine/cme_calendar + engine/roll_watch. Futures prices only; no Yahoo / CFD; no secrets. COT publishes Fridays 15:30 ET (Tuesday's positions).

## 2. sw.js precache (lead only)
Add `nq/portscore.js`, `nq/ports.js`, `nq/ports.css`, `nq/ports.json`. Versions changed: nq.js?v=r45, nq.css?v=a12.

## 3. run_area
`tests/run_area.py` gets `AREAS["nq"].append("nq_ports")` (one line under the night-nq-main block).

## 4. Shots (local, shots/ is git-ignored): research/handoff/2026-11-27/nqports/shots/ports2_phone.png, ports2_desk.png
