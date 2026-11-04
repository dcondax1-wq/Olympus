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

Keep going until you run out of room, then reply with the list of your pull request links.
