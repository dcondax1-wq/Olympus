# Runbook for ChatGPT / Codex: working without Claude

Read in this order: `AGENTS.md` -> `CLAUDE.md` (hard rules) -> `handoff/QUEUE.md` (what to do) -> this file.
Map of the apps and the checklist for adding one: `docs/CLAUDE_REFERENCE.md` ("OLYMPUS apps and tools" and "Wiring checklist").

## One task, start to finish
1. Pick the first unchecked task in `handoff/QUEUE.md`. Branch: `chatgpt/<task-id>` from the latest `main`.
2. Open the app folder `tools/web_public/<app>/`. Serve the site locally: `cd tools/web_public && python -m http.server 8000`, then open
   `http://localhost:8000/<app>/?demo=1` in a phone-size browser (390x844). Playwright is the easiest: `pip install playwright && playwright install chromium`.
   Add `?q=high` for the rich look and `?q=low` for the cheap LITE look. Both must look good.
3. Make the change. Keep edits small. No new libraries from the internet at runtime (the kit loads its own three.js files).
4. Check before you push (all must pass):
   - `node --check <each changed .js file>` (plain scripts) and valid JSON for each changed `.json`.
   - `python -X utf8 -m tests.test_jarvis_shell` (3/3) and `python tools/apps_list_build.py --check`.
   - the app's own test, e.g. `python -X utf8 -m tests.test_<app>_page` (ask it to run; if it times out on your machine, say so in the PR).
   - `python -X utf8 -m tests.test_money_wording` (no banned eval wording) and `python tools/numbers_audit.py --check`.
5. Screenshots: before and after at 390x844 (high and low). Put them in the PR description, not in the repo.
6. Version tags: when you change a script or css file an app page loads with `?v=xx`, bump that `?v=` in the page by one (o2 -> o3).
   If the file has no `?v=`, say so in the PR: the owner or Claude bumps the worker.
7. Open a pull request into `main` titled `<task-id>: <what changed>`. Tick the task in `handoff/QUEUE.md` in the same PR.
8. The bot `chatgpt-guard` checks the PR (allowed paths only, JS/JSON valid, shell test, apps list, money wording). If it is red, fix it.
   The owner merges green PRs with one tap on his phone (GitHub app -> PR -> Merge). The site republishes itself within about 15 minutes.

## What a good PR looks like
- Title says the result in plain words. Description has: what looked bad, what you changed, before/after screenshots, what you could not check.
- 1 app, under ~400 changed lines, tests green. No drive-by edits.

## If you are stuck
Write `handoff/inbox/<task-id>/QUESTION.md` with the exact question and what you tried, open a draft PR, and move to the next task.

## Never
Touch `engine/`, `live_model*.json`, `.github/`, `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`, `olympus/olympus.js` APPS table,
`data/`, secrets, or anything that arms, routes or places orders. Never push to `main` or to a `claude/...` branch.
