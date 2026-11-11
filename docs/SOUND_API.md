# OLYMPUS sound API (2026-11-11)

One engine for every sound in OLYMPUS: `tools/web_public/olympus/sfx.js` (`window.OLYMPUS_SFX`, a classic ES5 script).
Everything is synthesised in code (WebAudio): no files, no network, no imitation of any real game. Hear it all at
`olympus/sfx-lab.html`. Older notes: `docs/OLYMPUS_SFX.md` (still true; this page adds to it).

**Rules the engine enforces for you** (you never need to check them yourself):
- Nothing before the first tap: no AudioContext exists and every call returns `false`. The first `pointerdown / touchend / click / keydown`
  creates it (iOS Safari: resumed and unlocked inside that tap; a later tap resumes an interrupted one).
- `mute()` beats everything. The owner's **Sound** switch `sound(true | false | null)`: with no choice (null), cues, world sounds and beds are
  silent in LITE, reduced motion and battery saver. **Quiet** `quiet(true)`: everything softer, no music. **Music** is off by default.
- CPU: at most ui 6 / world 6 / ambience 8 / music 6 voices at once (half in LITE); every node is disconnected when its sound ends;
  sounds out of earshot (40 m) are not built; a hidden tab suspends the context.

## Call it from a page or a scene

```js
const S = window.OLYMPUS_SFX;                 // or OLYMPUS.sound.<hook> (sfx.js hangs the hooks on the kit's sound())
S && S.play('success');                       // a UI cue; returns true if it sounded
S && S.at('step', { x, y, z }, camera, { surface: 'sand' });   // a world sound placed in 3D
```

Always guard (`S && ...` or `try`): sfx.js may not be on the page. On pages with olympus.js, `OLYMPUS.cue(name)` and `OLYMPUS.sfx(name)` already work.

## UI cues: `play(name, opts?)` (alias `cue`)

All in the key of D, on a synthesised lyre (Karplus-Strong string) and small bronze bells, through the shared reverb.

| name | sound | use it for |
|---|---|---|
| `tap` | soft high pluck + wood touch | any tap (old name, follows mute only) |
| `tick` | tiny marble knock | list scroll, slider steps (old name) |
| `open` / `close` | harp rises A-D-F# / falls | a sheet or panel opens / closes |
| `swipe` (`{dir:'back'}`, alias `swipe-back`) | air moving past + a faint string | page swipe |
| `toggle` (`{on:false}`, alias `toggle-off`) | up a fifth / down, muted | a switch |
| `success` | D-A-D + crotale shimmer | it worked |
| `warning` | two warm falling notes | look at this |
| `error` | a muted low string | it did not work (never a buzzer) |
| `notify` (alias `notification`) | small bronze bell over a lyre note | a new message / alert |
| `money` (alias `money-in`) | coins land, lyre answers | money in, a win |
| `levelup` (alias `level-up`; old `rankup`) | lyre run + bell crown | level up, rank up |
| `portal` | wind through a doorway + harp run | an app opens (old name) |
| `thunder` | crack + long roll | storms (old name) |
| `pad` | warm drone, `stop('pad')` ends it | old name |

`opts.gain` (0..2) scales one sound. `data-oly-cue="success"` on any element plays it on click with no code.

## World sounds (characters, scenes)

Names: `step-stone`, `step-sand`, `step-wood` (or `step` / `footstep` + `{surface:'stone'|'sand'|'wood'}`), `hammer` (on anvil), `quill`,
`scroll` (unrolls), `coin`, `crate` (drop), `cheer`, `groan`, `door`, `fire` (whoosh). Aliases: `anvil`, `clink`, `drop`, `applause`, `sigh`, `gate`, `unroll`, `whoosh`.
Options: `k` (strength 0..1, default 1), `gain`.

- **Flat**: `S.world('hammer')` (same as `play`).
- **3D**: `S.at(name, {x,y,z}, listener?, opts?)`. `listener` may be `{x,y,z,yaw}` (yaw in radians, 0 = facing -z), a three.js
  camera / Object3D (`{position, rotation}`; its `rotation.y` is used as yaw) or `{x,y,z, forward:{x,z}}`. Omit it after `S.listener(L)`
  has set a default (call that once per frame or when the camera moves; it only stores the reference). Options: `ref` (full-volume
  distance, 2 m), `rolloff` (1.1), `max` (40 m: farther = skipped). Beyond 8 m the air softens the highs. The same sound at the same
  spot within 30 ms plays once, so a crowd of walkers is cheap.

