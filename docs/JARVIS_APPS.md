# Jarvis apps: plug a dashboard into Jarvis

**Send this to ChatGPT, together with this whole page:**

```text
Build "Ascend" as a phone-first web dashboard that also runs inside my hub app, Jarvis (Jarvis shows each dashboard in a frame).
Host it free on GitHub Pages: a repo named "ascend" on my GitHub account demetrades2000-coder, so it lives at https://demetrades2000-coder.github.io/ascend/
Follow the rules on this page: nothing that blocks frames, a mobile viewport with safe areas, the dark theme, every storage key starting with "ascend.".
Publish a status file at https://demetrades2000-coder.github.io/ascend/jarvis.json in the format on this page (plain text, 8 KB at most).
When it is live, send me the link. I add it to Jarvis once (+, then Add Ascend).
```

Any dashboard plugs into Jarvis the same way: one link, plus an optional `jarvis.json` that shows a live card on the
Jarvis screen. Jarvis is the owner's iPhone Home Screen app (`https://demetrades2000-coder.github.io/nq-dashboard/jarvis/`).
It opens each dashboard full screen in a frame under its top bar.

## 1. Look and work right inside Jarvis
- **Let it be framed.** Send no `X-Frame-Options` header and no CSP `frame-ancestors` that leaves Jarvis out (allow
  `https://demetrades2000-coder.github.io`). GitHub Pages sends neither. Never break out of the frame (no `top.location = ...`).
- **Phone viewport:** `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`. No sideways
  scroll at 390 px wide, 16 px side margins, tap targets at least 44 px, inputs at 16 px font (so the iPhone does not zoom).
- **Safe areas:** pad the page with `env(safe-area-inset-top)`, `-right`, `-bottom` and `-left`, so it also fits on its own
  from the Home Screen (the notch and the home bar).
- **Dark theme, the Jarvis look:** background `#0b0b0d`, panels `#1b1b1f`, lines `rgba(255,255,255,.09)`, text `#f4f4f6`,
  second text `#b3b4ba`, green `#46d79a`, amber `#f5b84a`, red `#ff6b7f`; font `-apple-system, system-ui, sans-serif`;
  `color-scheme: dark` and `<meta name="theme-color" content="#0b0b0d">`.
- **Share the site politely.** On GitHub Pages, Ascend shares one site with Jarvis, Zenith and the Planner, so:
  - every `localStorage` key starts with `ascend.`, and never call `localStorage.clear()`;
  - a service worker is optional; if you add one, register it with scope `./`, let it handle only its own folder, and
    delete only its own caches (names starting with `ascend-`).
- **Links that leave the app** open a new tab: `target="_blank" rel="noopener"`.
- **Pages by `#route`** (`#today`, `#history`), so a card can open a page directly.
- **Home Screen icon (optional):** a `manifest.webmanifest` with `name`, `start_url` and `scope` set to `./`,
  `display: standalone`, the colors above, and 192 px and 512 px icons; plus a 180 px `apple-touch-icon.png`.

## 2. Publish `jarvis.json` (the live card)
Put it in the app's folder: `https://demetrades2000-coder.github.io/ascend/jarvis.json`. Jarvis reads `<app link>jarvis.json`,
or another status link set when the app is added.

| key | type | rule |
|---|---|---|
| `v` | number | always `1` |
| `name` | text | the app's name, up to 40 characters |
| `status.level` | text | `ok` (green: all good), `warn` (amber: needs a look), `bad` (red: something is wrong), `off` (grey: paused) |
| `status.label` | text | up to 48 characters, e.g. `On track` |
| `kpis` | list, up to 3 | `{label, value, delta?}`: label up to 20 characters, value up to 24, delta up to 16 (text or a number) |
| `lines` | list, up to 3 | text lines, each up to 120 characters |
| `t` | number | unix **seconds** when the file was written |
| `open` | text, optional | a route inside the app that the card opens, e.g. `#today` |

`kpis` and `lines` can be empty or left out. Full example:

```json
{
  "v": 1,
  "name": "Ascend",
  "status": { "level": "ok", "label": "On track" },
  "kpis": [
    { "label": "This week", "value": "4 of 5", "delta": "+1" },
    { "label": "Streak", "value": "12 days" },
    { "label": "Score", "value": 82, "delta": -3 }
  ],
  "lines": ["Next: review at 6:30 PM", "2 tasks due today"],
  "t": 1793548800,
  "open": "#today"
}
```

Rules (Jarvis drops a card that breaks one, and keeps showing the last good one):
- **8 KB at most. Plain text only:** no HTML tags, no `&amp;`-style entities, no line breaks inside a text.
- **Format values yourself** (`"$1,250"`, `"82%"`, `"+3.2%"`); a number is shown as it is. A delta that starts with `+` shows
  green, one that starts with `-` shows red.
- **Keep `t` fresh.** 30 minutes after `t` the card turns grey ("not updated for ..."), so rewrite the file with a new `t`
  at least every 15 minutes, even when nothing changed; a free GitHub Action on a schedule can do it.
- Jarvis waits at most 5 seconds for the file.

**No server?** While Ascend is open inside Jarvis, it can post the same object to Jarvis on load and whenever its numbers
change; Jarvis keeps the last one for the card (`status` is the jarvis.json object):

```js
if (window.parent !== window) window.parent.postMessage({ jarvis: 1, href: location.href, card: status }, 'https://demetrades2000-coder.github.io');
```

## 3. CORS
- **Same site as Jarvis** (anything on `https://demetrades2000-coder.github.io/`): nothing to do.
- **Another site:** send `Access-Control-Allow-Origin: *` with `jarvis.json`. GitHub Pages already does. On Netlify or
  Cloudflare Pages use a `_headers` file; on Vercel, `headers` in `vercel.json`.

## 4. Add it to Jarvis (the owner, once)
1. Open Jarvis and tap **+**.
2. Tap **Add Ascend**. It finds `https://demetrades2000-coder.github.io/ascend/` by itself.
3. If Jarvis asks for the link, paste it and tap **Add**. Ascend then shows in the top bar, with its card on the Jarvis screen.

## For Claude (the Jarvis code)
- `tools/web_public/jarvis/apps.js`: an ES module the Jarvis page imports. It holds the registry (`listApps`, `addApp`,
  `removeApp`), the cards (`appStatus`, `cachedStatus`, `renderCard`, posted cards through `listen(window, onCard)`) and
  the Ascend slot (`ascendSlot`, `enableAscend`, `findAscend`). The API notes are at the top of the file.
- Storage on the phone: `jarvis.apps` is the registry, `jarvis.cards` the last good card per app. The older keys
  `jarvis.extra` and `jarvis.links` are read and kept in step, never deleted. Remove apps only with `removeApp(id)`:
  editing the older keys does not remove anything (the registry keeps what it imported).
- The Jarvis page: cards for apps that are not built in come from `cachedStatus(app)` (first paint), then
  `appStatus(app)` and `renderCard(card, document)`; `listen(window, ...)` refreshes them when an open app posts a card.
- A new app folder on the dashboard site (for example `nq-dashboard/ascend/`) goes into Zenith's `OTHER_APPS` in
  `tools/web_public/sw.js`, and needs a publish step like `scripts/add_planner.sh`, because each publish rebuilds the site.
- Test: `python -X utf8 -m tests.test_jarvis_apps`.
