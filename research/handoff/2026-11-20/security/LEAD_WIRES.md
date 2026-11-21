# LEAD_WIRES: day-security2 (round 2, 2026-11-20)

Branch `day-security2` (from origin/pc 69218831 + my 4 round-1 commits re-applied). Built for real this round: W3, W4, W6, W7.
W2 is NOT shipped: see W2 below, it needs the owner's yes. The round-1 notes are further down; W1, W5 and W8 have already landed.

| W | Files (bot side, review these) | Test |
|---|---|---|
| W3 the PC signs its public posts | `tools/pc_report.py` (`_signed`, 3 call sites, `MAX_STATUS_BYTES` 3900 -> 3800), `tools/status_sign.py` (`ensure_key`) | `tests.test_pc_report_sign` 18/18 |
| W4 phone pairing | `engine/push.py` (`pair_code`, `pair_payload`, `_tell_owner`, `intake(..., ntfy=None)`) | `tests.test_push_pairing` 18/18, `tests.test_webpush` 49/49 (2 checks updated: they pinned the old "newest 5 win") |
| W6 NQ chart | `tools/web_public/nq/nqbars.js` (`parse(text, nowS)` future guard, `verifyText`, `parseVerified`) | `tests.test_nqbars_sign` 5/5 |
| W7 data pipe | `engine/datafeed.py` (`_sign_msg` in `send`, `parse_answer(..., vk="pinned")`) | `tests.test_datafeed_sign` 8/8 |
| site / board (round 1 + a fallback) | `tools/web_public/pc_feed.js` (`canVerify`: a phone without WebCrypto works as before) | `tests.test_status_sign` 31/31 |

**Hard requirements, how each is met:**
1. No paid service, no secret in the repo. The key is made on the PC by `status_sign.ensure_key`, which runs on Windows only and
   never under LE_CLOUD or GITHUB_ACTIONS. The file is `<home>/.olympus/status_sign.json`, mode 0600, created with O_EXCL. The
   public key travels as `svk` in the PC's own signed core posts. Pin it with `python tools/status_sign.py check` after about 6 h.
2. Nothing stops working when something fails:
   - pc_report: no key, no `cryptography`, a broken key file or a too-big post means the post goes out exactly as before (tested).
     The run record gets `unsigned: <why>`, never an error, so a post is never dropped.
   - Trade alerts (private topic, phone app) are never signed or touched (tested).
   - Phone: no vk pinned, no WebCrypto, or a vk that will not import means it reads as before (tested).
   - Data pipe: unsigned answers are accepted until a vk is pinned, and a test's fake server is never checked.
3. W4: phones already in `data/push.json devices` stay, and keep re-sending their own subscription without a code. The owner does
   nothing (tested on an upgrade-shaped push.json). A new phone needs the one-time 8-digit code. The PC sends it to the owner's
   phones and to the private alert topic the first time an unknown phone asks, then at most every 6 h. At most 30 wrong codes a
   UTC day; after that no new phone joins until tomorrow. A full list (5 phones heard from in 14 days) never pushes one out.
4. Tests: trade_alerts 21/21, notify 96/96, pc_bars 75/75, live_publish 86/86, push 41/41, webpush 49/49, datafeed 42/42, and the
   pc area (all but win_scripts): see the REPORT, round 2.

**Still to wire (not my files):**
- **W4, phone side (`tools/web_public/jarvis/push-ui.js`, the jarvis owner).** Without this, a NEW phone cannot pair. The owner's
  current phone is not affected.
  In `postSub` add the code to the sealed body:
  `await sendSealed('sub', { sub: {...}, key: wp.k, ua: env().device, pair: String(store.get().pair || '').replace(/\D/g, '') || undefined }, wp);`
  Add `async function pair(code) { store.set(Object.assign({}, store.get(), { pair: String(code || '').replace(/\D/g, '').slice(0, 8) })); return check({ repost: true }); }`
  and export it on `window.OLY_PUSH`.
  In the 'waiting' card, once 2 minutes have passed since `posted`, show one numeric input: "Your PC sent a code to your other phone
  (or your alert topic). Type it here", which calls `OLY_PUSH.pair(value)`. Bump the jarvis cache (`jarvis-vNN`) and `sw.js`.
- **W6, one line in `tools/web_public/nq/nqchart.js` `fetchPost()`:** `const p = await B.parseVerified(t, S.feed);` in place of
  `const p = B.parse(t);`. `parse` already ignores a future-dated chart with no change there. Bump `nqbars.js?v=b1` to `?v=b2` in
  nq.js and nqchart.js, and the sw cache.
