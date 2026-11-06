# Atlas phone search feedback

At 390 px, Atlas hid its live result count. A typed search changed cards below the fold without immediate feedback. The count now appears between the heading and search box, and one result reads `1 destination`.

Verification: `node --check` passed. Local Chromium at 390×844 in high/low effects showed `1 destination` for Oracle and `0 destinations` plus the empty-state message for a nonsense query; no JavaScript errors or horizontal overflow. CSS and JS cache versions bumped. No trading, worker, catalog, or Jarvis code changed. Repository area tests and physical iPhone QA remain pending.
