# A5 - Execution audit: order lifecycle, reconciliation, recovery, startup (2026-10-25)

Agent 5 of 5, pre-launch audit for the go-live tonight (2026-10-25 18:00 ET). Paper / Sim only: every test below runs on
fake NinjaTrader folders (`engine/ninjatrader._FakeNT`, temp dirs, Sim101/102/103 or made-up names). Nothing was armed,
nothing was sent to a real NinjaTrader. Plain-language runbook: `STARTUP_AND_RECOVERY_RUNBOOK.md` (same folder).

## Result in one screen

| # | Finding | Label | Fixed in | Regression test |
|---|---|---|---|---|
| 1 | **Account B / extra-account kill and the remote "flatten" wrote `FLATTENEVERYTHING`.** `AccountB.kill`, `multi_account.Account.kill` and `LiveBot.flatten_now` (remote flatten) route `{"reason": "KILL SWITCH"}`; the adapter turned every such action into `FLATTENEVERYTHING`, which NinjaTrader applies to ALL accounts and connections. With LIT 50K + account B 25K on one NinjaTrader, closing B (or a remote flatten while B was open) also flattened the LIT eval and cancelled its stop/target. Demonstrated on the old code: `a5_logs/test_nt_exec_audit_on_OLD_code.txt` (A: "LIT's Sim101 position ... untouched" FAIL; B: both LiveBot rows FAIL). | **BUG_FIX** | `engine/ninjatrader.py` `kill(scope)`, `_kill_account`, `send`; `engine/live.py` `kill_switch` | `tests/test_nt_exec_audit.py` A, B |
| 2 | **No duplicate-process guard at the account level.** `run_bot.ps1` has a supervisor mutex + port check, but a second `python server.py` (other port, other checkout, a CLI `--sim-roundtrip` while the bot runs) could write orders for the same account into the same `incoming`. Old code: second adapter "READY" and writing. | **BUG_FIX** | `NinjaTraderAdapter._acquire_lock` / `release_lock` (`<NinjaTrader 8>\le_locks\<account>.lock`, OS lock, released by the OS on exit/crash and by `LiveBot.stop`) | C |
| 3 | **Order file published with overwrite.** "move" mode used `os.replace(le_outbox\x, incoming\x)`, which silently replaces a file of the same name still waiting in `incoming` (another writer, same ms + seq). Old code: our file overwrote an existing `oif_le_<ms>_1.txt` (log F). | **BUG_FIX** | `_publish` (Windows `os.rename`, POSIX hard link: both refuse an existing target) + retry under a new name | F |
| 4 | **Corrupted state file.** `data/ninjatrader_state.json` holding `[]` crashed the adapter constructor (`AttributeError: 'list' object has no attribute 'get'`, bot start fails); a torn file was logged as a warning and the open bracket silently forgotten (no alert, stop moves lost). | **BUG_FIX** | `_restore` (moved aside as `.corrupt-<t>`, `state_problem` saved, phone alert at the first tick), `_state_problem_resolved` (entries blocked until NinjaTrader shows the account FLAT and no bot order is working - orphans from the OIF audit log cancelled by id - or `--confirm-reset`) | G |
| 5 | **No account allowlist.** Any account Name passed with armed + phrase + `NINJATRADER_LIVE=1` got orders (a typo, or account B's / a funded account's Name in the wrong slot). | hardening (requested d) | `allowed_accounts` / `allow_account`, `--allow-account`, `_live_gate`; line-level `_scope_problem` (PLACE/CLOSEPOSITION must name the adapter's own account; CANCEL/CHANGE only `LE...` ids; FLATTENEVERYTHING/CANCELALLORDERS only inside the owner's global kill) | D, A |
| 6 | **No startup reconcile.** A restarted bot could route its first entry before anything was compared. | hardening (requested c) | `engine/guards.py` guard 0 `startup_reconcile` (`startup_problems`, `startup_tick`, latched), `NinjaTraderAdapter.startup_problems` | E |
| 7 | Interrupted publish: a crash between writing `le_outbox\x` and the move left the file there forever (never executed, but clutter that a later manual copy could run). | hardening | `_sweep_outbox` at adapter start (files > 10 s old deleted, never moved in) | F |

Owner impact tonight: **one extra line, once**: `python -m engine.ninjatrader --allow-account "<eval Name>"` before
the live `--start` (a non-allowlisted real account starts DISABLED with that exact command in the log). The bot then
waits for `STARTUP RECONCILED` in the log before its first entry (normally the first poll; the clock probe takes a few
seconds). Sim101 needs nothing new.

