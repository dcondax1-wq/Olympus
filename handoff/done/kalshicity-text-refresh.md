# Kalshi City text-only refresh

Kalshi City already keeps a readable atlas if WebGL fails, but the five-minute refresh returned early when there was no 3D scene and never scheduled refresh on that path. The city therefore stopped learning on the open page. This change keeps fetching updated published edge, log, and live feed data and refreshes the open text sheet without a renderer. The scene path retains its existing rebuild and fireworks behavior. No orders are placed.

Static check: `node --check kalshicheck/kalshicity.js` passed. Browser testing still requires an authenticated checkout/device.
