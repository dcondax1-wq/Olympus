# OLYMPUS sound API (2026-11-11)

One engine for every sound in OLYMPUS: `tools/web_public/olympus/sfx.js` (`window.OLYMPUS_SFX`, a classic ES5 script).
Two layers (2026-11-11 evening): **real CC0 recordings** (harp, wood, paper, bells, coins, steps, anvil, doors, sea, wind, fire, crowds, birds,
crickets; `tools/web_public/assets/audio/`, licences in `docs/ASSETS_LICENSES.md`) layered with **sound made in code** (WebAudio). The synth is
always there: when a recording is not loaded yet, failed, or the A/B switch says "synth", the made-in-code version plays exactly as before.
No imitation of any real game. Hear it all at `olympus/sfx-lab.html`. Older notes: `docs/OLYMPUS_SFX.md` (still true; this page adds to it).

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

## Recorded layer (CC0 recordings, 2026-11-11)

**What is real now.** Taps: a soft VCSL woodblock under a high harp touch; tick: a tiny Kenney click; open / close / swipe: real paper (a map
opening, book pages) under the harp; toggle: a real small switch; success / level up: the harp + a real finger cymbal / hand chime; notify: a real
hand chime; money: real coins; error: a dull real wooden knock. The lyre of every cue and of the music is a **real folk harp** (VCSL, 19 notes
D3..D6, retuned at most 3 semitones; measured in tune within 8 cents). World: steps on stone / sand / wood / leaves (7 / 6 / 3 / 2 takes), a real
anvil (6 takes) **plus a synthesised ring tail**, pen on paper, a map unfolding, coins, crates, doors, a fire whoosh, crowd cheers; new names `page`,
`chime` ({midi}), `drum` (frame drum), `jingle` ({kind}); aliases `step-leaves`, `jingle-keys`, `jingle-coins`, `keys`, `rustle`, `book`.
Still synth only: `thunder`, `groan`, the wind of `portal`, `pad`.
Beds keep their generative layers and gain real loops: marble (a far crowd murmur through the hall), agora (crowd + birds over the roofs),
workshop (fire), desert (wind + gusts, real camel bells), harbour (sea, real breaking waves, gulls), night (crickets), colosseum (a crowd that swells
into real applause, frame drums), grove (birdsong + a brook, leaves, single birds), temple (wind, wind chimes, hand chimes); library and treasury
use real events (pages, pen, map, coins counted and poured) over the synth hush.

**How it plays.** One-shots of a family share one file (a sprite: one request, one decode). `sp()` picks a take that is never the one before
(round robin), with a little pitch (+/- 0.5..2 semitones) and level (up to -30 %) jitter, so nothing repeats; `at()` places it in 3D as before.
A bed loop runs through a crossfading looper: each pass plays 45..80 % of the file from a random place, 2 s equal-power crossfades, +/- 1.5 %
speed, so the bed never repeats exactly and the file's seam never matters. A loop fades in over 2.5 s when it arrives and the synth texture steps
back (to 35..80 %); events stay generative. Everything stays on the ambience bus: ducking under voices, mute, Quiet and the sliders apply.

**Loading.** Nothing is fetched before the first tap. The tap loads `ui` (148 kB) and `harp` (127 kB; not in LITE). A place loads its own files
when it starts (`BED_FILES` in sfx.js; at most about 600 kB in one format); music loads `harp-lo`. Format: Ogg Opus where the browser says it plays
it ("probably"), else AAC `.m4a` (every iPhone); a file that fails tries the other format, then the synth plays for the session. LITE and Data
Saver skip the bed loops (the synth beds stay). Decoded loops are big (20 s of stereo floats): only the four latest stay decoded. Offline: the files
are same-origin GETs, so the site's service worker (sw.js, its generic cache branch) keeps them after the first visit; no sw.js change needed.

**API (added; nothing removed):**

