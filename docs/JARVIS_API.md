# Jarvis brain API (2026-11-10)

The assistant side of Jarvis (`tools/web_public/jarvis/`): an offline tool layer, actions with a "yes" before any write, a
memory, proactive nudges, and the voice loop. The Jarvis home agent (layout, `jarvis.css`, `home3d`, briefing UI) talks to it only
through the functions below. Paper only: nothing here places, arms or routes an order. Every module is plain ES2020 (iPhone Safari 16).

## Modules

| File | Job |
|---|---|
| `router.js` | Intent router: synonyms, typos (edit distance), word order. `route(text, {apps})` -> `{ intent, score, args } \| null`. No network, no model. |
| `jdata.js` | Reads the published JSON and turns it into plain numbers with source and age. `loadSources()`, `readLocal()`, accessors. |
| `skills.js` | `createSkills(...)`: answers every intent from the data; owns the actions and memory. |
| `actions.js` | The typed action registry. A write asks first. |
| `memstore.js` | What the owner tells Jarvis to remember; export / import. |
| `nudges.js` | `nudges(sources, opts)`: up to 3 proactive suggestions. |
| `brain.js` | Loads `skills.js` itself in a browser (or takes `createBrain({ skills })`); `{ skills: false }` turns it off. |
| `voice-mode.js` | Voice loop with hold-to-talk. |

## Sources (what Jarvis reads)

`jdata.loadSources({ fetch?, now?, base? })` -> `sources`, one GET per file, relative to the page (`../home.json`), 8 s limit, never throws,
a missing file is `null`. `jdata.readLocal(storage)` adds what this phone keeps.

| Key | File / store | Used for |
|---|---|---|
| `home` | `../home.json` | drawdown, daily loss, target, balance, P&L today, connection |
| `money` | `../money/index.json` | deals ending, Sibyl's pick, the money streams |
| `odeon` | `../odeon/trades.json` | trades, worst / best weekday, win rate, explain a trade, usual 1R |
| `rules` | `../ledger/rules.json` | MFFU limits (micros, flat by, payouts, inactivity) |
| `pythia` | `../pythia/events.json` | next CPI / FOMC / NFP, event nudges |
| `kalshi` | the Kalshi bot's `kalshi.json` (the brain passes its facts; `sources.kalshi`) | how is Kalshi, balance, open bets, today |
| `kalshiEdges`, `kalshiLog`, `kalshiLearned`, `kalshiLedger` | `../kalshicity/edges.json`, `learning_log.json`, `learned.json`, `ledger.json` | the engine's copy when the feed is down; which bet kinds lose money |
| `planner`, `journal`, `ledger`, `compassState` | `planner.agora.v2`, `journal.v1`, `ledger.v1`, `compass.state.v1` | read only here |

Every answer carries `sources: ['home.json, 6 min ago']` and ends with "From home.json, 6 min ago." R is dollars divided by the owner's
usual 1R (the median `risk_usd` of his last 30 trades, shown in the answer). A missing file or field gives `{ missing: true }` and
"I don't have that: ...", never a guess. The brain uses that line only when its own rules also have no answer.

## Skills (`createSkills`)

```js
import { createSkills } from './skills.js';
const sk = createSkills({ getSources, apps, storage, now, assistant, env, mem, actions, compass });
// getSources() -> Promise<sources>   apps() -> [{ id, name, purpose }]
// env: { navigate(appId, route), copy(text) -> Promise<bool>, download(name, text, mime), briefing() -> Promise<{ text }> }
sk.handle(raw, q?, { now? })  // -> Promise<reply | null>   null = not one of its intents
sk.confirm() / sk.cancel() / sk.pending   // "yes" / "no" to a proposed write
sk.contextFor(raw)            // -> Promise<string>  the same answers as plain text, for the user's own model
sk.nudges({ max?, quiet? })   // -> Promise<[nudge]>
sk.route(raw)                 // the router's verdict
sk.mem, sk.actions            // the memory store, the registry
```

`reply`: `{ text, speak, intent, sources?, missing?, open?, route?, pending?, download?, copied?, ok? }`. The brain turns `open` / `route`
into a switch of app (existing contract), and `finish()` adds `say`.

