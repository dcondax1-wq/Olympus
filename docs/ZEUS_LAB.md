# ZEUS Lab (owner 2026-11-18)

Owner: "I want our strategies to keep getting stronger. Make a spot where the bot continues to learn as a whole from each,
and changes and adapts if it needs to."

| What | How |
|---|---|
| What it is | One list of every idea to make Zlarior (LIT) and ATLAS stronger, re-tested every night on the real backtests. |
| Where you see it | Business -> ZEUS Lab (`tools/web_public/business/lab.html`): status, $ a month today vs with it (Jan-Jun / Jul-Oct / 2021-25), paper shadow $, what it would change. |
| What it can change | Nothing live. It never edits `live_model*.json`, `second_model.json`, `data/account_b.json` (hashed before and after). |
| When you hear from it | One push + one Board line when an idea is READY TO ADOPT ("ZEUS Lab: X passed. Reply yes to adopt"), or when the edge light turns RED (size-down advice). |
| Your part | Say yes or no. On yes, Claude runs the CLAUDE.md steps (both live files together, `python tools/lit_losses.py live`, `python tools/model_versions.py`). |

## The path of one idea
1. **Registry** `research/lab/zeus_lab/registry.json`: written down before it is judged (kinds `lit_tilt`, `atlas_tilt`,
   `lit_x`, `lit_idea` = an exit or two-fact size rule from `tools/lit_lab_ideas.py` (time stop, NY-open / news exits,
   stall exit, breakeven on a close, NR7, London build-ups; `python -X utf8 tools/lit_lab_ideas.py check` = options off is
   live), `atlas_member` = a new ATLAS member judged by `tools/atlas_plus.py`, its stored verdict, every version it
   searched counted, `parked`). Add one with `zeus_lab.register(entry)` (validated, keeps the file's layout). The "Tested and rejected" list is `rejected_forever` (never re-run; `blocks` = a bot + fact).
2. **Proof** (every run): the real Zlarior backtest (`tools/lit_edge`, LIT size + live two_week eval path) or ATLAS
   (`tools/atlas_deep`, the real account-B rules), costs in. Picked on 2026 Jan-Jun, checked on Jul-Oct, both better,
   eval fails not up, 2-4 trades a week (LIT), 2021-25 shown (a gate for ATLAS), enough trades changed, the learn loop's
   size shuffle, plus a sign-flip placebo under a many-tests bar (0.2 / every cell ever tested here + the learn queue).
3. **Shadow**: a passing idea starts a paper ledger on its first pass day; only LATER days count.
4. **READY TO ADOPT**: still passing + 4 weeks of shadow + 2 changed trades + shadow $ not below 0. Shadow below 0 = rejected.
5. **Cross-learning**: each Zlarior size rule is tried on ATLAS and the other way round (VIX, stop vs ATR, R:R), unless
   that bot + fact is already rejected.
6. **Safety**: edge light (`tools/edge_health.py`) RED = advice to hold new evals / half size (your yes). Never a stop:
   the drift switch was tested and rejected (0/51); the approved guards keep running.

## Commands
- `python -X utf8 tools/zeus_lab.py run [--only id,id] [--publish]`: re-test now (~1-2 min), `--publish` writes the page copy.
- `python -X utf8 tools/zeus_lab.py status`: the table. Test: `python -X utf8 -m tests.test_zeus_lab` (offline).
- Nightly on the PC: `engine/learn_loop.run` calls `zeus_lab.nightly(C)` after its own ideas (same child, low priority;
  `LE_LAB=0` turns it off). Outputs: `research/lab/zeus_lab/out/` + `tools/web_public/business/lab_pc.json` (gitignored).

## First run (2026-11-18, cloud, data to Oct 16)
6 runnable ideas, 0 pass (normal): ATLAS skip VIX < 15 (only 4 Jan-Jun trades, Jan-Jun -$292 after fees), ATLAS x1.25 at
VIX >= 18 / tight stop / big R:R (Jan-Jun 2-week pass 61.3 -> 60.5%), Zlarior big R:R x1.25 (Jul-Oct -$215 at LIT size),
Zlarior 3R target from 14:00 (3 trades changed). 3 cross ideas blocked (VIX / stop-ATR already rejected for Zlarior),
5 parked (Kalshi 5c pause, Asia $300, scale-in from session 5, 15m trail, ATLAS hunts).
