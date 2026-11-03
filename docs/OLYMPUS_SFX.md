# OLYMPUS sound + haptics (sfx.js)

1. Add `<script src="olympus/sfx.js"></script>` once per page (path relative to the page). It makes `window.OLYMPUS_SFX`.
2. Call `OLYMPUS_SFX.play('tick'|'tap'|'portal'|'thunder'|'rankup')` on UI events; `play('pad')` / `stop('pad')` for the ambient pad.
3. Nothing sounds until the user's first touch/click/key (browser rule); earlier `play()` calls just return false.
4. Add a mute button calling `OLYMPUS_SFX.mute()` and a slider calling `setVolume(0..1)`; both persist in localStorage `olympus.sfx`.
5. iPhone: sound follows the silent switch (never overridden); vibration is a no-op on iOS Safari; reduced-motion turns off haptics and the pad. Hear everything at `olympus/sfx-lab.html`.
