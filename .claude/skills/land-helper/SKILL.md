---
name: land-helper
description: Land a finished helper branch (night-*) on claude/clever-heisenberg-51zwcr with the fewest tokens - merge, version bumps, smoke, ship. Use whenever a helper reports "committed on night-<x>, not pushed".
---

# Land a helper branch (cheap, same every time)

Run from the main checkout `/home/user/nq-liquidity-engine` (never from a worktree):

```bash
cd /home/user/nq-liquidity-engine
B=$(git rev-parse HEAD)
git merge --no-edit night-<x>                 # conflict? keep BOTH sides (STATE.md, tests/run_area.py lists)
python tools/bump_versions.py --apply --base $B && python tools/bump_versions.py --check --base $B
timeout 600 python tests/smoke.py | tail -1    # known env red: none now (8/8 since 2026-11-17)
git checkout -- data/GEX_1d.csv 2>/dev/null    # smoke rewrites it; never commit it
git add -A tools tests web_next && git commit -q -m "<what>" (+ trailers)   # only if bump wrote files
python tools/ship.py --no-tests | tail -1      # pushes GitHub + backup olympus/pc
git worktree remove --force .claude/worktrees/<x>
```

Rules that save usage:
- Read only the helper's report and `git diff --stat`; open a file only when the diff touches engine/ or live code.
- engine/ or live-loop changes: also run `python -X utf8 -m tests.test_lit_live --quick` and `python -m engine.ninjatrader --selftest`.
- Never run tests.test_win_scripts. Browser suites only under `flock -w 2400 /tmp/olympus_browser.lock`.
- `bump_versions --check` without `--base` reports old unrelated changes: always pass `--base`.
- Reply to the owner: one small table, at most 3 steps (CLAUDE.md).
