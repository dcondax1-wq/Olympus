"""DAPHNE: a branch-and-bound strategy-tree search on NQ (research and paper only).

Each *root* is a plain base entry rule on real CME NQ1! 5-minute bars, e.g. "short the opening-range high after a sweep
and reclaim, stop 1 tick beyond the sweep extreme, target 1R, out after 60 minutes". From each root the search grows a
tree: every child adds one more *condition* (a volatility band, the gap, where the open sits in yesterday's range, the
hour, ...). Branches whose optimistic bound cannot beat the best rule found so far are cut.

  sessions.py   bars -> one row per trading day: the levels (PDH/PDL, overnight, Asia, London, opening range) + day facts
  roots.py      the root rules and their trades ($ per MNQ micro after $1.90 a round trip)
  features.py   the conditions, each known at the entry bar's close (no look-ahead)
  search.py     the best-first branch-and-bound search (pure numpy, knows nothing about markets)
  report.py     the JSON for the DAPHNE page, the top rules in plain language, the run-library runs
  __main__.py   python -X utf8 -m tools.strategytree [--quick]

Train <= 2024-12-31, test 2025-01-01 onwards (and 2026 alone). It never reads or writes the live configuration or engine/
trading code (paper only): it reads data/ and writes research/strategytree/, research/runs/ and the page's copy of tree.json.
"""