| call | does |
|---|---|
| `samples()` / `samples(false)` | the layer's state `{on, use, fmt, base, loaded, failed, pending, played, kb, files}` / synth only (stored `sm`; `samples(on, false)` is not stored: the lab's A/B) |
| `preload(['ui', 'loop-sea'])`, `preload('harbour')`, `preload('all')` | a promise: those files (or a place's files) are ready (true) or some failed (false) |
| `play(name, {synth: true})` | the made-in-code version only (A/B) |
| `sample(bank, {gain, rate, i})` | one take of a recorded family on its own (`banks` lists them; `audio` is the manifest) |
| `meter()` | the output level now, `{rms, peak}` in dBFS |
| `murmur(profile, timeline, {at0})` | the formant murmur (below) |
| `presenceOf(person)`, `presence(person, pos, listener?)`, `walker(person).step(pos, listener?, {surface})` | a person's presence (below) |

Files: `tools/web_public/assets/audio/<stem>.ogg` + `.m4a` and `manifest.json` (banks, loops, measurements); the same manifest (without the
measurements) is written into sfx.js between `/*AUDIO*/ ... /*/AUDIO*/`. Rebuild: `python tools/audio_build.py --fetch --src <dir>` (downloads the
25 CC0 sources), `python tools/audio_build.py --src <dir>` (build + measure + licence rows), `python tools/audio_build.py --measure` (re-measure only).

### Measured (every file decoded again with ffmpeg after encoding; `python tools/audio_build.py --measure`)

Processing: trim to the hit (onset - 5 ms), high-pass 30 Hz (160 Hz for the open-field gusts: mic wind rumble), short fades; takes of a family at
the family's median loudness (loudest 50 ms, +/- 6 dB at most); harp notes at an equal attack level; beds: the window whose two ends sound most
alike, its tail folded into its head (1.2 s equal-power crossfade), -16 LUFS (BS.1770 gated), a 5 ms look-ahead limiter; then each file is lowered
until its *decoded* peak is <= -3 dBFS in both formats (the codecs overshoot on sharp clicks). Loop seam: "jump" = the sample step across the seam
divided by the file's own 99.9th-percentile step (below 1 = no click), "level" = RMS of 20 ms before vs after the seam. Sprite LUFS include the gaps
between takes (a level reference only).

| file | ch | ogg kB | m4a kB | length s | peak dBFS (ogg / m4a) | LUFS | centroid Hz | roll-off 85 % Hz | loop seam (jump / level dB) |
|---|---|---|---|---|---|---|---|---|---|
| ui | 1 | 147.6 | 148.5 | 23.41 | -3.8 / -3.2 | -25.9 | 2294 | 3164 | - |
| harp | 1 | 126.8 | 150.8 | 23.98 | -3.2 / -3.2 | -23.6 | 704 | 1031 | - |
| harp-lo | 1 | 78.2 | 103.1 | 16.44 | -3.4 / -3.5 | -19.9 | 265 | 328 | - |
| steps | 1 | 32.3 | 53.0 | 7.67 | -3.1 / -3.8 | -27.4 | 1871 | 4254 | - |
| forge | 1 | 39.6 | 51.2 | 7.50 | -3.3 / -3.6 | -21.2 | 4075 | 6984 | - |
| scribe | 1 | 22.2 | 39.5 | 6.02 | -4.8 / -3.0 | -26.5 | 5639 | 11344 | - |
| house | 1 | 26.9 | 50.3 | 7.11 | -3.2 / -3.4 | -25.0 | 1338 | 2684 | - |
| gear | 1 | 52.3 | 83.7 | 11.82 | -3.3 / -4.1 | -25.7 | 6373 | 12527 | - |
| coins | 1 | 28.1 | 39.9 | 6.08 | -3.5 / -3.6 | -29.6 | 5327 | 10734 | - |
| nature | 1 | 63.0 | 110.2 | 17.43 | -3.3 / -3.8 | -21.2 | 2302 | 4465 | - |
| arena | 1 | 40.7 | 73.3 | 11.12 | -3.3 / -3.0 | -23.3 | 939 | 1898 | - |
| bells | 1 | 83.3 | 96.7 | 15.42 | -3.7 / -3.6 | -17.8 | 7630 | 10348 | - |
| loop-crowd | 2 | 117.1 | 181.8 | 20.00 | -7.3 / -8.0 | -16.1 | 913 | 1230 | 0.894 / 2.2 (m4a 0.364 / 0.02) |
| loop-applause | 2 | 91.5 | 127.3 | 14.00 | -5.0 / -3.1 | -20.5 | 2138 | 2977 | 0.444 / 0.72 (m4a 0.332 / 0.65) |
| loop-fire | 2 | 106.1 | 164.5 | 18.00 | -7.4 / -6.6 | -24.1 | 242 | 164 | 0.144 / 0.13 (m4a 0.033 / 1.39) |
| loop-wind | 2 | 116.9 | 180.8 | 20.00 | -6.4 / -6.1 | -16.0 | 554 | 668 | 0.28 / 0.28 (m4a 1.39 / 0.04) |
| loop-gusts | 2 | 113.1 | 198.8 | 22.00 | -3.1 / -3.8 | -17.6 | 719 | 1090 | 0.885 / 0.21 (m4a 0.704 / 2.43) |
| loop-sea | 2 | 116.6 | 198.8 | 22.00 | -3.3 / -3.7 | -17.6 | 1004 | 1594 | 0.149 / 1.28 (m4a 0.141 / 0.06) |
| loop-crickets | 2 | 64.8 | 90.9 | 10.00 | -6.5 / -7.8 | -16.0 | 3922 | 4898 | 0.42 / 0.51 (m4a 0.519 / 0.84) |
| loop-birds | 2 | 116.4 | 199.0 | 22.00 | -4.2 / -3.5 | -18.6 | 966 | 1219 | 0.626 / 2.1 (m4a 0.68 / 0.65) |
| loop-brook | 2 | 61.7 | 108.9 | 12.00 | -5.3 / -4.3 | -18.1 | 1914 | 3141 | 0.164 / 0.78 (m4a 0.656 / 0.07) |

**Total 4.0 MB** on the shelf (Opus 1.65 MB + AAC 2.45 MB; budget 8 MB); a phone loads one format and only what a place needs. Notes: fire and
applause sit below -16 LUFS because their crackles / claps are the peaks the -3 dBFS ceiling holds; the .m4a files decode 4..20 ms longer than the
nominal length (AAC pads its last frame; the engine loops the nominal length). Levels against the synth (offline renders in Chromium, RMS
recorded / synth, 4 takes averaged): cues 0.5..1.35 (most 0.75..1.2), world sounds 0.75..1.5, beds 0.8..1.1 once their loops are in.
Harp tuning, measured on the decoded files: every note within 8 cents of its MIDI note.

## Voices and presence (2026-11-11)

- **Murmur.** `murmur(profile, timeline, {at0})`: a soft formant voice that follows the mouth timeline of people-voice.js (`visemes()`): a sawtooth
  + triangle "glottis" through two moving formant filters (F1 / F2 per vowel), breath noise that brightens on S / F, a sentence tune (starts a little
  high, drifts down, lifts on open vowels), behind a 3.2 kHz curtain, on the voices bus. people-voice.js now asks the engine first and keeps its own
  blips as the fallback. Returns `{stop()}`, or null before the first tap.
- **Presence.** `presenceOf(person)` -> `{jingle, surface}` from the accessory (hammer / helmet: armour, pouch: coin pouch, key: keys, scroll / owl /
  torch: cloth, laurel: leaves) or the kind (builder, bot: armour; scanner: pouch; keeper: keys; mind: cloth; champion: little bells; villager:
  beads). `presence(person, pos, listener)` plays it in 3D; `walker(person).step(pos, listener, {surface})` is a footstep on their surface and,
  about every third step, their things answering very softly. For scenes: call `walker(p).step(...)` where a foot touches the ground.

## Tests

- `python -m unittest tests.test_olympus_sfx tests.test_sfx_engine` (node, ~10 s): names and aliases, nothing before the tap, nodes released, caps,
  mute, 3D placement maths, rooms, all 24 beds, music, duck, Quiet, stored profile, the kit hooks, ES5 / only our own files.
- `python -m unittest tests.test_sfx_engine` also runs `SampleLayerTest` (node: nothing fetched before the tap, Opus first / AAC where Opus does
  not play, round robin never repeats a take, cues layered and released, a missing or undecodable file falls back to the synth with no error,
  `samples(false)` = synth only, murmur, presence, walker) and `AssetFilesTest` (both formats of every file, total <= 8 MB, each place's first load
  < 1 MB, decoded peaks <= -3 dBFS, loop seams, a CC0 licence row for every file, the manifest embedded in sfx.js, codecs by ffprobe).
- `flock -w 2400 /tmp/olympus_browser.lock python tests/test_sfx_lab.py [--shots]`: the lab in Chromium at 390x844, no AudioContext and no download
  before the tap, every sound rendered offline (synth, then with its recordings: audible, never clipping, the recordings used), every file decodes
  (Opus; this Chromium build has no AAC decoder, so the .m4a twins are checked by ffprobe), the assets folder missing (404) = the synth plays, the
  lab's A/B, families and meter, 44 px taps, no console error. Shots: `docs/shots/sound/`.
