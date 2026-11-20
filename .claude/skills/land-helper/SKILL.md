---
name: land-helper
description: Land a finished helper branch (night-* / day-*) on Olympus pc (the one home since 2026-11-20) with the fewest tokens - merge, version bumps, smoke, ship. Use whenever a helper reports "committed on night-<x>, not pushed".
---

# Land a helper branch (cheap, same every time)

Run from the main checkout of `dcondax1-wq/Olympus` on branch `pc` (never from a worktree):

```bash
cd /home/user/Olympus && git checkout pc
B=$(git rev-parse HEAD)
git fetch -q origin <branch> && git merge --no-edit FETCH_HEAD   # conflict? keep BOTH sides (STATE.md, tests/run_area.py lists)
python tools/bump_versions.py --apply --base $B && python tools/bump_versions.py --check --base $B   # --check after --apply passes since 2026-11-20
python -X utf8 tools/site_checks.py            # Kalshi cache = css/js ?v, worker tags = page tags, both launchers identical
git checkout -- docs/shots 2>/dev/null         # browser suites rewrite the golden shots: never commit them
timeout 600 python tests/smoke.py | tail -1    # known env red: none now (8/8 since 2026-11-17)
git checkout -- data/GEX_1d.csv tools/web_hub_snapshot.json 2>/dev/null    # smoke rewrites it (and tools/web_hub_snapshot.json); never commit them
git add -A tools tests web_next && git commit -q -m "<what>" (+ trailers)   # only if bump wrote files
python tools/ship.py --no-tests | tail -1      # pushes Olympus pc only (the old repo is retired)
git worktree remove --force .claude/worktrees/<x>
```

Known mis-bumps (check the diff for these, fix by hand):
- Fixed in the tool 2026-11-20 (no hand work): Kalshi CACHE ahead of kalshi.css/js ?v (now moved as one tag), the datacity ?v cascade
  failing --check, the Gate's script-array tags (`b + 'olympus/x.js?v=..'`) never bumped.
- Still by hand: launcher.js's apps-list ?v (below); a helper that edited a module but not its ?v (bump_versions only sees the diff
  vs --base: a file edited AND re-tagged by the helper is "already bumped", fine; edited and NOT re-tagged gets bumped).
- A red `site_checks` after landing = a worker precaching an old ?v: rerun bump_versions --apply, else set the worker entry (lead-only sw.js).

Rules that save usage:
- Read only the helper's report and `git diff --stat`; open a file only when the diff touches engine/ or live code.
- engine/ or live-loop changes: also run `python -X utf8 -m tests.test_lit_live --quick` and `python -m engine.ninjatrader --selftest`.
- Never run tests.test_win_scripts. Browser suites only under `flock -w 2400 /tmp/olympus_browser.lock`.
- `bump_versions --check` without `--base` reports old unrelated changes: always pass `--base`.
- Reply to the owner: one small table, at most 3 steps (CLAUDE.md).

## Wiring a new app (lead only)
apps.js BUILT_INS `app(...)` row, olympus.js APPS + AMBIENT, root sw.js OTHER_APPS (+ tests/test_zenith_mode.py pin),
build tuple in tools/build_web_dashboard.py, then `python tools/apps_list_build.py`.
Gotcha (2026-11-17): bump_versions mis-bumps launcher.js's apps-list ?v= (wrote o5). Set BOTH launcher.js copies to
`apps-list.js?v=lN` by hand (byte-identical), bump `launcher.js?v=` in tools/web_public/index.html, web_next/index.html,
web_next/sw.js ASSETS + SHELL, and the pins in tests/test_apps_list.py. Then tests.test_apps_list must be 33/33.
