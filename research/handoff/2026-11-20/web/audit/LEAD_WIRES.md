# LEAD_WIRES: web / audit

1. **A way in from the Agency app** (agency/index.html is another slice's file): one link, e.g. under the app's header:
   `<a class="ag-btn" href="audit/">Website checks</a>` (the audit index has its own "‹ Agency" back link).
2. **Offline / cache:** agency/ is in sw.js OTHER_APPS: with the perf hand-off's sw-offline.patch (already landed?) the audit pages work
   offline after one visit; no SHELL entry needed. No ?v= files (the report pages are static, one per prospect).
3. Publish: agency/audit/* passes tools/site_privacy (private_file: public; scan: 0 findings). Nothing for build_web_dashboard.py.
