# Monday landing runbook (rehearsed 2026-11-23 05:15-06:10 UTC, night-landrehearsal)

Heads used: `origin/pc` 30b01befe, `origin/night-integrate` df46185df, `origin/night-seedata` fdcdde105,
`origin/night-wirepatch` 85b7502e6 (lead_wires.patch). Rehearsal result (scratch, never pushed): **25cc77891** = pc + integrate +
seedata + patch. **If any of these heads moved, re-run step 5 (the proofs) before step 6.**

The 5-minute part is steps 1-4 + 6 (about 2 min of commands, 13 s of checks). The proofs (step 5) take ~60 min and were already
run tonight on exactly these heads: they only need to run again if a head changed.

## 0. Clean start (10 s)
```bash
cd ~/Olympus && git status --short          # must print nothing (ship.py refuses a dirty tree)
git fetch origin pc night-integrate night-seedata night-wirepatch
git checkout -B land-monday origin/pc
```
Must print: `branch 'land-monday' set up to track 'origin/pc'` (or "Switched to and reset branch"). Note the pc SHA: `git rev-parse --short origin/pc` -> **write it down (BACKOUT_SHA)**.

## 1. Merge night-integrate (20 s)
```bash
git merge --no-edit origin/night-integrate
```
Must print a merge summary and NO `CONFLICT`. Rehearsal: clean (pc 30b01befe is already inside integrate).

## 2. Merge night-seedata (optional, 10 s; it is not in night-integrate)
```bash
git merge --no-edit origin/night-seedata
```
Must print no `CONFLICT`. It bumps page ?v= tags itself (mffu v6, gate g21 / arenas v5, nq r33); no lead file.

## 3. The lead wires (10 s)
```bash
git show origin/night-wirepatch:research/handoff/2026-11-23/lead_wires.patch > /tmp/lead_wires.patch
git apply --check /tmp/lead_wires.patch && git apply /tmp/lead_wires.patch
git commit -am "Land Monday: lead wires (sw v209, web_next v61, ship brain/hub check, accents, RUN_MONEY text, CLAUDE push URL)"
```
`git apply --check` must print nothing (rehearsal: clean with and without seedata).
sw.js: ONE bump (v208 -> v209) covers this whole landing, seedata's pages included, because v209 has not been published yet.
Bump again (v210) only if a v209 build was already published before this push.
Check: `grep -n "CACHE = '" tools/web_public/sw.js` -> `le-public-v209`; `grep -o "le-shell-next-v6[0-9]" web_next/sw.js` -> `le-shell-next-v61`.

## 4. ship.py's checks without the push (13 s)
```bash
python tools/model_versions.py --check        # [OK] tools/model_versions.json is current (... live_model_lit.json 18 ...)
python tools/win_paths.py                     # windows paths: all fine
python tools/build_brain_hub.py --check       # brain-data.json up to date
python tools/build_research_hub.py --check    # hub-data.json is fresh
python tests/smoke.py                         # smoke: 10/11 green (11/11 on a box with python playwright; the red = tests.test_zenith_mode)
```
Any other red = STOP, do not ship. A stale brain/hub: run the builder without --check, commit, re-run step 4.

## 5. The proof trio (only if a head moved; ~60 min)
```bash
python -X utf8 tools/update_gate.py --base origin/pc --candidate HEAD --sessions 10 --json /tmp/gate.json   # 38 min
python -X utf8 -m tests.test_lit_live                                                                       # 19 min
python -m engine.ninjatrader --selftest                                                                     # 1 s
```
Must print (rehearsal, 25cc77891):
- `update gate: SAME  no trade differs on 7680 polls` (sessions 2026-11-09 .. 2026-11-20), exit 0. `HOLD` (exit 2) or `ERROR` (1) = STOP.
- test_lit_live: `intraday: 9923 polls on 120 trade days, 0 differences (+29 on known days ['2026-04-03'])`,
  `day-end replay ...: 120/120 trades identical`, last line `OK`, exit 0.
- `NinjaTrader offline self-test: PASS (80/80)`.

## 6. Ship (30 s)
```bash
python tools/ship.py
```
It re-runs model_versions / win_paths / brain + hub check / smoke, then pushes HEAD to `origin pc` only. Must end
`[OK] Olympus pc (origin)   at <sha>   (old repo: not pushed)`. Then publish the phone site as usual (publish-site skill).
The PC takes it at its next update window (or UPDATE.bat); its own auto-update gate + rollback still apply.

## Owner (hands, after the PC has it)
Double-click **MONDAY_SETUP.bat** (top folder): update -> clock ("Yes" once) -> START + type the live phrase yourself (it also
turns keep-alive ON) -> alert test. Claude never types the phrase.

## Back out
- Before step 6 (nothing pushed): `git checkout pc && git branch -D land-monday`. Nothing left anywhere.
- After step 6, the PC has NOT updated yet: `git revert -m 1 --no-edit <the integrate merge sha>` (and the seedata merge / lead-wires
  commit: `git revert --no-edit <sha>` each), then `python tools/ship.py`. A revert keeps pc fast-forward only, which the PC's
  auto-update requires. Never force-push pc.
- After the PC updated: the same revert + ship. The PC's auto-update rolls itself back on a failed self-test by itself; if the bot
  misbehaves meanwhile, the owner STOP BOT (or phone KILL) - flat first, then update. BACKOUT_SHA from step 0 is the code the PC ran before.
