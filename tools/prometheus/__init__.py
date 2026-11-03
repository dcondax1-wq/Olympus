"""PROMETHEUS: a strategy evolution forge for the live LIT strategy (research only, paper only).

A genetic algorithm evolves variants of ten numeric LIT knobs that exist in live_model_lit.json, scores them on 2026 H1
only (the LIT rule: pick on Jan-Jun), then checks the hall of fame on 2026 H2 and on 2021-25 (reference line).
It never edits live_model*.json; it only proposes, in research/writeups/2026-11-03-prometheus.md.

  genome.py   the knobs, their bounds and grid, genome <-> LIT params / eval sizing
  fitness.py  the H1-only fitness and the H2 / 2021-25 checks (engine/lit.py run_x via tools/lit_final.run, the eval path
              of tools/lit_adv_manage.run_eval)
  ga.py       the genetic algorithm (pure: seeded, deterministic, lineage kept)
  forge.py    the CLI: evolve, check, store runs (tools/runlib.py), write the page data

    python -X utf8 -m tools.prometheus.forge            # full forge (5 seeds), ~5-10 min on one core
    python -X utf8 -m tools.prometheus.forge --quick    # 1 seed, 4 generations (smoke)
"""
