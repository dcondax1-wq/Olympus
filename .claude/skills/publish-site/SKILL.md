---
name: publish-site
description: Publish the phone site (Olympus, https://dcondax1-wq.github.io/jarvis/) from the cloud after a landing, with the fewest tokens - checks, gh_publish, verify the live worker. Use when the owner or STATE says "publish", "push the site", "the phone still shows the old page".
---

# Publish the phone site (cheap, same every time)

The site = `tools/web_public/` built by `tools/gh_publish.py` (pc_publish's privacy pass, minus runs/, plus Data City) into the
Pages repo `dcondax1-wq/dcondax1-wq.github.io` (folder `/home/user/dcondax1-wq.github.io`). Max 6 publishes a day; it skips when
nothing changed. Never touches the bot, live_model*.json or orders.

```bash
cd /home/user/olympus
python tools/bump_versions.py --check --base origin/pc     # must say "check ok." (else --apply, test, commit first)
python -X utf8 tools/site_checks.py                         # must say "all fine"
python tools/apps_list_build.py --check && python tools/jarvis_search_build.py --check | tail -1   # stale = rebuild, commit
# the Pages clone: add_repo(owner=dcondax1-wq, repo=dcondax1-wq.github.io, access=push), then clone it to /home/user/dcondax1-wq.github.io
python tools/gh_publish.py --dry-run | tail -5              # what would change
python tools/gh_publish.py | tail -3                        # commit + push the Pages repo
```

Verify (2 min after the push): fetch `https://dcondax1-wq.github.io/jarvis/sw.js` and check `const CACHE =` equals
`tools/web_public/jarvis/sw.js` (same for `/sw.js` le-public-vNN and `/kalshi/sw.js`). Old page on the phone after that = the
worker cache name did not move: bump it (lead-only sw.js), publish again.

Rules: tests only for the touched area (`python tests/run_area.py <area>`), browser suites under
`flock -w 2400 /tmp/olympus_browser.lock`. Never publish owner names / emails / account ids (the privacy pass blocks them; a
`[privacy]` stop = fix the source, never skip the pass). Netlify is the backup host only (no publish there). Tests: `tests.test_gh_publish`.
Reply to the owner: one line + the link, `$` where it matters.
