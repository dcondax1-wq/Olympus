# Outreach: lines for the lead / the other teams

1. **day-kalshi (Leads page):** the status key is SHARED: `agency.leads.status.v1` = `{ id: { s, t } }`. Outreach adds three `s` values: `voicemail`, `emailed` and `won` (it already uses `called`, `interested` and `no` the same way). Please show them on the Leads page, or treat any unknown `s` as "Called". Lead ids must stay stable between finder runs (the `osm-n...` ids are).
2. **cities3 (the site factory):** publish `tools/web_public/agency/sites/index.json` = `{ "sites": { "<lead id>": "sites/<slug>/" } }`. Paths are relative to `agency/`; https URLs also work. Outreach then links each lead to its own built site ("Their site (built)") instead of the niche demo. `javascript:` and other schemes are refused.
3. **Agency HQ / hub:** a tile for `agency/outreach/` reading localStorage `agency.outreach.summary` (`{n, label, next, t, pipe: {due, interested, won}}`).
4. **sw.js:** add `agency/outreach/` (`index.html`, `outreach.css?v=1`, `outreach.js?v=1`, `outreachcore.js?v=1`, `scripts.json`) if agency/ is precached. Offers is now `offers.css?v=3`.
5. **Search words (doors.js / apps.js):** `outreach email call voicemail script follow up objections agreement contract invoice close today 20`.
6. **Owner steps** (add to STATE "Waiting on the owner" if you want): fill Me on the phone (name, business, phone, postal address or PO box); set up his own free payment account and paste its link on the invoice.

## 7. The email autopilot's counts ride the PC report (no ntfy posts of its own; lead 2026-11-20)
`agency/autopilot/card.py` writes `data/agency_mail/summary.json` after each pass. The file is gitignored and under 120 bytes:
`{"t","m":"off|dry|live","n","c","f","r","i","s","q","kind":"agency_mail_pub"}`.

Patch `tools/pc_report.py` in three places:

1. **EXT_ORDER** (line ~72): append `"am"` at the end:
```python
EXT_ORDER = ("brd", "life", "mf", "board_trades", "at", "fq", "zl", "learn", "lab", "glance", "kalshi_rewards", "kalshi_k1", "kalshi_live", "am")
```
2. **The snapshot** (next to the `kalshi_k1` block, line ~465):
```python
    try:                                    # the email autopilot's counts (agency/autopilot/card.py, < 120 bytes, numbers only)
        from agency.autopilot import card as _am
        snap["am"] = _am.read_card(os.path.join(root, "data", "agency_mail", "summary.json"), now)
    except Exception:
        snap["am"] = None
```
3. **The ext block** (next to `out["kalshi_k1"]`, line ~619):
```python
    if isinstance(snap.get("am"), dict):            # agency/outreach/ "Email autopilot" card (agency/autopilot/card.py), < 120 bytes, ext post
        out["am"] = snap["am"]
```
`pc_feed.js` already merges any unknown ext key into the lite live.json (`lite.am`), and `agency/outreach/` reads it with `PC_FEED.fetchLatest`.
Also: the autopilot's own phone pushes (private topic) are capped at 4 a day.
