# Olympus design system (one source, 2026-11-20)

Owner: "make Olympus as a whole better." This is the ONE design system every app follows. Live reference: **`/olympus/kit.html`**
(every token and component as the apps really draw them, with a look picker that previews only; open it at 390 x 844 before you change
a shared sheet). Slow-network check: `tools/perf_sweep.py` (PERF) or the layout-shift finder in the DESIGN report. Older notes it replaces or summarises: `docs/DESIGN_AGORA.md` (the AGORA look), `docs/OLYMPUS_DESIGN.md` (kit history,
themes, budgets).

## 1. The four shared files (load order)

| File | What it owns | Every app |
|---|---|---|
| `olympus/olympus.css` | veil, quality tiers, per-app name / glyph / colour | first |
| `olympus/agora.css` | **tokens** (`--ag-*`, painted from the look slots `--oly-th-*`), base, and the **component set** | second |
| `olympus/pulse.css` + `pulse.js` | the prop-trader cards (strip, hero, accounts, bots, stats, money), folded-in links, tax-pot card | apps that show money |
| `olympus/shell.css` | layout tokens (`--o-*`), the bottom bar (Zenith), the **calm** rules (reduced motion, no live blur on a phone) | **last** |

An app page says `<html lang="en" data-theme="agora" data-oly-shell="app" data-oly-light>`:
`data-oly-light` = its sheets use tokens only, so a light look (Ivory, Stocks Light, Editorial ...) paints it light; without it a light look
gives the page its dark "stage" variant (3D pages such as Fates). `data-oly-shell="app"` = shell.css's app rules apply (no blur behind
scrolling cards on a phone; the Zenith bottom-bar rules do NOT apply). A page without the kit engine (`olympus.js`) paints the chosen look
itself: `<script>OLYMPUS_THEMES.apply('page')</script>` right after `themes.js` (plan.html, atlas/).

## 2. Tokens (use these, never a hex)