- **`engine/alerts_plus.py:664` (optional):** add `"unpaired", "full", "told"` to the logged keys, so the ops log shows strangers.
- **The VAPID key changing** (rare: only when data/push.json is lost) gives the owner's phone a new endpoint, so it needs the code
  once. The code goes to his private alert topic, because his old subscription no longer works under the new key.
- **Pinning order:** land W3, let the PC run 6 h, run `python tools/status_sign.py check`, pin the key with about 4 posts an hour
  for 6 h+ as `"vk"` in `tools/web_public/status_feed.json`, then publish. `tests.test_status_sign` g checks that the pinned vk is a
  real P-256 key.

## W2 (HIGH, NOT shipped: needs the owner's yes): the bot server answers the home WiFi

Checked what uses the bot by a non-localhost address:
- add-account and kalshi-live go through Tailscale serve to 127.0.0.1: fine.
- The iPhone Shortcuts (`/inbox/day`, `/inbox/board`) use `https://<pc>.<tailnet>.ts.net`, a serve proxy to 127.0.0.1: fine.
- NinjaTrader talks through files (LE_BarFeed.cs / LE_Feed.cs), and engine/ninjatrader uses 127.0.0.1: fine.
- TradingView webhooks have no public route to the PC and are not in use: fine.
- **But the PC dashboard's Settings card "Open on your phone"** (`web/js/page-settings.js` <- `/api/net`, server.py:454) hands out
  `http://<LAN / Tailscale IP>:8766` links, and docs/LIVE_DASHBOARD.md:60 still calls that path "unchanged". If the owner saved one
  of those on a phone, `HOST=127.0.0.1` breaks it. I cannot confirm he never did, so it is not shipped.
Patch, once he says yes. In `scripts/run_bot.ps1`, before the `command :` line:
`if (-not $env:HOST) { $env:HOST = '127.0.0.1' }   # the phone uses the Tailscale link (:8444), never the WiFi`.
Change the Settings card to show the `https://<pc>.<tailnet>.ts.net:8444/` link (engine/phone_link) in place of the IP links.
Owner one-liner: "From now on, open the bot on your phone only with your PC link (the :8444 one). The old plain number address stops
working, so anyone on your WiFi can no longer press start/stop."

---

# LEAD_WIRES: day-security 2026-11-20

