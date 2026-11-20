# Outreach: lines for the lead / the other teams

1. **day-kalshi (Leads page):** the status key is SHARED: `agency.leads.status.v1` = `{ id: { s, t } }`. Outreach adds three `s` values: `voicemail`, `emailed` and `won` (it already uses `called`, `interested` and `no` the same way). Please show them on the Leads page, or treat any unknown `s` as "Called". Lead ids must stay stable between finder runs (the `osm-n...` ids are).
2. **cities3 (the site factory):** publish `tools/web_public/agency/sites/index.json` = `{ "sites": { "<lead id>": "sites/<slug>/" } }`. Paths are relative to `agency/`; https URLs also work. Outreach then links each lead to its own built site ("Their site (built)") instead of the niche demo. `javascript:` and other schemes are refused.
3. **Agency HQ / hub:** a tile for `agency/outreach/` reading localStorage `agency.outreach.summary` (`{n, label, next, t, pipe: {due, interested, won}}`).
4. **sw.js:** add `agency/outreach/` (`index.html`, `outreach.css?v=1`, `outreach.js?v=1`, `outreachcore.js?v=1`, `scripts.json`) if agency/ is precached. Offers is now `offers.css?v=3`.
5. **Search words (doors.js / apps.js):** `outreach email call voicemail script follow up objections agreement contract invoice close today 20`.
6. **Owner steps** (add to STATE "Waiting on the owner" if you want): fill Me on the phone (name, business, phone, postal address or PO box); set up his own free payment account and paste its link on the invoice.
