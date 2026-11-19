# Privacy (2026-11-14)

What private data the system holds, where it lives and who can see it. Three settings keep it that way.

## Your 3 settings (keep them)
1. **Netlify site stays Private**: in Netlify, your dashboard site (the one PUBLISH_NQ uploads to) keeps its visitor protection on (Netlify login / password). Never make it public.
2. **Tailscale only on your own devices**: the machines list at login.tailscale.com shows only your PC(s), your iPhone and the Jarvis VM. Remove anything else. Never turn on Funnel.
3. **Never share the ntfy alert topic**: the `nq-...` name in `%USERPROFILE%\.olympus\ntfy.json`. Anyone who knows it can read your trade pushes.

## Who can see what
| Data | Where it lives | Who can see it |
|---|---|---|
| Bank / card exports (CSV, OFX, QFX) | `%USERPROFILE%\.olympus\money_inbox\` | Only you (this PC) |
| Your money ledger, balances, net worth | `%USERPROFILE%\.olympus\money\` | Only you (this PC) |
| Household summary (month in / out, categories, subscriptions, runway) | `money_out\household.json` | You + your devices on Tailscale |
| Oikos from your bank, the money machines' real output | `money_out\` | You + your devices on Tailscale (anyone else gets the sample copy) |
| Cash you log from the iPhone | `%USERPROFILE%\.olympus\money_inbox\cash.jsonl` | Only you (sent over Tailscale) |
| Apple Health, card tracker (team ME1) | `data\inbox\`, `data\day\`, `money_out\` | You + your devices on Tailscale |
| Calendar links (secret ICS addresses) | `%USERPROFILE%\.olympus\calendars.json` | Only you (this PC) |
| Your day (shifts, free time, "Add to my day") | `data\day\`, `data\inbox\` | You + your devices on Tailscale |
| Agency clients, invoices, payments | `data\agency\` (totals in `money_out\agency.json`) | Only you; the totals also on your devices on Tailscale |
| Road to $10K figures (savings, jobs, Kalshi) | `data\goals_money.json` | Only you, unless "show on the phone" is on (then they are in the site) |
| Trading account names (the MFFU ids) | the PC (heartbeat, `data\accounts.json`, NinjaTrader) | You + your devices on Tailscale; the site shows the last 4 digits only |
| Eval balances, P&L, trades, positions, the strategy, the research | the Netlify site + the ntfy status topic | Anyone with the site's link if it were public; anyone who reads the status topic |
| NQ chart bars + our trades (prices, sides, micros, $; accounts by label like "Zlarior 50K", never an id or digits) | the ntfy chart topic = the status topic + `-bars` (`tools/pc_report.py` le-bars, through `public_status`) | Anyone who reads that topic (public on purpose, like the status topic) |
| Kalshi bot status (balance, P&L) | the Jarvis VM's feed, then the site's `kalshi.json` | Same as the site; the Kalshi keys never leave the VM |
| Trade pushes (entry, exit, $) | your private ntfy alert topic | Anyone who knows the topic name: keep it secret |
| Keys (Netlify token, Telegram / Discord, NinjaTrader login) | `%USERPROFILE%\.olympus\`, `data\alerts.json`, the PC | Only you (gitignored, never in the site) |
| Your name, email, birthday, Windows user name | not in the site, not in the status topic | Nobody: the build takes them out and a test checks every build |

## What the public side can never carry
The site the build makes (the zip / folder for Netlify) and the public ntfy status topic never hold: card or account numbers, emails, phone
numbers, street addresses, your name, email or age, keys or tokens, the alert topic, full broker account ids, personal folders
(`C:\Users\<you>\`), household / day / inbox / health / cards / agency / calendar files. The build's last step (`tools/site_privacy.py`)
masks or removes them; `tests/test_public_build_privacy.py` fails a build that still has one. What PUBLISH_NQ / SETUP_EVERYTHING step 1c
send to Netlify (`tools/pc_publish.deploy_set`, 2026-11-15) is checked again file by file with the same rule (a private file is kept
out and named; if the check cannot run, nothing is sent), and is only the lite set: the trade pictures, replay charts, write-ups, Data
City and the Mind vault stay on the PC and your Tailscale link. Nothing under `day/` or `me/` (the link's private routes) is ever sent,
and the Me hub's files (`me.json`, its cards / home / health-history kinds) are on the private list too (they were missing from it).

## The audit (team Q2, 2026-11-14)
| Risk | Found? | Fixed? | Test |
|---|---|---|---|
| Full broker account ids in the site (data.json + home.json, 17 places) | yes | yes: last 4 digits only | `test_public_build_privacy` d, f |
| Your full name in a published research doc (a Windows folder) | yes | yes: `<you>` (+ 5 repo files) | `test_public_build_privacy` f, `test_repo_secrets` b |
| Your git user name in the site (a commit "who") | yes | yes: dropped; the rule log writes "owner" | `test_public_build_privacy` b, d |
| Your age + birthday ("before I turn ..." with the date) | yes (the money card, a code comment) | yes: taken out of the site | `test_public_build_privacy` a, b, d |
| PC name and account id in the public status topic | yes | yes: dropped / last 4 digits | `test_public_build_privacy` e |
| Money / health / day data in the status topic | no | - | `test_public_build_privacy` e |
| Private files to anyone on the home WiFi (day, inbox, household, agency, the real Oikos) | yes | yes: 403 unless the PC itself or Tailscale | `test_private_link` a, b, f |
| Phone inbox open to the WiFi, oversize bodies read whole | yes | yes: Tailscale / PC only, 2 KB cap before reading | `test_private_link` d |
| A web page posting to the money inbox (DNS rebinding) | yes | yes: Host check, stalled clients dropped | `test_private_link` e |
| Path tricks (.., %2e%2e, backslash, NUL) | no | - | `test_private_link` c |
| Keys or tokens committed (tree + 3,996 commits) | no (only fake test keys) | - | `test_repo_secrets` a, e |
| Real broker ids in the repo (account code, tests, 2 logs, the reference) | yes | yes 2026-11-18 (row below) | `test_repo_secrets` c |
| Private paths not gitignored (dash/, site/, data/live_site/, data/health/, data/cards/, key files ...) | yes | yes | `test_repo_secrets` d |
| Real MFFU ids still in tests / docs / a fixture (2026-11-18) | yes (2 ids, ~90 places) | yes: last 4 digits in docs, fakes (...000006016) in tests | `test_repo_secrets` c |
| Lower-case / MFFUSFBLD25K-style ids, Tailscale IPs, tailnet names, keys in the status topic free text (Brain glance, Kalshi card) | could pass (none seen live) | yes: `public_status` masks them + the git-email canaries | `test_public_build_privacy` a, e |
| PC tailnet IP in README, Jarvis tailnet name in a doc | yes | yes: placeholders | `test_repo_secrets` b |
| The bot's own pages, buttons and the Road to $10K card answer any device on the home WiFi | yes | **no** (the trading server: needs your OK) | - |

## Honest limits
- If the Netlify site were made public, everyone could see the eval numbers, trades, positions, the strategy, the research and the Kalshi status. That is by design for your own dashboard: keep it Private.
- The status topic is public on purpose (its name is in the site): the eval numbers, positions and the bot's state, now without the PC name or account ids.
- The site check knows shapes (numbers, emails, ids, folders, keys). Private text in a brand-new form could slip through; the planted-value test covers the known ones.
- On the home WiFi the private files are now refused, but the bot server itself (port 8766) still answers any device there: its pages, the
  start / stop / kill buttons and the Road to $10K card (savings, jobs). The fix is one setting, `HOST=127.0.0.1` for the bot server (the Tailscale link keeps working, the phone on the WiFi would use Tailscale too). Not done here: it changes how the bot is reached, so it is the lead's / your call.
- The PC's tailnet address and the Jarvis VM's tailnet name are no longer in the repo (2026-11-18): the Tailscale app shows them.

## For the code (one rule each)
- Public site: anything new the build writes passes `tools/site_privacy.scrub` (the build's last step). Never add `household`, `agency`, `cards`, `health` or `day` to `tools/money_publish.KEEP`.
- PC link: a private route asks `engine/live_site.private_why(client, headers)` first. Health / cards JSON goes in `data/day/` or `money_out/` (both private routes), never a site folder.
- Public status topic: `tools/pc_report.lite()` ends with `public()`.
- Cloud PC-silent alert (`tools/pc_silent_check.py`): to the private topic only through the secret LE_NTFY_TOPIC (never printed); its fallback on the public status topic is plain text with no $, names or ids (`tests.test_notify` d).
- Tests: `python -X utf8 -m tests.test_public_build_privacy` (`--fast` without the full build), `tests.test_private_link`, `tests.test_repo_secrets` (`--state <state.json>` for the real account ids, `--history` for the history).
