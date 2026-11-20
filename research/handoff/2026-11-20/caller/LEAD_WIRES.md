# LEAD_WIRES: AI caller (team day-caller, 2026-11-20)

Branch `day-caller` (from pc 3aaa1d69). Everything new, nothing existing edited: no `sw.js`, no `tools/build_web_dashboard.py`,
no `jarvis/apps.js`, no `olympus.js` APPS table, no `tests/run_area.py`, no engine/, no server.py.

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
| `tools/caller/simulate.py` | 8 scripted owners, transcripts + scores (`--llm` = Claude brain) |
| `tools/caller/siteform.py` | the concept-page form JSON for the site factory |
| `tools/caller/cost.py`, `onoff.py`, `setup_keys.py`, `funnel.py`, `registry.py`, `settings.json` | cost table, switch (START CALLING typed), getpass keys, Funnel address + Twilio hook, DNC stamp, defaults |
| `CALLER_SETUP.bat`, `CALLER_ON.bat`, `CALLER_STOP.bat` | root bats, ASCII + CRLF |
| `tests/test_caller.py` | 87 checks, offline, ~10 s |
| `research/writeups/ai-caller-2026-11-20.md` | owner-plain law + cost + sign-up |
| `research/handoff/2026-11-20/caller/transcripts/` | 8 sample transcripts + `scores.json` |

## Wires for the lead (please)

1. **run_area** (one line, own line so it never clashes):
   `AREAS["agency"].append("caller")      # day-caller 2026-11-20: the consent-first AI caller (tools/caller/), offline`
2. **Concept pages (day-cities3, agreed 2026-11-20):** the slot `<div id="caller-slot">` takes
   `python -m tools.caller.siteform --endpoint <PUBLIC>` -> `{"caller_html", "caller_button", "caller_fields"}`; put `caller_html` in
   `tools/site_factory_agency.json` and fill the two hidden inputs per site: `lead_id` (the Leads id, osm-n...) and `business`.
   `<PUBLIC>` = the Funnel address CALLER_ON.bat shows (`https://<pc>.<tailnet>.ts.net:10000`); it is unknown until the PC runs it, so the
   slot stays empty (no form = no outbound calls; inbound still works). Button text: exactly "Have our assistant call me" (the Day-0 email
   names it). Form fields: business phone, full name (signature), best time (any / morning 9-12 / afternoon 12-5), optional email, the
   consent checkbox with the exact text (`consent.CONSENT_TEXT`, version `v2-2026-11-20`). Inline only, no third party, no secret.
   Privacy: rename the PC in Tailscale to something neutral (e.g. olympus-caller) before Funnel: the address appears on every concept page.
3. **Consent records:** the gate reads `<OLYMPUS_HOME>/caller/consent.jsonl` (append-only, on the PC, never in the public site):
   `{id, kind:"consent", phone, business, signed_name, email, lead_id, version, window, asked_t, phone_source:"their form", text, text_sha256, ts, ip, ua}`;
   a revoke is `{kind:"revoke", phone, why, ts}`. For the private **agency-inbox** branch the PC pushes `<OLYMPUS_HOME>/caller/share/` as
   `caller/`: `caller/consent/<id>.json` = `{id, lead_id, business, asked_t, window, phone_source, version}` (no phone, no name), so the
   email autopilot stops the sequence for that lead id.
4. **Email autopilot (day-a11y, its format):** the caller writes `share/outbox/<id>.json` = `{id:"call-...", inbox_id:"", lead_id, kind:
   demo | booking | payment, subject, body, approved:false, to, from_app:"caller", caller_kind, t}` ("to" = the address said on the call;
   the body has the CAN-SPAM footer). The PC sends demo / booking / payment drafts by itself (owner's own links). Call outcomes:
   `share/status/<lead_id>.json` = `{lead_id, s, t, outcome}` with s = called / interested / no (phone key agency.leads.status.v1;
   "won" stays the owner's). Every call is also one line in `<OLYMPUS_HOME>/caller/inbox/<YYYY-MM-DD>.jsonl` (outcome, actions,
   transcript file); transcripts stay on the PC.
5. **STATE.md "Waiting on the owner"** (max 5, one line): "AI caller: yes/no to a paid Twilio + Claude API key (~$8/month at 2 calls a
   day); if yes, the 20-minute sign-up in research/writeups/ai-caller-2026-11-20.md part 6, then CALLER_SETUP.bat."
6. Optional later: a `call-ai` card on the Agency page reading `inbox/*.jsonl` (not built: screens are the lead's).

## Tests run here

- `python -X utf8 -m tests.test_caller` -> 87/87
- `python tests/smoke.py` -> 9/10 (the 1 is `test_zenith_mode`: this container has no Python Playwright; unrelated)
- `python tests/run_area.py privacy --only repo_secrets` -> 13/13; `python -m tests.test_cold_calls` -> 115/115
- `python -m tools.caller.simulate` -> 8 personas, all 100%

## Never

Claude never ran `onoff on`, made no call, spent nothing, saved no key. The caller is OFF by default and refuses to start without the
typed phrase, the 4 keys, and a real agency name.
