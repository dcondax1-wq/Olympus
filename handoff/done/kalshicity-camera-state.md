# Kalshi City camera state

If a Fly or Street route cannot be built because fewer than two districts exist, the camera now synchronizes to Orbit and the selected UI button reports Orbit. Existing routes still report Fly or Street.

Checks: `node --check` on `cityrig.js`; Node runtime checks for missing Fly route, missing Street route, and a valid Fly route using the repository's bundled three.js. No order or trading paths touched.
