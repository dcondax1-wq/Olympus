# Cold calling local businesses: the US rules in plain words

Team B2, written 2026-11-14 from web searches that day (every part lists its sources with their dates). **This is not legal advice.**
Laws change and the sources below are mostly law-firm and vendor summaries, not the statutes. Before calling into a new state for
the first time, read that state's rule; before anything automated (AI voice, robocalls, mass texts), pay a TCPA lawyer for one hour.

The tool that follows these rules is the **Call copilot** (`tools/web_public/agency/call.html`, PC side `agency/calls/`, see part 11).

## The answer first

| What you want to do | Allowed? | Why, in one line |
|---|---|---|
| **You** call a business yourself, by hand, with a good script | **Yes, within the rules** | A live call by a person needs no consent; calls to business lines are outside the Do Not Call Registry. Keep the hours, say who you are, stop when asked. |
| The same, but the number is a one-person business's cell phone (plumber, stylist) | **Yes, with care** | Courts may treat a cell used for work AND home as "residential": check it against the Do Not Call list first, keep the hours, call at most once a day. |
| AI helps **you**: researches the lead, writes the script and the demo site, coaches you live, drafts the email you send | **Yes** | The AI never places the call or speaks on it. |
| **AI voice calls** the businesses for you (or a recorded message, or a "ringless voicemail") | **No: high legal risk** | Since February 2024 the FCC counts AI voices as "artificial voices": consent is needed for every cell phone and home line, and Pennsylvania (October 2026) now also covers business lines. Lawsuits pay **$500 per call, up to $1,500** if willful. |
| Text a business number you found online | **No, unless they said yes** | Texts count as calls, the Do Not Call rules cover texts, and carriers block unregistered business texting. Text only people who agreed (log when and how). |
| Follow-up email | **Yes, with the CAN-SPAM basics** | B2B email is covered: your real name, an honest subject, your postal address, an opt-out you honor within 10 business days. |
| Record the call | **Only if you announce it** | About 12 states need everyone's consent. The copilot never records. |

