# day-poseidon: lead wires

Done on this branch (file names / ids / keys unchanged: `orderflow.html`, `of`, `flow`, `#of*` all as before):
- NQ app text: the room is "POSEIDON · order flow" (title, h1 + trident mark `nq/poseidon.svg`), the NQ home door "🔱 POSEIDON",
  nav dock aria + account name, Story event title, Week lane card, chart absorption tooltip, Brain mind line, Ask names, Trading Home tile.
- NQ home: `#chartCard` right under the hero + "📈 Live chart" beside LIVE NOW (`.nq-doors`); jump nav lists Chart first.
- LCP: the page head starts the PC's core status poll (since=70m) with the other early fetches, nqfeed.js v2 answers it once;
  the chart view waits for the page's load event (it now sits on screen 2 and used to compete with the hero's $).
- `.hx-how` capped at 250 px (never in Jarvis's bottom-right corner). test_nq_chart first-screen check = "card right under the hero".

For you (other owners / files helpers never edit):
1. sw.js bump (many ?v changes: nqfeed 2, nqchartfeed 2, nqhero.css 12, nq.js r47, nqnav 5, orderflow css/js 4, story 3, storycore 3,
   brainmind m6, nq/ask a2, nqchart d4, nq/week 2, sharebtn 2) and precache `nq/poseidon.svg`.
2. Same name outside the NQ app (pinned by their own tests: test_pillars, test_warroom, test_pillars_hero, test_zerotouch2):
   gate/index.html + root index.html four-pillars tile ("ORDER FLOW"), pillars/{data,pillarscore,pillarof}.js, warroom/warcore.js,
   brain/{braincore,learned}.js + learned.html, cities/mind/{mindcore,mind}.js, pc/{pc,pccore}.js, olympus/gate-catalog.js,
   olympus/apps-list.js, jarvis/apps.js (search words: add "poseidon").
3. Telegram: /oflane replies in engine/of_lane.py ("Order flow: ON - Sim101", "Order flow ladder step ...") and
   engine/pc_checklist.py names {"OF": "Order Flow"} -> "POSEIDON (order flow)" by the bot-side owner (test_of_lane_ready pins them).
