verify_live 2026-11-04 08:08 UTC · https://demetrades2000-coder.github.io/nq-dashboard/

| check | result | detail |
|---|---|---|
| app zenith | PASS | page, manifest, icons |
| app oracle | WARN | no manifest (home-screen gap) |
| app odeon | WARN | no manifest (home-screen gap) |
| app fates | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app datacity | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app tree | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app prometheus | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app pantheon | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app ares | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app forum | FAIL | jarvis.json card is 107.1 h old (limit 24 h) |
| app labyrinth | PASS | page, manifest, icons, card fresh |
| app argus | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app nemesis | PASS | page, manifest, icons, card fresh |
| app chronos | PASS | page, manifest, icons, card fresh |
| app hephaestus | PASS | page, manifest, icons, card fresh |
| app cities | FAIL | page cities/ is 404 |
| app kalshicity | FAIL | page kalshicity/ is 404 |
| app journal | FAIL | page journal/ is 404 |
| app ledger | FAIL | page ledger/ is 404 |
| app inbox | FAIL | page inbox/ is 404 |
| app settings | FAIL | page settings/ is 404 |
| app bridge | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app planner | PASS | page, manifest, icons |
| app mind | FAIL | jarvis.json card is 30.0 h old (limit 30 h); no manifest (home-screen gap) |
| app arena | WARN | no manifest (home-screen gap) |
| app athena | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app kalshi | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app tyche | WARN | no manifest (home-screen gap) |
| app hermes | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| app plutus | WARN | no manifest (home-screen gap); no apple-touch-icon (home-screen gap) |
| root worker | FAIL | STALE DEPLOY: live le-public-v56, repo le-public-v59 |
| Jarvis worker | FAIL | STALE DEPLOY: live jarvis-v22, repo jarvis-v24 |
| Kalshi worker | FAIL | STALE DEPLOY: live kalshi-k14, repo kalshi-k18 |
| PC dashboard worker | PASS | not on the public site (PC dashboard only) |
| data data.json | PASS | 8385 KB, object of 34 |
| data home.json | PASS | 218 KB, object of 14 |
| data odeon/trades.json | PASS | 466 KB, object of 6 |
| data plutus/plans.json | PASS | 6 KB, object of 10 |
| data bridge/jobs.json | FAIL | 404 |
| data kalshicity/edges.json | FAIL | 404 |
| data kalshicity/learning_log.json | FAIL | 404 |
| data kalshicity/hypotheses.json | FAIL | 404 |
| data kalshicity/learned.json | FAIL | 404 |
| data kalshicity/jarvis.json | FAIL | 404 |
| bot heartbeat | PASS | 5 min old, running=True, armed=True [raw address answered HTTP 404: read from the local clone's origin/heartbeat, fetch it first] |

PROBLEMS: 45 checks, 17 problems, 16 warnings (warnings are home-screen gaps or notes, not a broken deploy)
