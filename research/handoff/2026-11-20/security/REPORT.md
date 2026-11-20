# Security check, 2026-11-20 (day-security)

## For the owner (read this part)

**What a stranger can see or do today, and the fix:**

| # | What a stranger can do | How bad | Fix |
|---|---|---|---|
| 1 | A web page open on the PC's browser can **start, stop or kill the real bot** (it sends a hidden request to the bot's own address on the PC) | CRITICAL | Lead wires a guard (W1, ready + tested) |
| 2 | Some PC fix buttons (FRESH START, and PC CARE / STATUS / CLEAN STORAGE when run outside the bot folder) **download and run code from your OLD GitHub account's site**. That account is deleted, so anyone can take its name | CRITICAL | Lead points them at the new site (W5). You: take the old name back (step 2) |
| 3 | Post fake numbers to the public status channel: fake balances on every page, a fake "owner note / Decide YES" for Claude, and they could swap your phone's push keys | HIGH | **Fixed today on the site and for Claude** (a post dated in the future never wins; Claude marks unsigned notes). Full fix = the PC signs every post (W3) |
| 4 | Tap "Allow" on your public site and **get your trade alerts**. Five strangers push your phone off the list, and then you get no alerts at all | HIGH | Pairing code (W4) |
| 5 | Anyone on your home WiFi can start/stop/kill the bot | HIGH | Bot listens only on the PC + Tailscale (W2) |
| 6 | Read the whole Olympus repo: it is **public**, not private. It holds your strategy, STATE, plans, your old GitHub name (your email's first half) and your birthday | MEDIUM-HIGH | You: make it private (step 1) |

**What is safe (checked):** the phone remote (only your GitHub login can write it), add-account and Kalshi-live (only your Tailscale
devices, the page itself and your typed phrase), the public site and status channel (no account ids, emails, keys, PC name or
private topic names), the GitHub workflows (no secrets reach strangers), and every key-shaped value in the repo history (all fakes
in tests). Nothing needs rotating.

**Your steps (hands only):**
1. GitHub -> repo **olympus** -> Settings -> General -> bottom: **Change visibility -> Private**. The PC already uses your login,
   so updates keep working. Your public site is a different repo, so it is not affected.
2. Make a free GitHub account with your **old** username (the one before dcondax1-wq) so nobody else can take it. Use a new
   email, e.g. your gmail with `+old` before the @.
3. Nothing else: the lead wires W1-W5 and Claude pins the PC's key once the PC has signed for 6 hours.

---

## Detail (for the lead)

### 1. Privacy: what is public
- **The repo `dcondax1-wq/olympus` is public** (GitHub API: `visibility: public`). `update_source.json` calls it "the private
  backup repo", so the owner thinks it is private. Public in it: the owner's birthday (engine/money_goal.py x3,
  tests/fixtures/argus/home_real.json x2: the car goal states an age and an exact date); the old GitHub handle (= the local part of the owner's
  gmail) in ~220 places; the whole strategy, STATE.md, docs, the plan and nickname-level balances. No real account ids, emails,
  phone numbers, tailnet names or keys (checked: site_privacy scan over every tracked file. Hits are test fakes and agency demo
  data, i.e. public business listings).
- **Published site** (built output, 3,859 files, via `pc_publish --provider folder --strict`, plus a read-only crawl of
  dcondax1-wq.github.io and its home.json, data.json, board.json, accounts.json): **0 private findings**. Only the agency demo
  fixtures (public business addresses), `git@github.com`, and a font licence email. The old handle is in 40 site JS/MD files
  (URL fallbacks), fixed by W5's sed.
- **Public status topic** (last 2 h read, 24 posts): 0 findings. No PC name, ids, emails or keys.
- **Images/EXIF/source maps:** no `.map` files are published. Images were not fetched (the crawl skipped binaries). site_privacy
  already scans binary strings in the build.
- **The Pages repo's git history** could not be read from this session (outside its GitHub scope): not checked.

