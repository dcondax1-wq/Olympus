"""PANTHEON: free, key-less market-context data for NQ futures, one Greek god per source (research and display only).

Each god reads one free public source, says what it means for NQ today, and votes risk-on / risk-off in the Council of the
Gods. Every vote is checked honestly against NQ futures next-session returns (TradingView NQ1! daily, 2021-11 -> 2026-10):
a weak relation is labelled "context, not a signal". Nothing here trades, sizes or filters a trade.

  sources.py  the fetchers (FRED, CBOE, CFTC, SqueezeMetrics, US Treasury, ForexFactory) and their parsers; network ->
              cache -> local repo file fallback; recorded fixtures for the tests
  stats.py    percentiles, rolling z-scores, the no-look-ahead "as known before session D" alignment, relation stats
  gods.py     the eight gods: source, reading, change, vote, regime states, the plain-language meaning
  council.py  the Council of the Gods: the votes combined into a risk-on / risk-off gauge
  build.py    the builder: research/pantheon/{pantheon,states}.json + the page copies + jarvis.json

    python -X utf8 -m tools.pantheon                    # fetch everything, build, write research/pantheon + the page
    python -X utf8 -m tools.pantheon --offline          # no network: cache, then the repo's own files
    python -X utf8 -m tools.pantheon --out <dir>        # also write pantheon.json, states.json, jarvis.json into <dir> (CRONOS)

docs/PANTHEON.md documents the gods, the sources and the states.json format (Data City reads it).
"""
