# The week queue for ChatGPT / Codex (quality work, no Claude needed)

Owner goal: every OLYMPUS app looks and feels great on an iPhone, and helps him make money. Work top to bottom.
One task = one branch `chatgpt/<task-id>` = one pull request. Read `handoff/CODEX_RUNBOOK.md` first (how to test, how to finish).
When a task is done, change `[ ]` to `[x]` here in the same PR and add one line under it: what changed, how you checked.

## Rules that never change
- Paper only. Never touch `engine/`, `live_model*.json`, `.github/`, `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`,
  the `APPS` table in `olympus/olympus.js`, or any secret. A bot guard blocks the PR if you do.
- Stay inside ONE app folder per PR (`tools/web_public/<app>/`) plus its test in `tests/`. Shared kit files (`olympus/*`) only if the task says so.
- Money wording: eval cards say "Drawdown left $X of $max loss". Never "X of 10 days". Every R figure sits next to its $.
- Never blank: every view has demo data and an empty-state sentence. Taps >= 44 px at 390x844. Plain words, no jargon.
- Say honestly what you could not check (no real iPhone here).

## P1: fix what the owner said looks bad (do these first)
- [ ] **cities-layout**: `tools/web_public/cities/`. Hub shows tiny dim clusters in a huge empty void and clipped group labels
      ("BSIDIAN", "RE", "MONE"). Make the first screen look like a lively night map of cities: bigger clusters, labels fully on screen,
      the 3 most interesting cities named, fill the void (denser layout, camera framing so everything fits 390x844).
- [ ] **datacity-look-check**: `tools/web_public/datacity/`. The owner said Data City looked worse tonight; the lead restored the full profile for phones
      (`caps.js` profileOf). Compare screenshots at 390x844 `?q=high` vs `?q=high&phone=1`, keep the richer look, and find any other
      thing tonight made worse (labels, density, colours). Report with before/after screenshots in the PR description.
- [ ] **kalshicity-look**: `tools/web_public/kalshicity/`. Same pass: the city should look rich on first open, not sparse.

## P2: look and feel, one app per PR (screenshots at 390x844 before and after in the PR)
- [ ] oracle, odeon, fates, labyrinth, hephaestus, prometheus, pantheon, arena, tree, tyche, hermes, athena, ares, plutus, forum, argus,
      nemesis, chronos, mind, ledger, inbox, journal, settings: open each at 390x844 (`?demo=1`), list what looks flat, empty, clipped or
      too small, fix the 3 worst. Keep the draw-call budget in `tests/test_olympus_kit.py` (PERF table).
- [ ] Every app: first-screen answer to "what do I do right now?" in one plain sentence at the top.

## P3: money features (read-only, from already-published JSON)
- [ ] **ledger-import**: Ledger: paste-a-CSV import of payouts/fees (client-side only, nothing sent anywhere), with a preview and undo.
- [ ] **journal-weekly-card**: Mnemosyne: Sunday review card with the one rule for next week, copy as Markdown for Obsidian.
- [ ] **athena-more-drills**: Athena Train: 10 more "read the chart" drills from `research/lab/backtest_live.json` via `tools/athena_drills.py`.
- [ ] **plutus-what-if-buy**: Plutus: "if I buy another ATLAS 25K now" card using `plutus/roadmap.json` numbers (no new numbers invented).

## P4: bridge jobs (ChatGPT's own creative work, see the Bridge page for the 78 jobs)
- [ ] Do the Bridge money jobs first (prop-firm rules digest, payout rules, discount codes WITH sources, CME holidays, NQ roll dates).
      Put results in `handoff/inbox/<job-id>/` with a `DONE.md`. Mark anything unverified as UNVERIFIED.

## Done log
(add one line per finished task: id, PR number, date)
