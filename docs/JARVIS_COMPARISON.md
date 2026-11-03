# Jarvis vs the best hub apps (2026-11-03)

What the best assistant / hub / trading-home apps give you on their first screen, what Jarvis already had, and what was
added in the OLYMPUS night (worker `jarvis-v12`, `jarvis.css?v=j8`). Rule for adding: only what is vital for the owner
(an 18-year-old running NQ bots, a Kalshi bot and a planner from an iPhone), fast, and organized under the mic row so the
mic / HANDS-FREE / VOICE buttons stay on the first 390 x 844 screen.

| App (what it is best at) | What it has | What Jarvis had | What was added |
|---|---|---|---|
| iOS Home Screen widgets | Glanceable tiles that each answer one question; tap = open the app | KALSHI TODAY / NQ BOTS TODAY boxes, the System strip, project cards | Quick actions grid (8 tiles: Briefing, System, NQ bot, Planner, Kalshi, Search, Hide $, Look) |
| iOS Calendar "Up Next" / Notion home | Today's agenda in order, what is next with a countdown | One "NEXT" chip (Planner only) | Today timeline: the trading day in ET (game plans 1:45 / 10:45, entries 2:00 to 3:30 PM, NY open, bots flat 3:55, RTH close, halt, Globex) merged with the Planner's events and to-dos; a 24 h day bar with the overnight / RTH / entry window, the event ticks and a NOW needle; the next item counts down |
| TradingView mobile home | Session context (pre-market, RTH, overnight) and the clock in the market's time zone | Market panel (open / closed, ET clock, NQ last) | The day bar shows the sessions and where now sits in them |
| Raycast / Arc command bar | Search everything, run any command from one box | Command palette (search button) | "Play the OLYMPUS intro" and "Today's timeline" in the palette; Search as a quick action |
| Rabbit R1 / Humane Ai Pin | A living orb as the identity; it reacts to state | 3D core (listening / thinking / speaking states), HUD ring | Satellites: one per system (PC, Zlarior, ATLAS, BLITZ, Kalshi, Planner) orbiting the core in its verdict colour (green / amber / red); tap one = the System panel. A pulse ring leaves the core when fresh bot numbers arrive |
| iOS / Things / Linear micro-interactions | Haptic ticks, spring presses, numbers that animate on change | Tap ripples, press glare, scan sweeps | Haptics (Android vibrate; iPhone iOS 18+ through the switch-control haptic), spring press on tiles and timeline rows, staggered tile entrance, KALSHI / NQ numbers glow once when they change; Look → Haptics switch |
| Apple / game launch screens | A branded opening that never slows the app | A 1.2 s boot log | The OLYMPUS entrance (below) |

## The OLYMPUS entrance

- **What plays (3.6 s, first start of the day):** the void and a spark on the ground; Zeus's lightning strikes it (two
  strokes, a branch, the screen flashes); a temple's six fluted marble columns rise out of a sea of clouds; embers fly into
  the letters OLYMPUS on the frieze (gold, a violet glow, an electric dissolve, then a shine); the pediment draws itself in
  gold light from its apex; an orb wakes in the pediment; the camera pushes through a tunnel of cloud into it and it ignites
  as Jarvis's own core (rings in violet and gold) right where the real core sits, then the overlay fades and Jarvis is there.
- **Later starts the same day:** the 1 s version (strike, temple, OLYMPUS, push, ignite). Reduce motion: a still OLYMPUS
  word mark that fades (0.8 s). 3D effects Off: 0.5 s. No WebGL: the still version.
- **Sound:** a bass "whoom" (Web Audio, synthesized, no file) only after a gesture: the tap that skips, or a replay from the
  command palette. Never on a cold open.
- **Fast:** one WebGL1 full-screen shader plus one point-sprite pass; every particle moves on the GPU (no per-frame JS but
  uniforms). Rendered at 1.5x (1x on low-end or 3D Low); a phone that runs late steps the resolution down, and one under
  20 fps cuts straight to the reveal. No files, no network, no assets: it is an inline script in `index.html`.
- **Never in the way:** Jarvis starts underneath while it plays (the 3D core waits for its end, 4.5 s at most). Tap anywhere
  to skip. Any error removes it at once; if its script never runs, the overlay hides itself by 0.7 s (the start script's
  timer) and by 0.95 s (CSS); a timer, a lost WebGL context and a hidden page end it too; the start watchdog's note removes
  it. A start after one that did not finish (or an intro the phone closed) gets the still fade. Look → OLYMPUS intro turns
  it off.
- **Why inline:** tested in WebKit: an `async` script runs only after the page's module, i.e. after Jarvis has already
  shown, so a separate file would mostly be skipped on the iPhone.

## Not added (and why)

| Idea | Why not |
|---|---|
| Lock-screen / Home Screen widgets | A web app cannot make iOS widgets |
| Wake word, double clap, "look at my screen" | PC-only features of the old Jarvis, left out on purpose |
| Live price ticker on the home screen | Jarvis reads the bots' feed every 30-60 s; a ticking price would need a paid / external feed (hard rule: no Yahoo, no paid services) |
| Background push from Jarvis itself | Zenith already pushes; two apps pushing the same alerts would double them |

Tests: `python -X utf8 -m tests.test_jarvis_hub` part o (the intro: plays, ends, skips on a tap, removes itself on every kind of
failure, the slow-phone cut, the versions, the replay; the home extras).
