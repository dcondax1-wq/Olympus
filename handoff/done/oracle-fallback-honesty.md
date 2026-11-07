# Oracle no-WebGL fallback honesty

PR #192's Delphi city and illustrated fallback are already merged into current `main`. This task keeps that city and makes its no-WebGL state honest and accessible:

- Hide the failed WebGL canvas and its misleading drag/zoom accessibility label when WebGL initialization fails.
- Pass the current Oracle mode to the 2D city. LAST SEEN suppresses active beacons; demo replay is labelled as historical sample data.
- Give the fallback canvas a mode-aware image label and visible LAST SEEN / REPLAY title.

Focused checks: `node tests/test_oracle_fallback_honesty.mjs`, `node --check` for the changed Oracle scripts, and the exact-head `chatgpt-guard` workflow.

Unverified release QA: render the 390×844 no-WebGL fallback for live, stale, and demo sources and check screen-reader output on a branch preview. Keep PR #232 draft until that QA is recorded. It is not merged or live.

## 390×844 verification (2026-11-06 ET)

On current dashboard main with this exact Oracle patch, forced no-WebGL phone QA passed for fresh site data, a one-hour stale snapshot, and demo replay. The failed WebGL canvas was hidden and aria-hidden; the Canvas2D fallback exposed role=img with live, last-seen, and sample-replay labels; stale data showed LAST SEEN and no active beacons; demo showed REPLAY. All three returned HTTP 200 with no page errors, horizontal overflow, or visible controls under 44px. The only fresh/stale console messages were the deliberately aborted external live-source probes in the isolated fixture. Main's future-timestamp rejection remains preserved, and the combined page cache tag is `ofst2`.
