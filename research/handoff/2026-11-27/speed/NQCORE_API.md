# NQ data layer API (night-nq-speed, 2026-11-27)

One file: `tools/web_public/nq/nqfeed.js` (classic script, `window.NQ_FEED`). It fetches the PC's signed status post ONCE per
page / per phone (all tabs and hub iframes), keeps the last verified post, and hands it to every widget.

## 1. Add one tag (page owners / lead)

Right after the `../pc_feed.js` tag, in the `<head>`, NOT defer / module (it must run before the modules):

```html
<script src="../pc_feed.js?v=n9"></script><script src="nqfeed.js?v=1"></script>
```

Pages: `nq/index.html`, `nq/live.html`, `nq/accounts.html`, `nq/brain.html` (and any new NQ page). That alone:

- starts the ntfy read in the head (before nq.js / live.js and their imports load: on a phone that was the 2-6 s wait),
- makes every existing `window.PC_FEED.fetchLatest(...)` call on the page share that one read (it wraps it; `data-wrap="0"` on the tag = off),
- uses the cached `status_feed.json` settings, so the ntfy poll does not wait for that file (it is still re-read; a key change re-polls),
- when the network fails, `fetchLatest` answers the LAST VERIFIED post (with its own `t`: an old post reads as old) instead of null;
  with nothing kept it is still null. Nothing is ever made up: posts only come from `PC_FEED.fetchLatest` (signature check passed).

## 2. Instant numbers + live updates (recommended, 3 lines in each page script)

```js
const NQF = window.NQ_FEED;                       // null if the tag is missing: keep your old path
if (NQF) {
  const first = NQF.cached();                     // sync: the kept post (localStorage) or null -> render it NOW with its age
  if (first) render(first);
  NQF.on((lite, meta) => render(lite));           // every newer post: network, another tab, the 60 s check. meta = {src, at, age}
}
```

or listen to the window event: `addEventListener('nq-feed', () => load())` (fires on every newer post).

## 3. Full API

| call | returns | notes |
|---|---|---|
| `NQ_FEED.latest({force})` | Promise of the newest post or null | kept post if read < 60 s ago, else ONE network read (shared by all callers) |
| `NQ_FEED.cached()` | post or null (sync) | the kept post (this page, localStorage, another tab). Copy: safe to mutate |
| `NQ_FEED.on(cb)` | unsubscribe fn | `cb(post, {src: 'cache'\|'net'\|'peer', at, age})` now (if kept) and on each newer post |
| `NQ_FEED.refresh(true)` | Promise | force a read (a "refresh" button) |
| `NQ_FEED.age(t)` | `{s, text, level}` | `text` "just now" / "12 min ago" / "3 h 5 min ago" / "2 days ago"; `level` ok (<= 20 min) / warn (<= 36 h) / bad / off |
| `NQ_FEED.info()` | `{at, src, t, fails, stats}` | debugging: where the post came from, how many reads / cache hits / probes |
| `<span data-age-t="1795756502"></span>` | | any element: nqfeed writes its age and keeps it counting (15 s ticker), plus `data-age-level` for colour |
| `window` event `nq-feed` | `detail {src, t}` | each newer post |

Rules it follows by itself:
- fresh window 60 s (no 2nd read inside it), one read in flight, 8 s cross-tab lease + BroadcastChannel `olympus-nq-feed`
- retries 2, 4, 8, 16, 30, 60 s while visible; at once on `online` and when the page comes back to the front (> 60 s)
- every 60 s while visible: `ntfy .../json?poll=1&since=<last read - 60 s>` (empty = a few hundred bytes). Only a new message
  triggers the full read; a full read at least every 5 min anyway. So a new PC post shows within ~1 min (was up to 5 min)
- storage blocked (private mode) = it still works, without the cache. Posts dated > 10 min in the future are refused.
- localStorage keys: `olympus.nqfeed.v1` (post, ~11 KB), `olympus.nqfeed.cfg.v1` (status_feed.json), `olympus.nqfeed.lease`

## 4. Do / don't

- DO show the post's age next to its numbers (`NQ_FEED.age(lite.t).text`): the cached post can be hours old on a quiet PC.
- DON'T fetch `status_feed.json` / ntfy yourself any more (the chart's bars topic in nqchart.js is a different topic: fine).
- DON'T call `fetchLatest` on a timer faster than 60 s: `on()` already gets every new post.
- Heavy 3D stays behind `../olympus/lazy3d.js` (data-near / data-skip="lite"): already the case on nq/index.html.

Tests: `python -X utf8 -m tests.test_nq_speed` (nq area). Timings: `python -X utf8 tools/nq_speed_probe.py` (real feed, 4G, 390x844).
