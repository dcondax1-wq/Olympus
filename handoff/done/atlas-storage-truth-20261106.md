# Atlas storage truth

The footer no longer promises device persistence when localStorage is blocked or full. Atlas probes storage without changing saved preferences, reports an unavailable save in a live status, and updates the message after every favorite/recent write. The current page still works for this visit.

Verification: `node --check` passed. Local Chromium 390×844 low effects with normal and forced-quota-error storage: the footer accurately showed saved/unsaved before and after a favorite tap; no JavaScript errors or horizontal overflow. Current main quick launch and mobile search improvements remain in the integrated branch. Full repository checks and physical iPhone QA remain pending.
