# day-brains + day-brains-feed (2026-11-27 overnight): THE STRATEGY BRAINS - lead wires

Owner: "as the creator I want to see everything happening within the brain, each brain for each strategy".

## What is built
- Web (branch day-brains):
  - nq/brainviewcore.js (pure model);
  - nq/brainview.js: `mount(el, {s, getState, compact})` -> `{update, setStrategy, destroy}`. This is the contract proposed to the chart helper for nq/strat.html #brainMount.
  - nq/brainview.css;
  - nq/brains.js + nq/brains.html: the 4-brain page. Phone: one brain + 4 chips. Wide: 2x2.
- Per brain: the decision pipeline (each gate green / red / now / waiting, the number it saw vs the rule), what would trigger a trade now, risk and size of the next trade, the levels it watches + distance, skipped today + why, every thought line in the post, health (report age, program, on / armed, brain-numbers age).
- Bot (branch day-brains-feed): engine/brain_xray.py builds the ext block "bx" (<= 1,600 B, rides LAST in EXT_LAST, cut 900 / 500, then out):
  - LIT: forming setups, the newest 4 setups with every check as "value / rule", setups today, the next trade's size, the blocker;
  - ATLAS: routed lobes' checks + armed plan;
  - BLITZ: paper state.
  POSEIDON uses the existing "ofp". Read-only, no ids, built in the 15-minute report task only.

## Wires (lead only)
1. sw.js precache: nq/brainviewcore.js, brainview.js, brainview.css, brains.js, brains.html.
2. Nav: the dock's "Brain" tab (nqnav.js, the nav helper's file) and/or jarvis/apps.js: point a "Brains" entry to nq/brains.html.
3. nq/strat.html (the chart helper): `import { mount } from './brainview.js?v=1'; mount(document.getElementById('brainMount'), { s, getState: () => ({ lite: <your merged post> }) })`.
4. Land day-brains-feed with the red team's review (request #44 sent). Until the PC runs it, the brains say "the gate numbers are not in this post yet" and show the stages from the glance.
5. Also fixed here: story.html never lifted the Olympus veil (it waited for the kit's 12 s fallback) and its nav row was unstyled. Now story.js v3, story.css v3.
