# Kalshi app feed status freshness

The Kalshi page previously showed Paused or Stopped indefinitely whenever a saved JSON report had `running: false`, even after that report aged out. It also treated a recent report with no running bit as Running. The status badge now says Not updating for a missing, future-dated, or over-15-minute report; only a recent explicit boolean can say Running, Paused, or Stopped. This changes no bot, feed, order, or sizing behavior.

Focused Node regression covers recent and stale running/paused, missing running, missing time, and future time. `kalshi.js` syntax and the 390px browser display still need release QA. Asset tags advance to k20.

The unmerged Signal City PR #153 uses its own strategy-tower glow from `s.running`; when rebased after this correction, gate that glow on a recent top-level running report as well.
