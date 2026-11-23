# LEAD_WIRES: day-notify (2026-11-23): "Send me a test alert" from the phone + the post-update push

Code on branch `day-notify` needs no wiring for the PC part (engine/post_update_check.py runs after every update restart already).
The cloud button needs ONE new workflow file and ONE secret. Free: ntfy.sh + about 1 Actions minute per tap.

## 0. Why nothing in the cloud alerts today (found 2026-11-23 11:30 ET)
`dcondax1-wq/olympus`'s default branch `main` holds only README.md, and GitHub registers / schedules / shows "Run workflow" ONLY for
workflow files on the default branch: the Actions API lists **0 workflows**. So pc-watch and cloud-monitor (and their PC-silent alert)
have never run on Olympus. The PC was silent 73 min this morning (board, 11:26 ET) and no cloud alert could go out.

## 1. New file `.github/workflows/alert-test.yml` on `main` (needed for the button) AND on `pc` (keep them equal)

```yaml
# SEND ME A TEST ALERT (day-notify 2026-11-23): one tap on the phone, the PC can be off. Sends "TEST: Olympus alerts work <time>"
# through the cloud's alert channels (private ntfy topic = secret LE_NTFY_TOPIC; Telegram / Discord when their secrets exist), reads it
# back, posts the receipt (ok / failed per channel, no topic, no token) to the public status topic; green check = it reached you.
# Read-only token, no commit, no pip install, ~1 billed minute a tap. tools/alert_test.py, tests/test_alert_test.py.
name: Send me a test alert

on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: alert-test
  cancel-in-progress: false

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 3
    steps:
      - name: Code (branch pc, shallow)
        uses: actions/checkout@v4
        with:
          ref: pc
          fetch-depth: 1
          persist-credentials: false
      - name: Send the test alert and read it back
        env:
          LE_NTFY_TOPIC: ${{ secrets.LE_NTFY_TOPIC }}
          LE_TG_TOKEN: ${{ secrets.LE_TG_TOKEN }}
          LE_TG_CHAT: ${{ secrets.LE_TG_CHAT }}
          LE_DISCORD_WEBHOOK: ${{ secrets.LE_DISCORD_WEBHOOK }}
        run: python3 tools/alert_test.py --out pcw
```

Alternative if you prefer one file: the same step as a `workflow_dispatch` boolean input `alert_test` on pc-watch.yml (also needs
main). A separate file is better for the owner: it shows as its own line "Send me a test alert" with no options to pick.
(cloud-monitor.yml is a poor home: ~1,300 min/month, a dashboard publish with DASH_DEPLOY_KEY to another account, and it is not
on main either.)

## 2. Put pc-watch.yml on `main` too (its own header already says so; today it is not there)
Copy `.github/workflows/pc-watch.yml` from `pc` to `main` unchanged (plus night-k7cloud's optional Sunday cron line). Then the
real "Your PC stopped reporting" alert runs every 30 min on weekdays.

## 3. Repo secret `LE_NTFY_TOPIC` (owner's hand step, or yours if he gives you the topic in private)
GitHub -> dcondax1-wq/olympus -> Settings -> Secrets and variables -> Actions -> New repository secret: name `LE_NTFY_TOPIC`,
value = the private topic the PC made (tools/bat/TEST_ALERT.bat prints it; `%USERPROFILE%\.olympus\ntfy.json`). Never in the repo.
Without it the test (and every PC-silent alert) goes to the PUBLIC status topic and the receipt says "DID NOT REACH YOU: add the
repo secret LE_NTFY_TOPIC". Telegram / Discord secrets (`LE_TG_TOKEN` + `LE_TG_CHAT`, `LE_DISCORD_WEBHOOK`) stay optional.

## 4. Check it worked (Claude / lead)
`python tools/alert_test.py --last` prints the newest receipt from the public status topic (12 h): WORKED / DID NOT REACH YOU and
each channel's result. The run's page on GitHub has the same table.

## 5. tests/run_area.py
One append-only line: `AREAS["pc"] += ["alert_test"]` (already on the branch, after the k7cloud line).
