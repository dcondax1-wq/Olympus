# Field audit: phone JS readers vs the PC's real status post (night-truth, 2026-11-22)

Source of truth: `real_status_merged.json` (tonight's merged core `le-live` + ext blocks). Producers checked: `tools/pc_report.py`
(full(), CORE_KEYS, CARD_KEYS, POS_KEYS, TRADE_KEYS, _life), `engine/brain_glance.py`, `engine/mffu_view.py`, `engine/clock7.py`.
Most NQ readers see the post through `pc_feed.js homeOver` (home.json shape: live.pc, live.reporter, board, accounts), the rest read the
raw post (`lite.mf / at / k7 / life / glog / zl / pc.glance`). A field empty tonight but produced when it exists (glance `pos`, `chk`, `blk`, `nar`;
mf.f `ft` / `pt`; card `position`) is not listed as a bug.

| reader file:line | field read | sent? | fix |
|---|---|---|---|
| business/mffumodel.js:212 (card, payout state) | coach `last_trade` / `first_trade` from accounts.json `told` only | PC SENDS `mf.a[].lt` and `mf.a[].f.ft`, the reader ignored them | **FIXED**: `last_trade: mf.lt \|\| told`, `first_trade: f.ft \|\| told`. ATLAS's 7-day countdown now shows (trade by 2026-11-26, 3 days left) instead of nothing, on MFFU center / Accounts / Board / payout card (all go through MFFU_MODEL.cards). |
| business/mffucenter.js:233 | `life.acc[id].why` (life_why line on a locked / failed / passed card) | NO: `pc_report._life` keeps only label, stage, since, bal (engine/lifecycle has `why`) | reader falls back to '' (fine). Python side for the lead: add `"why"` (cut to ~80 chars) to `_life`'s kept keys if the line is wanted. |
| business/mffucenter.js:173 | board card `position.unrealized_usd` | NO: POS_KEYS has `unrealized_r`, not `_usd` | none needed: falls back to $ from `lite.price` (labelled "NQ <price>"). |
| business/mffucenter.js:171 | board card `position.dir` | NO (POS_KEYS has `side`) | none: `side` is read first. |
| business/mffucenter.js:161 (boardTrade) | board.trades `entry / stop / target` | NO (TRADE_KEYS has none) | none: only the fallback when ext `at` is missing; `at` rows carry them. |
| business/payoutcard.js:26 (pcState) | `board[key].funded`, `board[key].last_trade` | NO (never a card key; the file's own comment says so) | none: `modelState` (MFFU_MODEL + mf) is the live path and now gets `lt` too. |
| business/payoutcard.js:49 | `first_trade: null` | ft exists in mf.f | none: `eligible_from` (= PC `ef`) is passed, same result. |
| business/mffumodel.js:59 | board card `stage` | NO (CARD_KEYS has `status`) | none: `status === 'funded'` is read first. |
| nq/nqdesk.js:263 (quality, "Last trade alert") | `live.reporter.na` | NO: reporter = t, server, nt, market_open, mode, hb_src, problems | none: falls back to the newest board trade entry/exit (pinned by tests/test_nq_desk.py fixture). |
| nq/nqcore.js:102 (evalBlock lit fallback) | `accounts[].eval.clock_text` | NO (eval whitelist in pc_report.full) | none: only when board.lit is missing; wait text is then empty. |
| nq/nqcore.js:108,114,115 | `live.pc.blitz`, `live.pc.second` | NO in the PC post (pc whitelist) | none: home.json (cloud) keeps them through overlayHome; BLITZ is hidden/paper. |
| nq/clock7.js:49 | `pc.keepalive` | NO (pc whitelist) | none: only when `k7` is absent; `k7` is always sent with `mf` (cuts drop only act/dl). |
| pc_feed.js:402 (accountsOver) | `accounts[].position / orders / stats` | NO (accounts whitelist) | none (read-only file): null for live rows; stats come from `mf`. |

Checked and SENT (no change): glance v2 `stage wait why lv arm log day room mll armed mode on what px lobes dll dll_used` (+ `pos chk blk nar` when
present); `mf.a[] id nm sd l4 td lt bd wd eq n w bt wt aw al pf ct f{cp bd cd ef pn mr st}`; `k7.a[] id nm base dl hard left ses act on lvl`; `at.a[].tr`
10-tuples; `life.acc{label stage since bal}`; `glog.lit/atlas [hm,text]`; `zl.s/d`; `board.lit/atlas` CARD_KEYS + window + waiting; `accounts[].eval/pnl/conn`;
`price`, `reporter.t`, `pc.adapter/running/t`, `ext_t`, `mf.t`, `at.t`.

## Python side + Trading Home (lead, night-truth)
| Reader | Field read | Sent? | Fix |
|---|---|---|---|
| nq/trading_home_core.js "Every account armed" | `accounts[].badge == LIVE` as "armed" | badge = a REAL account, not armed; ATLAS not in `accounts[]` at all | core `ar` {bot: [on, armed]} (pc_report.armed_core of the glance); held = off / locked / not LIVE / ar armed 0; synthetic ATLAS row from board.atlas |
| engine/brain_glance.build bots | extra accounts other than rapid/rapid2 | Zlarior 25K #2 (b25k_2) sent in acct.accounts, never shown | Package C (other builder): LEAD_WIRES |
| engine/brain_glance.rapid room | `eval.anchor.floor` | absent until a broker anchor exists (new Rapid: phone had no room) | Package C (other builder): LEAD_WIRES |
| mffucenter.js:233 life_why | `life.acc[].why` | dropped by pc_report._life ON PURPOSE (ext size; tests.test_live_publish pins it) | none: the page shows nothing in its place |
| tools/board.py ACCOUNTS | funded balance | $25,401 (eval terms) | engine/mffu_view.money_view (twin of pc_feed.js mffuView): $401, floor -$599 |
| (already on land-fixes) brain_glance.atlas armed | `account_b.armed` | never in account_b.info | _ab_armed (kind LIVE + enabled) |
| nq/braincore.js on / armed | `pc.glance.bots[].armed` (ext, up to 44 min old) | glance only | prefers core `ar`; desk rows fresh25 / rapid1 get on / armed |
| business/accounts.js Balance | funded `balance` | $25,401 (eval terms) | "Balance (MFFU, from $0)" $401 + "To the max payout" via PC_FEED.mffuView |
| pc_report full() accounts[] | `enabled` / `locked` / `armed` | dropped | kept when the PC sends them |
| pc_report post t | the 5-min heartbeat | the bot's 15 s live.json existed on 127.0.0.1 | gather() prefers it when newer (4 s timeout, full fallback); hb_t / hb_age unchanged |
