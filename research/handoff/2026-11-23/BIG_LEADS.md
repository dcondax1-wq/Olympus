# Big leads: the top 25 to call this week (2026-11-23)

From 17,230 new Maryland businesses with a phone (Overture Maps, 8 counties; `research/handoff/2026-11-22/leads/COUNTS.md`). These 25 head the caller portal's list (`agency/portal/calllist.json`, Today mode, biggest $ first). The 600 ranked calls (first 100 + next 500) are on the list; the 17k county files stay private.

**Why these first:** they are high-ticket trades (roofing and HVAC jobs run into the thousands, so a $1,500 site pays for itself with one job). Their own website **does not load**, so they already paid for a site once and are losing calls today. The opener is true: *"I tried your website and it didn't load for me, so we built you a fresh one. It's free to look at. Can I email you the link?"*

**$ per sale:** Starter $1,500 + $79/mo. After the caller's $300 commission, **$1,200 + $79/mo** to the owner. A 2-4% close on the first 100 is 2-4 clients = **$2,400-$4,800 + $158-$316/mo** (an estimate, not a result).

| # | Business | Trade | Where | $ score | Why |
|---|---|---|---|---|---|
| 1 | Thomas Air Conditioning Services | HVAC | Abingdon, Harford | 133 | HVAC, its web address no longer exists; storefront address |
| 2 | RED Roofing and Home Improvements | roofing | Accokeek, Prince George's | 133 | roofing, its web address no longer exists; storefront address |
| 3 | Branzell Plumbing & Heating | HVAC | Annapolis, Anne Arundel | 133 | HVAC, its web address no longer exists; storefront address |
| 4 | Apollo Plumbing & Heating | HVAC | Baltimore, Baltimore City | 133 | HVAC, its web address no longer exists; storefront address |
| 5 | Bollinger Roofing Company Inc | roofing | Baltimore, Baltimore City | 133 | roofing, the site answers "page not found"; storefront address |
| 6 | Correlli Roofing Co. | roofing | Baltimore, Baltimore City | 133 | roofing, its web address no longer exists; storefront address |
| 7 | DMV Building Services | roofing | Baltimore, Baltimore City | 133 | roofing, its web address no longer exists; storefront address |
| 8 | Exterior Experts Inc | roofing | Baltimore, Baltimore County | 133 | roofing, its web address no longer exists; storefront address |
| 9 | Fitz Mechanical Inc. | HVAC | Baltimore, Baltimore City | 133 | HVAC, the site answers "page not found"; storefront address |
| 10 | Get It Done Home Services | roofing | Baltimore, Baltimore City | 133 | roofing, its web address no longer exists; storefront address |
| 11 | Great American Gutters & Painting | roofing | Baltimore, Baltimore County | 133 | roofing, its web address no longer exists; storefront address |
| 12 | Jim's Plumbing and Heating | HVAC | Baltimore, Baltimore County | 133 | HVAC, its web address no longer exists; storefront address |
| 13 | Kelbie Home Improvement Inc - Baltimore Flat Roof Services | roofing | Baltimore, Baltimore City | 133 | roofing, the site is broken (server error); storefront address |
| 14 | Mitchell Plumbing & Heating | HVAC | Baltimore, Baltimore County | 133 | HVAC, the site answers "page not found"; storefront address |
| 15 | Ozone Heating And Air Conditioning | HVAC | Baltimore, Baltimore County | 133 | HVAC, its web address no longer exists; storefront address |
| 16 | Precision Heat Treating Corporation | HVAC | Baltimore, Baltimore County | 133 | HVAC, its web address no longer exists; storefront address |
| 17 | Royalty Roofing | roofing | Baltimore, Baltimore County | 133 | roofing, its web address no longer exists; storefront address |
| 18 | Sds Mechanical | HVAC | Baltimore, Baltimore City | 133 | HVAC, its web address no longer exists; storefront address |
| 19 | Sealcote Roofing Co. | roofing | Baltimore, Baltimore City | 133 | roofing, its web address no longer exists; storefront address |
| 20 | Tin Roof | roofing | Baltimore, Baltimore City | 133 | roofing, the site does not load; storefront address |
| 21 | William C Mcdermott & Son | roofing | Baltimore, Baltimore City | 133 | roofing, its web address no longer exists; storefront address |
| 22 | Your Hvac Specialist | HVAC | Baltimore, Baltimore City | 133 | HVAC, the site answers "page not found"; storefront address |
| 23 | Blevins Heating & Cooling | HVAC | Bel Air, Harford | 133 | HVAC, its web address no longer exists; storefront address |
| 24 | Champion Heating & Cooling | HVAC | Bel Air, Harford | 133 | HVAC, its web address no longer exists; storefront address |
| 25 | Beltsville Heating & Ac Inc | HVAC | Beltsville, Prince George's | 133 | HVAC, its web address no longer exists; storefront address |

$ score (tools/lead_value.py) = trade value x 10 (roofing / HVAC 10, plumbing / electrical 9, remodeling 8, auto / dental 7 ... restaurants 1) + 10 a phone + 15 the site is down + 5 a street address + 3 listed hours. Overture has no ratings or review counts, so they are not in it.

**Before dialing:** the portal's Do Not Call field + the PC scrub (`python -m agency.portal build` with the owner's free DNC download) apply; a person dials by hand (no auto-dialer, no AI voice: Maryland law). Ties at the top (133) are equal by score; the list order among them is by county, then name.
