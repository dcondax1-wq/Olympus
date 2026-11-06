# Bridge published status truth

Both Bridge job views now use one snapshot-aware wording helper. A published `in progress` state says “Last reported: in progress” and an unknown state needs review; it never asserts a currently running ChatGPT agent. No bot or trading control changed.

`node --check`, focused Node status-line test, and `python -X utf8 -m tests.test_bridge_page --no-browser` (30/30) passed on a mirrored source tree. The publisher copies every Bridge file, including the new `status-line.js?v=1`, and the root worker excludes Bridge. Branch index/helper rendered at 390×844 high and low in headless Chromium; a synthetic published in-progress status produced the snapshot wording. Full Playwright browser suite was unavailable because Python Playwright is not installed; final live Pages QA follows merge and mirror.
