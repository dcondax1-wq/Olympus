# ATLAS funded 25K at ~$150 a trade on the LIVE sizing path: pre-registration (2026-11-24, before any run)

PAPER RESEARCH ONLY; nothing applied. Follow-up of research/badcase (research lane said $150 beats $250 in all 4 markets).
Engine: tools/atlas_funded.py unchanged (ATLAS account units, tools/second_mix.play_day, engine/account_b.qty / engine/sizing
.funded_qty with the real best-day guard (max_win $1,000), the soft daily loss guard, engine/funded_life.track payouts:
buffer, $250-$1,000, best day <= 50%, 2 days a cycle, 48 h, 80% split, 5 payouts). Code research/atlasfund/run.py ->
results.json.
Variants (3, counted):
- **today**: the live 25K funded preset (pct 0.6 of the room, $50-$750, ref 20, max_win $1,000, skip_breach) = engine/account_b.qty.
- **cap150**: the same preset with pct_max_usd = $150 (sizing.funded_qty on the live preset, one number changed).
- **room15**: account_b's EXISTING switch "funded_room_pct": 0.15 in the account_b block (engine/account_b.funded_cfg: the share
  of the room becomes min(0.6, 0.15) = ~$150 at $1,000 of room) = engine/account_b.qty on that spec.
Spans: 2021-25 (2021-11-01 .. 2025-12-31), 2025, Jan-Jun 2026, Jul-Oct 2026. Per span: 1,000 MC funded accounts x 126
sessions (5-session blocks, seed 23) + the real back-to-back path. Report payouts (6 months), $ paid to the owner, lost %,
dead (lost + stuck) %, first payout median.
Pass ("needs owner yes") = $ paid (MC 6 months) higher than today in ALL 4 spans AND dead % not higher in any span.
