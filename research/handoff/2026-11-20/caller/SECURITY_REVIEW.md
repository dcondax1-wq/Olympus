# AI caller: security review (day-security, 2026-11-20)

Reviewed: branch `day-caller` 6d8a2df6 (`tools/caller/`, `CALLER_*.bat`, `tests/test_caller.py`, `research/handoff/2026-11-20/caller/`).
Read-only on that branch. The fixes are one tested patch, `research/handoff/2026-11-20/caller/security_fixes.patch`
(on day-security2). It applies cleanly to 6d8a2df6 (`git apply` checked on a fresh copy), with:
- the new `tests/test_caller_security.py` 25/25
- the existing `tests/test_caller.py` 81/81 (2 checks updated: a consent now needs its confirm)
- the simulator: 8 personas, 100%

Apply: `git checkout day-caller && git apply research/handoff/2026-11-20/caller/security_fixes.patch` (file taken from day-security2).

## For the owner

| What a stranger could do | How bad | Now |
|---|---|---|
| Fill the "Call me" form with **someone else's number**, so the AI calls them as if they had agreed ($500+ a call in Maryland) | CRITICAL | Fixed in the patch: the number must be one of our leads, and the business must confirm by calling us once from that line, or you approve it |
| Read what businesses said on the calls, if the call records are pushed to a GitHub branch (the repo is public) | HIGH | Your choice: keep the call records on the PC only (step 1) |
| Call your Twilio number over and over, and you pay for every AI minute | HIGH | Fixed: 3 calls a day per number, 40 a day total, then a short recorded message |
| Flood the caller's public address and slow down the trading PC | HIGH | Fixed: at most 16 connections at once, and a slow one is cut after 15 s |
| Reach the trading bot through the caller | none found | The public address only reaches the caller; the bot's links stay private |

1. Keep call records on the PC (no inbox branch) until the repo is private.
2. When a consent is waiting: `python -m tools.caller.consent list`, then `python -m tools.caller.consent approve <number>` once you have
   checked it is really them. Or wait for them to call in.
3. Nothing else: the caller stays OFF until you sign up and type START CALLING.

## Findings

