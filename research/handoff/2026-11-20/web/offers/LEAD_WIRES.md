# Web · Offers: lines for the lead

1. **A way in from the Agency page** (agency/index.html, not my folder): one link card near the top, e.g. after the "This month" hero:
   `<a class="ag-card card" href="offers/" style="text-decoration:none"><b>Offers</b><span class="note">Prices, proposals, invoices and the monthly goal</span></a>`
2. **sw.js (offline):** add `agency/offers/`, `agency/offers/index.html`, `offers.css?v=1`, `offers.js?v=1`, `offerscore.js?v=1`, `offers.json` to the
   precache list (if agency/ is precached).
3. **Search / Jarvis words (doors.js, apps.js):** under the Agency app: `offers prices packages proposal quote invoice retainer mrr deposit contract terms 3d showcase`.
4. **Prices:** when RESEARCH.md lands, edit only `tools/web_public/agency/offers/offers.json`: `price`, `monthly`, `hours`, `days`, `"placeholder": false`, `source`.
   The test checks the 3 package names, so keep them or change the test.
5. Branch: the work is on **day-a11y** (this session may only push that branch). It sits on pc 4f637df3 and adds only `agency/offers/`,
   `tests/test_web_offers.py`, the run_area line, `tools/a11y_sweep.py` (page paths) and this folder.
