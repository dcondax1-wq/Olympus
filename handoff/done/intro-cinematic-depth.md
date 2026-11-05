# Intro cinematic depth

The shared skyline intro now flies through a layered perspective city with roof planes, side faces, lit windows, converging road rails and an arrival glow. This applies to Cities, Data City and Kalshi City through the existing flavour map.

Checked: `node --check tools/web_public/olympus/intro-app.js`. No trading or data paths changed. Browser screenshot and full app gate remain for the lead because the private repo could not be cloned in this executor.

Wiring needed: bump intro-app.js `?v=i1` tags when releasing so cached clients receive the new shared script.
