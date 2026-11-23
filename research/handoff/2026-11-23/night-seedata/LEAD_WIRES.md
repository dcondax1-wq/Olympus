# night-seedata: lead wires (optional)

Nothing lead-only was needed: no sw.js, apps.js, APPS table or build_web_dashboard.py edits. Page script versions were bumped in the pages themselves
(mffu.html: mffumodel v6, mffucenter v3, mffu v6; gate/index.html: gate.js g21, arenas.js v5; nq/index.html: nq.js r33 -> nqcore d6).

Optional hardening (lead's call), tools/build_web_dashboard.py line ~701:

    HUB_SNAPSHOT = os.environ.get("OLY_HUB_SNAPSHOT") or os.path.join(ROOT, "tools", "web_hub_snapshot.json")

and in tests/run_area.py run_one() set env["OLY_HUB_SNAPSHOT"] to a temp copy. With that, even a test run in a subprocess could never rewrite
the tracked snapshot. Today the only in-process build that did (tests/test_accounts.py) uses a temp copy, and
tests/test_public_build_privacy.py part e fails any new test that runs bwd.build without protecting it.

Owner question (not changed): Home's "Right now" money strip (every account's balance, room, $ to pass) is hidden behind More since the
2026-11-22 "6 dashboards" decision. The NQ and Money tiles now carry the key money line instead. If he wants the full strip on the first
screen, it goes above the 6 tiles (pushes Kalshi below the fold on a 390x844 phone).
