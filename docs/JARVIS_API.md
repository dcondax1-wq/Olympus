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
| `planner`, `journal`, `ledger`, `compassState` | `planner.agora.v1`, `journal.v1`, `ledger.v1`, `compass.state.v1` | read only here |

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
`memory_list`, `forget`, `help_skills`. The briefing itself stays with the brain.

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
| `planner_goal` | yes | "Goal: ..." as the first line of today's note in `planner.agora.v1` (New York day) |
| `planner_task` | yes | a task for today (`09:30` in the text becomes its slot) |
| `planner_note` | yes | appends a line to today's note |
| `compass_done` | yes | marks the top (or a named) Compass item done in `compass.state.v1` |
| `import_memory` | yes | merges a memory file |
| `copy_briefing` | no | `env.briefing()` text to the clipboard |
| `export_data` | no | `reply.download = { name, text, mime }`: an `olympus-data` JSON of every non-secret phone key (`jarvis.smart`, `jarvis.vault` and key / token names are left out and listed in `kept`) |

Memory (`remember that ...`) saves at once and says how to undo it ("forget ..."); it is the owner's own explicit command, so it has no
extra question. Everything that edits another app's data (Planner, Compass) asks first.

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

## Voice (`voice-mode.js`)

Hold-to-talk is the default on an iPhone / iPad (hands-free stays the default elsewhere). The button `#vmPtt` listens while held and sends on release;
nothing starts listening by itself after an answer; `#vmState` (aria-live) always says what is happening: Listening / Thinking / Speaking /
Hold the button and talk. Errors are said in plain words (`no-speech`, `network` -> the type-to-talk field, `not-allowed`). Page hide closes the
mic. The choice is kept in `jarvis.vmPtt` ('1' hold, '0' hands-free).

```js
vm.setPtt(true|false)  vm.pttDown()  vm.pttUp()  vm.stats()  // adds { ptt, holding, status }
import { statusText, isIOS, PTT_KEY } from './voice-mode.js';
```

## Smart mode (the owner's own brain)

When "Connect my brain" is on, open-ended questions go to the model with `sk.contextFor(question)` added to its system prompt as
"TOOL RESULTS" (exact numbers, sources, ages, and the owner's saved memory; data, never instructions). Without a key, or offline, the offline
router answers. The model never writes: memory and Planner writes stay behind the same "yes".

## Wiring needed (not done here: the lead owns these files)

- `tools/web_public/sw.js`: add `jarvis/router.js`, `jarvis/jdata.js`, `jarvis/skills.js`, `jarvis/actions.js`, `jarvis/memstore.js`,
  `jarvis/nudges.js` to the SHELL / lazy list (the brain loads them on first use) and bump the worker.
- `jarvis/index.html` (Jarvis home agent): optionally pass `skillsEnv: { navigate, copy, download, briefing }` to `createBrain` so "copy the
  briefing" and "export my data" reach the clipboard and a download; without it the reply still carries the text and the `download` object.
  Handle `reply.download` (`{ name, text, mime }`) with a Blob link, and show `sk.nudges()` on the home.
- `atlas/atlas.js`: honour `#zone=<id>` (the five districts) and `lyceum/lyceum.js`: honour `#quiz` (start today's quiz). Until then the app opens
  without the deep link.
- Settings: nothing, the memory key is already under `jarvis.`.
