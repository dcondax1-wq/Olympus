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
