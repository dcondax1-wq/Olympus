# 3D Home Screen icon concepts (2026-10-17)

Real-3D app icons rendered with three.js r160 in headless Chromium (bloom, chrome, glass). Not shipped yet: the owner
picks one, then the 1024 render becomes `web/icons/*` (192, 512, maskable 512, apple-touch 180).

1. `monolith`: Chrome Monolith (black-glass candle before a synthwave sun, wick splashing a cyan floor line)
2. `gargantua`: Gargantua (black hole; polar jets are the wicks; the lower jet pierces the liquidity line)
3. `gyro`: Gyro Reactor (chrome gimbal rings around a glass candle above a cyan disc)
4. `crystal`: Crystal Core (neon hexagon chamber, glossy candle, hex-grid floor)
5. `orb`: Oracle Orb (glass orb holding a candle chart that sweeps a level, then reverses)
6. `letters3d`: Chrome LE (extruded chrome letters, the L's foot sinks through a cyan line)

Re-render: `npm install three@0.160.0` in this folder, serve it (`python3 -m http.server 8799 --bind 127.0.0.1`), then
`NODE_PATH=$(npm root -g) node shot3d.js 1024 monolith` (writes `out/monolith_1024.png`; needs Playwright + Chromium).