| Role | Token | Notes |
|---|---|---|
| Page / card / raised / line | `--ag-night` `--ag-panel` `--ag-raise` `--ag-line` (`--ag-s0..s4` surfaces low to high) | follow the look |
| Text / soft / muted | `--ag-text` `--ag-soft` `--ag-muted` | every text token >= 4.5:1 on every surface, dark and light |
| Accent | `--ag-gold` (`--ag-gold-hi` on dark only) | text ON gold: `--ag-on-gold` / `--oly-th-n3` (never a fixed #1b1610: it failed AA on light looks) |
| Money up / down | `--ag-olive-text` / `--ag-terra-text` | TEXT colours. `--ag-olive` / `--ag-terra` are FILLS (bars, dots), never text |
| Warn / info | `--ag-sun` / `--ag-aegean-text` | |
| Type | `--ag-serif` (titles), `--ag-sans` (body), `--ag-num` (numbers: rounded, `tabular-nums`) | |
| Sizes | cap 13, foot 14, sub 15, **note 15** (any sentence in a muted colour), body 15, lead 17, h3 18, h2 22, h1 30, stat 28, hero 44 (`--ag-fs-*`) | **a sentence is never under 15 px; a label of 1-4 words may be 13; nothing under 12** (A11Y K2) |
| Space | 4 px grid `--ag-sp-1..8`, gutter 16 | |
| Shape | radius small 12, card 16, hero 22, pills 999 | one hairline border per card |
| Elevation | `--ag-e1..e3` | soft, never a glow |
| Motion | curve `--ag-ease` = cubic-bezier(.2,.8,.2,1); `--ag-d1` 200 ms (tap, toggle), `--ag-d2` 260 ms (card, sheet), `--ag-d3` 340 ms (page, a bar filling) | reduced motion: nothing moves (shell.css) |

## 3. Components (class names in agora.css; examples on kit.html)

- **Headline**: `.ag-card.ag-hero` > `.ag-hero-label`, `.ag-hero-num`, `.ag-hero-sub` (+ `.ag-bar > i`). One per page, the number that matters first.
- **Pulse strip / hero**: `<section class="pulse" data-pulse="strip,hero:room" data-pulse-app="<id>">` with one `.pu-part.pu-<part>` placeholder per
  part (the height is reserved: layout shift 0). Parts: `strip`, `hero:room|today|pass|payout|net|last`, `accounts`, `bots`, `stats`, `money`.
- **Stats**: `.ag-stats` > `.ag-stat` (`-label`, `-value`, `-sub`), `.ag-delta`.
- **Rows**: `.ag-list` > `.ag-row` (`-ic`, `-main`, `-title`, `-sub`, `-end`, `.ag-chev`). A row that opens something is an `<a>`/`<button>` >= 44 px.
- **Chips / badges / pills**: `.ag-chip` (filter, `.on`), `.ag-badge ok|warn|bad|info|demo` (state). App sheets that keep `.pill` use the text tokens above.
- **Segmented / tabs / buttons / field**: `.ag-seg` (aria-pressed), `.ag-tabs`, `.ag-btn primary|ghost`, `.ag-field`.
- **Banner**: `.ag-banner` (warn) / `.ag-banner.bad`: data is old or something needs a tap.
- **Empty / error / loading**: `AGORA.state(el, {kind: 'empty'|'error'|'loading', title, text, action})`, skeleton `.ag-skel title|num|line`.
  Offline = show the last numbers WITH their age (olympus/truth.js `agesOf`), never a blank card.
- **Toast / sheet**: `AGORA.toast(text, {kind})`, `AGORA.sheet(...)` (agora-ui.js).
- **Folded-in apps**: `<nav class="folded">` links to archived apps whose job this page now does (pulse.css).
- **Data age**: `age.js` + `age.css` at the site root (one format site-wide, DATA TRUTH owns them): `OLY_AGE.chip(span, seconds, 'pc'|'live'|'bars'|'daily'|'weekly')`
  -> "updated 4 min ago", amber after a missed report, red when old. The pulse cards and Settings use it.

## 3b. How the kit keeps the page still (layout shift 0 on a phone line)

- **Under the veil** (olympus.js): while the loading veil is up, the page's content (everything but `header.top`) is laid out but not drawn
  (`html[data-oly-veil]`, visibility); it shows when the app calls `OLYMPUS.ready()` (or the 12 s fallback). Cards that fill as data
  arrives cannot count as a shift. An app MUST call `OLYMPUS.ready()` after its first real render (Business did not: its veil sat 12 s).
- **The back row** (agora.css): `header.top` keeps the empty 44 px row the back / crumbs (agora-ui.js, gate-nav.js) fill later.
- **Late parts reserve their height**: pulse parts have fixed heights; a list that fills late gets a `min-height` of its usual size
  (Atlas `#needs`, Fates `.hud`). Never insert a block above content already on screen.
- **3D after idle** (lazy3d.js): window `load` + idle (2 s cap); skipped like LITE on Save-Data, 2G/3G or <= 4 GB memory (never on iPhone Safari).
- A page without the kit engine (business/plan.html) does the same by hand: `data-oly-veil` on `<html>` until its scripts have drawn (8 s cap).

## 4. Rules that the audit checks (`python tools/design_audit.py --site <built site>`)

1. The number that matters first, at the top, readable in 5 s.
2. Kit sheets loaded in the order above; `data-oly-light` unless the page is a 3D stage.
3. No console errors, no failed requests on the public site (private files are asked only on the PC's own link).
4. Layout shift 0 (reserve heights), no long task > 200 ms outside 3D scene start, first paint < 1 s.
5. No sideways scroll, nothing under the bottom bar, taps >= 44 px (a switch inside a >= 44 px row label is fine).
6. Text >= 12 px, AA contrast (4.5:1, 3:1 for big text) in dark AND in a light look.
7. Same names and the same $ everywhere: account numbers only through `olympus/truth.js`; money only through pulse / ledger.
8. Sound: UI cues only through the kit (`data-oly-cue`, `OLYMPUS.cue`); the Settings Sound switch, LITE, reduced motion and the iPhone ringer decide.

## 5. Settings is the one place

Look (Theme, Quality, Reading), Sound (Sounds and touch), Alerts (Alerts and briefing, Phone notifications: on/off on this phone, link to the
card, the PC's `notify_settings.json` for the alert types), Data (How old the numbers are, storage, caches, export). Settings never uses the
network: it reads this phone's storage only (`olympus.push`, `olympus.pulse.ages`).
