# People of OLYMPUS: talk to any worker (owner 2026-11-11: "I should be able to see individual people and talk to them, chat with the agents / workers about what they are doing")

One shared kit so every 3D scene and page can show a PERSON and let the owner CHAT with them. A person is a character that speaks for one real worker (a build agent, a money scanner, a bot, the Mind, a city's keeper...). They only ever say what that worker's own data says; they never invent numbers and they cannot place trades.

## Files (owned by the "People" agent)
- `tools/web_public/olympus/people.js` (ES module, also sets `window.OLYMPUS_PEOPLE`), `people.css`, `people-data.js` (loaders), `people.json` (built by `tools/people_build.py`: the roster).
- App `tools/web_public/symposium/`: the hall where you meet everyone (roster, 1:1 chat, round table, daily stand-up).

## Roster entry (`people.json` -> `people[]`)
`{ id, name, title, kind: "builder"|"scanner"|"bot"|"mind"|"keeper"|"champion", area, app (app id to open), seed (number: face/voice), voice: {pitch, rate}, sources: [relative URLs it reads], home: {scene:"ergasterion"|"hellas"|"athens"|"colosseum", place:"<station/tent/polis id>"} }`
Ids are stable and predictable: `builder:<branch-short>`, `scanner:chrysos`, `bot:lit`, `mind`, `keeper:<polis-id>`, `villager:<app-id>`, `champion:<run-id>`.

## API (`window.OLYMPUS_PEOPLE`, all safe to call when data is missing)
- `ready(): Promise<void>`: roster loaded (falls back to a bundled fixture).
- `list(filter?) -> person[]`, `get(id) -> person|null`.
- `portrait(id, size) -> SVGElement`: a deterministic marble-bust avatar (no images).
- `facts(id): Promise<{status, doing, last:[{t,text}], learned:[{t,text,src}], blocked?:string, numbers:[{label,text}], asof, sample:boolean}>`: what this person can truthfully say right now.
- `ask(id, text, ctx?): Promise<{text, sources:[...], actions?:[{label, open}], followups:[...]}>`: offline answer in the person's voice from `facts`; if the owner connected his own model in Jarvis ("Connect my brain") open questions go there WITH the facts as context; otherwise a plain "I don't have that".
- `open(id, opts?)`: opens the chat sheet (portrait, status line, suggested questions, text box, mic if available, "Leave a request"). `opts.anchor` may be a DOM element.
- `standup(ids?) -> [{id, line}]`: one line per person ("Yesterday / today / blocked").
- `request(id, text)`: saves a note for that worker in localStorage `olympus.requests.v1` (id, text, time); `requests()` lists them; `exportRequests()` gives one text block the owner can paste to Claude. Nothing is sent anywhere.
- `speak(id, text)`: optional TTS through Jarvis's voice-out when present.
- Events on `window`: `olympus:people:open`, `olympus:people:close`, `olympus:people:request`.

## How a scene uses it
1. Load `<script type="module" src="../olympus/people.js?v=p1"></script>` (optional: guard `if (window.OLYMPUS_PEOPLE)`).
2. Give each figure a person id (see ids above) and call `OLYMPUS_PEOPLE.open(id)` on tap / on "Talk" in first person (within 3 m). Show `portrait(id, 44)` in cards.
3. No kit loaded = the scene's own card stays as the fallback. Never blank.

## Rules
Honest labels (sample / stale / snapshot at build time). Every $ with its R where both exist. "I can't place orders: paper and suggestions only." AGORA look, 44 px taps, works offline.

## The look of a person (owner 2026-11-11: "it should be like a Wii character or something like that")
People are friendly cartoon characters in the spirit of console avatars: a big round head, a simple expressive face (dot/oval eyes, eyebrows, a small mouth, optional glasses/beard), a short rounded body, mitten hands, simple legs; ORIGINAL designs (do not copy any company's avatar art, names or logos). Each person is recognisably different: skin tone, hair style and colour, outfit (a chiton / tunic / cloak in soft warm colours: gold, olive, terracotta, aegean blue, ivory, bronze), one accessory by kind (laurel for champions, a scroll for scribes, a hammer for builders, a coin pouch for scanners, a helmet for bots, an owl for the Mind). Soft, matte, toy-like; no neon, no glow. They idle (breathe, blink, look around), wave when you come near, turn to face you when you talk, nod / shrug / cheer / slump with the mood of their data.
- 2D: `portrait(id, size)` draws the same character as a round avatar (head and shoulders) in SVG.
- 3D (new module `olympus/people3d.js`, optional import): `spec(id) -> {skin, hair, hairStyle, outfit, accent, accessory, height, build, face:{eyes, brows, mouth}, mood}` (plain data, deterministic from the person's seed) and `figure(THREE, spec, {lite}) -> Object3D` with `.userData.pose(name)` for idle / wave / talk / cheer / slump and `.userData.lookAt(vec3)`. Budget: <= 14 meshes and <= 900 triangles per figure on high, <= 350 on LITE; shared geometries and materials so 60 figures stay within a scene's budget (or use `figureInstanced(THREE, specs[])` for crowds).
- ME: the owner can make his own character in Symposium ('Make my character': face, hair, outfit, name), stored in `olympus.me.v1`; scenes use it as the first-person body/shadow and in chat bubbles (`OLYMPUS_PEOPLE.me()`).

## Figure API v2 (2026-11-11, `olympus/people3d.js`; the v1 calls above all still work)
The look: our own stylised Olympus people (original design). Big expressive head, soft sculpted body (lathe / capsule / sphere shapes on a small skeleton), cel (toon) shading with a warm rim light and a thin ink outline. Faces: eyes with iris, pupil and highlights, upper and lower lids, brows, a mouth with visemes. Hair cuts (crop, side part, spiky, curly, afro, long, ponytail, wavy, swept, bob, bun, topknot, bald, shaved), garbs (chiton, cloak, apron, armour, toga), accessories by kind (laurel, helmet, hammer, scroll, coin pouch, owl, torch, key + lantern), eye colours; all from the seed (`drawLook(spec)` in people-core.js, shared with the 2D portrait), so every person looks the same everywhere and different from the others.

```js
import { spec, figure, figureInstanced, play, animate, lookAt, setMouth, setExpression, setTalking,
         POSE_NAMES, WORK_POSES, WORK_POSE_NAMES, VISEMES, EXPRESSIONS, workPose } from '../olympus/people3d.js';
const f = figure(THREE, spec('builder:abc'), { lite, seated, scale });   // 2 draw calls; feet at y = 0, faces +z, about 1 unit tall
scene.add(f);
play(f, 'hammer');                         // loops; one-shot poses (wave, cheer, nod, shrug) return to the last looping pose
play(f, 'wave', { then: 'idle' });         // returns the one-shot's length in seconds
lookAt(f, camera.position);                // head and eyes turn (clamped); lookAt(f, null) to stop
setExpression(f, 'happy', 1);              // 'neutral' | 'happy' | 'proud' | 'worried' | 'thinking' | 'surprised' | 'sheepish'
setTalking(f, true);                       // talk gestures + head bob + automatic syllable mouth until false
setMouth(f, 'O', 0.8);                     // drive the mouth yourself (voice / TTS): wins for 0.3 s after each call
animate(f, dt);                            // every frame (skip it for reduced motion: the figure holds its pose)
f.userData.dispose();                      // when it leaves the scene
```
- Poses (`POSE_NAMES`): `idle` (breathing, weight shift, looks around), `walk`, `wave`, `talk`, `cheer`, `slump`, `nod`, `shrug`, `think`, and the work poses (`WORK_POSE_NAMES`): `hammer` (at an anvil), `write` (quill on a wax tablet), `read` (an open scroll), `weigh` (coins on hand scales), `telescope`, `type` (a slate), `carry` (a crate, walking). `WORK_POSES[kind]` / `workPose(spec | id)` gives the job of a kind: builder hammer, scanner weigh, bot type, mind write, keeper telescope, champion read, villager carry. Work props are built the first time a work pose plays (`{ work: true }` builds them at once, `{ work: false }` never).
- Visemes (`VISEMES`): `rest`, `A`, `E`, `O`, `MBP`, `smile`, `frown` (6 morph targets on the mouth; rest = none).
- `setTalking(f, on)` while the pose is `idle` plays the talk gestures; in a work pose it only moves the mouth and head.
- `f.userData`: the v1 `pose(name)`, `lookAt(v)`, `tick(dt, t)`, `dispose()`, `parts.{head, armL, armR, torso, bones}`, plus `play`, `setMouth`, `setExpression`, `setTalking`, `state()` (pose, expression, talking, mouth weights, lids, props shown), `triangles`, `drawCalls` (2), `look` (the drawn look), `v: 2`.
- Materials are shared (`materials(THREE)` -> `{ toon, line }`: the rim colour is `toon.userData.rim.value`, the line width `line.userData.width.value`).
- Crowds: `figureInstanced(THREE, specs, { lite, seated })` bakes each person's own parts into one mesh, posed on the GPU from a small data texture: 2 draw calls for any number of people, each still with their own cut, garb and face (simpler: no lids, the mood sets the mouth). Calls: `place(i, x, y, z, ry, scale)`, `tick(t)`, `setActive(i, on)` (talk gestures + mouth), `setTalking(i, on)`, `setPose(i, 'idle' | 'talk' | 'cheer' | 'wave' | 'slump' | 'nod')`, `lookAt(i, v3 | null)`, `lookAll(v3 | null)` (everyone looks at the speaker), `setVisible(i, on)` (swap a person for a full `figure` when they come close), `pick(raycaster) -> i | -1`, `headWorld(i)`, `dispose()`.
- Budgets (measured by `tests/test_people.py`): a figure is 2 draw calls and at most 10,000 triangles with its ink line (LITE 6,000); a crowd is 2 draw calls and at most 3,000 triangles a person (LITE 2,000). A scene of 30 people = one crowd + a few close-up figures: well inside 45 draw calls / 160k triangles.
- Sound and voice are not here: the voice agent calls `setTalking` / `setMouth`; the 2D portrait (`OLYMPUS_PEOPLE.portrait`) draws the same face, hair, garb and mood.

## Voices, speech bubbles and work cards (2026-11-11, owner: "characters I can see, talk to, they talk and show work")
Files (People agent): `olympus/people-voice.js` (voices + mouth timeline), `olympus/people-show.js` (work cards + bubbles); `people.js` wires them into the API and the chat sheet.
- **Voice**: every person has a stable voice from their id: `OLYMPUS_PEOPLE.voice.profile(id) -> { gender, pitch, rate, timbre: {hz, formant, breath, wave}, kokoro, pick }`. Spoken with the phone's own voices through Jarvis's speaker (`jarvis/tts.js` createSpeaker + `jarvis/prosody.js`, loaded only when someone speaks), Kokoro only when the owner already downloaded it in Jarvis, else a soft WebAudio murmur; always captions. OFF by default: `voice.set(true)` (inside a tap: it also unlocks iPhone audio), remembered in `olympus.people.speak` = `'1'`. `voice.on()`, `hush()` stops everything.
- **say(id, text, { scene, figure, anchor, project, container, mood, work }) -> { el, done: Promise<bool>, cancel() } | null**: says it (when voice is on), shows an AGORA speech bubble (button, >= 44 px, one sentence at a time, words appear as spoken) over the figure, drives the figure's mouth / face / pose until done. Placement, first match: `scene = { figure, project() -> {x, y, front}, container, onTick(fn) -> off, P3 }`; `figure` + `scene.camera` + `scene.canvas`; `anchor` (a DOM element: the bubble sits above it, fixed); else the registered stage. No placement = no bubble (the voice and the sheet portrait still talk).
- **stage(provider)**: a scene lends its figures: `{ figure(id) -> scene-object | null, release(id), walk(id) -> Promise, card(id, miniCardEl) }`. Symposium's hall implements it (`hall.speaker(i)`: the talker becomes a full figure, 7 draw calls more). `stage(null)` to leave.
- **show(id, what, { mini }) -> <section class="pp-card">**: the work card, built ONLY from that person's facts (a mini bar chart whose values are read back out of the facts' own text, the verdict with net $ and $ a month for champions, last commits for builders, the Kalshi verdict after fees, picks as estimates for scanners), the source under it. `el.card` is the data, `el.ready` resolves when the files have loaded. The scene places it.
- **walk(id)**: the scene walks them out (`stage.walk`), then their app opens. **talkTogether(ids[2..3], topic) -> { turns: [{ id, name, text, sources, mood }], summary }**: they talk to each other; each speaker quotes only their own facts.
- Events: `olympus:people:say` `{ id, text, engine, bubble }`, `olympus:people:said` `{ id, cut }`, `olympus:people:show`, `olympus:people:walk` `{ id, app }`.
- **Lip sync through Figure API v2**: `say()` fires `olympus:people:speak` `{ id, on }`, `olympus:people:viseme` `{ id, viseme, amount }` (v2 names: `rest A E O MBP smile frown`, mapped from the kit's finer timeline `rest A E O U M F L S K`) and `olympus:people:expression` `{ id, expr }` (v2 expressions from the mood); a scene that listens (Symposium's hall) moves that person's close-up. A figure handed to `say()` directly is driven with `setMouth` / `setExpression` / `play`. The sheet's portrait draws the same mouth (`portrait(id, size, { mouth, expr })`). Ducking: `OLYMPUS_SFX.speaking(true/false)` around real speech; the murmur plays through `OLYMPUS_SFX.bus('voices')`.

## Scene direction: cameras, controls, the HUD and the opener (2026-11-11, `olympus/camera-rig.js`, `olympus/controls.js`)
How it feels to be in a world on a phone. Shared, pure where possible (node-tested in `tests/test_scene_direction.py`, which also drives the three scenes live).
- **Camera rig** `createRig(camera, { world, reduced, dist, pitch, radius, focus(p), near(alpha) })`: shots `follow` (third person behind your own character: swipe = `orbit(dAz, dPitch)`, pinch = `zoom(k)`, eases back behind you while you walk, frames a nearby person via `interest(p)`), `talk` (`{ a, b, side, two, lookDown, back }`: an over-the-shoulder two-shot, then a close-up of the speaker with a slow dolly in; `focus` gets the speaker's head for fx-cine), `establish` (`{ from, look, pivot, dur, to?, done }`: a wide glide down into the follow camera or into `to`), `tour`, `fixed`. Call `follow(target)` and `update(dt)` every frame. THE RULE: the camera is never inside geometry: every frame it is sphere-cast from a free pivot (your head, the speaker's head) against `makeWorld({ boxes, circles, walls, ground })` and pulled in front of the first hit; `inside()` says what it touches (tests: always '').
- **Controls** `gestures(el, { tap, drag, dragEnd, pinch, longPress })`; `createGrid(box, blocked, { pad })` + `findPath(grid, a, b, { reach, closest })` (A*, 8 ways, no corner cutting, string-pulled; `closest` walks as near as it can) + `createWalker()` (your character along the path) + `approach(from, person, gap)` (where to stand to talk). `joystick(box, onMove)` only as an option (`?joy=1`).
- **HUD** `createHud(container, { reduced, maxPlates, hintTop })`: `hint(key, text)` (fades; never again after `used(key)`), `plates(list)` (name + role for at most 3 near people, overlapping ones dropped), `ring(x, y, who, actions, onPick)` (Talk / Show work / Follow / Wave in an arc under the person, 56 px buttons, above the speech bubbles), `cta(text, onTap)` (one call to action), `toast`, `mark`.
- **Scenes**: `ergasterion/direct.js` (floor.js `drive / refs / setPlayer`), `symposium/direct.js` (hall.js `drive / refs / front`), `cities/walk-direct.js` (hellas.js `walkDirector`). Loaded by the scene loaders (`floorload.js`, `hallload.js`, on demand in `hellas-ui.js`); `?direct=0` keeps the old controls.
- **The opener** (`people-talk.js`): `opener(person, facts, env) -> { hello, intro ('I am <name>, <role>.'), mood (a whole sentence), fact (one real fact from their data: money with its R), invite, text }`, `highlight(person, facts)`, `roleShort(person)` (for name plates). `greeting()` is the opener + the remembered question. Every sentence is whole (a bubble shows one at a time), every number grounded.