### Intents (60+ phrasings are tested in `tests/test_jarvis_skills.mjs`)

`drawdown_left`, `daily_loss_left`, `eval_progress`, `pnl_today`, `balance`, `weekday_worst`, `weekday_best`, `win_rate`, `last_trade`,
`explain_trade`, `trades_count`, `next_event`, `can_trade_now`, `rules_limit`, `deals`, `sibyl_pick`, `streams`, `unrated`, `feeds`,
`next_action` (Compass's own rules when `../compass/compasscore.js` loads, else the nudges), `navigate`, `atlas_district`, `quiz_start`,
`planner_goal`, `planner_task`, `planner_note`, `compass_done`, `copy_briefing`, `export_data`, `import_data`, `remember`, `recall`,
`memory_list`, `forget`, `help_skills`, `kalshi_status` (kalshi-brain.js's own answer), `kalshi_balance`, `kalshi_positions`, `kalshi_today`, `kalshi_losers`, `kalshi_edge_research` (answers only from a published `sources.kalshiEdge = { text }`, else "I do not have that yet"; no such file exists today). The briefing itself stays with the brain.

`what can you do` is generated: `router.helpTable()` groups every intent from the router's own table with 3 example phrases (`INFO`); a test routes each example back to its intent, so the help cannot drift.

## Actions (`createActions`)

```js
acts.defs                // [{ id, label, write, args, about }]
acts.plan(id, args)      // reads and navigation run now; a write returns { pending: { token, id, summary } } and "Say yes or no."
acts.confirm(token?)     // runs the pending write (null when none or expired: 2 minutes)
acts.cancel()            // "Okay, nothing changed."
acts.run(id, args)       // no question (for an app that asked on its own)
```

| id | write | does |
|---|---|---|
| `open_app` | no | navigate to any of the 60+ apps (`open: id`) |
| `open_district` | no | Atlas on one district: `open: 'atlas', route: '#zone=<market\|research\|risk\|command\|life>'` |
| `start_quiz` | no | `open: 'lyceum', route: '#quiz'` |
| `planner_goal` | yes | "Goal: ..." as the first line of today's day note (Planner v2, key `planner.agora.v2`, New York day) |
| `planner_task` | yes | a task, read by the Planner's own `parseQuick` (`Fri 9am ...`, `!high`, `#project`); no day given means today |
| `planner_event` | yes | an event ("add event Fri 9am journal review"), same parser, `addEvent` |
| `planner_note` | yes | appends a line to today's day note |
| `plan_today` | no | today's (or tomorrow's) events, tasks, overdue and note from the Planner on this phone |
| `compass_done` | yes | marks the top (or a named) Compass item done in `compass.state.v1` |
| `import_memory` | yes | merges a memory file |
| `copy_briefing` | no | `env.briefing()` text to the clipboard |
| `export_data` | no | `reply.download = { name, text, mime }`: an `olympus-data` JSON of every non-secret phone key (`jarvis.smart`, `jarvis.vault` and key / token names are left out and listed in `kept`) |

Memory (`remember that ...`) saves at once and says how to undo it ("forget ..."); it is the owner's own explicit command, so it has no
extra question. Everything that edits another app's data (Planner, Compass) asks first.

Planner writes use `planner/plannercore.js` (v2) only: `loadAll` reads the plan (an older v1 plan is migrated, `planner.agora.v1` and `planner.v1` are never changed),
the change is made with `parseQuick` / `addTask` / `addEvent` / `setDayNote`, and it is saved like `planner.js` does (`planner.agora.v2`, `planner.today.v1`,
`planner.sessions.v1`). An unreadable v2 text is never overwritten ("could not be read").

## Memory (`createMemStore`)

Key `jarvis.memory.v1` = `{ v: 1, items: [{ id, t, u, kind: 'fact'\|'pref'\|'note', text, tags }] }`, this phone only, 400 items, 400 characters
each. Passwords, API keys, tokens and card numbers are refused. The key starts with `jarvis.`, so Settings > Storage lists it under Jarvis
and its Export / Import carries it. `mem.exportJson()` is the same envelope for this key alone
(`{ v: 1, kind: 'olympus-data', t, keys: { 'jarvis.memory.v1': '<json>' }, kept: [] }`), so either file imports with either button.

```js
mem.remember(text, { kind? }) mem.search(query, n?) mem.list() mem.forget(idOrWords) mem.clear()
mem.exportJson() mem.importJson(text, { mode: 'merge' | 'replace' }) mem.prefs()   // { name?, style? }
```

Settings can edit it like any key (a JSON text). Matching is fuzzy: words, stems ("trading" finds "trade") and small typos.

## Nudges (for the Jarvis home)

```js
import { nudges } from './nudges.js';
nudges(sources, { now?, max: 3, quiet: [keys] })
// -> [{ id, key, level: 'bad'|'warn'|'info', text, why, ask, open?, route?, usd?, r?, src }]
// or: await sk.nudges()
```

Rules (each fires only on data that is there): `dll_near`, `dd_low` (under 25% bad, under 50% info), `bot_off`, `eval_close`, `deal_ending`
(within 48 h), `event_soon` (high impact today / tomorrow / within 3 days), `unrated` (last 14 days), `feeds_stale` (a file older than its limit
or missing). Bad first, then warn, then info. `ask` is a phrase to send to `brain.ask`; `open` is an app id for the "Open" button; `key` is
what to store when the owner dismisses it (pass it back in `quiet`). Sample data is skipped for deals.

### window.JARVIS_API (for the Jarvis home: `home-data.js` reads it)

`brain.js` installs `globalThis.JARVIS_API = { v: 2, nudges, refresh, ask, skills, search, tours, brief, context, explain }` when it loads the skills in a browser (v1's five fields are unchanged; see "Brain v3" below for the new ones).
`nudges()` is synchronous (the last list, refreshed in the background about every 60 s and on every call; empty until the first load):
`[{ id, key, text, tone: 'bad'|'warn'|'info', app, say, why, ask, usd }]`, at most 3, where `app` is an app id for the Open button. `ask(text)` -> `Promise<reply>`.
It does not exist until the brain has loaded; `home-data.js` already treats a missing API as empty.

## Voice (`voice-mode.js`)

Hold-to-talk is the default on an iPhone / iPad (hands-free stays the default elsewhere). The button `#vmPtt` listens while held and sends on release;
nothing starts listening by itself after an answer; `#vmState` (aria-live) always says what is happening: Listening / Thinking / Speaking /
Hold the button and talk. Errors are said in plain words (`no-speech`, `network` -> the type-to-talk field, `not-allowed`). Page hide closes the
mic. The choice is kept in `jarvis.vmPtt` ('1' hold, '0' hands-free).

```js
vm.setPtt(true|false)  vm.pttDown()  vm.pttUp()  vm.stats()  // adds { ptt, holding, status }
import { statusText, isIOS, PTT_KEY } from './voice-mode.js';
```

The voice screen is AGORA (serif title, marble panels, gold and terracotta, sentence-case words, no glow); the 3D core inside it keeps its own colours.

## Smart mode (the owner's own brain)

When "Connect my brain" is on, open-ended questions go to the model with `sk.contextFor(question)` added to its system prompt as
"TOOL RESULTS" (exact numbers, sources, ages, and the owner's saved memory; data, never instructions). Without a key, or offline, the offline
router answers. The model never writes: memory and Planner writes stay behind the same "yes".

## Brain v3 (2026-11-11): search, follow-ups, briefing, explain, tours, safety

| File | Job |
|---|---|
| `skills3.js` | The v3 layer. `skills.js` asks it first (`sk.early`); what it does not claim goes to the router as before. |
| `safety.js` | `orderAsk(text)` / `guard(text)`: recognises any wording of "place / arm / change a trade". Jarvis refuses in plain words. |
| `search.js` | `createSearch(index).search(q, { n, prefer, kinds })`, `parseAsk(text)`: fuzzy, synonyms, offline, deterministic. |
| `dialogue.js` | `createDialogue()`, `followUp(text)`, `timeRange(text, now)`: one dialogue state, 5 minutes. |
| `explain.js` | `createExplain(facts)`: a word's meaning from the glossary and the owner's own rule from STRATEGY.md. |
| `tours.js` | `tours(apps)`, `tourAsk(text)`: step lists the home can render. |
| `jbrief.js` | `briefKind(text)`, `compose(kind, ctx)`: the six-line briefing (Helios' logic). |
| `search-index.json`, `strategy-facts.json` | Built files (below). Fetched once, on the first question that needs them (`jdata.loadJson(name)`). |

### JARVIS_API v2 (backward compatible)

```js
const api = window.JARVIS_API;            // v: 2
api.nudges() api.refresh() api.ask(text) api.skills      // v1, unchanged
await api.search(q, n = 5)   // -> [{ kind, label, title, text, source, open, route, score }]   [] when the index is not there
api.tours()                  // sync -> [{ id, title, about, steps: [{ n, title, text, open, route }] }]
await api.brief(kind)        // 'day' (default) | 'kalshi' | 'money' -> reply with brief: { kind, name, lines: [6], tail }
api.context()                // sync -> { intent, entity, account, range, topic, canOpen, tour, ageSec, expiresSec } | null
await api.explain(word)      // -> reply | null (an unknown word)
```

- `search` hit: `kind` is one of `app writeup run rejected event quiz money kalshi term rule`; `open` is an app id; `route` is a deep link inside it
  (`#find=<slug or run id>` for the Archive, `#quiz` for the Lyceum, `''` when the app has none). `reply.hits[i].action = { label: 'Open', open, route }`.
- `tours()` ids: `olympus` ("show me around"), `athens`, `money`, `trading`, `research`, `kalshi`, `life`. A stop's sentence is the app's own purpose line.
  By voice: "next", "back", "open it", "stop the tour" (`reply.step`, `reply.stepIndex`, `reply.stepCount`, `reply.open`).
- `brief(kind)`: six lines, each amount with its $ and R, then one line of sources ending "Paper and suggestions only." A missing file is said on
  its own line; with nothing to read the reply is `{ missing: true }` and the brain's older briefing answers. In the brain, "brief me" keeps the
  brain's own bot `cards` and its urgent "First: ..." line (it replaces line 6).
- `context()` holds no numbers and no answer text: only what a follow-up would refer to.

### What he can say

| Skill | Phrases | Reply |
|---|---|---|
| Search (`intent: 'search'`) | "find ...", "search ...", "where is ...", "which app shows ...", "what did we test about VWAP", "did we ever test ..." | top 5, each with its kind and source, `hits` with an `action`; nothing found = `missing` and "I will not guess" |
| Follow-ups (`reply.followup`) | "and yesterday?", "what about ATLAS?", "why?", "open it", "open the second", "explain that in plain words", "compare with last week", "and kalshi?" | resolved against the last skill answer; `range` / `account` / `entity` are kept for the next one |
| Briefing (`intent: 'briefing'`) | "brief me", "brief me on Kalshi", "brief me on money" | `brief.lines` (6) |
| Explain (`intent: 'explain'`) | "what is drawdown / CISD / an IFVG / a sweep / Kelly / PF", "where does the stop go", "what is the target rule", "what is the strategy" | the meaning, then "Your rule (STRATEGY.md, rule N, ...)" word for word; a word the live strategy does not use says so |
| Tours (`intent: 'tour'`) | "show me around", "tour Athens", "tour the money machines" | `reply.tour` |
| Safety (`intent: 'refuse_trade'`) | any wording of buy / sell / place / enter / arm / go live / move my stop / cancel / flatten / bet $50 on ... | "I can't place orders: paper and suggestions only." Nothing opens, nothing is pending, nothing is kept |

The dialogue state: `{ intent, args, entity, account, range, topic, link, hits, tour }`, set after every skill answer, gone after 5 minutes
(`dialogue.TTL_MS`), after a write (memory, Planner) and when another part of the brain answered (`sk.heard()`). With no live state the same
phrases are not claimed, so the brain's older follow-ups ("and atlas?" after "how are the bots") work as before. Time ranges are New York days:
today, yesterday, tomorrow, this / last / next week, this / last month, "last 7 days", a weekday. Results and trades come from
`odeon/trades.json`, Kalshi days from `kalshicity/edges.json`; a number with no history (drawdown) says so instead of guessing.

The order in `brain.ask`: a pending yes / no, privacy, "I traded ..." (his own report), then `skills.guard` (the refusal), then `skills.early`
(v3), then modes, bots, Kalshi, the router skills and the rest.

### The two built files

```
python tools/jarvis_facts_build.py  [--check | --selftest | --out DIR]      # STRATEGY.md + olympus/glossary-core.js -> jarvis/strategy-facts.json (17 KB)
python tools/jarvis_search_build.py [--site DIR | --check [--strict] | --selftest]   # -> jarvis/search-index.json (about 215 KB, limit 350 KB)
```

`strategy-facts.json`: `{ v, src, strategy, head, sections: [{ n, title, lines }], terms: { name: { def, src, rules?, live, prev } }, aliases, sha }`.
Rule lines are STRATEGY.md's own lines of the live LIT part (rules 1 to 11) with the markdown and file pointers removed; a test checks each one
against STRATEGY.md. The builder fails when its word-to-rule table no longer matches the file, so Jarvis cannot drift into an invented rule.

`search-index.json`: `{ v, kinds, counts, sha, docs: [[kindIndex, title, text, open, route, source], ...] }` from the apps list + `docs/OLYMPUS_MAP.md`
(district), `archive/index.json` (write-ups, runs, rejected ideas) + `research/writeups/*.md` (first paragraph), `pythia/events.json`, the Lyceum
question bank, the money machines (`money/<id>.json`, else the bundled fixture marked "[sample data]"), `kalshicity/edges.json` (stop / do-more /
watch lists), the glossary and the strategy rules. Deterministic (no clock in the file).

## Wiring needed (not done here: the lead owns these files)

- **v3 (2026-11-11)** `tools/web_public/jarvis/sw.js` SHELL (bump the worker): `./skills3.js`, `./search.js`, `./dialogue.js`, `./explain.js`,
  `./tours.js`, `./safety.js`, `./jbrief.js`, `./strategy-facts.json`, `./search-index.json` (the brain loads them on first use; without
  them offline, search / explain say "I don't have that").
- **v3** `tools/build_web_dashboard.py`, after the site's JSON is published (Archive, Pythia, money, Kalshi City):
  `python tools/jarvis_facts_build.py --out <site>/jarvis` then `python tools/jarvis_search_build.py --site <site>` (in-process:
  `jarvis_search_build.main(["--site", out_dir])`). The repo copies are already built; `--check` is in `tests.test_jarvis_skills`.
- **v3** Jarvis home (`index.html` / `home-*.js`), optional: render `reply.hits` (an Open button per hit: `action.open`, `action.route`),
  `reply.tour.steps` and `reply.brief.lines`; call `JARVIS_API.tours()` for a "Tours" row and `JARVIS_API.search(q)` for a search box.
- **v3** Archive (`archive/archive.js`), optional: honour `#find=<slug or run id>` (open that write-up / run). Until then the hit opens the Archive itself.


- (v1, done) `tools/web_public/sw.js`: add `jarvis/router.js`, `jarvis/jdata.js`, `jarvis/skills.js`, `jarvis/actions.js`, `jarvis/memstore.js`,
  `jarvis/nudges.js` to the SHELL / lazy list (the brain loads them on first use) and bump the worker.
- `jarvis/index.html` (Jarvis home agent): optionally pass `skillsEnv: { navigate, copy, download, briefing }` to `createBrain` so "copy the
  briefing" and "export my data" reach the clipboard and a download; without it the reply still carries the text and the `download` object.
  Handle `reply.download` (`{ name, text, mime }`) with a Blob link, and show `sk.nudges()` on the home.
- Done (2026-11-10): `atlas/atlas.js` honours `#zone=<id>` and `lyceum/lyceum.js` honours `#quiz`.
- Settings: nothing, the memory key is already under `jarvis.`.
