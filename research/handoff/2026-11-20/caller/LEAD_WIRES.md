# LEAD_WIRES: AI caller (team day-caller, 2026-11-20)

Branch `day-caller` (from pc 3aaa1d69). Everything new, nothing existing edited: no `sw.js`, no `tools/build_web_dashboard.py`,
no `jarvis/apps.js`, no `olympus.js` APPS table, no `tests/run_area.py`, no engine/, no server.py.

## Launch mode (lead decision 2026-11-20): INBOUND ONLY

- **Live funnel:** postcard / concept site -> "Call <agency number>" -> the AI receptionist answers (disclosure first) -> books one of 2
  slots or emails the payment link -> one phone ping per booking. Only Twilio knows the PC endpoint (Funnel :10000, signed webhooks),
  and no public page names it.
- **Outbound "call me" = PHASE 2, built but OFF:** `outbound_enabled: false` in `tools/caller/settings.json`. The gate and the dialer
  make no outbound call, and the KV pull doesn't run, even with CALLER_ON + consent + landline (tested). It can come back only through a
  non-PC endpoint: the Cloudflare Pages Function (`tools/caller/cloudflare/consent.js`, KV, CORS pinned to `ALLOWED_ORIGIN` = the
  GitHub Pages origin of the concept sites, never `*`). That needs the security review to pass, the owner's Cloudflare KV step, and the
  owner setting `outbound_enabled: true` in `<OLYMPUS_HOME>/caller/settings.json`.
- **Texts:** the AI answers voice calls only. A text to the agency number gets no AI reply (Twilio keeps it in its console). Print
  "Call <number>" on cards until texting is built and its carrier registration (10DLC) is done.

## Verdict (send to the owner as is)

A **cold** AI caller to Maryland businesses is **not legal** for us: Md. Com. Law 14-4502(a)(3) bans sales calls by an automated dialing
system or a recorded/artificial message without the called party's **signed** consent; the B2B exemption (a)(1)(iii) needs 3+ years
under the same name. $500/call, x3 if willful. So the build is the closest legal version: **inbound AI receptionist + outbound only to
businesses that signed the "Call me" form**. Full law + sources + cost: `research/writeups/ai-caller-2026-11-20.md`.

## Files

| File | What |
|---|---|
| `tools/caller/compliance.py` | the gate: switch, cap, consent, our DNC, federal DNC copy, landline only, 9-5 weekdays local, holidays, 1 call + 1 follow-up; disclosure-first opener built in code; human-claim filter; opt-out phrases |
| `tools/caller/consent.py` | signed consent store (append-only JSONL), wording `v1-2026-11-20`, `consent_form_html()` for demo pages |
| `tools/caller/brain.py` | `CallSession` (opt-out first, filter last), `ScriptedBrain` (offline), `ClaudeBrain` (claude-opus-5-5, effort low, server-side fallbacks, tools book_slot / send_email / end_call) |
| `tools/caller/actions.py` | 2 slots, booking, email outbox, inbox records, one ntfy ping per booking |
| `tools/caller/telephony.py` | `Adapter` interface, `FakeAdapter`, `TwilioAdapter` (Lookup v2 line type, Calls API with machine detection, inbound hook), ConversationRelay TwiML, Twilio signature check |
| `tools/caller/server.py` | stdlib server 127.0.0.1:8790: /health, /consent, /voice/inbound, /voice/status, /relay (RFC 6455 WebSocket for ConversationRelay); dialer thread |
| `tools/caller/run.py` | `plan()` / `tick()` (one dial per minute max), `--dry` |
| `tools/caller/simulate.py` | 9 scripted owners (1 inbound), transcripts + scores (`--llm` = Claude brain) |
| `tools/caller/siteform.py` | the concept-page form JSON for the site factory |
| `tools/caller/cloudflare/consent.js`, `tools/caller/pull.py` | the Pages Function that takes the form (KV) + the PC puller |
| `tools/caller/cost.py`, `onoff.py`, `setup_keys.py`, `funnel.py`, `registry.py`, `settings.json` | cost table, switch (START CALLING typed), getpass keys, Funnel address + Twilio hook, DNC stamp, defaults |
| `CALLER_SETUP.bat`, `CALLER_ON.bat`, `CALLER_STOP.bat` | root bats, ASCII + CRLF |
| `tests/test_caller.py` | 97 checks, offline, ~10 s |
| `research/writeups/ai-caller-2026-11-20.md` | owner-plain law + cost + sign-up |
| `research/handoff/2026-11-20/caller/transcripts/` | 9 sample transcripts + `scores.json` |

