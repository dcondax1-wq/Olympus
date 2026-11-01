# Planner add-ons

The owner's Planner app lives on the `planner-backup` branch of the public repo `nq-dashboard`. It is built by its own
Claude session, and this repo can't push there. Features built here ship as patches in this folder.
`scripts/add_planner.sh` applies them on top of planner-backup at every site publish:

- **Order:** by file name.
- **Each one on its own:** every patch is committed in the temp clone, so one failure never undoes another.
- **Fallback:** a patch that no longer applies is skipped and the Planner publishes without that add-on, never half-patched.
  It first tries a 3-way merge, for when planner-backup moved on.
- **Record:** `planner/addons.json` on the site lists what was applied and what was skipped.

## Making a patch
1. Clone planner-backup.
2. Build the feature, mostly in new files (`planner/ext-*.js`) with minimal hooks in `index.html`.
3. Run the Planner's own tests (`planner/tests`).
4. Run `git diff <base>` (new files included) into `NN-name.patch` here.
5. Run `python -X utf8 -m tests.test_planner_addons`. Its section f checks every patch here against the live planner-backup.

Owner data lives in the phone's localStorage. An add-on never renames, migrates or drops existing keys, and writes only new
keys or goes through the Planner's own save functions.