### 2. Integrity: a forged post on a public ntfy topic
| Reader | What a forged post did | Now |
|---|---|---|
| Every site page (`PC_FEED.fetchLatest`) | Picked the newest `reporter.t`, so a post dated 2099 won for 12 h: fake balances, verdict, trades | **Fixed:** never a post >10 min in the future. With `vk` pinned, only signed posts (WebCrypto ECDSA P-256) |
| Push opt-in (`jarvis/push-ui.js` reads `wp` from the same feed) | A forged `wp` made the phone re-subscribe to the forger's keys: fake pushes, real alerts lost | Fixed once `vk` is pinned (same check) |
| Claude's board (`tools/board.py read`, every chat) | Showed Zlarior "PASSED $99,999" and an open "owner note: Decide ...: YES" (proven offline) | **Fixed:** future posts dropped. Unsigned feed = events labelled `[ntfy-unsigned]`, not counted as owner notes, header warning. With `vk`: forged posts never reach it |
| PC push relay intake (`engine/push.intake`) | Anyone can subscribe (both keys are public) and evict the owner | W4 |
| Data pipe (`engine/datafeed`) | Forged answers -> fake bars in Claude's data | W7 |
| NQ chart (`nq/nqbars.js`) | Fake chart | W6 |
| Kalshi bot / PC trading loop | Nothing reads public ntfy (checked: only push.py, datafeed.py, pc_doctor, pc_silent_check read topics) | safe |

The check is free and uses no account: an ECDSA P-256 key on the PC (`<home>/.olympus/status_sign.json`, never in the repo), the
public key `vk` in `status_feed.json`, and the signature as one extra JSON field at the end of the post (old readers ignore it).
Rollout order: W3 on the PC -> 6 h of signed posts -> `python tools/status_sign.py check` -> pin `vk`.

### 3. Who can trigger what
| Path | Who can | Verdict |
|---|---|---|
| Phone remote (`control` branch: update, restart, kill, flatten, start-on-Sim) | Repo writers only: collaborators = the owner alone. Note: every Claude helper session can push too (no branch protection), and so can `pc` (what the PC auto-updates to) | OK for strangers. Helpers stay rule-bound |
| :8444 add-account, kalshi-live arm, /safety | `private_why` (tailnet IP + `Tailscale-User-Login`, no Funnel) + page header + JSON + same Origin + typed phrase | OK |
| :8766 `/api/live/start|stop|kill|arm|golive` and the other POSTs | **Any web page in a PC browser (CSRF/DNS rebinding) and any WiFi device**. No origin/host check, `req.json()` takes text/plain | **CRITICAL -> W1 + W2** |
| Update now via ntfy / a fake "update" push | Nothing acts on ntfy. A fake push notice can only mislead the owner (W3/W4) | OK after W3 |

Small note: `private_why` accepts any signed-in tailnet user. If a PC node is ever shared to another tailnet, its users would pass.
Don't share the PC node.

### 4. Secrets hygiene
`git log -p` on all 245 commits in this clone (shallow: older history not here) for private keys, GitHub/Slack/Stripe/OpenAI/Google/
Telegram/Netlify/ntfy tokens, JWTs, push endpoints, `key = "..."` assignments and the private ntfy-topic shape. Hits are only in
tests (test_obsidian_brain/sync, test_setup_everything, test_jarvis_tools, test_bridge_ingest, test_kalshi_live/publish,
test_money_machines, test_update_from_zip), and all are planted fakes the tests look for. Nothing to rotate. The workflows use
repo secrets correctly (schedule/dispatch only; the one PR workflow is read-only and only for chatgpt/* branches). PC-side docs:
no values, only names.

### Tests run
- `python -X utf8 -m tests.test_status_sign`: 29/29 (includes the phone's WebCrypto verifying the PC's Python signature).
- `research/handoff/2026-11-20/security/test_cross_site.py`: 15/15 (with a real FastAPI TestClient; without the guard the route
  takes `{"adapter":"ninjatrader","armed":true}` from evil.example).
- `python tests/smoke.py`: 7/8. The one red is `test_zenith_mode`: `No module named 'playwright'` in this container (Python
  playwright not installed), unrelated to this change.
- Area runs: see the end of this file.
- `python tests/run_area.py privacy`: 5/5 suites, 163/163 (public_build_privacy 59, private_link 35, repo_secrets 12,
  phone_safety 28, status_sign 29).
- `run_area.py board --only board,bots_back,payout_coach,edge_chip,decide,status_sign` (BOARD_NO_BROWSER=1): 243/243 after one
  fix (test_board pins the post's exact keys, so the "signed" mark now sits beside the post). `zenith --only feed_accounts`: 25/25.
  Browser suites were not run: no screen changed.
- Trade-off: until the vk is pinned, the owner's real phone notes that reach Claude only through the status channel are labelled
  `[ntfy-unsigned]` and not counted as "not answered" (they still show in the events). See LEAD_WIRES, last section.
