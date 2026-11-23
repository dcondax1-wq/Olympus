# The Website Factory's email autopilot (agency/autopilot/, 2026-11-20)

The owner wants zero hands-on outreach. **Phone calls by AI are out:**
- The FCC treats an AI voice as a robocall under the TCPA ($500-1,500 per call).
- Maryland bans cold automated calls without signed consent (Md. Com. Law 14-4502).
- It would also need a paid phone service and his identity.

So the PC sends **email only**, as its own scheduled task, with hard limits. The AI caller (day-caller) rings only businesses that ticked
"Have our assistant call me" on their concept site. The day-0 email points at that button when the business has its own built site.

## Owner: turn it on (once, on the PC)
1. Make a FREE business Gmail and turn on 2-Step Verification. Then create an **app password**: Google account > Security > App passwords.
2. Double-click **tools/bat/EMAIL_SETUP.bat** and answer: the Gmail address, the app password (hidden), your name, your business, your phone, your postal address (a PO box is fine; the law needs it in every email), your own test address, and an optional booking link and payment link. The payment link comes from your own free payment account: that is your step.
3. The phrase gate:
   - Type `SEND EMAILS` to email businesses for real.
   - Anything else gives a **DRY RUN**: 3 sample emails a day, to your test address only.
4. It sends one test email to your test address and installs the task **OlympusAgencyMail**, which runs every 30 minutes.
5. **tools/bat/EMAIL_STOP.bat** turns everything off and removes the task. The settings and the never-again list stay.

Everything stays in `%USERPROFILE%\.olympus\`:
- `agency_mail.json`: the settings and the app password. Never in the repo, never printed.
- `agency_mail_state.json`: who got what, and the never-again list.
- `agency_mail.log`: counts only. The password is scrubbed even from error text.

## The limits (agency/autopilot/core.py)
- Only businesses with a **public business email**: `email` in the leads list, or the owner's own private file `agency_leads_private.json` in `%USERPROFILE%\.olympus\` (`{"emails": {"<lead id>": "info@..."}}`). One address is written to once.
- **20 new businesses a day** (warm-up), at most 5 per run, paced 20-60 s apart, and at most 60 messages of any kind a day.
- **Mon-Fri 9:00-16:00 ET** only. Replies are read at any time.
- Follow-ups on **day 3 and day 7** only. Any reply stops the sequence.
- **Never again:** an opt-out ("no thanks", "remove me", "stop", "not interested", "unsubscribe", the mail app's Unsubscribe button) or a bounce.
- **Every message** carries:
  - an honest subject;
  - the sender's real name and business;
  - the postal address;
  - a "reply no thanks" line, plus a List-Unsubscribe header.

  A message missing one of these is refused, not sent. The words are `tools/web_public/agency/outreach/scripts.json`, the same as the manual page.

## The reply bridge: the private branch `agency-inbox`
**H1 gate (2026-11-20): nothing is pushed while the repo is public.** Before any push the PC asks the GitHub API (`bridge.repo_private`, day-caller's
`tools.caller.export.repo_private` when installed; `GITHUB_TOKEN` if set). Only `"private": true` opens the gate; a public repo, a 404 or an error keeps
the replies, the caller files and the postcard results on the PC (the state file, `postcards_results.json`). The owner makes the repo private, then it flows.

The PC keeps its own clone in `%USERPROFILE%\.olympus\agency_inbox` and pushes plain commits. It never force-pushes and never touches another branch.

| File | Who writes it | What |
|---|---|---|
| `inbox/r<uid>.json` | the PC | `{id, lead_id, business, class, words, subject, t}`: class = interested / question / not_now / optout / bounce. `words` = only their new text, with no quoted thread and no signature; phone numbers and emails are masked. No sender address. |
| `status.json` | the PC | the day's counts and `needs_owner` (drafts that wait) |
| `outbox/<id>.json` | **Claude** (the scheduled cloud session) | a draft answer: `{"id", "inbox_id", "lead_id", "kind": "price" \| "demo" \| "payment" \| "booking" \| "other", "subject", "body", "approved": false}` |
| `sent/<id>.json` | the PC | `{id, status: sent \| refused, why, t}` |
| `caller/consent/<id>.json`, `caller/status/<lead_id>.json`, `caller/outbox/<id>.json` | the PC, copied from the AI caller's `<home>\caller\share\` (day-caller) | consent = the business asked for the call; status = `{lead_id, s, t, outcome}`; outbox = an email the caller promised (`"to"` masked in the copy) |
| `postcards/results.json` | the PC | the postcard results table by code (FR-27): card 1, the day-10 card, responded / call me / claimed. No addresses. |

**The AI caller and the postcards (2026-11-20):**
- A lead in `caller/consent` or `caller/status` leaves the email sequence (no more follow-ups).
- A caller draft (`kind` demo / booking / payment, `inbox_id` empty) goes to the `"to"` the business said on the call, under the same rules as Claude's drafts (our own links only, never a suppressed address, once).
- An email opt-out also calls the caller's `compliance.add_dnc(phone, "email stop")` and `consent.revoke(phone, "email stop")` when `tools/caller` is installed.
- A reply that names a postcard code (`FR-27`) counts as that business's reply, and Claude's answer goes back to the person who wrote.
- The phone's lead status (`agency.leads.status.v1`) lives in the phone's browser: the PC cannot write it. The caller status files on `agency-inbox` are where a page could read it.

**Claude, when answering:**
- Read `inbox/` for items with no `sent/` result yet. Write one `outbox/<id>.json` per reply. Sign it with the owner's name exactly as on the first email; the PC adds the postal address and the no-thanks line when missing.
- Prices come from `agency/offers/offers.json` (Starter $1,500 + $79/mo, Call engine $500 + $299/mo, no upfront $149/mo x 12).
- The PC sends **by itself** only `price`, `demo`, `payment` and `booking` drafts whose links are all the owner's own: his site, the booking link or the payment link.
- Anything else waits for `"approved": true`, and the owner gets **one phone push** listing what waits. Words such as guarantee, legal, refund or discount also wait.
- `optout`, `bounce` and `not_now` get no answer.

## The page
`agency/outreach/` (owner only) shows the autopilot's numbers. The autopilot posts **nothing** to ntfy itself, because the PC shares ntfy's 250-a-day per-IP budget with the bot's alerts. Instead:
- after each pass it writes the tiny card `data/agency_mail/summary.json` (`agency/autopilot/card.py`: numbers and the mode only, under 120 bytes);
- the PC report carries it in its existing ext block as `am` (patch: `research/handoff/2026-11-20/web/outreach/LEAD_WIRES.md` #7);
- the page reads it through `pc_feed.js`.

Phone pushes for replies that need the owner go to his private topic, 4 a day at most.

Tests: `python -X utf8 -m tests.test_agency_autopilot` (fake Gmail, a temp home, a local bare git repo; never the network).
