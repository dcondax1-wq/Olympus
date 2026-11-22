# Jarvis apps: plug a dashboard into Jarvis

**Send this to ChatGPT, together with this whole page:**

```text
Build "Ascend" as a phone-first web dashboard that also runs inside my hub app, Jarvis (Jarvis shows it full screen, its own look and header, no Jarvis bar).
Host it free on its own site, never under dcondax1-wq.github.io: Netlify, Vercel, Cloudflare Pages, or GitHub Pages of a separate account.
Follow the rules on this page: nothing that blocks frames, a mobile viewport with safe areas, and the bottom-right corner (80 x 160 px) kept free for Jarvis's orb.
Publish a status file jarvis.json next to its index.html in the format on this page, sent with Access-Control-Allow-Origin: *, with "theme" = its top colour.
When it is live, send me the link. I add it to Jarvis once (+, Add Ascend, paste the link).
```

Any dashboard plugs into Jarvis the same way: one link, plus an optional `jarvis.json` that shows a live card on the
Jarvis screen. Jarvis is the owner's iPhone Home Screen app (`https://dcondax1-wq.github.io/jarvis/`).
It opens each dashboard as its own screen (since 2026-11-02): full screen, its own look and header, no Jarvis bar; the
owner switches apps with Jarvis's floating orb (bottom right). The strip behind the iPhone's status bar takes the app's
colour: `theme` in its jarvis.json (another site's page cannot be read), else black.

## 1. Look and work right inside Jarvis
- **Its own site, never under `dcondax1-wq.github.io`.** Why: every page there shares one origin with Jarvis and
  the Planner, so it could read the keys they keep on the phone. Good homes: Netlify (`*.netlify.app`), Vercel
  (`*.vercel.app`), Cloudflare Pages (`*.pages.dev`), or GitHub Pages of another account or organization.
- **Let it be framed.** Send no `X-Frame-Options` header and no CSP `frame-ancestors` that leaves Jarvis out (allow
  `https://dcondax1-wq.github.io`). Never break out of the frame (no `top.location = ...`).
- **Inside Jarvis it is another site's frame.** The iPhone blocks its cookies there and keeps its storage apart from when
  it is opened on its own, so don't depend on a cookie login; keep data that must show in both places on a server.
- **Phone viewport:** `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`. No sideways
  scroll at 390 px wide, 16 px side margins, tap targets at least 44 px, inputs at 16 px font (so the iPhone does not zoom).
- **Safe areas:** pad the page with `env(safe-area-inset-top)`, `-right`, `-bottom` and `-left`, so it also fits on its own
  from the Home Screen (the notch and the home bar).
- **Its own look** (any theme; the dark Jarvis look as a default): background `#0b0b0d`, panels `#1b1b1f`, lines `rgba(255,255,255,.09)`, text `#f4f4f6`,
  second text `#b3b4ba`, green `#46d79a`, amber `#f5b84a`, red `#ff6b7f`; font `-apple-system, system-ui, sans-serif`;
  `color-scheme: dark` and `<meta name="theme-color" content="#0b0b0d">`.
- **Links that leave the app** open a new tab: `target="_blank" rel="noopener"`.
- **Pages by `#route`** (`#today`, `#history`), so a card can open a page directly.
- **Home Screen icon (optional):** a `manifest.webmanifest` with `name`, `start_url` and `scope` set to `./`,
  `display: standalone`, the colors above, and 192 px and 512 px icons; plus a 180 px `apple-touch-icon.png`.

## 2. Publish `jarvis.json` (the live card)
Put it next to the app's `index.html`, for example `https://ascend-dash.netlify.app/jarvis.json`. Jarvis reads
`<app link>jarvis.json`, or another status link set when the app is added.

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
| `theme` | text, optional | the app's top colour, `#rrggbb` (e.g. `#0b0b0d`): shown behind the iPhone's status bar while it is open in Jarvis |
| `stale_after` | number, optional | seconds the card stays current (60 to 1,209,600; default 1,800 = 30 min). A nightly-refreshed app can say 259200 (3 days) |

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
  "open": "#today",
  "theme": "#0b0b0d"
}
```

Rules (Jarvis drops a card that breaks one, and keeps showing the last good one):
- **8 KB at most. Plain text only:** no HTML tags, no `&amp;`-style entities, no line breaks inside a text.
- **Format values yourself** (`"$1,250"`, `"82%"`, `"+3.2%"`); a number is shown as it is. A delta that starts with `+` shows
  green, one that starts with `-` shows red.
- **Keep `t` fresh.** 30 minutes after `t` the card turns grey ("not updated for ..."), so rewrite the file with a new `t`
  at least every 15 minutes, even when nothing changed; a free scheduled job (a GitHub Action, a Netlify or Vercel cron)
  can do it.
- Jarvis waits at most 5 seconds for the file.

**No server?** While Ascend is open inside Jarvis, it can post the same object to Jarvis on load and whenever its numbers
change; Jarvis keeps the last one for the card (`status` is the jarvis.json object):

```js
if (window.parent !== window) window.parent.postMessage({ jarvis: 1, href: location.href, card: status }, 'https://dcondax1-wq.github.io');
```

## 3. CORS (needed: Ascend is on another site)
`jarvis.json` must be sent with `Access-Control-Allow-Origin: *`, or Jarvis cannot read it.
- **GitHub Pages** (of another account) sends it already.
- **Netlify or Cloudflare Pages:** a file named `_headers` next to `index.html`:
  ```text
  /jarvis.json
    Access-Control-Allow-Origin: *
  ```
- **Vercel:** in `vercel.json`:
  `{"headers": [{"source": "/jarvis.json", "headers": [{"key": "Access-Control-Allow-Origin", "value": "*"}]}]}`

## 4. Add it to Jarvis (the owner, once)
1. Open Jarvis and tap **+**.
2. Tap **Add Ascend**.
3. If Jarvis asks for the link, paste the one ChatGPT gave you and tap **Add**. Ascend then shows in the top bar, with its
   card on the Jarvis screen.

## For Claude (the Jarvis code)
- `tools/web_public/jarvis/apps.js`: an ES module the Jarvis page imports. It holds the registry (`listApps`, `addApp`,
  `removeApp`), the cards (`appStatus`, `cachedStatus`, `renderCard`, posted cards through `listen(window, onCard)`) and
  the Ascend slot (`ascendSlot`, `enableAscend`, `findAscend`). The API notes are at the top of the file.
- **Never host an outside-built app on `dcondax1-wq.github.io`** (not in `nq-dashboard/`, not as a repo of that
  account): it shares Jarvis's origin and could read the keys Jarvis and the Planner keep in localStorage. `addApp` still
  adds such a link, with `warn: SAME_SITE_WARN` in the result and on the app.
- When the owner sends Ascend's link (on its own site), put it in `ASCEND_URL` in `apps.js`: **Add Ascend** then adds it
  with one tap. Nothing is guessed; a same-site link there is refused.
- Storage on the phone: `jarvis.apps` is the registry, `jarvis.cards` the last good card per app. The older keys
  `jarvis.extra` and `jarvis.links` are read and kept in step, never deleted. Remove apps only with `removeApp(id)`:
  editing the older keys does not remove anything (the registry keeps what it imported).
- The Jarvis page: cards for apps that are not built in come from `cachedStatus(app)` (first paint), then
  `appStatus(app)` and `renderCard(card, document)`; `listen(window, ...)` refreshes them when an open app posts a card.
- Test: `python -X utf8 -m tests.test_jarvis_apps`.
