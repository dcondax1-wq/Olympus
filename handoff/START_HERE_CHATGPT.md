# ONE message to start every agent (copy all of it; change only "agent N of M")

You are agent N of M (for example "agent 1 of 6") working on my OLYMPUS dashboards. Repo: demetrades2000-coder/nq-liquidity-engine (GitHub connected). Claude is not available this week. Many agents work at once and I merge your green pull requests from my phone, so you must NEVER stop and NEVER wait for me: after every pull request, take the next task.

Start now:
1. Read `AGENTS.md`, `CLAUDE.md` (Hard rules), `handoff/CODEX_RUNBOOK.md` (especially PARALLEL MODE), then `handoff/QUEUE.md` and `handoff/QUEUE_BULK.md`.
2. Pick your first task the way PARALLEL MODE says (your number N, step M). CLAIM it by pushing branch `chatgpt/<task-id>` before you start.
3. Do it: open the app at 390x844 (`tools/web_public/<app>/?demo=1`), fix or build what the task says, run the checks from the runbook, take before/after screenshots.
4. Open a pull request into `main` (one app, small). Put in the description: what looked bad, what you changed, screenshots, and what you could NOT check. Add `handoff/done/<task-id>.md`.
5. When the `chatgpt-guard` check is green go straight to the next task. If it is red, fix it first.
6. Never touch `engine/`, `live_model*.json`, `.github/`, any `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`, or secrets. Paper only. Never push to `main`.
7. Plain words, every $ next to its R, "Drawdown left $X of $max loss" on eval cards, never a blank screen, taps >= 44 px.

## What changed on 2026-11-10 (read this before the queue; it is newer than the queue)
- **Look:** every app now uses the AGORA look (marble, bronze, gold, olive, terracotta; serif headings; no neon, no HUD, no techno fonts). Rules: `docs/DESIGN_AGORA.md`. Page tests share `tests/agora_kit.py`. Queue items that say "neon", "cyber" or "HUD" are obsolete.
- **Money machines (paper only):** scanners in `tools/money/` (Mercury deals, Chrysos, Sibyl prediction-market picks, Oikos, Arbiter) run by `tools/money_engine.py` and shown on Mint / Stoa. They only read public data and write JSON; they never trade. Guide: `docs/MONEY_MACHINE.md`.
- **New apps:** about 30 new pages (Delphi, Pnyx, Hestia, Kronos, Pythia, Pheme, Sibyl, ...). The generated list is `docs/OLYMPUS_MAP.md`. New apps are wired with `tools/new_apps.json` + `tools/wire_new_apps.py` by the lead, not by hand and not by you.
- **Hosting plan:** the site is published by **Netlify Drop of the built site folder** (drag the built folder in). The GitHub account was suspended for a while and is **back on the same repo** (same name, same branches); pull requests work again. No secrets are in this repo or in any handoff file: never paste one.
- Still true: paper only; never touch `engine/`, `live_model*.json`, `.github/`, any `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`.

Keep going until you run out of room, then reply with the list of your pull request links.
