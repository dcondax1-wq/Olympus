# Caller portal + privacy fixes (day-a11y, 2026-11-21)

Plan of record: `research/writeups/cold-calling-plan-2026-11-20.md`. A real person dials by hand, which is legal in Maryland. The page gives them the list, the rules, the words and the log. Claude does everything else.

## 1. Privacy: no default public address, never the owner's handle
- **`agency/public.py`** is the one source for public links.
  - `public_base` comes from `tools/site_factory_agency.json` (`{"public_base": "https://...", "agency_number": "..."}`) or the sender's `site_base`.
  - There is **no default**. A plain-http address, `dcondax`, `github.io/jarvis` or `ts.net` is refused.
- **Email autopilot.** `SITE_BASE` is gone.
  - Without a public base, `cfg_problems` keeps it OFF and `message()` raises.
  - `compliant()` refuses any message showing a banned piece.
- **Postcards** (parked, OFF): the same gate. `render()` refuses banned text or QR targets, and samples use `https://your-agency.example`.
- **Outreach page.** Email links used the page's **own address**. Opened from the owner's dashboards, that would have put his handle in every copied email. It now uses `portal.json`'s `public_base` only; with none, the link reads `[the site link: set public_base first]`.
- **agency-inbox H1 gate** (shipped last night as d91d706a): nothing is pushed until GitHub says the repo is private.

## 2. Wording: "Call <agency number>: our AI assistant answers"
- Emails (autopilot), postcards and the outreach page all use it.
- There is no "Have our assistant call me", no "or text" and no "any time".
- The line appears only once the agency number is set (`agency_number` in `tools/site_factory_agency.json` / `portal.json`).

## 3. The caller portal: `tools/web_public/agency/portal/`
Self-contained: no Olympus file and relative paths only, so it runs on the neutral host. noindex, no referrer, light and dark, 390 px first, 44 px taps.

| Ask | What it does |
|---|---|
| The list | Business, **tap-to-call**, town, kind, **code FR-n**, **their concept site** (public_base + `agency/f/<id>/`). Tabs: Call now / Need a number / Later / Done. Numbers first, then trades > health > salons > auto > food. |
| Rules in the UI | Weekdays **9:00 am-5:00 pm their time**, no federal holidays (including the day after Thanksgiving); **1 call + 1 follow-up**, **never twice in a day**. **No / Do not call = never again**: on the phone at once, and on the PC (every channel) on import. Outside the window the Call button is disabled and says when calls open. |
| Identify yourself | Always at the top: "Hi, it's <caller> with <agency>. We build websites for local businesses." The rules sit one tap below. |
| Logging | Talked / Voicemail / Interested / Booked a call / No / Do not call / Won, plus Undo for 15 minutes. |
| No number | 51 of 58 have none. Each row gets a **Find on Google Maps** search link (a link, not scraping) and a box to save the number found. |
| Add a business | Name, phone, town, kind. It is saved with the caller's name; on import it goes to `tools/agency_added_leads.json` for the factory to build its site (LEAD_WIRES #1). |
| Email them the link | Opens **the agency Gmail's compose** (`authuser=<agency email>`), filled in: honest subject, their site link, prices, sender + agency, postal address, "no thanks". The caller presses Send. The page sends nothing. It isn't ready until the agency settings and the public base exist. |
| Per-caller name | Asked at sign-in and stamped on every log line. **Save my log file** + **Email the agency** go to the owner, then `python -m agency.portal import <file>`. |
| Commissions | `agency.portal commissions`: **$300 a sale**, **$40 a booked call once it shows** (a `showed` line). The page shows "if it all closes". |
| Passphrase | `python -m agency.portal pass` (typed hidden, 10+ characters) saves a **salted SHA-256 only** in `portal.json`. Until then the page stays locked ("Not set up yet"). Honest limit: on a static host this is a soft gate. The data is public map data, and no secret is on the page. |

**PC side:** `python -m agency.portal`
- `build`: 58 businesses today (9 chains left out). Leads with a website and the never-again list are dropped too; only ids are used, and the list itself is never published.
- `pass`, `setup`, `import`, `commissions`.

**Limit:** the log lives on the caller's phone until they send it. There is no shared live list: a static page has no backend, and that keeps it free with no secret. With one caller, that's fine.

Tests:
- `test_web_portal` 53/53 (static; node core; PC side; browser 390 + 320: lock, wrong / right passphrase, tel:, never twice a day, undo, Gmail compose, find a number, add a business, the export, no h-scroll, 44 px).
- `test_agency_autopilot` 55/55, `test_postcards` 37/37, `test_web_outreach` 49/49.

## Owner steps
1. Pick the agency name, number and Gmail. Then on the PC: `python -m agency.portal setup` and `python -m agency.portal pass`, and give the passphrase to the caller yourself.
2. Post the caller ad (`research/handoff/2026-11-20/caller-job-ad.md`).
3. Once a day, save the caller's emailed log file and run `python -m agency.portal import <file>`.
