---
tags:
  - zeus/apps
  - door/kalshi
type: "apps"
door: "Kalshi"
---

# Kalshi

| App | Group | What it is | Data | Test |
|---|---|---|---|---|
| Dionysus (`dionysus`) | kalshi | The Kalshi desk: guard, what-if, scan. Suggestions only | `fixture.json`, `../kalshicity/edges.json`, `../kalshicity/whatif.json`, `../kalshi/k8.json`, `../kalshicity/learned.json`, ... | `tests.test_dionysus_page` |
| Kalshi (`kalshi`) | kalshi | Kalshi bot · from your PC | bundled fixture / its own files | `tests.test_kalshi_page` |
| Kalshi City (`kalshicity`) (retired) | kalshi | The Kalshi bot's edges as a night city | `fixture.json`, `edges.json`, `learning_log.json`, `hypotheses.json`, `learned.json` | `tests.test_kalshicity_page` |
| Sibyl (`sibyl`) | kalshi | Prediction-market edges after fees: paper picks, ruin odds | `fixture.json`, `../money/sibyl.json`, `../money/sibyl_forward.json`, `../kalshicity/suggestions.json`, `suggestions_fixture.json` | `tests.test_sibyl_page` |
| Tyche (`tyche`) | kalshi | The Kalshi bets as a 3D fortune wheel | bundled fixture / its own files | `tests.test_tyche_page` |

Back to [[ZEUS Apps]]
