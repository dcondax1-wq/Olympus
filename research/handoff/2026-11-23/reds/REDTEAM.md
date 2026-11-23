# night-reds red team (2026-11-23): f739173e0 -> night-reds-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | test_bat_menu d red: the rebuilt tools/web_public/cities/brain-data.json carries "GITHUB_SIGNIN.bat" (old top-folder place) from research/findings/LEDGER.md (history, rightly not rewritten); build_brain_hub --check says the JSON is up to date | LOW | allow-list entry for the generated file (test_bat_menu ALLOW) |
| 2 | test_agora_audit: 3 FAIL (hard FAIL per app, theme-color, accents vs apps.js) | pre-existing | the same 3 fail on origin/pc; this branch lowers the per-app counts; the accents one waits for the lead's apps.js |
| 3 | research/lit/live_check.json (test_lit_live's output) is committed with new numbers | LOW | left (tracked; the lead decides) |
| 4 | STATUS.bat / pc_care: the download URL of pc_status.ps1 is the public site (dcondax1-wq.github.io/pc/): running a script fetched from a public page = whoever can change the site can run code on the PC | LOW (pre-existing) | not changed |

Checked: the 5 "stale tests aligned" follow real changes, none weakens a check: account_b_funded = the owner's payout plan
(first request the max $1,000 at $2,100 profit: payout line $27,100, CLAUDE.md), now 71/71 (was 65/71 on pc); ops = the
FIX_CLOCK.bat fix text (7f22befd); context_refresh = the fsutil write; help_page = the gate-nav script; kalshi_k8 = ?v= k58 or
newer; why_page = OLYMPUS NIGHT black theme; premarket_brief = the first weekday after the newest bar (no fixed date). No live-
loop change vs origin/pc (engine/ninjatrader.py: one docstring line) -> test_lit_live not needed. Merge with night-integrate
7bd71589e: clean.
Tests: smoke 10/11 (zenith_mode: no playwright here), account_b_funded 71/71, context_refresh 23/23, help_page 26/26,
kalshi_k8_dash 65/65, ops 114/114, pc_care 48/48, why_page 46/46, premarket_brief 74/74, node_suites ALL PASS, bat_menu 18/18,
agora_audit 3 FAIL (= origin/pc).
