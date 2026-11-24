# day-unstick (2026-11-24): getting the PC's held-back update installed with nobody at the PC

Paper only. Nothing here touches live_model*.json, sizing or arming. Branch day-unstick, not pushed to pc.

## What the PC runs
- Code that wrote "Self-heal could not fix: the auto-update is held back by a local change it may not touch:" =
  `engine/self_heal.py:572` at **75d5a60b9** (2026-11-24 02:05 UTC = 11-23 21:05 ET, last pc commit before 21:20 ET).
  day-updfix 312bcbd00 (22:57 ET) changed that path later; the PC never got it.
- Old rule (`engine/autoupdate.py` fast_forward ~489-501): **any** dirty tracked file that isn't bot-made blocks, even one the
  update doesn't touch (only day-updfix relaxed that). The only way through is from_main(): the local blob (worktree AND index)
  must be a version of that path committed somewhere in old..new.

## 1. What the owner's evening commands write (old code, run here at 75d5a60b9 in a sandbox worktree)
| Command | Writes | Tracked? |
|---|---|---|
| finish_tonight: powercfg | Windows power plan | no |
| finish_tonight: pip install pyarrow | site-packages | no |
| finish_tonight: LE_TickRec.cs copy | Documents\NinjaTrader 8\...\AddOns (repo file is only read) | no |
| tickrec enable | data/tickrec.json (ignored), NT le_ticks\enabled.txt + instruments.txt | no |
| combo50k --on (50K + 25K #2) | data/combo_50k.json (ignored); decisions.json / research/lab/combo_50k.json only read | no |
| KEEPALIVE_ON (keepalive --on all) | data/keepalive.json (ignored) | no |
| ALERTS_SETUP | %USERPROFILE%\.olympus\alerts.json (outside the repo) | no |
| rapid --blitz on | data/rapid.json (ignored) | no |
| ADD_ACCOUNT / TRADE_HOME 4 (onboard, accounts add, lit25 --funded) | data/accounts.json, nt_accounts_allow.json, rapid*.json, lit25.json (all ignored) | no |
| UPDATE.bat (ops_checks --update-guard, autoupdate --pull, pip) | logs/, state | no |

After running each one here, `git status` stayed clean. **None of the owner's commands dirties a tracked file.**

Also ruled out:
- CRLF: a checkout with core.autocrlf=true is clean. Every .bat in the index is LF, and the CRLF-in-index files are protected.
- Windows path problems: no paths that differ only by case, no reserved names, no paths over 100 characters.
- **second_model.json cannot be the (only) culprit.** Old self_heal skips TRACKED_LOCAL when it builds the "need" list, so the
  alert the PC sent names some other file. (If second_model.json is dirty too, account_b.migrate_local clears its account_b
  block by itself. Any other edit in it blocks, but is never in that alert line.)
- An untracked file in the update's way that the self-heal may not move (data/*, *notes*, STATE.md ...): none of those paths
  were added in 75d5a60b9..pc.

## Culprit ranking (no file name seen yet: the feed cut the line at 90 characters)
1. **A hand edit** (a file opened and saved in Notepad/an editor while following the evening steps). It's likely because none
   of the scripts writes a tracked file. Not reproducible.
2. **A tracked, non-bot-made file the running bot or report task writes** with features switched on that evening. Possible
   writers: notify_settings.json, dashboard_view.json, research/mind/store.json, research/learn_queue.json,
   research/lab/edge_health.json, research/lab/rule_log.json, data/clean/manifest.json (datapipe via ops_checks),
   data/board/shared.jsonl, research/kalshi_k8_live/data/tape.jsonl, research/lab/combo_25k_check.json /
   combo_50k_check.json (tests write them). These hold timestamps/market data, so their bytes are **not reproducible**.
3. **An old version of a file put back** (backup/zip restore, a tool rewriting a deterministic file). This is the only
   case where the bytes are knowable, and the route below covers it without knowing which version.

Plainly: no candidate file could be reproduced byte for byte from the owner's commands, because the commands write none.

## 2. Zero-touch route: the version cycle (covers case 3; tells cases 1/2 apart at no cost)
`research/handoff/2026-11-24/unstick/cycle_versions.py --path <file> --build [--verify 75d5a60b9]` builds a chain on origin/pc
that commits the path's every earlier version in turn, then puts the current pc version back.
- The chain's net tree change is nothing (checked: tip tree == origin/pc tree), so the new code works exactly as without it.
- If the PC's copy equals ANY committed version, the old from_main() accepts it. The file goes back to HEAD, the fast-forward
  runs, and the PC gets the current pc version. The owner's content is lost only where it was an old version anyway.
- If the PC's copy is a fresh edit, the update still blocks with the same receipt. Nothing gets worse.
- `--bytes FILE` adds an exact copy if one can ever be rebuilt (e.g. a deterministic JSON).
- `--verify` replays the OLD fast_forward in a temp clone, once per cycled version and once for an unknown edit (which must
  stay blocked).
- Lead: `git push origin <tip>:pc` (a plain fast-forward), then send the remote 'update' again.

### Timeline for 16:05 ET
1. The lead sends 'update'. The receipt names `<names>` ("local changes in tracked files (not touched): ...").
2. The lead sends me the names. I run `cycle_versions.py --path A [--path B ...] --build --verify 75d5a60b9` (~2-5 min) and
   report the tip.
3. The lead pushes the tip to pc and sends 'update' again. "updated ... restarting" = done.
   Still "local changes ..." = a real hand edit or runtime bytes: go to the fallback.

### Other old-code paths that might clear it (checked: none clears a hand edit)
- START / restart `--pull`, UPDATE.bat, the hourly auto-update, and remote 'update' (`engine/remote_ctl.py` ~509-530:
  run_update "manual", which needs the bot flat, supervised and outside 01:50-16:00 ET on weekdays) all use the same
  fast_forward, with the same rule.
- self_heal fix_update only moves untracked files and resets bot-made files. It reports a hand edit and never touches it.
- migrate_local helps only with second_model.json's account_b block.
- The only force checkout (`autoupdate.connect`, `checkout -f -B`) is run by the owner (setup_everything.ps1 / --connect).
  No remote command reaches it. remote_ctl COMMANDS = kill, stop, flatten, update, restart, status, start, pause,
  resume_entries, present: none runs git checkout/stash.

## 3. Fallback (one owner line, then UPDATE)
```
git stash push -m "owner park" -- engine tools scripts docs tests
```
then double-click UPDATE.bat. If the receipt names a file outside those folders (e.g. notify_settings.json,
dashboard_view.json, research/...), add its path to the end of the stash line. The change is kept in the stash
(`git stash list`). After the update, the new code (day-zerotouch2) parks hand edits by itself, so this happens only once.

## Proof (run here 2026-11-24 ~13:20 ET, OLD fast_forward from 75d5a60b9, PC HEAD = 75d5a60b9, upstream = chain on pc 9393a5105)
| PC copy of notify_settings.json | Old auto-update result |
|---|---|
| = an earlier committed version (3e7686891) | updated 75d5a60 -> chain tip |
| = another earlier version (0ed39de35) | updated |
| = an unknown edit | skipped: "local changes in tracked files (not touched): notify_settings.json" (unchanged, as it must be) |
The chain is rebuilt on the then-current pc when the name arrives (pc moves). It works for any PC HEAD that is an ancestor of pc.

## Round 2 (lead 16:59 ET: "find ANY zero-touch route in the old code")
| Question | Answer (old code 75d5a60b9) |
|---|---|
| Which commit does the PC run? | The lite feed has no commit or version field. `sh` (self-heal tiny) is stale since 11-23 16:30 ET (the Windows state-save bug day-updfix fixed). Board `ev` repeats the truncated held-back line every 15 min, with no file name and no `rc` receipt. Unknown beyond "≤ 75d5a60b9 era". |
| (1) Old paths that read fetched remote content and write or apply it | Only: the update's own fast_forward (merge --ff-only / reset --keep); self_heal restore_untracked (writes `new:<path>` back only for files it moved itself); remote_ctl (reads control/command.json, a fixed command list: no git, no file writes); heartbeat.read / tools/data_pull (CLOUD side, not run on the PC); live_board / lit_learn pull (read-only shows). None resets or parks a dirty tracked file. |
| (2) Windows scheduled tasks | OlympusPCReport (pc_report_task.ps1), publish_nq, the keeper + weekly care (pc_tune.ps1), OlympusClock (w32tm only), wake/sleep (schedule_pc.ps1), PC Care, agency mail, live_link. All run the PC's LOCAL code. Only the bot start does `autoupdate --pull` = the same fast_forward rule. |
| (3) Boot / power cut / Windows-update reboot | run_bot.ps1 → `--pull` (same rule). Rollback and refused merges use `git reset --keep` (keeps local changes). The ONLY forced checkout (`checkout -f -B`) is `autoupdate.connect`, run by the owner (setup_everything.ps1 / GITHUB_SIGNIN). No remote or scheduled path reaches it. |
| Remote 'update' preconditions | LE_REMOTE defaults to 1 under run_bot.ps1 (LE_SUPERVISED). Refused while not flat, or 01:50-16:00 ET on a weekday. Then the same fast_forward. |
| (4) Pre-emptive chain | Built on pc 1ea04f047: 84 commits cycling every earlier version (all 195 branches) of notify_settings.json, update_source.json, dashboard_view.json, research/mind/{store,calibration}.json, research/learn_queue.json, research/lab/{edge_health,rule_log,kalshi_adapt,health_band,combo_25k_check,combo_50k_check,combo_50k}.json, data/clean/manifest.json, data/board/shared.jsonl, research/kalshi_k8_live/data/tape.jsonl, data/draw_learner.json, data/{NQ,ES}_rolls.json, data/clean/{NQ,ES}_rolls.json, research/orderflow/results.json, tools/model_versions.json, data/NQ_imported_days.json, data/ltf/NQJ_imported_days.json, tools/web_public/business/decisions.json. Tip tree == pc tree. Merged into day-unstick. |

Left out on purpose: live_model*.json and STRATEGY.md (hub_data / rulelog read their git history; hard rule), second_model.json (it can't be the
culprit), and the big data CSVs (a2_lit_audit reads data/NQ_5m.csv's last commit, and the PC appends live bars, so they never equal a committed version).

Safe to push to pc? Yes. It's a fast-forward and the net tree change is none. No workflow runs on a pc push. The only side effect is
cosmetic: ~84 "day-unstick" subjects in `git log` (botctl's recent-commits list, vault/hub changelogs). Push it only while pc is still the
chain's base. If pc has moved, rebuild (1 min): the command is in the next section.

Honest odds: low, about 5-10%. It only unblocks if the PC's file equals a committed version. A hand edit, or a file the bot rewrites
with times or prices (the likely cases), stays blocked, and the owner's one stash line remains the only way. No legitimate old-code
mechanism resets an unknown edit to a tracked file without someone at the PC.

Side finding (security, cloud side): tools/data_pull.copy_days writes `days/<day>/<p>` from a fetched ref with no `..` check
(`os.path.join(d, *p.split("/"))`). It is a cloud tool, not a PC route, and is NOT used here. Worth a path check later.

Rebuild on the current pc: `git fetch origin '+refs/heads/*:refs/remotes/origin/*' && python3 research/handoff/2026-11-24/unstick/cycle_versions.py $(sed 's/^/--path /' research/handoff/2026-11-24/unstick/candidates.txt) --build`,
then `git push origin <tip>:pc`.