**In 5 lines:**
1. Human calls to businesses with a good script are OK: weekdays 10 am to 6 pm their time is legal in every state (the app shows each state's exact hours), say who you are and that it is a sales call, never on Sundays or holidays.
2. Check numbers against the National Do Not Call list (free for 5 area codes) and keep your own do-not-call list forever; "don't call me" means never again.
3. No AI voice, robocall, recorded message or ringless voicemail to anyone who has not signed a written consent: that is $500-$1,500 per call.
4. Emails: real name, honest subject, postal address, an opt-out that works. Texts: only to people who said yes, with "Reply STOP to opt out".
5. AI is safe as your coach (scripts, research, demo sites, notes, email drafts), not as the caller.

---

## 1. The TCPA (the federal phone law)

- The Telephone Consumer Protection Act (47 U.S.C. 227) and the FCC's rules (47 CFR 64.1200) are the main federal law.
- **What needs consent:** calls made with an autodialer or an **artificial or prerecorded voice** to a **cell phone** (any purpose, B2B included),
  and artificial or prerecorded voice calls to a **home line**. For sales calls the FCC requires **prior express written consent**.
- **What does not need consent:** a person dialing by hand (or tapping a number) and talking live. Since *Facebook v. Duguid* (Supreme
  Court, 2021-04-01) an "autodialer" is equipment that generates random or sequential numbers, so a tap-to-dial phone is not one.
- **Money:** a private lawsuit gets **$500 per call or text, up to $1,500** if the court finds it willful or knowing (227(b)(3)); every call is a
  separate violation. Calling again after "stop" is the classic way to become "willful". A Do Not Call claim needs **more than one call in 12
  months** to the same listed number (227(c)(5)): one more reason the copilot never calls a listed number twice.
- **Since June 2025** (*McLaughlin Chiropractic v. McKesson*, Supreme Court, 2025-06-20) courts are no longer bound by the FCC's readings of the
  TCPA; they still give them "respect". Practical effect: some FCC rulings (like "cell phones are residential") are now argued case by case.
  Plan as if the FCC's reading holds.

Sources: Burr & Forman, "The TCPA - recoverable damages" (accessed 2026-11-14); ActiveProspect, "TCPA damages" (accessed 2026-11-14);
Husch Blackwell, "Supreme Court clarifies district courts' independence from FCC's TCPA interpretations" (2025-06); Gibson Dunn (2025-06).

## 2. AI voices are "artificial voices" (FCC, February 2024)

- **FCC Declaratory Ruling FCC 24-17** (CG Docket 23-362, adopted 2024-02-02, released 2024-02-08): voices made by AI, including voice
  cloning, are "artificial" voices under the TCPA. A call that uses one needs the called party's **prior express consent**, and for sales
  calls **prior express written consent**, exactly like a robocall. State attorneys general can enforce it.
- **Real fines:** the AI-cloned Biden robocalls (New Hampshire, January 2024) led to a **$6 million** FCC fine for the consultant (2024) and a
  **$1 million** settlement for the phone carrier that passed the calls (2024-08-21).
- **Coming, not yet final:** an FCC proposal (adopted 2024-08-07, Federal Register 2024-09-10) would define "AI-generated calls", make callers
  say in the consent form that they will use AI, and say at the start of every AI call that it is AI. We found no final rule on 2026-11-14.
- **Ringless voicemail** (a message dropped straight into voicemail) is also a "call" that needs consent (FCC ruling 2022-11-21).
- **What it means for us:** an AI agent that dials local businesses and talks is a robocall. Without signed consent it is illegal for every
  cell phone and home line in the list, and we cannot tell those apart from a business landline without paying for a line-type lookup.

Sources: FCC, FCC-24-17 (2024-02-08), docs.fcc.gov; Mayer Brown, "FCC declares authority and intent to regulate AI generated calls under the
TCPA" (2024-02-27); Wilson Sonsini, "FCC rules AI-generated voices are 'artificial' under the TCPA" (2024-02); Federal Register 2024-19028
(2024-09-10); Wiley, "FCC proposes new rules for AI-generated calls and texts" (2024-08); AP via KSL, "Company that sent AI calls mimicking
Joe Biden ... agrees to pay $1M fine" (2024-08-21); Faegre Drinker, "FCC releases declaratory ruling ... ringless voicemails" (2022-11).

## 3. The Do Not Call Registry, and your own do-not-call list

- **Business numbers are not covered.** The FTC: "The National Do Not Call Registry is only for personal phone numbers. Business-to-business
  calls and faxes are not covered." The FTC's sales-call rule (the TSR) also exempts most B2B calls, but **since 2024-05-16 B2B calls must not
  misrepresent anything** (price, what you sell, who you are).
- **The catch: one-person businesses on cell phones.** The FCC (2003) said calls to "home-based businesses" are judged case by case, and a
  federal appeals court held that a registered cell phone used for both work and personal life is **presumed residential**
  (*Chennette v. Porch.com*, 9th Cir., 2022-10-12: home-improvement contractors who got sales texts on their cells). That is exactly the
  plumber or stylist whose listing shows a cell number. Since 2025 courts are split on how far this goes.
- **What to do (the copilot enforces it):**
  - Scrub your list against the registry before calling. Access is **free for up to 5 area codes** a year (FY2027 fees from 2026-10-01:
    $85 per extra area code, $23,425 for all). Sign up at telemarketing.donotcall.gov, download your area codes, re-download at least every
    31 days.
  - A number **on the registry = do not call** (it is probably personal). A number not checked yet needs your "this is their business line"
    confirmation in the app.
  - Keep **your own do-not-call list forever.** Anyone who says "take me off your list" or "don't call again" is never called, texted or
    emailed again. The FCC's rule is to honor it within **10 business days**; the app does it at once.
- **Penalties:** FTC civil penalties are up to **$53,088 per call** (the 2025 level, kept for 2026).

Sources: FTC, "National Do Not Call Registry FAQs" (consumer.ftc.gov, accessed 2026-11-14); Federal Register 2024-07180, Telemarketing Sales
Rule (2024-04-16, effective 2024-05-16); Husch Blackwell, "FTC amends Telemarketing Sales Rule ... business to business" (2024-04); TCPAWorld,
"FTC announces 2027 telemarketer fees" (2026-08-26); Convoso, "FTC announces 2027 DNC registry fees" (2026-08); govinfo FR 2005-04-13
(05-7346, the 2003 home-based business wording); National Law Review / Olshan / Goodwin on *Chennette v. Porch.com* (2022-10/11);
TCPAWorld, "Are cell phones still residential post McLaughlin?" (2025-06-25); FTC civil penalty notice (2026: 2025 levels unchanged).

## 4. Call hours (their local time, not yours)

- **Federal:** sales calls to residential numbers only **8 am to 9 pm** at the called person's location (64.1200(c)(1)).
- **Stricter states** (sales calls to consumers; many exempt pure B2B calls, but the copilot applies them to everyone because you cannot always
  tell a business cell from a personal one). From compliance charts checked 2026-11-14; the sources disagree on some states:

| State | Window (local) | Days | Extra |
|---|---|---|---|
| Alabama | 8 am - 8 pm | no Sundays, no holidays | |
| Connecticut | 9 am - 8 pm | | Conn. Gen. Stat. 42-288a (2023) |
| Florida | 8 am - 8 pm | | max 3 calls / 24 h on the same subject (Fla. Stat. 501.616, 2021) |
| Kentucky | 10 am - 9 pm | | KRS 367.46955 |
| Louisiana | 8 am - 8 pm | no Sundays, no holidays | |
| Maryland | 8 am - 8 pm | | max 3 calls / 24 h (Stop the Spam Calls Act, 2024-01-01) |
| Massachusetts | 8 am - 8 pm | | B2B calls are outside it, per one source |
| Mississippi | 8 am - 8 pm | no Sundays | holiday ban lifted in 2024 (DNC.com); unconfirmed |
| Nevada | 9 am - 8 pm | | NRS 597.814 |
| Oklahoma | 8 am - 8 pm | | max 3 calls / 24 h (OTSA, 2022-11-01) |
| Oregon | 8 am - 8 pm | | since 2026-01-01 |
| **Pennsylvania** | **9 am - 7 pm** | **Mon-Sat; no Sundays, no legal holidays** | **Act 47 of 2026 (SB 992), signed 2026-07-20, in force 2026-10-18; covers texts and ringless voicemail** |
| Rhode Island | 9 am - 6 pm weekdays, 10 am - 5 pm Saturday | no Sundays, no holidays | |
| Texas | 9 am - 9 pm Mon-Sat, noon - 9 pm Sunday | | Bus. & Com. Code 301.051 |
| Utah | 8 am - 9 pm | no Sundays, no legal holidays | |
| Washington | 8 am - 8 pm | | RCW 80.36.390 (commonly listed; not confirmed in our search) |
| Wyoming | 8 am - 8 pm | | Wyo. Stat. 40-12-302 |

- **The copilot's own stricter policy:** no Sundays, no federal holidays (plus the day after Thanksgiving), at most **one call per lead per day**
  (the 3-in-24-hours states are then safe by a wide margin), and only inside the trade's good window (part 11). Some state-only holidays (Utah's
  Pioneer Day on July 24, Louisiana's Mardi Gras) are not in the app: skip those days in those states.
- **Time zones:** the app uses the lead's own time zone. If a state has two (Texas, Florida, Tennessee, Kentucky, Indiana, ...), and the city is
  not known, it only allows the hours that are legal in both.

Sources: Kixie, "Telemarketing laws by state 2026"; Prospeo, "Cold calling times allowed: every rule to know in 2026"; Trellus.ai state
pages (Kentucky, Connecticut, Oregon, Pennsylvania, Rhode Island, Texas, Massachusetts; accessed 2026-11-14); Drop Cowboy, "State compliance"
(Nevada, Kentucky); DNC.com, "Mississippi lifts prohibition on telemarketing on legal holidays" (2024); Convoso, "Pennsylvania telemarketing
law takes effect October 18, 2026" (2026-07); TCPAWorld, "Pennsylvania SB 992 signed by the Governor" (2026-07-21); Kelley Drye, "State
telemarketing update: Pennsylvania" (2026); Gryphon, "Florida Telemarketing Act and Florida Do-Not-Call Act"; Kelley Drye, "Maryland's new
telemarketing law now in effect" (2024-01); Manatt, "Oklahoma's mini-TCPA takes effect" (2022-11); clickpoint, "Federal and local call time
and date compliance".

## 5. State "mini-TCPA" laws (stricter copies of the federal law)

- **Florida (FTSA, Fla. Stat. 501.059):** no "automated system" sales calls or texts without written consent (since 2023-05-25 that means a
  system that both selects AND dials numbers); calls to Florida area codes are presumed to reach Florida residents; private lawsuits with
  attorney's fees. It covers sales of **consumer** goods and services, so pure B2B calls are the strongest case for being outside it, but a
  one-person business on a personal cell is not safely B2B.
- **Oklahoma (OTSA, 2022-11-01):** the Florida model; 8 am - 8 pm, 3 calls / 24 h, $500 per violation, up to $1,500 if willful.
- **Maryland (2024-01-01):** 8 am - 8 pm, 3 calls / 24 h, no automated or prerecorded sales calls without written consent; Maryland area codes
  presumed in-state.
- **Texas (SB 140, 2025-09-01):** "telephone solicitation" now includes **texts**; telemarketer registration (with exemptions) and lawsuits
  under the Texas DTPA.
- **Pennsylvania (Act 47 of 2026, in force 2026-10-18):** 9 am - 7 pm Mon-Sat, no Sundays or legal holidays; texts, voicemails and ringless
  voicemails count; **robocalls to residential, business or wireless lines need consent**; no fake caller name or number.
- **What it means for us:** human, hand-dialed calls inside the strictest window are fine everywhere; automation is where every one of these
  laws bites.

Sources: Goodwin, "Florida amends mini-TCPA" (2023-06); Quarles, "A return to (relative) sanity: amendments to the FTSA" (2023); Carlton Fields,
"How Fla. amendment changes the state's mini-TCPA" (2023); Leadgen Economy, "State mini-TCPA laws: FTSA, OTSA" (2026); Lerman Senter,
"Oklahoma passes new telephone solicitation act" (2022); Maryland General Assembly fiscal note HB 37 (2023); Morgan Lewis, "Texas telephone
solicitation law now covers text messages" (2025-09); Paul Hastings, "Marketing texts in Texas: SB 140" (2025); InfoLawGroup, "Another state,
another layer of calling and texting compliance" (2026-08-03); Data Privacy + Security Insider, "PA's new telemarketing law" (2026-07).

## 6. Recording a call

- Federal law and most states: **one-party consent** (you may record your own call).
- **All-party consent** (everyone must agree), per 2026 guides: California, Connecticut (phone calls), Florida, Illinois, Maryland,
  Massachusetts, Montana, Nevada, New Hampshire, Pennsylvania, Washington; often also Delaware and Michigan (disputed). Oregon needs it for
  in-person talks only. On a call between two states, follow the stricter one.
- AI note-takers and call "transcribers" are recordings for these laws.
- **What the copilot does:** it never records or transcribes. If you record with another app, say at the start: "This call is recorded."
  The call screen shows an all-party badge for those states.

Sources: Kixie, "What are the laws governing call recordings"; Rev, "Phone call recording laws"; Layer3 Labs, "Two-party consent states"
(updated 2026-08-13); Brass Transcripts, "State-by-state recording laws: 2026 guide" (all accessed 2026-11-14).

## 7. Follow-up emails (CAN-SPAM)

- **B2B email is covered** ("the law makes no exception for business-to-business email").
- Every sales email: true "From" name and address; a subject that matches the email; your **valid postal address** (a registered P.O. box is
  fine); a clear way to opt out that works for at least 30 days; opt-outs honored within **10 business days**; no selling the address after.
- Penalty: up to **$53,088 per email**.
- **What the copilot does:** every email template ends with your name, business, postal address and "Reply 'no thanks' and I will not email
  you again"; the app will not open an email without a postal address in Settings, and an email opt-out stops all follow-ups. The app never
  sends: it opens your own mail app with the text filled in.

Sources: FTC, "CAN-SPAM Act: a compliance guide for business" (ftc.gov, accessed 2026-11-14); Transcend, "The CAN-SPAM Act: a complete 2026
compliance guide".

## 8. Texting

- A text is a "call" for the TCPA. The FCC confirmed in its December 2023 order (Federal Register 2024-01-26) that the Do Not Call rules
  cover texts. Florida, Texas (2025) and Pennsylvania (2026) put texts in their own laws.
- Consent: the FCC's stricter "one-to-one consent" rule was struck down (*Insurance Marketing Coalition v. FCC*, 11th Cir., 2025-01-24) and the
  old wording is back (Federal Register 2025-08-29); consent is still needed for marketing texts.
- Business texting through an app or service needs **A2P 10DLC registration** (brand + campaign); unregistered traffic has been blocked since
  2025 (fees from about $4.50 for the brand plus $41.50 vetting, 2025).
- Opt-outs: from **2026-11-25** (FCC 26-67, adopted 2026-09-30) a business may name one exclusive opt-out method (for texts: a reply with one of
  seven standard words like STOP); requests must still be honored within 10 business days (the FCC is asking whether to shorten that).
- **What the copilot does:** the text button stays locked until you tap "They said I can text" on the call (it logs the date and how). Every text
  ends with "Reply STOP to opt out", and it is sent by you, from your phone's Messages app, one at a time. "STOP" = the lead's text consent is
  removed.

Sources: Federal Register 2023-28832 (2024-01-26); Duane Morris, "FCC order requires one-to-one consent, codifies do-not-call rule for texting"
(2024-01); Mofo, "Eleventh Circuit vacates FCC's TCPA one-to-one consent rule" (2025-01-30); Federal Register 2025-16641 (2025-08-29);
getterms.io / conduit.ai, "A2P 10DLC 2026"; Faegre Drinker, "New FCC rule gives callers more control over TCPA opt-outs" (2026-10-27);
Brownstein, "New TCPA revocation of consent rules take effect on November 25" (2026-10); Troutman (2026-09-17).

## 9. Caller ID and saying who you are

- Call from your **real number** (no spoofing: the Truth in Caller ID Act; Pennsylvania 2026 says it outright).
- Say **your name, your business and that it is a sales call** in the first sentence; give your number if asked. Never misstate price, results
  or who you are (B2B calls are covered by the FTC's misrepresentation rule since 2024).
- Never invent reviews, clients or results in a pitch or an email.

## 10. What AI can and cannot do here

| Safe | Risky: get a lawyer first | Do not |
|---|---|---|
| Find leads, read their sites, write the demo site (team B1) | AI that listens to the call and coaches (it is a recording in all-party states: announce it) | AI or cloned voice that calls people |
| Write and tailor the script, objection answers, voicemail and emails | Bulk texting through a texting platform (needs consent + 10DLC) | Prerecorded messages, voicemail drops, ringless voicemail |
| Live teleprompter on your screen while **you** talk (this app) | Buying lead lists with "consent" in them (consent from someone else rarely holds) | Auto-dialers that call down a list |
| Role-play practice (AI plays the shop owner) | | Spoofed caller ID; "this is not a sales call" when it is |
| Summarize the notes **you** typed, plan follow-ups, draft the email **you** send | | Texting people who never said yes |
| An **inbound** AI receptionist for a client (part 12) | | |

## 11. How the Call copilot follows these rules

`tools/web_public/agency/call.html` (phone) + `agency/calls/` (PC). Everything stays on the phone (`localStorage`, with JSON / CSV export) or
on the PC (`agency/calls/out/`, git-ignored). The page reads only its own published rule and script files and sends nothing over the network:
calls go through the phone's dialer (`tel:`), emails through your mail app (`mailto:`), texts through Messages (`sms:`), always tapped by you.

- **Call windows:** the lead's local time from its state (or exact time zone), the strictest state window from part 4, the federal 8 am - 9 pm,
  no Sundays or federal holidays, and the trade's best window (restaurants 2-4 pm, contractors 4-6 pm, ...). Outside the legal window the Call
  button is locked and the app says when it opens.
- **Do Not Call:** a lead on the registry, on your own do-not-call list, or who opted out is locked for good (matched by number, whatever the
  formatting). A number not checked yet needs a one-time "this is their business line" confirmation.
- **Limits:** one call per lead per day (hard cap 3 per 24 hours), the 7-day follow-up plan stops at "not interested" (no calls for 180 days) and
  at "do not call" (never again).
- **Texts** only after logged consent; **emails** only with your postal address; **no recording**; the script says who you are and that it is a
  sales call.
- **With team B1's Agency app:** the PC builder reads B1's day lists (`agency/out/<city>/leads.json`, never its sample files); the page offers
  B1's published `leads.json` with one button, reads B1's demo-site link and package price into the script, and treats B1's CRM stages
  "Do not contact" and "Won" (`localStorage['agency.crm.v1']`, read-only) as locks. Call mode's own outcomes stay in
  `localStorage['agency.calls.v1']` (B1's CRM can read its `optouts` list to show the same locks).
- **On the PC:** `python -m agency.calls.build` (add `--dnc <download>` for the registry check, `--merge <phone export>` to bring the phone's
  do-not-call numbers back) writes `agency/calls/out/call_list.json` to import on the phone; opt-outs and registry results there never shrink.

## 12. Optional future (documented only, nothing built)

### A. Outbound AI voice agents: costs and the consent that would make them legal

**Costs (2026 list prices, verify before buying):**

| Part | Price | Source |
|---|---|---|
| Phone line (Twilio) | $1.15 a month per local number; outbound US calls about $0.014 a minute, inbound $0.0085 | twilio.com/voice/pricing/us (page dated 2026-08) |
| Voice AI platform | Vapi about $0.05 a minute + model costs (about $0.09-0.11 all-in); Retell $0.07-0.31 (about $0.115 typical); Bland $0.12-0.14; ElevenLabs Agents $0.08 a minute + the model | MorphLLM / Dupple comparisons (2026) |
| All-in | about **$0.10-0.30 a minute**: 1,000 two-minute calls is roughly $200-600 a month | same |
| Line-type lookup (cell or landline) | about a cent per number (Twilio Lookup) | price not checked in this research: verify |
| Lawyer review of the consent form and script | one-time; the part that matters most | - |

**What would make outbound AI calls legal** (all of it, every time):
1. **Prior express written consent from each person called**, before the first call: a written (or E-SIGN electronic) agreement, signed by
   them, that clearly authorizes **your business** to call **this number** with sales calls using an **artificial or AI voice**, and says
   clearly that signing is **not a condition of buying** anything. In practice: a form on your website ("Yes, call me with a free website
   review; calls may use an AI assistant"), an unticked checkbox, their number typed by them, the date, time, IP and the exact wording kept
   for **at least 4 years** (the TCPA's lawsuit window). Lists bought from others do not count.
2. **Say it is AI** at the start of each call, plus your business name and a callback number (federal identification rule; the FCC's 2024 AI
   proposal; several states' bot-disclosure laws).
3. **An opt-out inside the call** ("say 'stop' or press 9 and we will never call again") and honor it at once (10 business days at most).
4. Only within the strictest call window (part 4), scrubbed against the registry and your own do-not-call list, at most 3 calls in 24 hours.
5. **No recording or transcript** without the all-party announcement (part 6); 10DLC if it texts.
6. State checks: Pennsylvania (business lines covered since 2026-10-18), Florida / Oklahoma / Maryland (written consent for automated calls),
   Texas registration.
Honest view: for cold outreach to businesses that never asked, there is no consent, so outbound AI calling is not a fit. It can fit
**warm** leads who filled in the form.

**A consent form that would hold up** (a starting draft for the lawyer, not final wording). On your own site, next to "Get a free website review":
- Their business name, their name, **their phone number typed by them**, their email.
- One checkbox, **not ticked in advance**, its own line: "Yes, [Your Business] may call and text me at the number above about my free website
  review and offers, including calls made with an AI assistant or a prerecorded voice. This is not a condition of buying anything. I can say
  'stop' or reply STOP at any time."
- The button says what happens ("Send my free review"), and the page links the privacy policy.
- **Keep, for every sign-up, at least 4 years:** the exact wording shown, the checkbox state, the number, date and time (UTC), the page address,
  the IP address and browser, and how they later opted out (if they did). Without these records, a lawsuit is lost even if consent was real.
- Treat it as consent for **your** business only, for **that** number, until they say stop. Bought "consented" lists do not count.

**What it would take to build (if the consent exists):** one Twilio number; a voice-AI agent (Vapi or Retell) with a fixed script that
opens with "Hi, this is an AI assistant calling for [Your Business] about the free website review you asked for. Say stop anytime and we will
never call again."; a small consent store (the records above) that the dialer checks before each call; the same windows and locks as the
copilot (part 11). About a week of work plus the lawyer's review. Not built: the owner's leads today are cold, so it has nothing legal to call.

### HIPAA note for clinic clients (dentists, doctors, chiropractors, physical therapists; vets are not covered)
An AI receptionist for a dentist, doctor or chiropractor hears patient health information, so the voice-AI vendor must sign a **business
associate agreement (BAA)** with the practice **before the first call**, encrypt the audio and transcripts, and not train on them. Some
vendors do not offer a BAA at all, and some charge extra for it (one is reported at about $500 a month). Offer the receptionist to medical
practices only on a vendor that signs the BAA; restaurants, shops and trades do not have this issue. (Sources: Aira, "HIPAA and AI
receptionists" (2026); JustCall, "Is an AI receptionist HIPAA compliant"; Keragon, "AI receptionist dental" (2026); Trillet, "Why HIPAA
compliance shouldn't be a $500 add-on"; all vendor sources, accessed 2026-11-14.)

### B. Inbound AI receptionist as a SERVICE to sell (legal and sellable)

- **Why it is legal:** the TCPA limits calls you **make**; an AI that **answers** a business's incoming calls is not a robocall (the FCC's 2024
  AI proposal covers outbound calls only). The rules that still apply: announce recording / transcription in all-party states ("This call is
  answered by an AI assistant and may be recorded"), disclose that it is AI (state chatbot laws are spreading: Utah, California's companion-
  chatbot law of 2026-01-01, Washington from 2027-01-01), and do not let it text callers marketing messages without consent.
- **What it does for a client:** answers 24/7, books appointments, takes orders or quote requests, sends the owner a summary, texts the caller
  the booking they asked for (an informational text the caller requested).
- **Market price (2026):** most small-business AI receptionists sell for **$30-300 a month** (RingCentral AI Receptionist $49 with 100 minutes,
  Dialzara from $29, Smith.ai from $150). Our cost at about $0.10-0.15 a minute + $1.15 a number: a 300-minute month is about $35-50.
- **The pitch fits the website sale:** "Your new site plus a receptionist that never misses a call: $X setup, $Y a month." Selling it is a
  normal human cold call (parts 1-9); the AI only works after the client says yes.
- **A price list that leaves a margin** (our cost about $0.10-0.15 a minute + $1.15 a number + the platform's monthly fee, if any):

| Plan | Price to the client | Minutes included | Our cost (about) | What it does |
|---|---|---|---|---|
| Missed-call catcher | $49 a month | 100 | $12-17 | Answers when they cannot, takes a message, texts the owner |
| Receptionist | $129 a month + $149 setup | 400 | $42-62 | 24/7 answers, books into their calendar, quote / order requests, FAQ from their site |
| Busy shop | $249 a month + $149 setup | 1,000 | $102-152 | The same with more minutes, Spanish, a monthly call report |

  Over the minutes: $0.25 a minute. Check the margin against the vendor you pick before quoting, and quote the HIPAA-ready vendor's price for
  medical practices.
- **The setup checklist per client:** a Twilio number they forward to (or forward on no answer), the greeting with the AI line and, in an
  all-party state, the recording line ("This call is answered by an AI assistant and may be recorded"); their hours, services, prices and FAQ
  from the new website; where bookings go (their calendar); what the AI must never do (quote a final price for a job, promise a time it cannot
  see, give medical or legal advice); and who gets the summary text. Test 10 calls yourself before it goes live.
- **The objection line on the cold call:** "Do you ever miss calls when you are busy? A missed call is usually a lost customer. For $49 a month a
  receptionist answers, takes the message and texts it to you."

Sources: Twilio, "Programmable Voice pricing, United States" (2026-08); MorphLLM, "Vapi vs Retell vs Bland vs Synthflow (2026)"; Dupple, "The
best AI voice agents in 2026"; Bland, "Voice AI pricing" (2026); Federal Register 2025-16641 (prior express written consent wording,
2025-08-29); DLA Piper, "E-SIGN consumer disclosures must be provided ... to meet TCPA" (2024-06-26); Wiley (2024-08) on the AI proposal
covering outbound calls; Dupple, "How much does an AI receptionist cost in 2026"; OnceHub, "Answering service cost in 2026"; Orrick, "2026
state chatbot laws" (2026-04); Ashurst Perkins Coie, "California companion chatbot law now in effect" (2026).