## Wires for the lead (please)

Items 2 and 3 are PHASE 2 (outbound). For launch only items 1, 4 (inbound outcomes and emails) and 5 apply.


1. **run_area** (own lines so they never clash):
   `AREAS["agency"].append("caller")           # day-caller 2026-11-20: the AI caller (tools/caller/), offline`
   `AREAS["agency"].append("caller_security")  # day-security2 review of the caller: 25 attack checks`
2. **Concept pages (day-cities3 wired the slot, 628798aa):** the form now posts to the concept site's OWN `/api/consent`, not the PC.
   A `.ts.net` address on a public page is refused (`tools/site_privacy.py mask_net` would mask it, and it maps the owner's devices).
   - Publisher (lead): copy `tools/caller/cloudflare/consent.js` to `functions/api/consent.js` of the Cloudflare Pages project that
     serves `agency/f/`, and bind one KV namespace as `CONSENT` (free tier). It re-checks the form, caps 5 a day per IP, stores
     30 days, and holds no secret.
   - The PC's caller pulls the KV entries every minute into `consent.jsonl` and deletes them (`tools/caller/pull.py`, with a Cloudflare
     token that has "Workers KV Storage: Edit"; CALLER_SETUP.bat asks for it as optional keys 5-7).
   - Markup: `python -m tools.caller.siteform` -> `{"caller_html", ...}` for `tools/site_factory_agency.json`. It refuses to run while
     agency/config.json still holds placeholders (YOUR AGENCY, (555) 555-0100), so generate it where the real config exists, or give Claude
     the real agency name, phone and first name for the repo's caller settings.
   - Until the function is deployed, the slot stays empty. Twilio still reaches the PC over Funnel :10000, but that address appears on
     no page.
