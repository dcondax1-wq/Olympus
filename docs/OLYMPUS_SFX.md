# OLYMPUS sound + haptics (sfx.js)

1. Add `<script src="olympus/sfx.js"></script>` once per page (path relative to the page). It makes `window.OLYMPUS_SFX`.
2. Call `OLYMPUS_SFX.play('tick'|'tap'|'portal'|'thunder'|'rankup')` on UI events; `play('pad')` / `stop('pad')` for the ambient pad.
3. Nothing sounds until the user's first touch/click/key (browser rule); earlier `play()` calls just return false.
4. Add a mute button calling `OLYMPUS_SFX.mute()` and a slider calling `setVolume(0..1)`; both persist in localStorage `olympus.sfx`.
5. iPhone: sound follows the silent switch (never overridden); vibration is a no-op on iOS Safari; reduced-motion turns off haptics and the pad. Hear everything at `olympus/sfx-lab.html`.

## Ambience: a quiet sound bed per app (2026-11-04)

Eight synthesised beds (WebAudio, no files, one shared 2 s noise loop + filters + slow LFOs; sparse events on a timer): `wind` (temple wind),
`forge` (furnace roar + crackle), `sea`, `city` (distant hum), `forest` (leaves + a bird), `crowd` (far murmur that swells), `chimes` (wind chimes),
`space` (sub drones + hiss). Bus level 0.5 of the master, 2.5 s fade in, 0.8 s out.

`OLYMPUS_SFX.ambient('sea')` (this page wants that bed), `ambient('')` / `ambientStop()`, `ambience(true|false)` (the owner's switch, stored as
`a` in `olympus.sfx`, shared by every page; no argument = may a bed play now), `ambientState()` = `{ want, playing, allowed, setting, saver, names }`.

Rules (all enforced in `sfx.js`): nothing before the first touch (the gesture that unlocks the sounds); silent while muted; **off when battery saver is
on** (`OLYMPUS.saver()`) unless the owner turned ambience on explicitly; paused on a hidden tab; a switch made in Jarvis reaches framed apps through
the `storage` event.

**No per-app edit is needed.** The kit (`olympus/olympus.js`) holds the app -> bed table (`AMBIENT`) and starts the bed 0.4 s after load; it steps
aside while Jarvis talks or listens (`OLYMPUS_QUIET`, also read from the parent frame) and comes back. Table: datacity / cities / kalshicity / kalshi
`city`; oracle / mind / argus `space`; odeon / arena / forum / ares `crowd`; fates / plutus / chronos `chimes`; labyrinth / pantheon / athena / hermes /
nemesis / bridge `wind`; prometheus / hephaestus `forge`; tyche `sea`; tree `forest`. To change one app: edit its entry, or call (one guarded line in
the app's init) `window.OLYMPUS && OLYMPUS.ambient('forge');` / `OLYMPUS.ambient('')` for none. Jarvis: Settings -> **App ambience** (and **Battery saver**).

Test: `tests/test_olympus_sfx.py` (beds build and stop, gesture gate, mute, saver, owner override) and `tests.test_olympus_kit power` (live in Mind).
Worker note: `sfx.js` / `olympus.js` / `render.js` changed under the same `?v=` query; bump `sfx.js?v=s1` -> next in Jarvis `index.html`, `jarvis/sw.js` SHELL and
the kit's loader (`olympus.js` two places) together, and the apps' `olympus.js?v=` if they pin it.
