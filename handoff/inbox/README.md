# ChatGPT -> Claude inbox

ChatGPT's finished work lands here, one folder per task (the task ids on the Olympus Bridge page,
https://demetrades2000-coder.github.io/nq-dashboard/bridge/). Two ways in:

1. **ChatGPT Codex** (best): connect GitHub in ChatGPT, open this repo, and let Codex open a pull request on a
   `chatgpt/<task>` branch that only adds files under `handoff/inbox/<task>/`. Claude reviews and wires it in.
2. **By hand**: GitHub app -> this repo -> handoff/inbox -> Add file -> Upload, into `handoff/inbox/<task>/`.

Claude never runs code from this folder unreviewed; it is read as data and built into the apps by hand.
