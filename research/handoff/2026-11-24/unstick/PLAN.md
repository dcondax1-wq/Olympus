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