These are fixes in files a helper may not edit (engine/*, server.py, scripts/*.ps1, *.bat, nq/, jarvis/, sw.js). Each one has the
exact change and a test. They're in order of risk. W1 and W5 are CRITICAL, so land them first.
Already on `day-security` (no wiring needed): `tools/status_sign.py`, the site-side check in `tools/web_public/pc_feed.js`,
`tools/board.py` (unsigned owner notes are labelled and not counted), `tools/site_privacy.py` (the key file is private),
`tests/test_status_sign.py` (29/29), and `tests/run_area.py` (privacy + board areas).

---

## W1 (CRITICAL): the bot server takes POSTs from any web site (server.py)

**Hole.** Every `POST /api/*` route reads `await req.json()`, and that parses a `text/plain` body too. A text/plain POST is a
"simple" request, so the browser sends it to `http://localhost:8766` **without asking first**. Any page open in a browser on the
PC (an ad, a link) can therefore POST `/api/live/start {"adapter":"ninjatrader","armed":true,...}` (with its own settings),
`/api/live/kill` (flatten mid-trade), `/api/live/stop`, or `/api/live/arm` (the phrase is in the public repo). A DNS-rebinding
page gets in the same way: these routes never look at Host. Proven here: without the guard, FastAPI hands
`{'adapter': 'ninjatrader', 'armed': True}` from `Origin: https://evil.example` to the route. Chrome and Edge now show a
"local network access" prompt first. Firefox and older browsers do not.

**Fix.** Copy `research/handoff/2026-11-20/security/cross_site.py` to `engine/cross_site.py`, then add 3 lines to server.py right
after the CLOUD GUARD block:

```python
# ---- CROSS-SITE GUARD ---- (engine/cross_site.py, day-security 2026-11-20): a POST from another web site / a rebinding name is refused
from engine import cross_site as _xs
_xs.install(app)
# ---- END CROSS-SITE GUARD ----
```

What still works: the PC's own dashboard (same origin), the phone on the Tailscale link (`*.ts.net`), a page opened by LAN IP,
curl/scripts on the PC (no Origin), and the TradingView webhooks (exempt, they keep their own key). Cloud mode is skipped (it has
cloud_guard). Switches: `LE_ALLOWED_HOSTS=name1,name2` adds host names; `LE_CROSS_SITE_GUARD=0` turns the guard off.
**Test.** Copy `research/handoff/2026-11-20/security/test_cross_site.py` to `tests/test_cross_site.py` (it already imports
`engine.cross_site` once that file exists) and add `"cross_site"` to `AREAS["privacy"]` and `AREAS["pc"]`. Today: 15/15 against the
handoff copy, including a real FastAPI TestClient check.
Before landing, check that no page of the bot posts from another origin, e.g. a `web/` page that calls `http://127.0.0.1:8766` while
it is open on `localhost`. If one does, use the same name in both places.

## W2 (HIGH): the bot server answers any device on the home WiFi (scripts/run_bot.ps1)

`HOST` defaults to `0.0.0.0`. W1 stops web pages, but anyone on the WiFi can still `curl -X POST http://<pc-lan-ip>:8766/api/live/kill`
(docs/PRIVACY.md already lists this as "needs your OK"). Fix in `scripts/run_bot.ps1`, just before the line that prints `command :`:

```powershell
if (-not $env:HOST) { $env:HOST = '127.0.0.1' }   # day-security 2026-11-20: the phone uses the Tailscale link (:8444), never the WiFi
```

The phone keeps working through `https://<pc>.<tailnet>.ts.net:8444/` (engine/phone_link.py proxies to 127.0.0.1:8766). Anything
that opens `http://<lan-ip>:8766` from the phone stops working. Tell the owner in one line.
Test: `tests/test_win_scripts` must NOT be run here. Add a grep check to `tests/test_phone_link.py`:
`assert "$env:HOST = '127.0.0.1'" in open('scripts/run_bot.ps1').read()`.

## W3 (HIGH): sign the PC's public posts (tools/pc_report.py) and pin the key once

**Hole.** The status topic name is public, and ntfy lets anyone post. One forged `le-live` post dated in the future:
(a) shows fake balances, verdicts and trades on every page for 12 h. Site side, a future-dated post now never wins (done).
(b) replaces `wp`, the PC's push keys. The owner's phone then "re-subscribes" to the forger's keys: the forger can push fake
"trade closed" or "update now" notices to the phone, and the phone drops the PC's real alerts.
(c) puts a fake `owner_note` ("Decide atlas-on-rapid: YES") at the top of every Claude session. Board side, it is now labelled
`[ntfy-unsigned]` and not counted (done).
Proven offline: one forged post made `board.py read` show Zlarior "PASSED $99,999" and "OWNER NOTES NOT ANSWERED: 1".

**Fix (PC side).** In `tools/pc_report.py`, add near `ntfy_post`:

```python
# ---- STATUS SIGN ---- (tools/status_sign.py, day-security 2026-11-20): every public post carries the PC's signature
def _signed(body: str, core: bool = False) -> str:
    """The exact text + ,"sg":"..."}; the core also carries "svk" (the public key, for pinning once). No key / no `cryptography` /
    over 4,000 bytes: the body as it was. Never raises."""
    try:
        from tools import status_sign as _ss
        k = _ss.load_key()
        if not k and os.environ.get("LE_STATUS_SIGN", "1") != "0":
            _ss.main(["keygen"])                  # once: <home>/.olympus/status_sign.json (0600), prints only the public key
            k = _ss.load_key()
        if not k or not str(body).startswith("{"):
            return body
        b = str(body)
        if core:
            withvk = b[:-1] + ',"svk":"' + _ss.vk_of(k) + '"}'
            if len(withvk.encode("utf-8")) <= 3905:
                b = withvk
        out = _ss.sign_text(b, k)
        return out if len(out.encode("utf-8")) <= 4000 else body
    except Exception:  # noqa: BLE001
        return body
```

Then change the three public posts:
- the ext loop: `ok, why = ntfy_post(cfg["ntfy"], cfg["status_topic"], _signed(body), priority="min", http=http)`
- the core: `ok, why = ntfy_post(cfg["ntfy"], cfg["status_topic"], _signed(body, core=True), priority="min", http=http)`
- the chart bars: `ok, w = ntfy_post(cfg.get("ntfy") or NTFY_DEFAULT, topic, _signed(body), priority="min", http=http)`

Also lower `MAX_STATUS_BYTES` from 3900 to 3800, so core + svk + signature (about 190 bytes) always stays under ntfy's 4,096-byte
limit (over it, ntfy turns the post into an attachment). Leave the private alert topic unsigned: nobody else knows its name.

**Pin the key (lead, once, about 6 h after W3 is on the PC):** `python tools/status_sign.py check` lists every key it saw, with its
post count and time span. Copy the key that signed ~4 posts an hour for 6 h+ into `tools/web_public/status_feed.json` as `"vk"`.
Optionally check that its first 6 characters match what the PC printed at keygen. From then on the site and the board ignore
every unsigned post. (Pinning before W3 runs on the PC blanks every page, because nothing would verify.)
**Test (add to tests/test_trade_alerts.py or a new tests/test_pc_report_sign.py):** with `LE_STATUS_SIGN_KEY` pointing at a temp key,
a fake `http` records the core body; assert `status_sign.verify_text(body, vk)`, `json.loads(body)["svk"] == vk`, and
`len(body.encode()) <= 4000`. Without `cryptography`, the body is unchanged.

## W4 (HIGH): anyone can subscribe to the owner's trade alerts and push the owner's phone off the list (engine/push.py intake)

**Hole.** A `sub` request only has to be sealed to the PC's box key and carry the VAPID key. Both are public, in every status post's
`wp`. So any visitor who taps "Allow" on the public site, or a script, gets every real-account entry/exit with the account name and
$. `MAX_DEVICES = 5` keeps the newest 5, so five fake subscriptions evict the owner's phone. And `_pc_send` skips the private ntfy
backup when "the phone app has it", i.e. when a stranger's browser took it. Result: the owner gets no trade alerts, silently.

**Fix (engine/push.py `intake`, the `if kind == "sub":` branch):** (1) a pairing code, and (2) no eviction of a recent phone.

```python
            if kind == "sub":
                subs = parse_subs(body.get("sub"))
                if not subs or body.get("key") != c["public"]:
                    out["ignored"] += 1
                    continue
                pair = str((_read_json(path).get("pair") or "")).strip()          # day-security: set on the PC's private /safety/ page
                if not pair or not _hmac.compare_digest(str(body.get("pair") or "").strip(), pair):
                    out["ignored"] += 1                  # no pairing code = no trade alerts (a stranger's "Allow" lands here)
                    out.setdefault("unpaired", 0)
                    out["unpaired"] += 1
                    continue
```

Before `keep = sorted(...)[-MAX_DEVICES:]`, never drop a phone seen in the last 14 days to make room:

```python
        recent = [d for d in devs.values() if now - int(d.get("seen") or 0) < 14 * 86400 and d["id"] not in out["added"]]
        if len(devs) > MAX_DEVICES and len(recent) >= MAX_DEVICES:
            for sid in list(out["added"]):               # the list is full of recent phones: the new one waits, nobody is pushed out
                devs.pop(sid, None)
            out["added"] = []
```

Pairing code: `data/push.json "pair"` = 8 random digits, made on first use (`secrets.randbelow(10**8)`). The private `/safety/`
page (engine/phone_safety.py, tailnet only) shows it. `tools/web_public/jarvis/push-ui.js` (the jarvis helper's file) asks for it
once on "Allow" and puts it in the sealed body: `sendSealed('sub', { sub, key: wp.k, ua, pair })`. When `out["unpaired"]` is
non-zero, send one line to the private ntfy alert topic: "A phone without the pairing code asked for your trade alerts: ignored".
Until this lands, have `_pc_send` always ALSO post entries/exits to the private ntfy topic, so the owner never misses one.
Test: tests/test_push.py: a sub without `pair` is ignored; one with the right `pair` joins; 5 recent phones + 1 new means nobody
evicted.

## W5 (CRITICAL): PC scripts download and run code from the OLD GitHub account, which no longer exists

The old account (the one in CLAUDE.md's "never use the old ... repo") is gone: a GitHub user search finds 0 users and its Pages site
answers 404. A deleted GitHub username can be registered again by anyone. These still fetch from `<old>.github.io/nq-dashboard/`:
- `FRESH_START.bat`: `irm https://<old>.github.io/nq-dashboard/pc/FRESH_START.ps1 | iex`. **This runs remote code every time.** The
  same command is in docs/CLAUDE_REFERENCE.md:83 and docs/MOVE_TO_MAIN_PC.md:25, and the published copies are in
  `tools/web_public/pc/*.bat` and `pc/FRESH_START.ps1`.
- `PC_CARE.bat`, `STATUS.bat`, `CLEAN_STORAGE.bat`: the same, when the bat runs outside the bot folder.
- `engine/eval_life.py:486 SITE_HOME` (`--anchor-from-site` sets the eval balance/floor anchor from it, after a Y/N),
  `scripts/move_bot.ps1:48` and `scripts/pc_status.ps1:33` (read home.json from it).
- `tools/kalshi_kit/public/SETUP.md:32` (`curl ... kalshi_status_vm.py`, run on the Kalshi VM), `tools/kalshi_kit/install_windows.ps1`,
  `tools/kalshi_kit/print_sha.py`, `engine/push.py:50-51` (APP_URL / VAPID subject: harmless), `engine/kalshi_publish.py`,
  `engine/live_publish.py`.

**Fix.** Replace `https://<old>.github.io/nq-dashboard/` with `https://dcondax1-wq.github.io/` in each file above (checked: the new
site serves `pc/FRESH_START.ps1`, 200). One command, from the repo root, then review the diff:

```bash
OLD=$(git grep -h -o -m1 -E "[a-z0-9]+-coder\.github\.io/nq-dashboard/" -- FRESH_START.bat | head -1)   # the old site, read from the repo
git grep -l "$OLD" -- '*.bat' '*.ps1' '*.md' 'engine/*.py' 'tools/kalshi_kit/*' 'tools/web_public/pc/*' \
 | xargs sed -i "s#https://$OLD#https://dcondax1-wq.github.io/#g"
```

Then add to `tests/test_repo_secrets.py`: no `.bat`, `.ps1` or `engine/*.py` file may contain `-coder.github.io`. The JS fallbacks
(`location.origin : 'https://<old>-coder.github.io'` in launcher.js, live.js, more.js ...) only matter on a `file:` page. Switch them
to the new site in the same pass (several helpers' folders: one sed).
**Owner, hands-only (free, 3 min):** register the old username as a new free GitHub account, so nobody else can take it. It needs
an email GitHub has not seen, e.g. a `+old` gmail alias.

## W6 (MEDIUM): the NQ chart reads its own topic unsigned (tools/web_public/nq/nqbars.js, nq/ helper)

Once W3 signs the chart post, verify it in `nqbars.js` fetch the same way the feed does: `if (feed.vk) text = await
window.PC_FEED.keepSigned(text, feed.vk)` before `parse(text)` (pc_feed.js is already loaded on that page). Also drop a post whose
`t` is more than 600 s in the future (`PC_FEED.SKEW_S`). Until then, a stranger can draw a fake chart (no money impact).

## W7 (MEDIUM): the data pipe trusts any answer on its topic (engine/datafeed.py)

Its topic name is in the public repo. A forged `le-data` answer, with its own announced sha256, can put fake NinjaTrader bars and
trades into Claude's `data/` and quietly poison research. A forged request makes the PC pack and upload (capped at 8 a day).
Fix: in `send()`, the meta message goes through the same `_signed()` as W3 (`status_sign.sign_text(msg, load_key())`). In
`parse_answer()`, when `status_sign.feed_vk()` is set, require `status_sign.verify_text(m["message"], vk)` and return None
otherwise. Requests stay unsigned: the cloud has no key, and the daily cap already bounds them. Test: tests/test_datafeed.py, a
forged answer with a correct sha256 but no signature is ignored once a vk is pinned.

## W8 (MEDIUM, privacy): the owner's birthday is in the public repo (engine/money_goal.py)

`engine/money_goal.py` (3 places) and `tests/fixtures/argus/home_real.json` (2) carry the car goal with the owner's age and an exact
date, which together give the birthday. The public site already scrubs it (site_privacy AGE_RX), but the repo is public. Change the
text to "by Feb 2027" (no age, no day), and update the 2 assertions in tests/test_money_goal.py. Git history keeps the old text,
which is why the owner step "make the repo private" (REPORT.md) is the real fix.

## W9 (housekeeping): the service worker cache

`tools/web_public/pc_feed.js` changed. Bump `CACHE` in `tools/web_public/sw.js` (le-public-v167 -> v168) when landing, as usual,
so phones load the new check.
Also run `python tools/archive_build.py` when landing. `tests.test_archive_page` was already 46/47 (stale index, 203 vs 210
write-ups) before this branch added `research/writeups/security-2026-11-20.md`.

## Trade-off to know (tools/board.py, already on this branch)
Until the vk is pinned (W3), every event that reaches Claude only through the public status channel is labelled `[ntfy-unsigned]`
and not counted under "OWNER NOTES NOT ANSWERED". That includes the owner's real notes from the phone: they still show in
NEWEST EVENTS. To relax this, count them again but keep the label. Do not drop the label.
