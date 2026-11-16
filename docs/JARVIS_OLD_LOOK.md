# The owner's old Jarvis: look and features (reference for the phone Jarvis)

Reconstructed 2026-11-01 from the owner's PC sessions "Jarvis Bot" and "Jarvis Background Code" (research agent R1). The
phone Jarvis (tools/web_public/jarvis/) follows it: the Reactor/Eclipse violet HUD, Orbitron/Rajdhani, the 3D Gimbal Reactor
core (core-visual.js, ported from the old reactor scene), the HUD panels, the command bar and the ⋯ menu. PC-only features
(wake word, double clap, look at my screen, CPU/RAM gauges, the kill switch, mail) are left out on the phone.

**Night A 2026-11-16 ("bring back our Jarvis we had"):** the violet HUD is back as an opt-in look, **Classic Jarvis**: ⋯ → Look →
Jarvis look → Classic Jarvis, or say "classic Jarvis" / "bring back the old Jarvis" ("agora look" switches back). Black + Eclipse violet
`#a855f7 / #7c3aed / #c084fc`, Orbitron titles, Rajdhani text, glowing capital labels, the violet core (the sheet's --c colours). Its own sheet
`tools/web_public/jarvis/classic.css`, loaded only when picked (`localStorage 'jarvis.look' = 'classic'`), so AGORA stays the default and
byte-identical. Picking any OLYMPUS theme turns Classic off.

---


## What the phone Jarvis must look like and do (summary)
1. **Dark sci-fi HUD in violet.** Default theme "Eclipse": black `#000` background, violet accent `#a855f7` / `#7c3aed` / `#c084fc`, text `#ece9f2`, muted `#8a8499`. The owner said "keep the color for sure" about the violet.
2. **Fonts:** Orbitron for titles, labels and buttons (all caps, wide letter-spacing, glow); Rajdhani for body text; a monospace for logs and hints.
3. **The centrepiece is a real 3D WebGL core** in the middle of the main screen: a plasma "Nexus" reactor (glowing faceted core, 3 chrome gimbal rings, orbiting cubes) or the default "Singularity" black hole with a bright accretion ring. Around it sit a rotating wireframe hologram globe, a particle starfield and nebula, a perspective grid floor, and a ticked HUD ring with curved "CPU 97% · RAM 14%" text, the clock and "STANDBY".
4. **Under the core:** the state word (STANDBY / LISTENING / THINKING / SPEAKING), the line "Good day. Click the core or type below to speak with me.", and a row of three buttons: HANDS-FREE, a big round mic, and VOICE ⚙. Below them the hint "TAP · HANDS-FREE HOLD · PUSH-TO-TALK".
5. **Top of the screen:** green status dot, "J.A.R.V.I.S." title, pills MODULES / KALSHI / FUTURES / INSTAGRAM, a "KALSHI TODAY" P&L box, and mode tabs CHAT / CODE / TRADE / RESEARCH.
6. **Stacked HUD panels** with clipped corners, a glowing top-left tick and a scan sweep: Connect my brain (Groq/Gemini key), Awaiting approval, To-do, Forex Factory USD calendar, Add-ons (verse of the day, quote of the day, BTC/ETH/SOL), Activity feed, System core (CPU/RAM/DISK/POWER bars).
7. **Fixed glass command bar** at the bottom: "Ask Jarvis anything…", mic, SEND, and ⋯. The ⋯ menu holds CORE, FULL SCREEN, WAKE WORD, LOOK, KILL, LOOK AT MY SCREEN, AI KEY, THEME, HOLD-TO-TALK, 3D ON/OFF, TILT, ALERTS. There is also a floating round search button (command palette) and a "Nothing scheduled today" chip.
8. **Motion:** boot screen ("J.A.R.V.I.S." boot log), cards that tilt in 3D as they scroll and when pressed, tap ripples, scan lines, and the core speeding up or turning red while it listens. **On phones nothing may drift or move with the gyro unless Tilt is on.** The owner complained about this on 10-18 and it was fixed.
9. **Themes:** 24 themes, including the Reactor family (Violet, Stark gold, Ice, Emerald) and a Custom theme with hue, saturation and backdrop sliders. A switch, "Also switch the app icon and the 3D core", is on by default. There are 6 3D core designs and an effects level (ultra / high / low / off).
10. **App icon:** the violet "Gimbal Reactor" 3D render (plasma core, 3 chrome rings, mirror floor). Before 10-17 the icon was a black-hole "J.A.R.V.I.S · CORE ONLINE" dial. The Three.js scene that made it was rebuilt and re-renders correctly: `old_jarvis_ui/reactor_r3d2.html`.
11. **Brain:** chat in 4 modes with Groq (`openai/gpt-oss-120b`) or Gemini (`gemini-3.5-flash`), using a free key the owner pastes in. Questions get "smart depth" (quick / think / deep; "millionaire expert" mode for decisions). It has a 15-agent crew, memory, plans and approvals.
12. **Voice:** tap / hands-free / hold-to-talk mic. Speech-to-text was Groq Whisper. Speech out was Microsoft Edge neural TTS (`en-US-AvaNeural`, rate +6%, pitch +10Hz), with the phone's built-in voice as backup. The wake word "Jarvis" and the double-clap were PC only.
13. **Phone-first:** an iPhone Home Screen PWA that works with the PC off. Notifications are Kalshi **outcomes only** ("🌌 +$1.26" style). Jarvis is read-only on trading, and any outward action needs the owner's Allow tap.
14. **The owner's bar for the look:** "make it sick like futuristic sick", "looking insane", real 3D with chrome, glass, glow and particles. Flat or subtle designs were rejected.

**What was read.** Session B, "Jarvis Background Code" (session_016UPBCgYYZ1ZGrnLNrsSifH, the cloud dev session): **100% of its user and assistant events**, in 16 pages (10-12 09:14 to 10-18 20:12, plus idle events to 10-30). Session A, "Jarvis Bot" (session_015KWYYpbrGkK71eTdqtZ6SU, the PC session): **the newest ~2,200 events only**, 10-12 03:14 to 10-17 12:54. That is roughly the last 5 of its 11 days. Its first ~6 days (10-06 to 10-12 03:14), where most of the app was first built, were **not reached**: the overnight build stretch runs about 100 events per 4-8 minutes, which is hundreds more pages. Subagent transcripts are not part of either session, and most front-end files were written by subagents, so their sources are not in these transcripts. Main sources: 50 real screenshots inside the transcripts; the project's own `DEV_GUIDE.md`, `HANDOFF.md` and memory notes as quoted in tool results; `cat`/`grep` output of `static/` files; and the Write/Edit/patch inputs.

---

## a. LOOK, precisely

### Colours (exact CSS variables, from `static/themes.css` / `themes3.css` / `themes4.css`)
Every colour comes from CSS variables on `<html data-theme=…>`, stored in `localStorage.jtheme` (default `eclipse`). Variable meanings: `--bg` page, `--bg2` centre glow, `--pr` panel RGB, `--txt` text, `--mut` muted text, `--dim/--dim2/--dim3` borders, `--c/--c2/--c3` accents, `--cr/--cr2/--cr3` the accents as RGB triplets, `--tint` the core's centre, `--fxpal` the particle palette, `--grid` grid opacity, `--scan` scanline opacity. Shared: `--bad:#ff4d6d; --ok:#4ade80; --warn:#fbbf24`.

| Theme (key) | --bg / --bg2 | --c (accent) / --c2 / --c3 | --txt / --mut | --tint | notes |
|---|---|---|---|---|---|
| **Eclipse (eclipse), DEFAULT** | `#000` / `#0b0a10`, panel rgb `12,10,20` | **`#a855f7` / `#7c3aed` / `#c084fc`** | `#ece9f2` / `#8a8499` | `#e9ddff` | dim `#221b2e` `#3b2a5c` `#4c2f86`; fxpal `168,85,247 / 217,70,239 / 196,181,253 / 124,58,237 / 244,114,182`; grid .05, scan .035 |
| **Reactor (reactor)**, violet, matches the icon | `#03010a` / `#0d0620`, pr `14,8,30` | `#a95cff` / `#6d28d9` / **`#22d3ee` (cyan accents)** | `#efe9ff` / `#958ab3` | `#f5d0fe` | body: violet + blue + cyan radial glows |
| Reactor Stark (reactor-stark) | `#070101` / `#160606` | `#ffbe3d` gold / `#d6281f` red / `#6fd8ff` arc-blue | `#fff4e6` / `#c3a189` | `#fff1d0` | "Gold rings, arc-blue core" |
| Reactor Ice (reactor-ice) | `#01050b` / `#06121f` | `#4fe3ff` / `#0284c7` / `#9d8cff` | `#e8f8ff` / `#86aac2` | `#e6fbff` | "Ice blue and silver" |
| Reactor Emerald (reactor-emerald) | `#010805` / `#04140d` | `#1ff5a4` / `#059669` / `#b4ff3c` | `#e6fff4` / `#86b8a2` | `#dcfff0` | "Emerald plasma" |
| Obsidian | `#000` / `#09090b` | `#e5e7eb` / `#9ca3af` / `#ffffff` | `#ececef` / `#86868f` | `#f4f4f5` | monochrome silver |
| Arctic | `#00060b` / `#050b10` | (blue; rest of the block not in the transcripts) | `#e6f1f8` / `#7d8fa3` | | |
| Aurora | `#01080a` / `#06130f` | `#34f5b0` / `#14b8a6` / `#a78bfa` | `#e8fff6` / `#8bbfae` | `#d6fff0` | |
| Tokyo | `#05031a` / `#0c0830` | `#ff2bd6` / `#6d28d9` / `#22e5ff` | `#f3eeff` / `#a79ad6` | `#ffe0fa` | neon pink |
| Ocean | `#000a14` / `#04172a` | `#2ef2d0` / `#0ea5a0` / `#38bdf8` | `#e2f8ff` / `#7fb3c8` | `#d2fff7` | |
| Forge | `#0b0806` / `#17100b` | `#ff7a1a` / `#c2410c` / `#ffd9a8` | `#fff3e6` / `#bf9d82` | `#fff1dc` | |
| Void | `#000000` / `#050505` | `#f2f2f2` / `#9a9a9a` / `#ffffff` | `#f5f5f5` / `#9a9a9a` | `#ffffff` | |

The full list of 24 themes: eclipse (default), obsidian, daylight (the only **light** theme), arctic, crimson, matrix, solar, sakura, ghost, custom, aurora, tokyo, ocean, forge, void, jade, royal, vapor, blood, glacier, reactor, reactor-stark, reactor-ice, reactor-emerald. Colours not listed above never appeared in the transcripts. **Light/dark:** dark by default; Daylight is the light option. `<meta name="theme-color" content="#000000">`, status bar `black-translucent`.

### Fonts
- Google Fonts: `Orbitron` (500/600/700, and 600/800 on preview pages) and `Rajdhani` (400/500/600/700).
- The Look settings default is `font: 'orbitron'`. The HUD canvas font is `"Orbitron","Bahnschrift","Segoe UI",sans-serif`.
- The base CSS falls back to `"Segoe UI",system-ui,sans-serif`. Logs and hints use `ui-monospace,Consolas,monospace`.
- Labels are uppercase with letter-spacing .15em to .5em and a `text-shadow:0 0 12px var(--c)` glow.

### Global surface (from the inline `<style>` of `static/index.html`)
- **Background:** `radial-gradient(ellipse at 50% 45%, var(--bg2) 0%, #000 65%)`.
- **Scanlines** (`body::before`): `repeating-linear-gradient(0deg, rgba(var(--cr),.035) 0 1px, transparent 1px 3px)`.
- **48px grid** (`body::after`): faint `rgba(var(--cr),.05)` lines, masked to the centre.
- **Panels:**
  - gradient `rgba(var(--pr),.55→.65)`, a 1px `var(--dim)` border, and an inset glow;
  - the shape is `clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px))`, i.e. clipped top-right and bottom-left corners;
  - a 36×2px glowing accent tick at the top-left;
  - h2 titles are 11px, uppercase, .3em spacing, in the accent colour, with a "◆" bullet and a green status dot.
- **Buttons:**
  - transparent, with a 1px accent border, uppercase, 11px, .15em spacing;
  - on hover they fill with `rgba(var(--cr),.15)` and glow;
  - `.no` buttons are red and `.ok` buttons are green;
  - on phones they become rounded pill "keys" that press in (p3d.css).
- **Command bar:** clipped-corner form. On phones it is a fixed, rounded glass bar with a spinning glowing conic edge (`@property --p3a`).

### Main screen layout
**Desktop (3 columns, `.stage` grid 1fr / 1.2fr / 1fr):**
- **Left column:** System Core gauges (CPU/RAM/DISK/POWER mini bars) and Awaiting Approval.
- **Centre:** the orb/core, a 32-bar voice visualiser (`#vbars`), `#state`, `#says`, and Connect my brain (hidden).
- **Right column:** Connect Kalshi (read-only), Forex Factory · USD (ET), Add-ons and Activity Feed.
- **Header:**
  - left: "● SYSTEM ONLINE";
  - centre: "J.A.R.V.I.S." with a "Change key" button;
  - right: the KALSHI TODAY box and the clock;
  - an ECG line and the HUD clock come from hud2.js.
- **Footer:** `> COMMAND`, the input, and Wake / Voice / Send / Kill buttons.

**Phone (≤ 820px, `mobile.css` + `hud2.css` + `p3d.css`). This is what the owner used, top to bottom** (see `old_jarvis_ui/ref/ref_th_violet_reactor_main.jpg`, `old_jarvis_ui/ref/ref_main_eclipse_singularity.jpg`, `old_jarvis_ui/ref/ref_phone_fullpage_before_p3d.jpg`):
1. **Header:** green status dot, then "J.A.R.V.I.S." in extruded, slowly glowing Orbitron with .32em spacing. Next row: MODULES · KALSHI · FUTURES · INSTAGRAM pills, then the "KALSHI TODAY" box (big % in accent, $ in muted; green/red glow for up/down) and a button.
2. **Mode tabs:** CHAT · CODE · TRADE · RESEARCH. The active one is a glowing pill.
3. **3D core:** `min(66vw, 290px)`, with the rings, the HUD ring (clock, STANDBY, CPU/RAM arcs) and the starfield behind it.
4. **STANDBY** (11px, .3em spacing, glow) between two hairlines.
5. The `#says` line in 16–18px white: "Good day. Click the core or type below to speak with me." Then the mono hint "New: tap the big mic once, then just talk. Hold it for push-to-talk."
6. **HANDS-FREE** pill (with a status dot), **big round mic**, and **VOICE ⚙** pill. Below: "TAP · HANDS-FREE HOLD · PUSH-TO-TALK".
7. **Panels:**
   - CONNECT MY BRAIN: Groq/Gemini select, "Paste key", SAVE;
   - AWAITING APPROVAL: "No actions pending.";
   - TO-DO: "Nothing to do. Add a task, or tell Jarvis 'add finish the report by 5pm, takes an hour'.", plus Add a task…, a date/time, minutes, a priority (med) and ADD TASK;
   - toasts like "ⓘ Your morning briefing is ready. OPEN IT" (INFO · time);
   - FOREX FACTORY · USD: ■ High red `#ff4d4d`, ■ Medium orange `#ff9f1a`, one row per event with time, forecast and previous;
   - ADD-ONS: VERSE OF THE DAY (KJV, big drop-cap quote mark), QUOTE OF THE DAY (zenquotes.io), BTC / ETH / SOL price with a red/green % pill, and "More slots open. Ask Jarvis for weather, calendar, news, anything.";
   - ACTIVITY FEED;
   - SYSTEM CORE: segmented CPU/RAM/DISK/POWER bars with a CLOUD badge.
8. **Floating round search button** at the bottom-right (command palette), a "Nothing scheduled today" chip, and the **fixed bottom bar**: Ask Jarvis anything… / mic / SEND / ⋯.
9. **The ⋯ "More" menu** is a grid of pill keys: CORE, FULL SCREEN, WAKE WORD: ON (green), ⚙ LOOK, KILL (red), LOOK AT MY SCREEN, AI KEY, THEME, HOLD-TO-TALK: AUTO, 3D ON (green), TILT OFF, ALERTS. See `old_jarvis_ui/ref/ref_more_menu.jpg`.

### The centrepiece (3D, raw WebGL2, no libraries, works offline)
- **`scene3d.js`** draws a fixed `<canvas id="scene3d">` behind everything:
  - a particle universe (stars, spiral dust, bokeh), a state tunnel and warp streaks;
  - a **rotating hologram globe** (lat/long wireframe, nodes, pulsing great-circle arcs, tilted orbit rings, voice-ripple shells);
  - a **perspective terrain/grid floor** that reacts to audio, and a 3D P&L skyline (Kalshi daily P&L as glass columns);
  - quality levels: ultra 10,500 particles at 60fps; high 5,200 at 30fps (the phone default); low 3,000.
- **`core3d.js`, the "Quantum core"** in the centre:
  - nucleus: a displaced icosphere with plasma and a fresnel rim, plus a volumetric glow and anamorphic flare;
  - 3 counter-rotating geodesic wireframe shells;
  - **3 chrome gimbal torus rings** with energy channels;
  - **6 satellites** (cubes and octahedra) with light trails;
  - 12 tendrils that reach toward the camera while listening;
  - a holographic halo disc with shock rings while speaking;
  - bloom, chromatic aberration and a vignette.
- **Core designs** (`core3d_styles*.js`, picker under ⋯ → CORE):
  - **Nexus** ("Faceted core, gimbal rings and satellites (the original)"), the core the Reactor themes switch to;
  - **Singularity** (the default `corestyle`: black hole with a white-violet accretion ring, see `old_jarvis_ui/ref/ref_main_eclipse_singularity.jpg`);
  - Crystal, Tesseract, Plasma Storm, Neural Bloom, and "Surprise me".
- **`hud2.js`** adds:
  - `#hudbg`: an aurora, a grid floor, grain and a vignette, with parallax;
  - `#hudframe`;
  - **`#hudorb`**, the ticked ring around the core: curved "CPU nn% · RAM nn%" text, the clock "14:18:40 · STANDBY", a tick arc gauge, a dotted ring and vertical "JARVIS // CORE" text.
- **Legacy 2D orb** (`index.html`; shown when WebGL fails): an SVG with 4 dashed rings spinning at 24s / 16s reverse / 40s, plus a radial-gradient core that pulses every 3s.
- **Core states** (classes on `#orb`, shared by every layer):
  - `listening`: the core turns red (`--bad`) and pulses every 0.8s; the projector rings turn red and spin faster;
  - `thinking`: the rings spin at 3s/2s and the core at 1s;
  - `speaking`: the core pulses every 0.5s;
  - `window.__level` (mic/voice level) drives the nucleus and the floor.

### Animations and effects (all gated by the effects level `html[data-fx=ultra|high|low|off]`; phones default to `high`)
- **Boot screen** `#boot`: full screen with "J.A.R.V.I.S." in 26px at .6em spacing with a glow, a typing boot log, then a 0.8s fade (`hud2boot.js`, `.hb-reactor`).
- **Phone 3D layer** `p3d.js/.css` (10-17):
  - panels lean back as they scroll in and sink as they leave;
  - press tilt with a glare under the finger;
  - a one-time **scan sweep** per panel;
  - holographic rings under the core;
  - the floating glass command bar with a spinning edge, and keys that press in;
  - the raised glowing title, tap ripples (plus a buzz on Android), and a 3D fly-in when switching Modules tabs;
  - switches in ⋯: **3D on/off** and **Tilt** (motion, which asks iOS for permission).
- **Desktop-only extras:**
  - `m3d.js`: 3D P&L landscape, market planets, card tilt and holo rows, tab warp, count-up numbers, glowing sparklines;
  - `pc3d.js`;
  - `cursor.js` (cursor trail);
  - `amb3d.js` (ambient 3D).
- **Sounds:** `sfx.js` UI sound effects (setting `sound: false` by default, volume .5).
- **Ambient mode:** 30fps after 8s unfocused or 90s untouched, and 20fps after 15 minutes.
- **`rm.js`** makes Jarvis ignore the OS "reduce motion" setting, so 3D stays on. The owner's PC has reduce motion ON.
- **Owner rule (10-18):** on phones, scrolling or moving the phone must not move the ring or core. Everything scrolls with the page; there is no idle sway and no gyro unless Tilt is on.

### App icon
- **10-17 onward:** the "Gimbal Reactor" in violet: a plasma core with lightning arcing to 3 machined chrome gimbal rings, a glass shell, a swirling particle disk and a holographic projector dial on a mirror floor. Per-theme sets are `static/icons/reactor-{violet,stark,ice,emerald}-{64,180,…}.png` with matching manifests. See `old_jarvis_ui/ref/ref_icon_reactor_violet_final.jpg` and the full contact sheet `old_jarvis_ui/ref/ref_icon_sheet_all_colours.jpg`.
- **Before that:** a black-hole dial reading "J.A.R.V.I.S · CORE ONLINE" with an orange/cyan HUD ring and an equaliser. See `old_jarvis_ui/ref/ref_icon_old_blackhole.png`.
- **Runner-up designs** the owner saw: Iris Lens (his old ring icon rebuilt in 3D), Chrome J, and Quantum Crystal.
- **The exact Three.js scene that rendered the violet reactor** has been rebuilt as `old_jarvis_ui/reactor_r3d2.html`: three@0.160.0, bloom, a mirror floor, lightning, chrome gimbal rings and a projector dial. It renders correctly; see `old_jarvis_ui/shot_reactor_reactor_violet.png`. **This is the quickest way to give the phone Jarvis the same reactor centrepiece:** animate this scene, recolour it per theme with its `PAL` table (violet / stark / ice / emerald / …), and drive it from the core states.

---

## b. Every FEATURE

Legend:
- **[PHONE OK]**: runs in a phone browser from public or local data.
- **[NEEDS OWNER KEY: x]**: the owner types the key for service x on the phone.
- **[PC ONLY]**: cannot run on a phone, with the reason given.

### Main screen and shell
- [PHONE OK] Boot screen, header, status dot, J.A.R.V.I.S. title, clock, toasts, What's new popup (shows once per release; reopen with "what's new"), and the connection-lost banner.
- [PHONE OK] Mode tabs Chat / Code / Trade / Research: one brain with a different system prompt and tool set per mode. Answers need the LLM key below.
- [NEEDS OWNER KEY: Groq or Gemini] **Connect my brain** panel: a provider select (Groq / Gemini), "Paste key" and Save. The links point to console.groq.com/keys and aistudio.google.com/apikey.
- [NEEDS OWNER KEY: Groq or Gemini] **Chat** ("Ask Jarvis anything…"). Replies stream. **Smart depth** (`smart.py`, 10-18) sorts each message:
  - **quick:** greetings, commands, lookups;
  - **think:** real questions get more reasoning;
  - **deep / Expert Mode:** money, business, career, strategy, trading reviews, or "think hard". It uses maximum reasoning and the persona "self-made millionaire operator who also knows the topic":
    - it opens with one recommendation and real numbers;
    - it gives a 3–5 step plan and a do-today action;
    - it names the biggest risk and how to cap it;
    - it checks its own math, gets the owner's real numbers through tools, treats any trading edge as unproven, never promises returns, and uses no markdown symbols.
  - **By voice:** short answers.
- [PHONE OK] **Voice in**: tap the mic once to talk (auto-stop); **HANDS-FREE** keeps listening; **hold** for push-to-talk; HOLD-TO-TALK: AUTO setting. The old engine was Groq Whisper (`whisper-large-v3-turbo`). On the phone, either use the browser's SpeechRecognition, or [NEEDS OWNER KEY: Groq] for Whisper.
- [PHONE OK] **Voice out:** the phone's `speechSynthesis` (this was already the fallback). The original Edge neural voice (`en-US-AvaNeural`, +6% rate, +10Hz pitch) needs a server; [NEEDS OWNER KEY: Gemini] for Gemini TTS. **VOICE ⚙** opens the voice settings (voice, rate, pitch) and the Voice Doctor self-test.
- [PC ONLY] **Wake word "Jarvis"** (WAKE WORD: ON) and the **double-clap on/off** (`jarvis_clap.py`). They need an always-on mic process, which iOS Safari does not allow in the background. On the phone, hands-free while the page is open is the substitute.
- [PHONE OK] **KILL**: stop talking, listening and running actions now.
- [PHONE OK] **Awaiting approval**: every outward or risky action queues here for an Allow tap. Voice can never approve (a rule in `commands.js`).
- [PHONE OK] **To-do**: add a task with a date/time, minutes and priority, or say "add finish the report by 5pm, takes an hour". Quick capture (Alt+N) saves into it.
- [PHONE OK] **Command palette**: Ctrl+K or the round search button. It jumps to any module, runs any voice command, asks Jarvis, changes the theme, or reopens something recent.
- [PHONE OK] **Good morning briefing** card (say "good morning"): yesterday's and this week's Kalshi P&L, open positions, to-dos, 24h alerts, PC/cloud health and crew flags. It is cached and read aloud. The Kalshi parts need the Kalshi data.
- [PHONE OK] **Add-ons:**
  - Verse of the day (KJV);
  - Quote of the day (zenquotes.io in the old app; on a phone, bundle the quotes or publish them, because CORS is uncertain);
  - BTC / ETH / SOL price with 24h % (public crypto APIs).
- [PHONE OK] **Forex Factory · USD** calendar: High/Medium events, ET times, forecast and previous. Use a published JSON on the phone, because the FF feed has no CORS.
- [PC ONLY] **System core gauges** (CPU / RAM / DISK / POWER) and the core's curved CPU/RAM text. These are real PC stats. On the phone, show cloud/bot health instead, or hide them.
- [NEEDS OWNER KEY: Kalshi key ID + private key] **KALSHI TODAY** box and the **Kalshi page** (full-screen `#kpage`): read-only balance, P&L, positions, heat-maps, replay and what-if. Caveat: Kalshi's API signs requests with RSA-PSS or Ed25519 and probably blocks browser CORS. Prefer data published by the cloud monitor; a browser key is risky.
- [PHONE OK] **FUTURES** page: the NQ bot data (published nq-dashboard JSON).
- [NEEDS OWNER KEY: Meta/Instagram Graph token] **INSTAGRAM** page: insights for @zlarior (never connected), IG replies, the IG wizard and the IG dashboard.
- [PHONE OK] **⋯ More menu:**
  - CORE: the 3D core picker;
  - FULL SCREEN;
  - ⚙ LOOK: appearance;
  - AI KEY;
  - THEME;
  - 3D ON/OFF;
  - TILT;
  - ALERTS.
  LOOK AT MY SCREEN is [PC ONLY]: it screenshots the PC. On the phone it could become "look at this photo" [NEEDS OWNER KEY: Gemini vision].
- [PHONE OK] **Hide balance** switch: hides all $ figures.

### Look and appearance
- [PHONE OK] **24 themes** and the theme picker. The **Reactor** section has 4 cards, each previewed with its real icon, and the switch "Also switch the app icon and the 3D core" (on by default; `localStorage.jthemematch`).
- [PHONE OK] **Custom theme**: ACCENT HUE (rainbow slider, e.g. 195°), SATURATION (85%), BACKDROP (25%), 5 swatches, hex readout, USE CUSTOM, and SURPRISE ME. See `old_jarvis_ui/ref/ref_theme_picker.jpg`.
- [PHONE OK] **6 3D core designs**, plus Next / Prev / Random / Surprise me (voice and palette too).
- [PHONE OK] Effects level ultra/high/low/off, particles, glow, motion, scan, grain, cursor trail, sounds and volume, compact mode, font (Orbitron), 3D scene quality auto/ultra/high/low, 3D inner pages (desktop), and a 3D core on/off.
- [PHONE OK] **App icon follows the theme.** iPhone only picks up a new icon when Jarvis is removed and re-added to the Home Screen.

### Modules overlay (MODULES button). Tab keys from DEV_GUIDE.md, grouped by the CATS groups in `modgroups.js`
**Overview / daily**
- [PHONE OK] home (launcher tiles), today, brief / brief2 (briefings), calendar view, focus (focus timer "focus2"), habits, goals, study, bible, notes, about, and appearance.
- [PHONE OK] **mission**: Mission Control, one live screen with system health, an account-value sparkline, all crew statuses and next duties, recent alerts and to-dos (say "mission control"). The health part is cloud/PC data.

**Trading & money** (Jarvis is read-only and can never trade; tests enforce it)
- [PHONE OK] trades, money, futures, markets, fmarkets, crypto, liquidity (NQ/ES session levels, "liquidity sweeps"), playbook, corr (correlations), days, journal (Kalshi journal and trade screenshots `shots.js`), from published data.
- [PHONE OK] Money Lab: edge finder, paper forward tester, mispricing radar, risk cockpit and bot attribution. It is read-only/paper; the "hourly 90–93c" rule is on paper test. It needs the Kalshi trade history. Its quote collector ran on the cloud, which is [PC ONLY] as a background job.
- [PHONE OK] Edge Lab, and Signal/Outcome log (`siglog`). The data was synced every minute from the bot VM, Discord and the journal by the server, so on the phone this needs published data.
- [PC ONLY] **Bot Ops**: SSH to the trading VM through a restricted `jarvis-ro` login and a command whitelist. This needs SSH and a server.

**Work / business ("Work OS", `bizos*`)**
- [PHONE OK] tasks, OKRs/goals, clients/CRM and deals, finance/invoices, routines, reviews and staff.
- [PHONE OK] Automations, approval-only.

**Life**
- [PHONE OK] **My Calendar** (own calendar). Its subscribable ICS feed needs a server.
- [PHONE OK] Life lists and trackers.
- [PHONE OK] Documents, for uploaded documents. [PC ONLY] for PC files.
- [NEEDS OWNER KEY: secret ICS URLs] **Agenda** merges Google, Outlook and iCloud with My Calendar. CORS on those feeds makes this effectively [PC ONLY], or it needs a publisher.

**Brain**
- [NEEDS OWNER KEY: LLM] **Crew of 15 specialist agents**, with a scrolling side rail on the main screen. Each has a status, duties, and Chat / Details / Power off buttons. Tests pin exactly 15:
  - **core 8:** NOVA, ORION, HELIX, ATLAS, MUSE, SENTINEL, ECHO, FORGE;
  - **read-only trading desk:** VEGA (Kalshi markets), ARGUS (bot ops), MERIDIAN (NQ/ES/gold/silver session levels), CIPHER (crypto), MENTOR (risk/journal coach), VECTOR (backtests), HERALD (Discord/notifications).
- [PHONE OK] agents, plus memory (Jarvis remembers what you tell it), plans (multi-step plans with approvals), proactive nudges and a "needs list" ("what can't you do"). The brain parts need the LLM key.
- [PHONE OK] **Research team**: Quick (~1 min), Standard (~3 min) or Deep (6–10 min). An agent board shows planner, scouts, analysts, verifier and writer live. Scouts: Wikipedia, OpenAlex, Crossref, HackerNews, CoinGecko, DuckDuckGo, Bing News, YouTube, SEC EDGAR. Results are written as notes to the Obsidian vault and as **Word reports** ("Make Word doc", Download, Rebuild). On a phone: [NEEDS OWNER KEY: LLM], and the CORS-friendly sources only.
- [PHONE OK] knowledge; Test Drive (Jarvis tests itself on you; invitation under System → Test Drive).
- [PC ONLY] Evals/Quality (Python test harness, routing eval 99.4%).

**Social / growth**
- [NEEDS OWNER KEY: Instagram token + LLM] Growth: weekly IG content plan, hook A/B tests, funnel from views to leads to paid, sponsor drafts. It only drafts and never posts.
- [PC ONLY] reels and reels_dash (video building with ffmpeg and edge-tts).
- [PC ONLY] **Discord feed** ("trades" channel, wizard): a bot token, and Discord blocks browser CORS.

**Mail / people**
- [PC ONLY] **Mail** clean-up (Gmail app passwords over IMAP; approval-only). IMAP is not possible from a browser.
- [PHONE OK] **People & Calls**: contact book.
- [PC ONLY] Real approval-only calls via Twilio (keys never set). The secret cannot sit in a browser.

**System**
- [PC ONLY] notify / Notification Studio / Alerts (Web Push needs a server with VAPID keys). The owner's final rule (10-17): **phone pushes only for Kalshi outcomes**, in the "🌌 +$1.26" style with day totals. No signal-fill pushes and no bot-restart alerts. The daily-loss-limit and big-loss warnings stay on.
- [PC ONLY] pchealth, doctor (`doctor_ui`), backup, cloud, phone (pairing), plugins, devlog, vault / vaultmap / obsidian / obsidianstyle (Obsidian vault on the PC), screenhelp, and browser (drives the PC's browser).
- [PHONE OK] voiceset and voicedoc (Voice Doctor).
- [PC ONLY] PC bridge: open apps on the PC and read PC files. These answer "PC offline" when the PC is off.

### Voice commands (instant, no AI round-trip; `commands.js`, `voicecmds.js`, `lifecmds.js`, `mailcmds.js`, `mycalcmds.js`, `callcmds.js`, `workcmds.js`)
Examples seen: "open liquidity", "hide my balance", "good morning", "mission control", "what's new", "open tradingview", "remind me in 20 minutes to call mom", "add buy milk to my todo", "what time is it", "what's the weather tomorrow", and "add finish the report by 5pm, takes an hour". There are also theme and core changes by voice; "switch to Reactor Stark" was **not** wired, because the voice theme list is protected. Voice can never approve an action.

---

## c. The owner's requests and complaints over time (his own words)
- **10-06 to 10-12** (session A's early part was not reached). From A's memory note: he "sends big overnight task lists and wants a morning breakdown" (`MORNING_REPORT.md`). He wanted Jarvis to be "my own assistant in anything": business, life and trading monitoring, voice, phone-first, working with the PC OFF, and eventually helping make money ("honestly: no promises").
- **10-12** "Log in the server": he wanted to work from the cloud with the PC off.
- **10-13** "Is this running clause usage even when I'm not talking to it?" (No. Jarvis runs on the free Groq/Gemini pool.)
- **10-16**
  - "Make sure that jarvis can run when my pc is off. I dont think it can at the moment"
  - "Theres not a straughgt button for them to be on o nmyphone" (no visible notifications switch). A main-screen banner was added: Turn on / ×, and the iPhone "Add to Home Screen" steps.
  - "Give me how to do the kalshi one, then figure out and make sure my phone will work with jarvis when my pc is off"
  - "Make sure the background jarvis chat when my pc is off knows exactly what you are doing and can do it there if i turn my pc off"
  - "Instagram is fine right now but eveyrhting else good". Voice on the cloud was broken (Edge 403) and was fixed.
- **10-17** (the look day, session B)
  - "Make the notifcations for jarvis.. for kalshi appear only for outcomes not when a signal fills. Like outcome + or - however much make it cool"
  - **"I want the Jarvis app on my phone to look sick. 3d enhanced UI everything I want it very high tech make that."** This led to the phone 3D layer `p3d`.
  - "I'm talking about the app logo not that actual thing"
  - **"Change it up, 3D, UI, make it sick like futuristic sick. Take your time on this I want it good. Give me a few color and design designs."**
  - "And don't give me notifications everytime the trade res restart I just want Kalshi ourcones"
  - **"I like both and keep the color for sure. Make them both way more enchanted like I want it looking insane . Take your time"** (both = Gimbal Reactor and Iris Lens)
  - **"I want the violet reactor, then in themes have a setting to change everything for this"**. This led to the Reactor themes and the icon/core switch.
  - "Perfect all good, thanks" / "Commit it" / "is it on now?"
  - His saved preference (memory note `visual-style-preference.md`): wants visuals to look "insane", futuristic 3D, "make it sick"; keep violet; **flat or subtle designs were rejected**; real 3D renders (chrome, glass, glow, particles); show options on a phone-viewable preview page.
- **10-18**
  - "Jarvis is off when my computer is off. Fix it now" / "Nevermind". The home-screen icon pointed at the PC copy; the fix was to re-add it from the cloud address.
  - **"Whenever I scroll or move on my phone the ring moves I want you to look into this and fix it. Now."** Fixed: the HUD ring, core and projector rings scroll with the page; no gyro unless Tilt; no idle camera sway on phones.
  - "Good it works. Now implement smartness and make it smart, whatever that means just make it think harder like a millionare and an expert.No errors". This led to `smart.py`.
  - "Make it like my personal assistant keep adding stuff it may need in the future and now". This led to Research Word reports, the YouTube scout, and the needs list.
- **What he loved:**
  - the violet colour;
  - the reactor/gimbal 3D look;
  - real 3D renders;
  - "Perfect all good";
  - the scroll fix ("Good it works").
- **What he disliked:**
  - things that move on their own when he scrolls or tilts;
  - flat designs;
  - notification spam (signal fills, bot restarts, generic alerts);
  - having to do busywork himself;
  - Jarvis dying when the PC is off.

---

## d. Architecture

### PC (Windows, "desktop-tf4ue", 8 GB RAM)
- **Folder** `C:\Users\<you>\OneDrive\Desktop\Jarvis\` (about 456 files deployed, 8.5 MB). Docs: `CLAUDE.md`, `DEV_GUIDE.md`, `HANDOFF.md`, `CREW.md`, `MORNING_REPORT.md`, `PC_TUNING.md`, `docs/FEATURES.md`, `docs/README.md`, `docs/TOOL_SAFETY.md`, `docs/EVALS.md`, `docs/CALLS.md`, `docs/BUSINESS_OS.md`, `docs/MYCAL_DESIGN.md`.
- **Server:**
  - Python 3.12 FastAPI `server.py`, run as `python -m uvicorn server:app --host 127.0.0.1 --port 8765`, started hidden by `jarvis-background.vbs` (`start.ps1` is the interactive launcher);
  - `Start/Stop/Restart Jarvis.bat` and `Open Jarvis.bat`;
  - shortcuts "Jarvis Double-Clap (on-off)", "Jarvis Listener (on-off)", "Jarvis Mic Check" and "Jarvis Voice Test";
  - `jarvis_clap.py` (PC only).
- **State:** `jarvis.db` (SQLite), `replay_cache.db`, `profile.md`, `todos.json`, `shortcuts.json`, `data/`, `plugins/`, `backups/`, `.env`.
- **Modules:**
  - `api_*.py` routers, about 70 (agenda, agents, assistant, backup, bible, bizos*, botops, brief2, browser, calls, chatlog, cloud, contacts, crew, dev, discord*, docs, edge, evals, extra, focus, futures, growth, igdash, igreplies, instagram, journal2, kdata, knowledge, kreplay, kscanner, kwhatif, life, liquidity, lists, markets2, memory, moneylab, mycal, notify, obsidian, pc, pchealth, planner, playbook, proactive, push, reels, screen, shots, siglog, stt, testdrive, todos, vault, voice, research_docx…);
  - plus `brain.py` (LLM + `TOOL_GROUPS`), `llm_pool`, `smart.py`, `tools_*.py`, `tools_extra.py`, `notify_kinds.py`, `crew*.py`, `memory_core.py`, `planner.py`, `proactive.py`, `injection_guard.py` and `assistant_ext.py`.
- **Front end:** `static/`, 164 files (4 MB), vanilla JS with no build step. `index.html` is 632 lines: head, inline style, links, body markup, ~300 lines of inline global helpers, then about 110 plain `<script src="/static/x.js">` tags in a fixed order.
  - Tabs: `TABFN.<key>` in each tab file, grouped in `modgroups.js` CATS, with home tiles in `ui3.js` TILES.
  - Full-screen pages use the `#kpage` pattern.
  - New tabs inject their own `<style>`.
  - `widget.html` is the phone widget; `manifest.json` and `sw.js` make it a PWA with push.
- **Global JS objects:**
  - `JSET` (settings), `JFX` (effects level), `JSCENE`, `JCORE`, `JCS` (core styles), `JORB` (orb styles), `M3D`, `JTOAST`, `JNUM`;
  - `TABS`, `TABFN`, `openKalshiPage()`, `openMods`, `setTheme` / `setThemeInstant`.
- **localStorage keys:** `jtheme`, `jtoken`, `jcorestyle`, `jthemematch`, `jp3dtilt`, `jp3dtiltv`, `jm3d`, `jm3dset`, `jambient`, `jnfbanner_off`, `jpush_on`, `ov_wn_seen`.

### Cloud (Oracle Always Free, Ubuntu 24.04 aarch64, 2 OCPU / 12 GB)
- **Access:** Tailscale-only HTTPS at `https://jarvis-cloud.tailc45470.ts.net`; public SSH is closed.
- **Layout:** releases in `/opt/jarvis/releases/<id>` (3 kept), the `current` symlink, venv `/opt/jarvis/venv`, state in `/var/lib/jarvis` (linked into each release), config `/etc/jarvis/jarvis.env`, systemd unit `jarvis` (user `jarvis`) on port 8765.
- **Timers:** backup at 03:40, health check every 5 minutes.
- **Deploy:** `cloud/deploy.py` from the PC or `cloud/local_deploy.py` on the server. Both do a secret check, an atomic switch, `/healthz`, and auto-rollback. `cloud/bootstrap.sh` sets up the server.
- **Dev copy:** `~/jarvis-dev`, worked on by Claude Remote Control sessions (environment `jarvis-dev`; session B was one of these).
- **Bot VM** `kalshi`, separate, with 9 kalshi-* services. It is read-only for Jarvis.
- **Phone sign-in:** an 8-digit one-time code, after which the page keeps `jtoken`. API calls send an `X-Token` header.

### Endpoints seen
`/healthz`, `/api/speak`, `/api/voice/status`, `POST /api/voice/selftest {"probe":true}`, `/api/stt`, `/api/kalshi`, `/api/kalshi/report`, `/api/crypto_dash`, `/api/futures_markets`, `/api/futures/ingest`, `/api/whatsnew`, `/api/obsidian/status`, `/api/research/{job}`, `/api/wordreports`, push subscribe/test (`api_push.py`), and the token endpoint used at boot.

### Voice
- **STT:** Groq Whisper `whisper-large-v3-turbo` (and `whisper-large-v3`).
- **TTS:** edge-tts (Microsoft Edge neural), default voice `en-US-AvaNeural`, rate `+6%`, pitch `+10Hz`; it needs `edge-tts>=7.3.1` after Microsoft's 10-16 token change.
- **Cloud fallback chain:** Edge, then Gemini TTS (`gemini-3.8-flash-lite-tts`, `gemini-3.8-flash-tts`, `gemini-2.5-flash-preview-tts`; 12 s budget), then Kokoro, then Piper `en_US-amy-medium`, then 503.
- **Client fallback** (`voicebrowser.js`, `voicefix.js`): the browser's `speechSynthesis` speaks the whole reply, or only a failed chunk.
- Gemini TTS ignores rate and pitch and hit a 429 after about 35 requests in 15 minutes.

### LLM
- `llm_pool` with `JARVIS_PROVIDER=groq`.
- **Groq:** `openai/gpt-oss-120b` (top), `openai/gpt-oss-20b`, `qwen/qwen3-*`.
- **Gemini:** `gemini-3.5-flash`, `gemini-3.5-flash-lite`.
- **No Anthropic key** (a `_ask_anthropic` path exists but was unused).
- Cool-downs for rate-limited models; the reasoning effort is set per request by `smart.py`.

### Env var / key NAMES (never values)
- **Jarvis settings:** `JARVIS_TOKEN`, `JARVIS_HOME`, `JARVIS_PROVIDER`, `JARVIS_MODEL`, `JARVIS_MODE`, `JARVIS_SMART`, `JARVIS_DATA`, `JARVIS_STATE_DIR`, `JARVIS_PORT`, `JARVIS_CLOUD`, `JARVIS_VOICES`, `JARVIS_GEMINI_MODELS`, `JARVIS_TTS_GEMINI`, `JARVIS_DOCS`, `JARVIS_BIZOS_BG`, `JARVIS_BASE_URL`.
- **LLM:** `GROQ_API_KEY`, `GROQ_MODELS`, `GROQ_REQUEST_CAP`, `GEMINI_API_KEY`, and `ANTHROPIC_API_KEY` (unused).
- **Kalshi:** `KALSHI_KEY_ID`, `KALSHI_KEY_PATH` / `KALSHI_PEM` (the key file is `/etc/jarvis/kalshi_key.pem` on the cloud), `KALSHI_ADVICE`.
- **Other services:** `DISCORD_BOT_TOKEN`, `OBSIDIAN_VAULT`, `BOT_LOG_DIR`, `MONEYLAB_PAPER`, `MONEYLAB_NO_BG`, `MONEYLAB_INTERVAL`, `PC_BRIDGE`, `CLOUD_DIR`.
- **Never set, names not seen:** Twilio keys, Gmail app password(s), the Instagram/Meta token (Meta app id in HANDOFF), and the Web Push VAPID keys.

### Safety rules the old app enforced (keep them)
- Read-only on Kalshi and the trading bots; no tool can trade.
- Outward actions (email, message, call, post, pay, publish, delete) need an Allow tap, and voice can never approve.
- Secrets live only in the env file and are never logged.
- The file reader refuses `.env`, keys and databases.
- A prompt-injection guard runs after reading outside content.
