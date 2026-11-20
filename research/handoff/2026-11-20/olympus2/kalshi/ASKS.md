# ASKS for the lead (day-kalshi helper: dionysus / sibyl / kalshicity, 2026-11-20)

1. sw.js: none needed. dionysus/, sibyl/, kalshicity/ have no sw.js of their own and the root sw.js lists them in OTHER_APPS (never cached there).
   New ?v: dionysus.css a3->a4, dionysus.js a4->a5; sibyl.css a1q->a2, sibyl.js a1->a2; kalshicity.css k18->k19 (file unchanged, bump only), agora-kalshicity.css g4->g5, kalshicity.js k26->k27.
2. tools/site_checks.py (smoke) has 3 faults in YOUR kalshi/: sw.js precaches kalshi.css/js ?v=k48 but index.html loads ?v=k50 (cache 'kalshi-k48'). Fix: `python tools/bump_versions.py --apply`.
3. tests/test_kalshicity_skyline.py fails 2 of 4 on the base commit too (913ead2b, not from this work): skylinePorts now has 4 children and the rail stays visible at tier 250;
   scenery() roads need `kind`; the atlas caption has no button at children[1].children[0]. Needs whoever owns the Olympus World skyline to re-sync test vs code.
4. Proposal (not done): Kalshi City (archive) could start the 3D only after a tap ("Show the 3D city"), drawing the 2D atlas first: removes ~5 s of main-thread work in
   software GL. Its page test expects the scene at load in ~40 checks, so it is a bigger change: your call.
