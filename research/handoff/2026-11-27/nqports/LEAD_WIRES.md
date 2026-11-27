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

# TODAY'S STORY (2nd commit on day-nqports)
- New: nq/storycore.js (pure model), nq/story.js (card + page + hero line), nq/story.css, nq/story.html. No new builder: today = the page's
  own state (NQ_HOME.bars + the post's glog + board.trades); past days = nq/replay/index.json + replay/<day>.json (tools/build_replay.py,
  already in the build); context = nq/ports.json.
- sw.js precache (lead only): nq/storycore.js, story.js, story.css, story.html. nq.js?v=r46.
- jarvis/apps.js / olympus.js APPS (lead only): optionally list nq/story.html ("NQ Story") next to Replay.
- run_area: AREAS["nq"].append("nq_story") (added).
- Data the PC could add later (LEAD_WIRES, engine side, not done): glog keeps only ~8 lines a bot, so a busy morning loses its early
  thoughts; a per-day thought log published with the day (like pc_days) would let past days show LIT's real reasons, not only the twin's.

# The PC's thought log on story.html (3rd commit; the bot side = branch day-thoughtlog)
- Site build: `python tools/nq_thoughts.py` after `tools/data_pull.py` (publishes data/pc_days/<day>/thoughts.jsonl.gz -> nq/thoughts/,
  the last 10 days, BLITZ never, ids masked again). Until the PC with day-thoughtlog sends a day, the index is empty and the page says
  "The PC's thought log for this day has not reached the site."
- sw.js: nq/thoughts/ is data (network first, like replay/). Versions: story.js?v=2, story.css?v=2.
