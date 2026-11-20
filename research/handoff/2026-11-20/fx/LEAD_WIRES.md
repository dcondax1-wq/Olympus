# FX / OLYMPUS NIGHT: what only the lead wires (DESIGN, day-arenas 1419c927+)

## 1. The one-frame AGORA flash on the pages whose engine loads late (13 files)

OLYMPUS NIGHT is the default look but is never saved as a choice (so Classic Jarvis stays on). The FIRST PAINT copy in each page's <head>
therefore paints nothing when no look is chosen, and the page shows AGORA until themes.js arrives. Fix: put this ONE line right AFTER the
page's FIRST PAINT `<script>` (the one that ends `} catch (e) { return; } })(..., 'page');</script>`). It paints the engine's saved copy of
'night' (themes.js writes it on every apply, on every page). It does nothing once the owner has picked a look, nothing with a mix, nothing
before the engine has run once. Same rule as the copy already in Zenith's index.html.

```html
<script>/* OLYMPUS NIGHT from the first frame while nothing is chosen (kit, day-arenas 2026-11-20) */(function(){try{var ls=window.localStorage,v=ls.getItem('olympus.theme'),d=document.documentElement,k,on=window.__olyPaint||[];if((v&&v!=='agora')||ls.getItem('olympus.theme.night')==='1'||ls.getItem('olympus.themeMix'))return;var c=JSON.parse(ls.getItem('olympus.theme.look.page.night')||'null');if(!c||!c.vars)return;for(k in c.vars){d.style.setProperty(k,c.vars[k]);on.push(k);}d.setAttribute('data-oly-theme','night');d.setAttribute('data-oly-scheme','dark');if(c.style)d.setAttribute('data-oly-style',c.style);window.__olyPaint=on;}catch(e){}})();</script>
```

Files (all call FIRST PAINT with place 'page'):

```
tools/web_public/gate/index.html
tools/web_public/hub/index.html
tools/web_public/hub/zeus.html
tools/web_public/hub/doors.html
tools/web_public/hub/steps.html
tools/web_public/hub/whatsnew.html
tools/web_public/hub/manual.html
tools/web_public/hub/setup.html
tools/web_public/hub/help.html
tools/web_public/kalshi/index.html
tools/web_public/jarvis/shortcuts.html
tools/web_public/agency/expert/index.html
```

NOT these two: `tools/web_public/jarvis/index.html` (Jarvis keeps the default, so Classic stays on) and `tools/web_public/index.html` (Zenith already
has its own copy, which also skips Zenith's own light look). The kit apps that load themes.js synchronously in <head> need nothing.

## 2. ?v bumps (content changed under an unchanged tag)

| File | Tag in pages now | Bump to | Why |
|---|---|---|---|
| `olympus/themes.js` | `?v=o9` (101 pages) | `o10` | OLYMPUS NIGHT look + the unsaved default + warn gold |
| `olympus/agora.css` | `?v=a9` (96 pages) | `a10` | night block (violet tints), Ask rules moved above the style layer |
| `olympus/zeus_core.js` | `?v=7` in `hub/zeus.html`, `jarvis/index.html` | `8` | the ZEUS card in OLYMPUS NIGHT (Zenith already loads `?v=8`) |
| `olympus/nqfx.js` | `?v=n3` in `nq/` | `n5` | OLYMPUS NIGHT defaults (the lab loads `n5`) |
| `zenith_agora.css` | `?v=a5df` in `index.html` | `a5dg` | night: the selected side item violet (tests/test_zenith_nq.py a. pins `a5df`: bump it there too) |
| `settings/settings.css` | `?v=s5aqde` | `s5aqdf` | a comment only (optional) |

`olympus/nqvault3d.js` is imported by nqfx.js as `?v=n2` (already bumped), `olympus/dashfx.css` is fetched by zenith_fx.js as `?v=d1`.

## 3. Root sw.js

No precache entry is needed. The root sw.js pre-caches only its SHELL (`./`, `index.html`, the manifest, the icons) and caches every other
file on first fetch under its full URL, so the new tags are fetched fresh: `zenith_settle.js?v=5`, `zenith_fx.js?v=4`, `main.js?v=w14`,
`zenith_nq.js?v=5`, `zenith_hero.js?v=6`, `olympus/zeus_core.js?v=8`, `olympus/dashfx.js?v=d1`, `olympus/dashfx.css?v=d1`.
Only if you want Zenith to open fully offline on the first visit after the update, add exactly these to SHELL:

```js
'./main.js?v=w14', './zenith_settle.js?v=5', './zenith_fx.js?v=4', './olympus/dashfx.js?v=d1', './olympus/dashfx.css?v=d1'
```
