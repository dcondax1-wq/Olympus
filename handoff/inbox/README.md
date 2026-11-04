# ChatGPT -> Claude inbox

**The owner does three steps** (on the Bridge page in Olympus): 1. pick a job and tap **Copy for ChatGPT**; 2. paste it into ChatGPT and send;
3. when ChatGPT says it is finished, tap **Tell Claude** and paste `Bridge: <id> done` into the Claude chat. Claude then runs
`python tools/bridge_ingest.py --handback "Bridge: <id> done"`, reads the plain answer, builds it in and ships it.
The first time: connect GitHub in ChatGPT, give it the rules, then use **Test the link** (ChatGPT must answer `LINK OK` and the LINK WORD from `handoff/SYNC.md`).
Folder names must be the job id in lowercase letters, numbers and dashes; a folder or a file that is not is skipped and `bridge_ingest.py` says so.

ChatGPT's finished work lands here, one folder per task (the task ids on the Olympus Bridge page,
https://demetrades2000-coder.github.io/nq-dashboard/bridge/). Two ways in:

1. **ChatGPT Codex** (best): connect GitHub in ChatGPT, open this repo, and let Codex open a pull request on a
   `chatgpt/<task>` branch that only adds files under `handoff/inbox/<task>/`. Claude reviews and wires it in.
2. **By hand**: GitHub app -> this repo -> handoff/inbox -> Add file -> Upload, into `handoff/inbox/<task>/`.

Claude never runs code from this folder unreviewed; it is read as data and built into the apps by hand.

## Ready jobs and the automatic check (JOB 24)

- The Bridge page's **Library** tab (`tools/web_public/bridge/jobs.json`, built by `python tools/bridge_jobs_build.py`) holds ready jobs with
  the exact prompt; each one delivers into `handoff/inbox/<job id>/` and ends with a `DONE.md`.
- `python tools/bridge_ingest.py` (also run inside the site build through `bridge_sync.publish`) reads every folder that has a `DONE.md` and checks
  each file: only png / webp / svg / json / md / txt / small js; size caps (images 5 MB, svg / md / txt 200 KB, json 1 MB, js 100 KB, 80 files and
  40 MB per job); real images only; no secret-looking strings; no script that fetches, evals, imports or writes markup; no symlinks or hidden files.
  `--apply` copies the approved images to `tools/web_public/olympus/assets/<id>/` with a `manifest.json`.
  Nothing delivered is ever executed or imported: the files are read as bytes and text.
- The **Deliveries** tab shows the approved images and text; **Claude: build this in** copies `Bridge: <id> done`.
- **Ask next** lists what to ask ChatGPT this week (static rules in `bridge_sync.suggest`).