## Commands run (worktree, 2026-10-25) and results

| Command | Result | Log |
|---|---|---|
| `python -X utf8 -m engine.ninjatrader --selftest` | PASS 70/70 (check 8 now sends the owner's global kill explicitly; the live-gate checks also cover the allowlist) | `a5_logs/selftest.txt` |
| `python -X utf8 -m tests.test_nt_exec_audit` (new) | 46/46 | `a5_logs/test_nt_exec_audit.txt` |
| same test on the pre-fix code (HEAD 808a931 copy) | 11/28 + 4 sections crash (missing APIs): the defects above | `a5_logs/test_nt_exec_audit_on_OLD_code.txt` |
| `python -X utf8 -m tests.test_nt_outgoing` | 26/26 | `a5_logs/test_nt_outgoing.txt` |
| `python -X utf8 -m tests.test_nt_roll_guard` | 10/10 | `a5_logs/test_nt_roll_guard.txt` |
| `python -X utf8 -m tests.test_multi_account --quick` | 49/49 (live-lock check now also proves the allowlist refusal) | `a5_logs/test_multi_account_quick.txt` |
| `python -X utf8 -m tests.test_guards` | 69/69 | `a5_logs/test_guards.txt` |
| `python -X utf8 -m tests.test_remote_ctl` | 51/51 (remote kill still FLATTENEVERYTHING, account flat) | `a5_logs/test_remote_ctl.txt` |
| `python -X utf8 -m tests.test_lit_add_safety` | 28/28 | `a5_logs/test_lit_add_safety.txt` |
| `python -X utf8 -m tests.test_lit_late_entry` | 10/10 | `a5_logs/test_lit_late_entry.txt` |
| `python -X utf8 -m tests.test_lit_exit_route` | 19/19 | `a5_logs/test_lit_exit_route.txt` |
| `python -X utf8 -m tests.test_lit_oif` (all 2026 trades through LiveBot + fake NinjaTrader, now with the startup gate) | 117/120, the same 3 days (2026-03-23, 04-03, 05-05) that also miss on the pre-fix code (`a5_logs/test_lit_oif_3days_on_OLD_code.txt`: 0/3); every day logs `STARTUP RECONCILED` before its entry; median 2.55 s after the 1m CISD close | `a5_logs/test_lit_oif.txt` |

`python -X utf8 -m tests.test_second_account_b --quick`: 42/42 in 1363 s (`a5_logs/test_second_account_b_quick.txt`).
Not run here: `tests.test_second_account_b` full (85 min), `tests.test_rehearsal` (server subprocess replay), `tests.test_lit_live` (paper adapter: no code path
changed for paper; guard 0 only applies to `adapter == "ninjatrader"`).

## EXECUTION_TEST_MATRIX

Test classes: **unit** (pure function), **mock** (stub bot / patched call), **fake-folder replay** (`_FakeNT` playing
NinjaTrader on temp folders, the real adapter / LiveBot code), **Sim101** (a real NinjaTrader 8 on its Sim101 account),
**provider** (Tradovate / MFFU account). Nothing in Sim101 / provider could run in this container (no NinjaTrader):
those rows are UNTESTED here and are the owner's `--sim-check` / `--sim-roundtrip` / `--sim-roundtrip-add` on the PC.

ST = `python -X utf8 -m engine.ninjatrader --selftest` (`a5_logs/selftest.txt`); EA = `python -X utf8 -m tests.test_nt_exec_audit`
(`a5_logs/test_nt_exec_audit.txt`); OUT = `python -X utf8 -m tests.test_nt_outgoing` (`a5_logs/test_nt_outgoing.txt`).

| Scenario | Test class | Command | Expected | Observed | Status | Log path |
|---|---|---|---|---|---|---|
| Entry accepted | fake-folder replay | ST; `tests.test_lit_oif` | 1 MARKET line; only after the fill, 1 file with STOPMARKET + LIMIT sharing one OCO id | exact lines matched; 120 LIT days replayed | PASS | `a5_logs/selftest.txt`, `a5_logs/test_lit_oif.txt`, `research/lit/order_trace.md` |
| Entry accepted on a real NinjaTrader | Sim101 | `python -m engine.ninjatrader --sim-roundtrip` | 3 OK lines, FLAT | not runnable here | UNTESTED | owner PC |
| Entry rejected | fake-folder replay | ST "entry REJECTED" | no stop/target sent, ok False, nothing tracked | as expected | PASS | `a5_logs/selftest.txt` |
| Entry partial fill | fake-folder replay | ST "partial fill" | bracket for the filled 2, then `CHANGE;;;;4;;0;0;;;<id>;;` on both legs | as expected | PASS | `a5_logs/selftest.txt` |
| Stop accepted | fake-folder replay | ST "bracket: ... WORKING" | stop + target WORKING, leg protected | as expected | PASS | `a5_logs/selftest.txt` |
| Stop rejected | fake-folder replay | ST "stop REJECTED"; OUT 6 | CLOSEPOSITION at once + alert, ok False | as expected | PASS | `a5_logs/selftest.txt`, `a5_logs/test_nt_outgoing.txt` |
| Target rejected | fake-folder replay | EA I | flattened at once, stop cancelled, alert | as expected | PASS | `a5_logs/test_nt_exec_audit.txt` |
| Fill before ack (withdrawn file executed anyway) | fake-folder replay | EA H | the late fill gets stop + target on the next ticks, never naked | as expected | PASS | `a5_logs/test_nt_exec_audit.txt` |
| Fill before ack (taken at the last moment) | fake-folder replay (patched withdraw) | EA H | treated as sent, bracket placed at once | as expected | PASS | `a5_logs/test_nt_exec_audit.txt` |
| Cancel pending vs cancelled | fake-folder replay | ST "cancel pending" / "cancel confirmed" | CANCELPENDING keeps the leg watched; CANCELLED retires it | as expected | PASS | `a5_logs/selftest.txt` |
| Fill during cancel | fake-folder replay | ST "cancel pending: ... a late fill gets its stop + target" | protected | as expected | PASS | `a5_logs/selftest.txt` |
| Partial exits | fake-folder replay | ST "partial exit: the stop fills 1 of 4" | other leg resized to 3 | as expected | PASS | `a5_logs/selftest.txt` |
| Partial exits on a real OCO pair | Sim101 | `--sim-roundtrip-add` | NinjaTrader keeps the OCO pair consistent | undocumented behaviour (help guide), not runnable here | UNTESTED | owner PC |
| BE CHANGE | fake-folder replay | ST "breakeven"; `research/lit/order_trace.md` | `CHANGE;;;;0;;0;<stop>;;;<id>S;;` (0 keeps qty / limit, per help guide) | as expected | PASS | `a5_logs/selftest.txt` |
| BE CHANGE on a real NinjaTrader | Sim101 | `--sim-roundtrip` step 2 | stop line moves on the chart | not runnable here | UNTESTED | owner PC |
| Qty-only CHANGE | fake-folder replay | ST "partial fill", "scale-in" | `CHANGE;;;;<q>;;0;0;;;<id>;;` on stop and target | as expected | PASS | `a5_logs/selftest.txt` |
| Qty-only CHANGE / OCO sibling resize (real) | Sim101 | `--sim-roundtrip-add` | the one OCO pair covers 2 | sibling resizing on plain OIF orders is undocumented | UNTESTED | owner PC |
| OCO sibling cancel | fake-folder replay | ST "target fills, OCO cancels the stop" | sibling CANCELLED, leg retired; a sibling still working gets a CANCEL | as expected (fake implements OCO) | PASS | `a5_logs/selftest.txt` |
| Flatten with working orders | fake-folder replay | ST "legs still working after CLOSEPOSITION" | CLOSEPOSITION, then CANCEL by id once flat | as expected | PASS | `a5_logs/selftest.txt` |
| Flat with orphan orders (bot's own, state lost) | fake-folder replay | EA G | account flat + lost bracket still working -> CANCEL by id (ids from the OIF audit log), nothing account-wide | as expected | PASS | `a5_logs/test_nt_exec_audit.txt` |
| Flat with orphan orders (late fill after exit) | fake-folder replay | ST scale-in / watch checks, `tests.test_lit_add_safety` | watched 4 h, late fill closed | as expected | PASS | `a5_logs/test_lit_add_safety.txt` |
| Stale data | fake-folder replay | ST "feed: stale ...", `tests.test_guards`; EA E | FEED STALE, no Yahoo, entries blocked; startup stays DISARMED | as expected | PASS | `a5_logs/selftest.txt`, `a5_logs/test_guards.txt`, `a5_logs/test_nt_exec_audit.txt` |
| Execution lost, data up (NinjaTrader off / all DISCONNECTED) | fake-folder replay | ST "NinjaTrader off: ... withdrawn"; OUT 7 | file withdrawn, never runs late; DISCONNECTED -> alert, entries refused | as expected | PASS | `a5_logs/selftest.txt`, `a5_logs/test_nt_outgoing.txt` |
| Data lost, execution up | fake-folder replay | ST "LiveBot: data_source ninjatrader ... stale" | new entries blocked; open trade keeps its broker bracket and is managed | as expected | PASS | `a5_logs/selftest.txt` |
| Python crash / restart mid-trade | fake-folder replay | `tools/lit_order_trace.py --py-restart`; ST "restart" | legs restored from the state file, exit routed once | as expected | PASS | `research/lit/order_trace_restart.md`, `a5_logs/selftest.txt` |
| NinjaTrader restart (outgoing wiped) | fake-folder replay | OUT 2-5; order_trace_restart | never read as flat, entries blocked + alert until the position file returns or `--confirm-reset` | as expected | PASS | `a5_logs/test_nt_outgoing.txt`, `research/lit/order_trace_restart.md` |
| NinjaTrader restart on a real install | Sim101 | restart NinjaTrader with a Sim trade open | same | not runnable here | UNTESTED | owner PC |
| Interrupted file publish | fake-folder replay | EA F | a file stuck in `le_outbox\` is deleted at start, never moved in | as expected (BUG_FIX 7) | PASS | `a5_logs/test_nt_exec_audit.txt` |
| Duplicate process (two bots, one account) | fake-folder replay (2 real processes) | EA C | 2nd process DISABLED, writes nothing; other account fine; lock gone after exit/crash and after `LiveBot.stop` | as expected; old code: 2nd process READY (FAIL) | PASS (BUG_FIX 2) | `a5_logs/test_nt_exec_audit.txt`, `a5_logs/test_nt_exec_audit_on_OLD_code.txt` |
| Reused file names | fake-folder replay | EA F | a name already in `incoming\` is never overwritten | as expected; old code overwrote (FAIL) | PASS (BUG_FIX 3) | same |
| Reused order IDs | unit (review) | `LE{entry_t}{4-char nonce}{N/M}{E/S/T/O}`, ST "restart ... same ids" | unique per entry; a restart reuses the same ids for the same leg (never re-sends) | one entry per day per account; LIT and B ids collide only with the same second AND nonce (1 in 923k) | PASS (residual noted) | `engine/ninjatrader.py` `place_bracket` |
| Corrupted state file | fake-folder replay | EA G | torn / wrong-shape file: no crash, moved aside, alert, entries blocked (also after a restart) until flat + no bot order working, or `--confirm-reset` | as expected; old code: `[]` crashed the constructor | PASS (BUG_FIX 4) | `a5_logs/test_nt_exec_audit.txt` |
| Restart exit routing | fake-folder replay | `tests.test_lit_exit_route` | every exit kind routed once after a restart, P&L = backtest | 19/19 | PASS | `a5_logs/test_lit_exit_route.txt` |
| Expired credentials | n/a (OIF has none) / provider | - | OIF needs no credentials; an expired Tradovate session shows as DISCONNECTED (row "Execution lost") | fake DISCONNECTED path PASS; real Tradovate expiry not reproducible here | UNTESTED (provider) | `a5_logs/test_nt_outgoing.txt` |
| Early close | fake-folder replay | ST "early close" | flat 5 min before the halt, entries stop 15 min before | as expected | PASS | `a5_logs/selftest.txt` |
| DST | unit | EA J | gates in ET wall time on both DST Mondays; trading day across the change | as expected | PASS | `a5_logs/test_nt_exec_audit.txt` |
| Wrong account | fake-folder replay | EA D, A | not allowlisted -> DISABLED (with the command); writer refuses a line for another account | as expected | PASS (new) | `a5_logs/test_nt_exec_audit.txt` |
| Wrong contract | fake-folder replay | `tests.test_nt_roll_guard`; EA E | chart on the old contract -> entry refused; startup DISARMED | as expected | PASS | `a5_logs/test_nt_roll_guard.txt`, `a5_logs/test_nt_exec_audit.txt` |
| (a) kill scope with 2 accounts | fake-folder replay (adapters + LiveBot) | EA A, B | B / extra / remote flatten: CLOSEPOSITION + CANCEL by id on that account only; only the owner's kill writes FLATTENEVERYTHING | as expected; old code FLATTENEVERYTHING closed LIT's account (FAIL) | PASS (BUG_FIX 1) | `a5_logs/test_nt_exec_audit.txt`, `a5_logs/test_nt_exec_audit_on_OLD_code.txt` |
| (b) duplicate-process guard | see "Duplicate process" | EA C | - | - | PASS | - |
| (c) startup DISARMED until reconcile | mock + fake-folder | EA E | unexplained position / stale feed / wrong contract / clock not checked / bad eval anchor -> DISARMED; passes once -> latched | as expected | PASS (new) | `a5_logs/test_nt_exec_audit.txt` |
| (d) account allowlist | fake-folder | EA D | only listed Names (exact, case-sensitive); Sim always | as expected | PASS (new) | `a5_logs/test_nt_exec_audit.txt` |
| Kill / flatten on the real broker | provider | HOLD TO KILL on the eval | account flat in the MFFU app | never run (never arm) | UNTESTED | - |

## How the new pieces behave (for the next Claude)

- **Kill scope.** `send({"side": "exit", "reason": "KILL SWITCH"})` = `kill(scope="account")`: CLOSEPOSITION for every
  instrument this account holds (one for the bot's MNQ when flat), CANCEL by id for entries / adds still working at
  once, and for the stop / target only after NinjaTrader shows flat (a failed close never strips the stop). Only
  `{"scope": "global"}` (written only by `LiveBot.kill_switch` for the primary) sends FLATTENEVERYTHING; `--kill` with the
  server down does the same. `_global_kill` is True only inside that call, and the writer refuses account-wide commands
  otherwise.
- **Guard 0 `startup_reconcile`** (ON; only `adapter == "ninjatrader"`): adapter folders, not disabled (lock / live
  gate / allowlist), no NinjaTrader reset or unreadable state open, not all DISCONNECTED, chart contract = order
  contract, every protected bracket's stop/target report present, no position the bot cannot explain, NinjaTrader net =
  ledger net, feed not stale, one finished clock probe (real clock only), and for a real account in an eval mode: eval
  start known, anchor file valid if present, as_of not in the future, eval room > 0 (`startup_require_anchor` false by
  default: no anchor is allowed, as before). Latched in `bot._startup_ok` (reset on every start); health key `startup`.
  Fails CLOSED on an exception inside the NinjaTrader check.
- **Lock.** `<NinjaTrader 8>\le_locks\<account>.lock` (+ `.info` with pid / start / folder). Readonly adapters (status,
  auto-resume probe) never lock. `nt_lock: false` in a cfg turns it off (harness only).
- **Corrupt state.** `state_problem` is saved in the new state file, so a restart keeps the block. `--confirm-reset`
  clears it (same file as the NinjaTrader-restart confirmation).

## Uncertainties / residual risks

1. **Real NinjaTrader behaviour is unverified here**: CLOSEPOSITION cancelling the instrument's working orders (the fake
   assumes the documented behaviour; the account kill also cancels by id after flat), OCO sibling resizing on plain OIF
   orders (undocumented), the `Name;Exchange` position file spelling on the owner's install. The owner's Sim101
   `--sim-roundtrip` / `--sim-roundtrip-add` remain the gate.
2. After the kill switch the LiveBot stops ticking adapters (pre-existing): a CLOSEPOSITION that NinjaTrader does not
   confirm within `nt_verify_wait_s` is NOT retried (phone alert "flat not confirmed" is sent). Same for the global
   FLATTENEVERYTHING (never confirmed at all).
3. A remote flatten marks account B's adapter `killed` (pre-existing, in memory): B takes no entry until the bot
   restarts, also on the next trading day if the bot keeps running.
4. The startup gate covers the primary (LIT) account through `guards.entry_block`. Account B / extra accounts get the
   adapter-level parts (lock, allowlist, corrupt state, NinjaTrader reset, position on the instrument) but not the
   feed / clock / anchor latch.
5. The owner's global kill still flattens every account connected in NinjaTrader (documented in SETUP.md and
   GO_LIVE_TONIGHT.md step 10: connect only the bot's accounts).
6. The clock probe needs internet once: with none, the probe finishes "unknown" and the gate passes (same rule as guard 7).
7. `test_lit_oif` timing rows depend on box load (other audit agents were running in parallel); this run had none over 10 s.
