# PC WATCH: a phone push when the trading PC goes silent (owner YES 2026-11-20, card cloud-alerts)

**What it does:** every 30 minutes on weekdays, GitHub's free cloud runs one small check (`tools/pc_silent_check.py`). If your
PC has not posted its status for 20+ minutes between 01:30 and 16:00 ET, you get ONE push: "Your PC stopped reporting at
HH:MM ET. Check it: STOP BOT, START BOT." One reminder 2 hours later, then quiet for the day; "PC reporting again" when it is back.
It works with the PC off (that is the point). It never trades, never arms anything, never changes the PC or the website.

## Your 2 steps (hands only, 2 minutes, on github.com)

1. **Actions on:** github.com/dcondax1-wq/Olympus > **Settings** > **Actions** > **General** > "Allow all actions and reusable
   workflows" > **Save**. (If it already says that, skip.)
2. **Your private alert topic:** same repo > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**:
   Name `LE_NTFY_TOPIC`, Secret = the ntfy topic your phone app already follows for bot alerts (just the name, or the full
   `https://ntfy.sh/<name>` link) > **Add secret**. Without it the alert still comes, plain text, on the public status topic.

Check it once (optional): repo > **Actions** > **pc-watch** > **Run workflow** (Dry run is ticked: it only prints what it would send).

## How it is built (for Claude)

- `.github/workflows/pc-watch.yml`: cron `7,37 5-21 * * 1-5` (UTC) = a run within 30 min of every minute of 01:30-16:00 ET in
  winter and summer time; runs outside the window exit in seconds. No Sunday run: the script's window (engine/notify.silent_window
  = engine/push.pc_offline_window) is weekdays 01:30-16:00 ET only, so a Sunday-evening run could never push.
- Read-only token (`contents: read`), no commit, no push, no pip install (stdlib only), 3-minute cap, code checked out from branch
  `pc`. State (`pc_silent.json`: who was told what today) in the Actions cache, never a commit, so the PC's `git pull` can never
  conflict; a lost cache never repeats a push (today's pushes are read back from the topic).
- **It must be on the default branch.** GitHub runs a schedule only from the repository's default branch, and Olympus's default
  branch is `main` (a stub, "the code is on branch pc"; checked 2026-11-20 through the GitHub search API: default_branch main,
  public). So the same file is also committed to `main` (lead, with the owner's OK to touch `main`: one file, nothing else).
  The alternative, making `pc` the default branch, would also wake every other workflow on `pc` (cloud-monitor, cronos ...): no.
- Never touches the old demetrades2000-coder account or cloud-monitor.yml (its own PC-silent step there keeps working where it runs).
- Cost: ~34 runs a weekday x ~1 billed minute = **~740 minutes a month**. Public repo (today): free, no limit. Private repo: 37%
  of the free 2,000 minutes a month (nothing else runs on this repo's schedule).
- Test: `python -X utf8 -m tests.test_pc_watch` (the workflow's safety, the schedule's coverage both DST ways, a dry run, where
  the alert goes; no network). By hand: `python3 tools/pc_silent_check.py --out /tmp/pcw --dry-run`.
