# night-reds: lead-only lines (2026-11-22)

1. tools/build_web_dashboard.py:1343 prints "RUN_MONEY.bat": make it "tools/bat/RUN_MONEY.bat" (text only; tests/test_bat_menu ALLOW lists it until then).
2. tests.test_agora_audit (not in the 6 areas, red on land-fixes too): "accents: the kit's APPS and every page's pre-paint agree
   with jarvis/apps.js" -> dionysus, nq, business differ from jarvis/apps.js / the APPS table (lead-only files). The other two
   reds there (hard FAILs per app, theme-color #000000 on every page) are real design debt, not stale tests; night-reds only
   cleared the archive banner's OLYMPUS NIGHT glow (#9d59ee) from them.
3. Cloud env: the python `playwright` module is not installed here (node's is), so kalshi_page, kalshicity_page, brain_hub b,
   money_pipeline c and smoke's zenith_mode cannot run in this container. They need a run where `python -c "import playwright"` works.
