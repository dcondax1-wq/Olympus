# Proof for the site-down pitch (2026-11-22)

`python tools/site_down_proof.py` (re-check + proof) and `--parked` (parked / for-sale scan of sites that look up). Detail per lead stays in the
private county files; the public call list carries one plain line per row (the domain, what failed, two check times in ET), e.g.
*"Your site thomasacservices.com didn't load: the address no longer points anywhere. Checked Sun 11-22 1:01am and 1:53am ET."*

| What | Count |
|---|---|
| Broken sites re-checked (3rd fetch, Sun ~2am ET) | 2,377 -> 14 answered again and were dropped |
| Why the rest fail | address gone (DNS) 1,685 · page not found 267 · no answer 202 · server error 87 · certificate warning 82 · other 40 |
| 'Working' sites that are really parked / for sale | 139 confirmed (12,291 high-ticket county sites + 710 town sites scanned; 9 false alarms reverted after tightening the patterns) |

## The top 600 calls (first 100 + next 500)

| Reason | First 100 | Next 500 | Top 600 |
|---|---|---|---|
| Address gone (DNS) | 58 | 227 | **285** |
| Page not found | 19 | 27 | 46 |
| No answer (timeout) | 9 | 21 | 30 |
| Server error | 6 | 16 | 22 |
| For sale | 4 | 14 | **18** |
| Certificate warning | 3 | 11 | 14 |
| Parked | 1 | 2 | 3 |
| Other | 0 | 6 | 6 |
| No website at all | 0 | 176 | 176 |

Openers: site down = *"I tried your website and it didn't load for me, so we built you a fresh one. It's free to look at. Can I email you the link?"*;
for sale / parked = *"Your old web address <domain> now shows a 'for sale' (or parked) page, so people who look you up online find nothing. We built you a fresh site..."*

$: each is a trades lead (roofing / HVAC / plumbing / electrical first): trades package $2,000 + $378/mo, or Starter $1,500 + $79/mo.
After the caller's $300: $1,700 + $378/mo or $1,200 + $79/mo to the owner.