Example (people3d.js, a walker's foot touching the ground):
```js
if (footDown && window.OLYMPUS_SFX) OLYMPUS_SFX.at('step', person.position, camera, { surface: ground, k: 0.6 });
```

## Places (ambience beds): `ambient(name)`

The kit (olympus.js) already starts each app's bed from its `AMBIENT` table; call `OLYMPUS.ambient('harbour')` only to override, `''` for none.
Each bed is several noise layers with random drift (it never repeats) plus random events, panned, through the bed's own reverb room.

| new bed | what you hear | room |
|---|---|---|
| `marble` | low room tone, moving air, far footsteps, a far bell | hall |
| `agora` | voice murmur in moving formants, chatter, a pottery clink, feet | courtyard |
| `workshop` | the fire and its crackle, hammer on anvil, the quench, the bellows | tent |
| `desert` | wind in gusts, a whistle over the dunes, camel bells passing | courtyard |
| `harbour` | waves that swell and break, lapping water, gulls, a rope creaks | courtyard |
| `night` | crickets that come and go, a far owl | courtyard |
| `library` | a hush, pages turning, a reed pen, a scroll unrolling | hall |
| `colosseum` | a big crowd that swells into cheers and claps, drums | courtyard |
| `grove` | leaves and birdsong, a far dove | courtyard |
| `temple` | wind through the columns, bronze chimes on the gusts | hall |
| `treasury` | a hush, coins counted, now and then a pour | tent |

**Old names keep working** (the AMBIENT table needs no change): `wind`->temple (few chimes), `chimes`->temple (more chimes), `forge`->workshop
(fewer hammers), `smithy`->workshop, `sea`->harbour, `city`->agora (far, muffled), `forest`->grove, `crowd`->colosseum, `space`->night (starry: one
cricket, a low drone, faint bells), `scroll`->library, `coins`->treasury, `agora`->agora, `lab`->marble (with a water clock), `breeze`->desert (no bells).
`bedOf(name)` tells which new bed an old name plays.

## Music: `music(true|false)`, `district(name)`

A calm generative lyre (motif + variations, rests, a soft drone; very quiet). Off by default; the owner's switch is stored (`mu`).
Districts: `trading` (D dorian), `money` (G pentatonic), `life` (F lydian), `research` (A aeolian). With no `district()` it follows the bed
(treasury/coins -> money, library/night/marble -> research, grove/harbour/desert -> life, else trading). `musicState()` = `{on, allowed, playing, district}`.

## Voices and ducking

- While a character or Jarvis speaks: `S.speaking(true)` at the start, `S.speaking(false)` at the end (alias `duck`; counted, so two speakers need
  two `false`s). Places drop to 30 %, music to 25 %, world sounds to 60 %; UI and voices stay. `window.OLYMPUS_QUIET()` (Jarvis talking or listening,
  this frame or the parent) ducks automatically while a bed or music plays.
- Your own synthesis (a voice, a creature): `S.onUnlock(() => { const ctx = S.context(), out = S.bus('voices'); /* build nodes, connect to out */ })`.
  `bus(cat)` returns the input of a category (`ui | ambience | voices | world | music`) so the owner's slider, mute, ducking and the shared reverb
  apply. Both return null before the first tap. Disconnect your nodes when done.
- Web Speech (TTS) cannot be routed through WebAudio: just call `speaking(true/false)` around it.

## Settings (all stored in localStorage `olympus.sfx`, shared by every app)

| call | stored | default |
|---|---|---|
| `setVolume(0..1)` / `volume(0..1)` | `v` | 0.35 |
| `mute(on?)` | `m` | false |
| `sound(true/false/null)`; `sound()` = may cues sound now; `sound('tap')` plays a cue (never flips the switch) | `s` | auto |
| `ambience(on)` | `a` | auto |
| `volume('ui'/'ambience'/'voices'/'world'/'music', 0..1)`, `volumes()` | `c` | 1 / 0.8 / 1 / 0.9 / 0.6 |
| `quiet(on)` | `q` | false |
| `music(on)` | `mu` | false |

`room('hall'|'courtyard'|'tent')` sets the shared reverb (beds set their own). `state()` adds `voices`, `nodes`, `released`, `room`, `quiet`, `ducked`,
`music`, `bed`, `reverb`, `volumes` to the old fields.

## Tests

- `python -m unittest tests.test_olympus_sfx tests.test_sfx_engine` (node, ~10 s): names and aliases, nothing before the tap, nodes released, caps,
  mute, 3D placement maths, rooms, all 24 beds, music, duck, Quiet, stored profile, the kit hooks, ES5 / no files.
- `flock -w 2400 /tmp/olympus_browser.lock python tests/test_sfx_lab.py [--shots]`: the lab in Chromium at 390x844, no AudioContext before the tap,
  every sound rendered offline (audible, never clipping), 44 px taps, no console error. Shots: `docs/shots/sound/`.