3. **H1 (lead decision, security review): NOTHING goes to an agency-inbox branch while `dcondax1-wq/olympus` is public.** Every caller
   file stays on the PC in `<OLYMPUS_HOME>/caller/`: consent.jsonl, calls.jsonl, inbox/*.jsonl, transcripts/, share/ (outbox drafts,
   consent copies, lead status). The only export is `python -m tools.caller.export DEST`. It writes `DEST/caller/outcomes.json` =
   `[{business, outcome, ts}]`, and only after the GitHub API answers `"private": true` for the repo. A public repo, a 404 or no answer
   is refused (tested). day-a11y: the caller's outbox drafts in `share/outbox/<id>.json` (your format) must be sent by the PC from that
   folder, not through the branch, until the repo is private.
4. **Formats (all on the PC):** outbox drafts `share/outbox/<id>.json` = `{id:"call-...", inbox_id:"", lead_id, kind: demo|booking|payment,
   subject, body, approved:false, to, from_app:"caller", caller_kind, t}`. Lead status `share/status/<lead_id>.json` = `{lead_id, s, t, outcome}`
   with s = called / interested / no. Consent copy (phase 2) `share/consent/<id>.json` = `{id, lead_id, business, asked_t, window,
   phone_source, version}`. One line per finished call in `inbox/<YYYY-MM-DD>.jsonl`.
5. **STATE.md "Waiting on the owner"** (max 5, one line): "AI caller: yes/no to a paid Twilio + Claude API key (~$8/month at 2 calls a
   day); if yes, the 20-minute sign-up in research/writeups/ai-caller-2026-11-20.md part 6, then CALLER_SETUP.bat."
6. Optional later: a `call-ai` card on the Agency page reading `inbox/*.jsonl` (not built: screens are the lead's).

## Security review applied (day-security2 5b941202)

The review patch is merged by hand onto the newer branch: C1 forged consent (lead match + pending until the business calls in, or
`python -m tools.caller.consent approve <number>`), H2 inbound caps (3 per number, 40 a day), H3 BoundedServer (16 connections, 15 s)
plus CALLER_ON `/low` priority, and M1-M4 (one plain email, CallSid used once, 180 s relay tokens, the kill switch mid-call). On top of
the patch: H1 (above), L4 (`/health` = `{"ok": true}`), L3 (example.com in every transcript), and M5: `speech_filter` swaps any money
promise (discount, guarantee, refund, free hosting, a $ price that isn't the owner's own price_line) for "<owner> will confirm prices and
terms by email". The Cloudflare puller is lead-matched too.

## Tests run here

- `python -X utf8 -m tests.test_caller` -> 97/97; `python -X utf8 -m tests.test_caller_security` -> 25/25
- `python tests/smoke.py` -> 9/10 (the 1 is `test_zenith_mode`: this container has no Python Playwright; unrelated)
- `python tests/run_area.py privacy --only repo_secrets` -> 13/13; `python -m tests.test_cold_calls` -> 115/115
- `python -m tools.caller.simulate` -> 8 personas, all 100%

## Never

Claude never ran `onoff on`, made no call, spent nothing, saved no key. The caller is OFF by default and refuses to start without the
typed phrase, the 4 keys, and a real agency name.

## Phase-2 form markup for day-cities3 (sample values; regenerate with the real agency config)

`python -m tools.caller.siteform --endpoint https://<project>.pages.dev/api/consent` prints this as `caller_html`. It is a cross-origin
POST from GitHub Pages, so the function must have `ALLOWED_ORIGIN` set to the concept sites' origin. Fill `lead_id` and `business` per site.

```html
<form id="callme" class="callme" data-version="v2-2026-11-20" data-post="https://olympus-consent.pages.dev/api/consent">
<p class="callme-lede">Our AI assistant can call your business line on a weekday between 9 and 5 to answer questions and book a short call with Dee. Or call us yourself: (301) 662-0100.</p>
<label>Business phone <input name="phone" type="tel" required autocomplete="tel" inputmode="tel"></label>
<label>Your full name (your signature) <input name="signed_name" required autocomplete="name"></label>
<label>Best time <select name="window"><option value="any">Any time 9-5</option><option value="morning">Morning (9-12)</option><option value="afternoon">Afternoon (12-5)</option></select></label>
<label>Email (optional) <input name="email" type="email" autocomplete="email"></label>
<input type="hidden" name="lead_id" value=""><input type="hidden" name="business" value="">
<label class="callme-agree"><input type="checkbox" name="agree" required> <span>By typing my name and tapping &quot;Have our assistant call me&quot;, I agree that Brightline Web Studio may call me at the number I type below using an AI assistant (an artificial voice) and an automated dialing system, to talk about the website preview it made for my business. The call is recorded and transcribed. I do not have to agree to this to buy anything. I can say &quot;stop&quot; on the call, or email or call (301) 662-0100 at any time, and you will never call again.</span></label>
<button type="submit">Have our assistant call me</button>
<p class="callme-out" role="status" aria-live="polite"></p>
</form>
<script>(function(){var f=document.getElementById("callme");if(!f)return;f.addEventListener("submit",function(ev){ev.preventDefault();var o=f.querySelector(".callme-out");
var b={phone:f.phone.value,signed_name:f.signed_name.value,window:f.window.value,email:f.email.value,lead_id:f.lead_id.value,business:f.business.value,agree:f.agree.checked,version:f.dataset.version};
o.textContent="Sending...";fetch(f.dataset.post,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b),referrerPolicy:"no-referrer"})
.then(function(r){return r.json()}).then(function(j){o.textContent=j.message;if(j.ok)f.querySelector("button").disabled=true})
.catch(function(){o.textContent="Could not send. Please call us instead."});});})();</script>
```
