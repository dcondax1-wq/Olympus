# Kalshi City phone views

On 390×844 tall phones, the six views now form two rows of three. Every view is visible on first open and buttons measure about 83×44 px. Before, Risk and Lessons were offscreen in a 354 px scrolling row within a 262 px viewport, with no visible swipe cue. Camera controls retain their left column.

After #266 merged, this branch was integrated with current main at `df3b4bf`: the status fix and JS tag `k14` are preserved and the CSS tag advances to `k8`. The full mirrored Kalshi City static/model suite passed 37/37. Headless Chromium at 390×844 rendered the integrated app in high and low WebGL: all six views visible, no JavaScript errors or horizontal overflow. High and low forced no-WebGL atlas was also exercised with synthetic fresh Stopped, Paused and stale feed cases; labels were correct. Screenshots were inspected. Physical iPhone Safari and the original full Python browser suite were not run. No betting or trading code changed.
