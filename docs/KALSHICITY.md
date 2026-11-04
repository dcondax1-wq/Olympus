# KALSHI CITY

A night city built from the Kalshi bot's bets, plus the engine that keeps learning which slices of those bets have an edge. Read only: it reads the public
`kalshi-feed` (`kalshi.json`), never calls Kalshi, never holds a key, never places an order.

| Piece | File | What it does |
|---|---|---|
| The engine | `tools/kalshi_edges.py` | reads `kalshi.json`, keeps every bet it has ever seen (`ledger.json`), re-measures every edge, writes `edges.json`, appends dated lessons to `learning_log.json`, writes `jarvis.json` |
| The demo | `tools/kalshi_demo.py` | 1,500 invented bets with planted edges -> `fixture.json` (the DEMO city, offline) |
| The page | `tools/web_public/kalshicity/` | `cityfeed.js` data, `citylayout.js` where everything stands, `cityscene.js` the 3D city on the OLYMPUS render core, `cityrig.js` cameras, `kalshicity.js` the page |
| Tests | `tests/test_kalshi_edges.py`, `tests/test_kalshicity_page.py` | engine maths vs an independent mirror (46 checks); modules in node + the page at 390 x 844 |

## What an edge is
Any 1 to 3 of five dimensions fixed (the rest `*`): strategy, market, hour (ET, 4 h block), price band (the bot's own edges), side. Per edge: n, win rate vs the
market's implied probability (mean entry price), EV per $1 staked (realised, fees in), Wilson 95% range, a z-test of wins against sum(price), the 7 / 30 day
windows, the decay, Kelly (full, safe on the Wilson low end, quarter of safe), the stake in $, the chance of losing half the bankroll at that stake (Lundberg bound
on the Wilson low win rate), and a status: NEW (< 30 bets: grey, no stake), GROWING, HOLDING, DECAYING, DEAD. Advice: DO MORE (proven, z >= 1.645, sized), KEEP,
WATCH, STOP (DEAD), COLLECT (too few bets).

The feed carries only the last 40 bets, so the engine **accumulates**: each run adds the bets it has not seen. The feed's whole-life totals (strategies, markets,
price bands) are edges too (`src: feed`; the implied price is the band's mean price or the break-even rate w / (1 + EV)); a daily snapshot of those totals gives them real
7 / 30 day windows after a week. Combinations that hold exactly the same bets as a simpler edge are dropped. Run every <= 6 hours or bets are missed (the feed window is
about a day; `ledger.seen_share` says how much the engine has seen one by one).

## City
District = market (ring round Downtown, which holds strategies, bands, hours, sides). Height = EV per $1, roof glow = recent win rate, roof colour = status, windows
= bets (gold won, red lost), grey and low = n < 30, going up with a crane = a new edge, crumbling with embers = one that just died. Roads: capital out (cool cars) and back
(gold won, red lost); pink cars = open orders. Weather = last 7 days (clear / overcast / rain / storm; fog = bot paused). Day / night = New York time. Dark far towers are scenery
(no data; the guide says so). Tiers via OLYMPUS: low 700 towers, high 2,600, ultra 4,200 + bloom; reduced motion = a still scene.

## Wiring the lead does (this folder only adds files)
1. `olympus/olympus.js` APPS: `kalshicity: ['Kalshi City', 'K', '#2ef2d0']`
2. `jarvis/apps.js`: `app('kalshicity', 'Kalshi City', 'money', '#2ef2d0', "The Kalshi bot's edges as a night city", { glyph: 'K' })`
3. `tools/build_web_dashboard.py` app tuple (line ~1212): add `"kalshicity"`; `jarvis/sw.js` bump if it lists apps.
4. CRONOS refresh (state must persist, so a branch like `datacity`): a workflow every 6 h that checks out `kalshicity` (edges / ledger / log), runs
   `python tools/kalshi_edges.py --out <state dir>` and force-pushes the four files; the registry task is
   `Task("kalshicity", "kalshicity", "nightly", "workflow", 5 * 60, NIGHTLY_MAX_H, files=("edges.json", "learning_log.json", "jarvis.json"), branch="kalshicity",
   branch_files=(("edges.json", "kalshicity/edges.json"), ("learning_log.json", "kalshicity/learning_log.json"), ("jarvis.json", "kalshicity/jarvis.json")), workflow=".github/workflows/kalshicity.yml", est_min=0.3)`.
   `ledger.json` stays on the branch (not copied to the site). First run seeds from the repo copies in `tools/web_public/kalshicity/`.

```yaml
name: kalshicity
on: { schedule: [{ cron: "17 */6 * * *" }], workflow_dispatch: {} }
permissions: { contents: write }
concurrency: { group: kalshicity, cancel-in-progress: false }
jobs:
  learn:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 1, sparse-checkout: "/tools/kalshi_edges.py\n/tools/__init__.py\n/tools/web_public/kalshicity" }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: State (previous run, else the repo seed)
        run: |
          mkdir -p state
          if git fetch -q --depth 1 origin kalshicity 2>/dev/null; then
            for f in edges.json ledger.json learning_log.json jarvis.json; do git show "FETCH_HEAD:$f" > "state/$f" 2>/dev/null || rm -f "state/$f"; done
          else cp tools/web_public/kalshicity/{edges,ledger,learning_log,jarvis}.json state/; fi
      - run: python tools/kalshi_edges.py --out state
      - name: Publish
        run: |
          cd state && git init -q && git checkout -q -b kalshicity && git add -A
          git -c user.name=cronos -c user.email=cronos@users.noreply.github.com commit -qm "kalshicity $(date -u +%FT%TZ)"
          git push -q -f "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}" kalshicity
```
