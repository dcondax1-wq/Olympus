# DATA TRUTH: asks for other slices (day-nqdash3, 2026-11-20)
Found by `python -X utf8 tools/truth_check.py --pages`. TRUTH = the PC's 15-minute report (ntfy), decoded by tools/pc_feed.py; report: TRUTH.md.
At 10:20 ET ATLAS won +$514.18: **$25,401.38, room $1,401.38, today +$514.18, to payout $948.62** (the payout coach's need_more, the number
pc_feed.js `payoutLines` gives every page). Re-run the checker after a fix; a row disappears when it is right.

## 1. HOME + CITIES (day-cities3): Glance shows ATLAS "TO PAYOUT $1,449"; every other page shows $949
- File: `tools/web_public/widget/olympus-widget.js` line ~87: `to_go: okN(c.to_target) ? ... : null, to_label: funded ? 'to payout' : 'to pass'`.
- Wrong source: the raw PC card `board.atlas.to_target` (= the PC's own $750-ping line, balance $26,850).
- Right source: the same rule as NQ / Trading / Board / ZEUS: run `PC_FEED.payoutLines(board, accounts, lite, PAYOUT_COACH)` on the post
  before reading `to_target` (it sets `to_target = coach.need_more`).
- glance.html: add `<script src="../business/payoutcoach.js?v=1"></script>` before olympus-widget.js.
- Scriptable script (no coach): label the number "to the $750 ping" or leave it out; never "to payout" with a different number.

## 2. DESIGN (day-arenas): Helios draws the cloud's paper twin as the Zlarior 50K tree ("MFFU 50K Eval $49,900 · Drawdown left $1,900")
- File: `tools/web_public/helios/helios.js` boot(): `T.canonHome(await T.withPcFeed(home), ...)`; the grove lists every home.json account.
- Wrong: `home.accounts[id=mffu50k_eval]` (badge PAPER, cloud numbers) and the `cloud_paper` row show as accounts.
- Right: the PC's numbers ($49,192.78 / $1,024.58), or nothing for that tree when no PC post has arrived. Skip any account with
  `badge === 'PAPER'` or `source === 'cloud'` (nqcore `cloudCopy` does this on NQ), or keep the twin only as one grey "cloud paper test" leaf.

## 3. LEAD (tools/build_web_dashboard.py, lead-only): home.json puts the cloud twin under the REAL account id
- `home.json accounts[]`: id `mffu50k_eval`, source `pc`, badge `PAPER`, balance $49,900 (the twin), plus a separate `cloud_paper` row
  with the same numbers. `board.lit` (source "cloud paper") and `live.eval` say $49,900 too.
- Any page that reads home.json alone, or before the PC post arrives, shows $49,900 / $1,900 for Zlarior 50K.
- Ask: in the build, keep the twin ONLY under `cloud_paper` / `live.eval_paper`. Leave `mffu50k_eval` out when there are no PC numbers
  (or set its eval to null with `source: 'none'`). Set `board.lit` balance / room / to_target to null when its source is the cloud.
  Check after: `python -X utf8 tools/truth_check.py` (the 3 home.json rows go away), test_bots_back, test_feed_accounts.

## 4. ALL SLICES: one data-age format (`tools/web_public/age.js` + `age.css`)
- `OLY_AGE.text(sec)` gives "updated just now / 4 min / 2 h 10 min / 3 days ago".
- `OLY_AGE.level(sec, kind)` gives ok / warn / bad with ONE set of limits: pc 20 min / 1 h, bars 80 min / 3 h, daily 26 h / 3 days, weekly 8 / 15 days.
- `OLY_AGE.chip(el, sec, kind)` draws the dot + words.
- Board, NQ and Trading use it now. Seen elsewhere in other formats: "PC silent 36 min ago" (Glance), "4 minutes ago" (NQ source line,
  pinned by test_nq_page), "Last report 10 days ago" (Board banner). Adopt the chip where a page shows a data age; keep page-specific sentences.

## 5. Not problems (checked)
- Business / Oikos / Chrysos / Mercury / Planner show DEMO: their data (business.json, money files) is the owner's private file, not published. Correct.
- Clio quotes ATLAS $24,887: a dated research write-up (atlas_health, Nov 18). It's history, not a live number.
- Board's $26,946: the owner's own Nov 17 note. When the PC post is missing, the tile now says "funded" (the plan, newer than the note)
  with a red "updated 3 days ago".
- The PC's report was 36-38 min old at 15:06 UTC (2 posts missed). The checker flags it. Worth a look by the alert investigation.
