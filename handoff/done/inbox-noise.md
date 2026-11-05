# Inbox noise

Removed Git commit subjects from Inbox delivery items. Bridge jobs marked question or done remain. The Inbox no longer fetches the absent root `live.json`; local Argus history and published app cards remain its system sources.

Checks: `INBOX_PART=b python -X utf8 -m tests.test_inbox_page` passed 9/9 in a minimal local fixture; `node --check` passed for both changed JS files, and Python test syntax compiled. Full app browser test could not run without a Playwright browser binary or authenticated private clone.
