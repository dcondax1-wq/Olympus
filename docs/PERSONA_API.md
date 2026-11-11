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

## Voices, speech bubbles and work cards (2026-11-11, owner: "characters I can see, talk to, they talk and show work")
Files (People agent): `olympus/people-voice.js` (voices + mouth timeline), `olympus/people-show.js` (work cards + bubbles); `people.js` wires them into the API and the chat sheet.
- **Voice**: every person has a stable voice from their id: `OLYMPUS_PEOPLE.voice.profile(id) -> { gender, pitch, rate, timbre: {hz, formant, breath, wave}, kokoro, pick }`. Spoken with the phone's own voices through Jarvis's speaker (`jarvis/tts.js` createSpeaker + `jarvis/prosody.js`, loaded only when someone speaks), Kokoro only when the owner already downloaded it in Jarvis, else a soft WebAudio murmur; always captions. OFF by default: `voice.set(true)` (inside a tap: it also unlocks iPhone audio), remembered in `olympus.people.speak` = `'1'`. `voice.on()`, `hush()` stops everything.
- **say(id, text, { scene, figure, anchor, project, container, mood, work }) -> { el, done: Promise<bool>, cancel() } | null**: says it (when voice is on), shows an AGORA speech bubble (button, >= 44 px, one sentence at a time, words appear as spoken) over the figure, drives the figure's mouth / face / pose until done. Placement, first match: `scene = { figure, project() -> {x, y, front}, container, onTick(fn) -> off, P3 }`; `figure` + `scene.camera` + `scene.canvas`; `anchor` (a DOM element: the bubble sits above it, fixed); else the registered stage. No placement = no bubble (the voice and the sheet portrait still talk).
- **stage(provider)**: a scene lends its figures: `{ figure(id) -> scene-object | null, release(id), walk(id) -> Promise, card(id, miniCardEl) }`. Symposium's hall implements it (`hall.speaker(i)`: the talker becomes a full figure, 7 draw calls more). `stage(null)` to leave.
- **show(id, what, { mini }) -> <section class="pp-card">**: the work card, built ONLY from that person's facts (a mini bar chart whose values are read back out of the facts' own text, the verdict with net $ and $ a month for champions, last commits for builders, the Kalshi verdict after fees, picks as estimates for scanners), the source under it. `el.card` is the data, `el.ready` resolves when the files have loaded. The scene places it.
- **walk(id)**: the scene walks them out (`stage.walk`), then their app opens. **talkTogether(ids[2..3], topic) -> { turns: [{ id, name, text, sources, mood }], summary }**: they talk to each other; each speaker quotes only their own facts.
- Events: `olympus:people:say` `{ id, text, engine, bubble }`, `olympus:people:said` `{ id, cut }`, `olympus:people:show`, `olympus:people:walk` `{ id, app }`.
- **Figure API v2 (people3d.js, the character artist) as this kit calls it**, every call feature-checked: `setMouth(fig, viseme, amount 0..1)` with visemes `rest A E O U M F L S K` (A open, E wide, O round, U pucker, M lips shut, F lip on teeth, L tongue, S teeth, K small open); `setExpression(fig, mood)` with moods `calm proud busy worried sheepish`; `play(fig, pose)` with `talk work walk` plus the old poses. Missing: the kit scales the mouth mesh (`userData.parts.mouth`) and uses `userData.pose`. A crowd (figureInstanced) cannot talk: the scene swaps in a full figure for the speaker.