| # | Severity | Area | Finding | Fix |
|---|---|---|---|---|
| C1 | **CRITICAL** | consent | `POST /consent` takes any US number. Nothing ties it to a real lead or to the person who owns the line. `run.lead_for` turns a consent for an unknown number into a lead, so the dialer queues it. One curl = an AI sales call to a person who never agreed (TCPA + Md. 14-4502: $500/call, x3 willful). | Patch: `consent.record(..., leads=)`: the number must be one of our leads and `lead_id` must be that lead's id. Every consent starts PENDING; `valid_for` needs a `confirm` row (`inbound_call` when that number calls our Twilio number, with StirVerstat recorded; or `owner` via `python -m tools.caller.consent approve`). The form's reply says "call us once from that line". |
| H1 | **HIGH** | privacy | LEAD_WIRES item 4 says to copy `<home>/caller/inbox/*.jsonl` as-is to an "agency-inbox" branch. Those rows hold `summary` (the person's own words, 400 chars), emails, outcomes. `dcondax1-wq/olympus` is public (security REPORT), so this publishes third-party speech and emails. | Not in the patch (it's a routing decision). Never push caller files to a branch of a public repo. If the inbox must travel, send only `{business, outcome, ts}`, and only after the repo is private. `tools/site_privacy` now treats `caller.json`, `dnc.txt`, `linetype.json` as private (`.jsonl` already was). |
| H2 | **HIGH** | cost | Inbound calls had no cap. Anyone can call the Twilio number repeatedly, and every call is ConversationRelay + TTS + Claude minutes on the owner's card. | Patch: `inbound_per_number_day` 3, `inbound_per_day` 40 (settings.json). Over the cap = the short `<Say>` + `<Hangup/>` (no AI, cents). |
| H3 | **HIGH** | trading PC | Funnel is public and has no rate limit. `ThreadingHTTPServer` makes one thread per connection with no read timeout, so a flood or slowloris eats the trading PC's CPU and memory. | Patch: `BoundedServer` (16 at once; extra ones closed), handler `timeout = 15`, relay `ws_idle_s` 60. Also recommended for CALLER_ON.bat: `start "Olympus caller" /min /low python ...` (below-normal priority, like pc_selftest). |
| M1 | MEDIUM | email | The consent form's `email` and the model's `book_slot` / `send_email` `email` were unchecked free text (`[:120]`). `"a@b.com, x@y.com"` or a newline + `Bcc:` reaches the email autopilot's To line, making it a spam relay from the agency's address. A caller can do this by prompt injection ("send it to ..., ..."). | Patch: `actions.valid_email` (one plain address, 120 chars) in `queue_email`, `consent.record` and `ClaudeBrain.respond`. |
| M2 | MEDIUM | webhooks | Twilio signatures carry no timestamp. A replayed signed `/voice/inbound` minted a fresh relay token each time, and that token goes back in the TwiML response, giving a WebSocket straight to the Claude brain. Needs a captured request (TLS ends on the PC, so it's hard), but it's cheap to close. Outbound relay tokens never expired. | Patch: each inbound `CallSid` is used once (24 h memory; a replay gets the short message); relay tokens expire after `relay_token_s` 180 s and stale ones are pruned. |
| M3 | MEDIUM | consent | Rate limit was global (30/min), so one sender could burn it for everyone. `X-Forwarded-For` was stored as sent, but Funnel's proxy APPENDS the real client, so the first entry is attacker-chosen. CORS `*`. | Patch: per sender 5/hour on the LAST XFF entry, 200/day total, optional `consent_origins` allowlist (403 for other Origins). CORS `*` is harmless (no cookies, no session: CSRF has nothing to ride on). An allowlist stops browser-driven spam, not curl; C1 is what makes forgery useless. |
| M4 | MEDIUM | kill switch | `onoff off` stops new dials within a minute, but a live call ran on up to `max_call_seconds` (300 s). `onoff off` alone also left Funnel (the public address) open. | Patch: an outbound call ends with a goodbye at its next turn once OFF, and the OFF message says CALLER_STOP.bat closes the public address. CALLER_STOP.bat itself is good: OFF + kill the window + `funnel --https=10000 off`. |
| M5 | MEDIUM | prompt injection | The brain's tools are limited to book / demo / pay link / end. Nothing can reach trading, files or the network beyond the outbox and one ntfy ping (good). But `speech_filter` only blocks claims to be human: an injected caller can still get the model to promise a discount, "free forever" or a guarantee, which is a reputational / contract risk. | Not in the patch. Suggestion: a second filter for money promises (`\$\d`, "free", "discount", "guarantee", "refund") that swaps the sentence for "{owner} will confirm that by email". `payment_link` is the owner's fixed link, so no payment detail can be injected. |
| L1 | LOW | Funnel / ports | Port isolation holds. `CALLER_ON.bat` opens Funnel only on `:10000 -> 127.0.0.1:8790`. Funnel is per host:port, so `:8444` (phone_link) stays tailnet-only. `server.serve` refuses any host but 127.0.0.1. The bot server (8766) is not behind any Funnel, and `live_site.private_why` refuses a `Tailscale-Funnel-Request` anyway. The PC's `<pc>.<tailnet>.ts.net` name becomes public in the consent form URL. It is already in Certificate Transparency logs (Tailscale HTTPS certs), but `site_privacy` (TAILNET_RX) will flag it in a strict public build. | Lead's call: allow-list exactly the caller URL in the demo pages' build, or keep the form off the public Pages site (LEAD_WIRES item 2 already says "leave the block out until the PC has the address"). |
| L2 | LOW | signatures | The check signs `public + path` with no query, which matches both `VoiceUrl` (funnel.py hook) and `StatusCallback` (run.tick), and `compare_digest` with an empty token is refused. If `public` ever differs from the URL Twilio was given (a trailing slash, another port), it fails closed: calls get Twilio's error. `MAX_BODY` 4 KB could also refuse an unusually large legit webhook (fails closed). | Optional: raise `/voice/*` to 16 KB. |
| L3 | LOW | keys | `caller.json` sits in `%USERPROFILE%\.olympus` (outside the repo; `setup_keys.save` refuses inside the repo; getpass input). `chmod 600` does nothing on Windows (the user-profile ACL protects it). `redact()` covers logs / transcripts / outbox / calls. Branch scan: no key-shaped value except the test fakes. Sample transcripts use invented emails; one is `@gmail.com`, so make it `@example.com`. | Done: site_privacy rule. Nothing to rotate. |
| L4 | LOW | info | `/health` tells anyone on the internet whether the caller is ON. | Optional: answer `{"ok": true}` only. |

## Patch summary (`security_fixes.patch`, 8 files, +463 / -26)
- `tools/caller/consent.py`: lead match, pending + `confirm()` (inbound_call / owner), `pending()`, CLI `approve` / `list`, `valid_email`.
- `tools/caller/server.py`:
  - consent limits per sender (last XFF), per day, and the Origin allowlist
  - inbound: CallSid once, per-number and daily caps, confirm on an inbound call from a pending number
  - relay token TTL + pruning
  - WebSocket total-size limit and idle timeout
  - kill switch checked every turn
  - `BoundedServer` (16 connections, 15 s)
  - a bad `Content-Length` is refused
- `tools/caller/actions.py` (`valid_email` in `queue_email`), `brain.py` (the model's email checked), `onoff.py` (OFF message),
  `settings.json` (the new limits, `consent_origins`).
- `tests/test_caller.py`: `sign()` confirms, and the POST /consent check expects pending-then-valid. New `tests/test_caller_security.py`
  (25 checks, one per attack above). Add `AREAS["agency"].append("caller_security")` next to the caller line.
