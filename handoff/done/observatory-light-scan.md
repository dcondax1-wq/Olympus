# Observatory compact Data City scan

Observatory used to download Data City's 2,052,989-byte `city.json` every five minutes. It now reads the published 918-byte `jarvis.json` health card, uses `cronos.data_t` for the research age, honors source/publisher warning states, and compares `cronos.orig` to avoid false “changed” findings on routine card refreshes.

Source file existence and sizes checked in nq-dashboard. `node --check app.js` passed. Rendered QA waits for Observatory publication.
