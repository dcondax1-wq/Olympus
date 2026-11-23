# Monday cold calls: Mon Nov 23 2026 (website business)

**Human dialing only.** A person dials by hand on their own phone. No auto-dialer, no AI voice, no recorded message, no cold
texts (Maryland law + the TCPA). Business names and phones below are public map data already in the repo
(OpenStreetMap / Overture).

## Goal for the day (3 lines)

1. **60 dials** in the two blocks below (the first 20 here, then the portal's Today list), about **15-20 people reached**.
2. **2 "interested" + 1 proposal sent or a follow-up booked**. That is **$1,500-$2,000 setup + $79-$378/mo** in the
   pipeline (after the caller's $300: $1,200-$1,700 to you).
3. The week's real target: a 2-4% close on the first 100 dials = **2-4 clients = $2,400-$4,800 + $158-$316/mo**. These are
   estimates, not results; no sale is promised on day one.

## Before the first dial (must, in this order)

1. **Do-Not-Call scrub on the PC:** `python -m agency.dnc_scrub`. Download the area codes first (free for up to 5 a year at
   telemarketing.donotcall.gov: **301, 240, 410, 443, 667**) into the registry folder the script names. **Never dial a number
   on the Do-Not-Call list**, or one the scrub removed. Today's dial sheet still says "do-not-call: NOT SCRUBBED". If the
   scrub cannot run, check each number by hand before dialing and tap "Checked: not on it" in the portal.
2. **Unlock the portal:** `python -m agency.portal pass`, then publish. The live portal
   (https://dcondax1-wq.github.io/agency/portal/) currently says **"Not set up yet"** and nobody can sign in. Checked tonight at
   390x844.
3. **Pick the agency name** and put it in the portal config. Today every script says "<agency>", and a caller must say a real
   business name. Until then say: "Hi, it's <your name>, I run a small local web studio."
4. **Re-open each site right before you call** (10 seconds). If it loads now, do not say it is down: use the redesign opener.

## Call hours

- **Maryland law: 8 am-8 pm**, at most 3 calls in 24 h to one number, no Sundays (the dial sheet rule: 1 a day).
- **The portal uses 9 am-5 pm** (stricter): stay inside it.
- Best windows per trade (dial sheet + portal): **dentists / clinics / vets 2:00-4:00 pm on a Monday** (avoid Monday
  mornings and 12-1 pm); **HVAC / roofing / plumbing 4:00-5:00 pm** (their best is 8-9 am or 4-6 pm; the portal closes at 5).

## The opener (honest, with the proof line)

**Site down (we built a draft):**
> "Hi, is this the owner of **<business>**? It's <your name> with <agency>. I tried your website and it didn't load for me:
> **<the proof line, e.g. "thomasacservices.com: the address no longer points anywhere, checked Sunday 1 am and again at 2 am">**.
> So we built you a fresh one. It's free to look at. Can I email you the link?"

**Their site does not load, but no draft was built (redesign lane):**
> "...I tried your website today and it didn't load for me. I'd like to send you a free 2-minute check of it, no cost. What's the
> best email?" (Never say "we built you a site" on these.)

**No website (draft built):**
> "...I noticed **<business>** doesn't show a website, so we built a sample one for you. It's free to look at. Can I text or
> email you the link?" (Text only if they say yes.)

## The two offers (say one, then the other only if price is the objection)

1. **Starter site: $1,500 once + $79/month** care plan (5 pages, live in 7 days, 2 rounds of changes; $750 deposit, $750 at
   launch; MD 3% sales tax on setup where it applies). Or **$149/month for 12 months, nothing upfront**. Trades and dentists
   with the call engine: **$2,000 + $378/mo** (the BIG40 package). All from `agency/pricebook.json`.
2. **$0 upfront + $75 per qualified call** (pilot, `research/writeups/rank-rent-pay-per-job-2026-11-22.md`): a flat fee per
   inbound call of 60+ seconds from the tracked number, a new customer, in their towns. First 3 calls free. **Never a % of the
   job** (Maryland home-improvement rules), never negotiate with their customers. **Take interest only; sign nothing** until a
   Maryland attorney has read the one-page term sheet.

## The first 20, in order

Block 1, **2:00-4:00 pm: dentists / vet** (BIG40, site did not load on 11-22; $2,000 + $378/mo package, ~$6,536 first year each)

| # | Business | Town | Phone | Lane in the portal | What to say |
|---|---|---|---|---|---|
| 1 | Urbana Dental Spa | Urbana | (301) 874-0124 | site down, draft UR-5 | "urbanadentalspa.com shows a server error, checked Sunday 1:53 am" |
| 2 | AllClear Dentistry of Columbia | Columbia | (410) 381-7300 | redesign | free website check (site did not load 11-22) |
| 3 | Carroll County Dental Associates | Westminster | (410) 848-5577 | redesign | free website check |
| 4 | Garbis Dental Associates of Columbia | Columbia | (410) 730-3800 | redesign | free website check |
| 5 | Pearlfection Dentistry | Frederick | (301) 663-5550 | redesign | free website check |
| 6 | Rockville Advanced Dentistry (Mehr Tucker DDS) | Gaithersburg | (301) 963-8900 | redesign | free website check |
| 7 | McClellan Veterinary Clinic | Frederick | (301) 663-6531 | redesign | free website check |
| 8 | Family Dentistry | Rockville | (301) 340-2309 | no website, draft RO-221 | "we built you a sample: new-patient booking and reviews on a phone" |

Block 2, **4:00-5:00 pm: HVAC / roofing / plumbing** (BIG_LEADS top, site down, a draft built for each; $ score 133; trades
package $2,000 + $378/mo, or Starter)

| # | Business | Town | Phone | Code | The proof line (say it plainly) |
|---|---|---|---|---|---|
| 9 | Thomas Air Conditioning Services | Abingdon | (410) 679-3683 | AB-3 | thomasacservices.com: the address no longer points anywhere |
| 10 | Branzell Plumbing & Heating | Annapolis | (410) 263-2239 | AN-26 | branzellplumbing.com: the address no longer points anywhere |
| 11 | Apollo Plumbing & Heating | Baltimore | (410) 243-0058 | BA-36 | apolloservices.biz: the address no longer points anywhere |
| 12 | Bollinger Roofing Company Inc | Baltimore | (410) 539-0286 | BA-107 | roofingbybollinger.com: shows "page not found" (same number as the Towson row: call once) |
| 13 | Correlli Roofing Co. | Baltimore | (410) 243-8668 | BA-219 | correlliroofingllc.com: the address no longer points anywhere |
| 14 | DMV Building Services | Baltimore | (410) 375-0566 | BA-117 | dmvbuildingservices.co: the address no longer points anywhere |
| 15 | Exterior Experts Inc | Baltimore | (410) 789-2088 | BA-161 | exteriorexpertsmd.com: the address no longer points anywhere |
| 16 | Fitz Mechanical Inc. | Baltimore | (410) 426-4243 | BA-44 | fitzmechanicalbaltimore.com: shows "page not found" |
| 17 | Get It Done Home Services | Baltimore | (410) 746-9053 | BA-73 | get-it-done-home-services.com: the address no longer points anywhere |
| 18 | RED Roofing and Home Improvements | Accokeek | (240) 682-3944 | AC-1 | its listed site (aconstructionandhomeimprovementscompany.com) no longer points anywhere: ask if that is still their site |
| 19 | B & B Air Conditioning Service Co., Inc. | Rockville | (301) 881-2700 | redesign | free website check (site did not load 11-22) |
| 20 | Dan's Fan City | Rockville | (301) 424-4383 | redesign | free website check (site did not load 11-22) |

All proof lines were checked Sun 11-22 at 1:01 am and 1:53 am ET (`tools/site_down_proof.py`). After #20, open the portal's
**Today** tab: it puts each trade in its best hour (after 4 pm the HVAC / roofing rows lead), follow-ups first.

## In the portal (checked tonight on the live site at 390x844, with a test passphrase in my browser only)

- Today mode, row order, call buttons, the site-down proof lines, the outcome buttons, the tally ("Today: 1 dials, 1 connects,
  0 booked, 1 in the pipeline ($1,500 + $79/mo...)", Copy works), the proposal page: all work, no errors, no sideways scroll.
- **Fixed on night-calls:** the proposal and emails signed "Prepared by Ann, ·" with a stray comma while the agency name is
  empty. Now "Ann" (test added; cache versions bumped, nothing lead-only touched).
- **Setup gaps (owner, not code):** passphrase not set (nobody can sign in), agency name / number / postal address empty
  ("<agency>" in the scripts), `public_base` empty, so the proposal says "[the link]" instead of the draft site's address.

Log every call in the portal: Talked / Voicemail / Interested / Booked / No / **Do not call** (that number is never dialed again).
