# Phone dashboard: the clean-up (2026-10-25)

Read-only UI work. No trading rule, route or engine file changed. Nothing was deleted: every page still opens, and
every old link (`#/brain`, `#/second`, `#/goals` and the rest) still works.

Pictures: `phone_before_after.png` (every tab, before on top, after below), `before/` and `after/` (390 px).

## What moved where

| Before | Now |
|---|---|
| 6 tabs: Home · Brain · ATLAS · Trades · Money · More | **5 tabs: Home · Trades · ATLAS · Money · More** (new house icon for Home) |
| Brain had its own tab | **Home > Bot Brain** (tap the LIT card, or "One tap away" on Home). `#/brain` still works |
| Home was about 6,200 px tall: Surface line, launch checklist with 9 copy-command boxes, Goals card, two small cards, Today's plan, verdict card, open trade, eval card, health card, plan, why-no-trade, radar, 11 link buttons | **Home, in this order:** launch checklist (only while a line is red: count, the first 3 red lines, one "See the fixes" button), **LIT · 50K** card, **ATLAS · 25K** card, **Today's plan** in one line, **Last trade** (or the open trade), and a short "One tap away" list (Bot Brain, Goals, LIT plan, Full overview) |
| Each account card had today, week, bar, three numbers and a next-step line | **One big number** ($ left to the target, or ATLAS's paper trades before go-live), **one line** (room / sessions left), **one status chip** (green good, amber watch, red act). The LIT card also carries the Surface check-in line and, when the PC is silent, the one fix |
| Every old Home card | **Home > Full overview** (`#/homefull`): exactly the old Home, nothing removed |
| The launch-checklist fix commands on Home | **More > Launch checklist** (one tap from "See the fixes") |
| Long scrolling page strips under every tab (Home had 13, Trades 17) | Each tab shows only its main pages: Trades (Trades, Last 10, Journal, Stats, Weekly), ATLAS (ATLAS, Setup stats), Money (Money, Eval timeline, Prop firms, What if). Every other page has one "‹ Back" button |
| More: six sections, "What's new" banner, theme button, tab badges, NEW badges | **More: search on top, one grouped list** (Today, Bot and health, Trades, Money, Strategy, This app), each page once. Research and technical pages (Lab, Experiments, Write-ups, Losses, Replays, Data sources, Archive …) sit under **Advanced, closed by default**; it opens by itself while you search. The six-section hub and What's new are still in More > All features |
| 3D world, particles and splash on by default | **3D off by default** (calm, faster). Settings > 3D effects > Max / Lite turns them back on |

## Look

- One card style: flat surface, thin border, 16 px corners, 16 px padding, 12 px between cards (8-point grid).
- Colours mean one thing: green = good, amber = watch, red = act.
- Tap targets are at least 44 px; list rows are 56 px tall; numbers use tabular figures; the hero number is 40 px.
- Short fade when you change page; skeleton blocks while data loads; empty states in plain English
  ("No trades yet. The first one shows here the moment the bot closes it.").
- The K3 icon and the manifest are unchanged. Service worker cache `le-public-v31` -> `le-public-v32`, so the iPhone
  picks up the new layout on its next open.

## Files

- `tools/web_public/clean.js` (new, loaded last): the tabs, the calm Home, the More list, the sub-bar, the styles.
- `tools/web_public/index.html`: loads `clean.js`, 3D default off (one-time reset of the old default), hub.js v6, more.js v3.
- `tools/web_public/hub.js`, `more.js`: one line each, sharing existing parts (Surface line, open trade, install guide) with clean.js.
- `tools/web_public/sw.js`: cache v32.
- Tests updated where they pinned the old layout: `tests/test_atlas_ui.py` (5 tabs, the two hero cards on top, stacked),
  `tests/test_atlas_v2_shadow.py` (cache name v31 or later instead of exactly v31).
