# Security red team, 2026-11-21 (day-security3)

Scope (olympus/pc 7adf312d): `engine/alerts_box.py` (/alerts/), `engine/alert_bus.py`, `tools/alerts_setup.py`, the phone pairing
default (`engine/push.PAIR_CODE_ON = False`), `engine/account_box.py`, the Tailscale / LAN / Funnel detection, and the public repo history.
Fixes on branch `day-security3` (see the head commit in the lead message), with tests. Nothing merges before the lead reviews it.

## For the owner

| What a stranger could do | How bad | Now |
|---|---|---|
| Any device on your home WiFi (a guest, a hacked smart TV) could read your account names and **stop, kill or start the bot** | CRITICAL (if Windows lets the bot's port in on WiFi) | Fixed on the branch: the bot's controls answer only the PC itself and your Tailscale devices |
| Tap "Allow" on your public site and quietly get every trade alert (the pairing code is off for now) | HIGH | You now get a "New phone added" notice for every new phone, with the one command that removes it |
| Grab your new Telegram bot in the 3 minutes after you connect it, so your alerts go to their chat | MEDIUM | Fixed: the page's "Open" link carries a one-time code; a stranger's START is ignored |
| Leak your Telegram token | none found | Never in a log, an answer, a status post or the site |

1. Make the GitHub repo private (Settings -> Change visibility). It's still public, with a few weeks of history in it.
2. If your phone ever says "New phone added" and it wasn't you: on the PC, type the command the notice shows.
3. Nothing else.

## Findings (severity, path, status)

| # | Sev | Path | Finding | Status |
|---|---|---|---|---|
| 1 | **CRITICAL** (conditional) | `server.py` `/api/live/*` + `scripts/run_bot.ps1` (HOST 0.0.0.0) | Any device on the home WiFi can call `GET /api/live/state`: `BOT.snapshot()` returns the whole cfg, with the **full NinjaTrader account name** (only `confirm` is stripped). It can then `POST /api/live/stop` / `kill`, and `POST /api/live/start` with `armed`, the public live phrase and that account. The live gate (armed + phrase + NINJATRADER_LIVE=1 + allowlist) is all met on the real PC. The W1 cross-site guard does not stop it: a script sends no Origin, and the Host is a bare IP. Condition: Windows Firewall lets 8766 in on the private network (Python's first-run "Allow" prompt). | **Fixed**: `engine/cross_site.peer_why`. `/api/*` (read or write) and every non-GET request answer only loopback (this includes the tailscale serve proxy) or Tailscale addresses (100.64.0.0/10, fd7a:115c:a1e0::/48). The peer is the socket's own address, which uvicorn rewrites from X-Forwarded-For only for a 127.0.0.1 proxy, so a WiFi device cannot fake it with headers (tested with forged XFF + Tailscale-User-Login + Host). Page files still open on the WiFi. `LE_ALLOW_LAN=1` = the old behaviour. `tests/test_cross_site.py` 24/24. W2 (HOST=127.0.0.1) is still worth shipping too. |
| 2 | **HIGH** | `engine/push.py:937` `PAIR_CODE_ON = False` | Until push-ui.js can take the code, a new phone joins with no check. Anyone who taps Allow on the public site gets every real-account entry/exit (account name + $) and nobody is told. (The no-eviction guard stays on, so the owner's phone is never pushed out.) | **Mitigated**: every join on a PC that already had a phone sends one notice to the owner's phones + the private topic ("New phone added ...", 8-hex id, `python -m engine.push --forget <id>`). New CLI `python -m engine.push --devices` / `--forget`. tests: push_pairing 24/24, webpush 50/50. Full fix unchanged: ship the push-ui pair input + `PAIR_CODE_ON = True` in one publish. |
| 3 | MEDIUM | `tools/alerts_setup.wait_chat_id`, `engine/alerts_box.do_connect` | The first private `/start` to the new bot inside the 3-minute wait became the alert chat. A stranger who finds the bot's username in that window (Telegram search) and taps START gets every trade alert, and the page still says "done" because the test message reached *their* chat. | **Fixed**: `do_connect` makes a one-time code and the page's link is `https://t.me/<bot>?start=<code>`. In page mode only `/start <code>` counts. ALERTS_SETUP.bat (owner at the PC) works as before. tests: alerts_box 64/64 (the fake now sends the code), new alerts_start_code 5/5. |
| 4 | MEDIUM | `tests/test_rapid_arm.py` (commit 50a9105d, today) | One "made-up" Rapid account name had a real-looking MFFU id shape (`tests.test_repo_secrets` c failed). It is in the public history. | **Fixed** in the tree (an obvious fake, the last 4 digits kept; test_rapid_arm 19/19, test_repo_secrets 14/14). History keeps it: the owner step "make the repo private". An account name is not a credential, so there is nothing to rotate. |
| 5 | LOW | `tools/site_privacy.py` | `alerts.json` (`{"telegram": {"token", "chat_id"}, "discord": {"webhook"}}`) was not a private name, and its nested keys were not a private content shape (only the token's regex would catch it). | **Fixed**: the name + the nested shape are private (and `JSON_HINTS` look for them). public_build_privacy --fast 56/56. |
| 6 | LOW | `tools/alerts_setup.save_raw` | Writes the file, then chmods it (a short umask window on Linux; on Windows the profile ACL protects it). Outside the repo (OLYMPUS_HOME). | Not changed. Suggest `os.open(..., 0o600)` for the tmp file. |
| 7 | LOW | `engine/live_site.private_why` | Any signed-in tailnet user passes, so if the PC node is ever *shared* into another tailnet, those users pass too. | Advice: never share the PC node. |

## Checked, no finding
- **Token leaks.**
  - alerts_box: the token lives only in the request and the wait thread. Replies / status are reason words and booleans; the log
    goes through `AB.redact` with the bot name masked; route exceptions return the class name only.
  - alert_bus: `_http` returns the exception CLASS name (the `/bot<token>/` URL never reaches a log); `redact` covers the token
    regex, `/bot***`, webhooks, the chat id, topics and account ids.
  - uvicorn runs at log_level warning (no access log), and the token is in a POST body, not a URL.
  - pc_report posts only booleans (`alert_bus`, `alerts_pc`); board, heartbeat and the ntfy status carry nothing from alerts.json.
  - Crash tracebacks show code lines, not values.
  - The token box is `type=password autocomplete=off`.
- **CSRF / origin.** The page needs X-Olympus-Alerts + JSON + Sec-Fetch-Site same-origin + Origin = Host, which needs a preflight
  the server never answers. W1 is on top. The lead's X-Forwarded-Host change is safe: a DNS-rebinding page is refused either way
  (Origin mismatch, or an unknown host name), checked.
- **Tailscale vs LAN vs Funnel.** `check()` refuses `Tailscale-Funnel-Request`. `private_why` needs EVERY X-Forwarded-For entry to
  be a tailnet address (Funnel and serve append the real client), plus Tailscale-User-Login, plus a ts.net Host, plus a loopback
  or tailnet peer. A LAN device faking all of those is refused (its peer is a LAN IP). Funnel only exists on :10000 (the caller),
  never 8766.
- **Rate limits.** alerts_box 8 presses / 10 min and 512-byte bodies; account box the same pattern, with names masked in its log
  and status.
- **History scan** (every commit since 2026-10-01 on olympus/pc, added lines only, values never printed): see "History" below.

## History
The full olympus/pc history (unshallowed here: 4,555 commits, back to 2026-10-16). Added lines were scanned with the site_privacy
detectors (keys / tokens / private ntfy topic / key assignments / broker ids / tailnet names); values were never printed.
- **Keys / tokens / private topic:** none outside tests. The test hits (test_obsidian_*, test_setup_everything, test_jarvis_tools,
  test_bridge_ingest, test_kalshi_*, test_money_machines, test_update_from_zip) are planted fakes. Nothing to rotate.
- **Account ids, MEDIUM (privacy, not a credential):** two real-looking 9-digit MFFU ids are in the **history** of
  docs/CLAUDE_REFERENCE.md and engine/new_accounts.py (39b639612), engine/account_rename.py (ffa76f571),
  research/handoff/2026-10-25/a5_logs/test_nt_outgoing.txt (737a25a30), research/handoff/2026-10-26/MORNING_REPORT.md (d562adc45),
  research/writeups/atlas-funded.md + INDEX.md (bda0731b9), tools/web_public/athena/library.json (9efefdf20) and
  tools/web_public/ergasterion/queue.json (9e34782a3). They are **not in today's tree**: the 2026-11-18 cleanup cut them, and
  test_repo_secrets c passes after fix 4. The 6-digit hit in engine/notify.py is the `mask_ids` docstring example.
- **Tailnet name, LOW-MEDIUM:** a real-looking `tail…` tailnet name in the history of docs/JARVIS_OLD_LOOK.md (4a17c9c8f, ca4ade5dc).
  Not in today's tree.
- The only fix for history is **making the repo private** (owner step 1). A history rewrite would mean force-pushing every
  branch, and copies already cloned keep it, so it is not recommended.

## Tests run on day-security3
- cross_site 24/24 (7 new), push_pairing 24/24, webpush 50/50, push 41/41, trade_alerts 83/83, notify 99/99, alerts_box 64/64,
  alerts_start_code 5/5 (new), alert_bus 86/86, rapid_arm 19/19, repo_secrets 14/14, public_build_privacy --fast 56/56.
- Suites that drive the real server through Starlette's TestClient (the new peer check sees its client): account_c 167/167,
  alerts_box 64/64, autopilot 7/7, board 59/59, brain 47/47, calendar_sync 143/143, fleet 131/131, kalshi_clock 40/40, launch_kit 129/129,
  live_link 72/72 (its link client now reports 127.0.0.1, as the tailscale serve proxy does), liveview_api 37/37, mind 67/67,
  money_goal 86/86, pc_command_center 60/60, phone_safety 28/28, presence 59/59, private_link 35/35, run_switch 50/50,
  start_api 117/117. Red on base 7adf312d too, not this branch: holo_api 52/53, pcdash_api 129/130.
