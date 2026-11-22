# Do-Not-Call: the free registry access, Maryland's area codes, and the scrub step

## Short answer

- **Business numbers are not covered** by the National Do Not Call Registry: "The National Do Not Call Registry is only for personal phone
  numbers. Business-to-business calls are not covered" (FTC). We scrub anyway, because many small businesses list a cell phone that is
  also personal, and a court may treat that as residential (*Chennette v. Porch.com*, 9th Cir. 2022).
- **Access is free for up to 5 area codes a year.** By law the FTC "shall not charge a fee to any person for accessing the first 5 area
  codes of data" (15 U.S.C. 6152). Each further area code is **$85 a year** (FY2027, from 2026-10-01) or $43 for half a year (FTC, 2026-08).
- **Maryland has 6 area codes:** 301, 240, **227** (overlay of 301/240, in service since 2023-06-14, given out only once 301/240 run out),
  410, 443, 667 (overlay of 410/443).
- **Our free 5: 301, 240, 227, 410, 443.** 667 is the sixth. Our list has no 667 numbers today (2026-11-21: 48 x 301, 16 x 410,
  6 x 240, 2 x 443). Any 667 number is held off the list automatically. Add 667 for $85 only if callers start finding many 667 numbers.

## The owner's one-time sign-up (about 10 minutes, then 2 minutes a month)

1. Go to **telemarketing.donotcall.gov** -> **Register**. Choose the "Seller" entity type, give the agency name, address and the
   agency Gmail, and say who calls ("telemarketer calling on our behalf", or yourself).
2. You get a **SAN** (Subscription Account Number). Keep it in your password manager; it is not a secret for the repo, but keep it private.
3. **Choose area codes:** 301, 240, 227, 410, 443 (free). Pay $0.
4. **Download** each area code as a text file ("full list", flat text, one number per line) into
   `%USERPROFILE%\.olympus\caller\registry\` named `301.txt`, `240.txt`, `227.txt`, `410.txt`, `443.txt`.
5. Run `python -m agency.dnc_scrub --stamp` (it records the date and the area codes).
6. **Every 31 days:** download again, stamp again. The TSR requires a copy no older than 31 days. The scrub refuses an older copy and
   marks the list STALE, so callers stop.

## The scrub step in the pipeline (built: `agency/dnc_scrub.py`, tests `tests/test_dnc_scrub.py` 9/9)

```
python -m agency.portal build      # the list from leads + concept sites, minus chains, websites, never-again
python -m agency.dnc_scrub         # NEW: minus the registry; listed numbers -> never-again on every channel
(publish the portal as usual)
```

- A number on the registry -> the row leaves the list, and its lead id joins `agency_never.json` (no call, no email, ever).
- An area code we did not download (667, toll-free 8xx, out of state) -> held off the list, counted in the header (`dnc_held`).
- No download, or one older than 31 days -> the list header says `"dnc": "STALE"`, nothing counts as scrubbed, and the command exits 1.
- A number a caller found on Google Maps reaches the list at the next build, and is scrubbed there before anyone dials it. Callers dial
  only numbers that are on the list.
- **Registry data never leaves the PC.** The published list only loses rows, and never says why. The FTC allows registry data to be used only to
  prevent calls to listed numbers.

## Business line or personal line?

| Sign | Treat as |
|---|---|
| The number is on the business's own sign, website, Google Maps or OpenStreetMap listing, with a street address | **Business**: callable after the scrub |
| The person answers "hello?" with no business name, says it is their personal or home phone, or it's clearly a home-based one-person business | **Personal**: apologise, log **Do not call**, never again |
| A number found only on a personal Facebook profile or in a review | **Don't use it** |
| The number is on the registry | **Never** (the scrub removes it) |

Sources: FTC "National Do Not Call Registry FAQs" (consumer.ftc.gov); FTC press release "FTC announces 2027 telemarketer fees to access
the National Do Not Call Registry" (2026-08); 15 U.S.C. 6152 (govinfo.gov); Maryland PSC "227 area code arrives in MD June 14 2023";
Wikipedia "Area codes 301, 240, and 227" and "List of Maryland area codes"; 16 CFR 310.4(b)(3) (31-day rule); *Chennette v. Porch.com*
(9th Cir., 2022-10-12).
