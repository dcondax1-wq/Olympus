# A sturdier execution path for the MFFU accounts (big-execution, 2026-11-26)

Question (lead): most of our pain (missed trades, stuck starts, NinjaTrader disconnects, F5 recompiles, OneDrive file locks, a GUI
that must stay open) comes from running through NinjaTrader's GUI and a file bridge on one Windows PC. Is there a more robust
route for MFFU accounts? Paper only: nothing here arms an account, places a real order or changes a strategy / size.

## The short answer
| Question | Answer |
|---|---|
| Can the bot reach MFFU accounts without NinjaTrader (Tradovate API, Rithmic, CQG, ProjectX)? | **No.** MFFU lists only Tradovate-connected platforms (official page, Oct 8 2026). Tradovate gives prop / eval accounts **no API key**. MFFU offers no Rithmic, CQG or ProjectX connection |
| Could a paid bridge do it? | Yes: TradingView alerts → TradersPost / PickMyTrade / CrossTrade → Tradovate. That costs **$29-50/mo**, plus a paid TradingView plan for webhooks, **and LIT rewritten in Pine**. Ruled out (no paid services, and a rewrite) |
| Headless or on a free always-on host? | **No.** NinjaTrader 8 needs a signed-in Windows desktop. No free Windows host can run it: Azure's free B1s has 1 GB for 12 months, NinjaTrader's minimum is 2 GB and 8 GB is recommended; Oracle Always Free has no Windows. A usable Windows VPS is about $25-60/mo, which needs the owner's yes. Not recommended now |
| So what is more robust? | **Stay on NinjaTrader, and replace the FILE bridge with a SOCKET bridge** inside NinjaTrader: an add-on that runs the same order commands through NinjaTrader's own Account API. This removes the file failures (OneDrive locks, empty-file reads, withdraw races, outgoing\ wiped) and keeps every safety guard. Built here as a **paper prototype** and tested end to end (C# under mono + the Python adapter) |
| Would it have saved the money we lost? | **Mostly not.** livegap (2026-11-24) found that the dollars went to the PC being OFF (Nov 9-15), accounts not armed (the Rapid) and a wrong account Name (Oct 27). No API fixes those; uptime and checks do (docs/HANDS_FREE.md, docs/FAILURE_MAP.md). The bridge removes the **next** class of failure: the silent unprotected fill (94 min in the Oct 20 rehearsal) and file locks |

**Recommendation: stay on NinjaTrader with hardening (no platform migration).** Move the order transport from files to the
socket bridge only after one week of side-by-side Sim101 proof (plan below), then on one small account, then on all.

## 1. Where the pain actually comes from
| Failure (source) | Layer | Would another API fix it? | Socket bridge fixes it? |
|---|---|---|---|
| PC off / silent Nov 7-17 (5 missed trades; livegap) | PC uptime | no (any route needs a running machine) | no: auto-logon, UPS, PC-silent alarm G8 |
| Rapid EOD 25K not armed (-$1,683 if armed; livegap) | operations | no | no: 01:55 armed check (FAILURE_MAP row 10) |
| Orders to an account Name without the "R" (Oct 27) | config | no | no: Name check (rows 9, 11) |
| Empty order file read by NinjaTrader's watcher, so the fill had no stop or target for 94 min (Oct 20 rehearsal) | **file bridge** | yes | **yes**: no file; NinjaTrader acknowledges in the call |
| OneDrive Documents: 604 file reads per poll, sync-filter locks (2026-10-26) | **file bridge** | yes | **yes**: one snapshot request per poll |
| Order file not picked up, so it is withdrawn and the entry missed (row 21) | **file bridge** | yes | **yes**: answer or refusal in ~1 ms; a TTL refuses a late command |
| outgoing\ wiped on a NinjaTrader restart (reset guard, rows 8 / 29) | **file bridge** | partly | **mostly**: orders and positions come from NinjaTrader's Account API, which re-syncs from Tradovate; the guard still runs once |
| F5 to compile an add-on (LE_TickRec, HANDS_FREE) | NinjaTrader | yes (no NinjaScript) | no: the bridge itself needs one F5 at install, then rarely |
| NinjaTrader GUI must stay open / Tradovate disconnects | NinjaTrader | only via an API we cannot get | no (NinjaTrader reconnects itself; the bot blocks entries meanwhile) |
| Contract roll chart click (ROLL_DEC_2026) | bar feed | n/a | no: no-chart mode (LE_Feed) already removes it |

## 2. What MFFU accounts support (checked 2026-11-26)
| Route | MFFU supports it? | Free? | API for a bot? | Verdict |
|---|---|---|---|---|
| **NinjaTrader 8** (Tradovate connection) | **yes** (official list) | yes (MFFU login) | ATI files (today); ATI TCP DLL (NinjaTrader staff call it unsupported; 32/64-bit issues on the forum); **NinjaScript add-on with the Account API** (the documented, in-process way) | **keep; switch to the add-on API** |
| Tradovate (web / desktop) | yes | yes | Tradovate REST/WebSocket needs the **API Access add-on: $25/mo, a LIVE Tradovate account with $1,000+; "prop firm and evaluation accounts are not eligible"**. A personal key only reaches accounts under your own username | no |
| Tradovate partner API | the firm's own | n/a | keys go to the prop firm (evaluation partners), not traders | no |
| TradingView (via Tradovate) | yes (charting/trading) | webhooks need a paid TV plan | only through a paid webhook bridge (TradersPost ~$49/mo, PickMyTrade ~$50/mo, CrossTrade $29/mo; vendor pages) + Pine | no (paid + rewrite) |
| Quantower / Volumetrica / DeepChart / ATAS / Hyperprop | yes (listed; one competitor's page says Quantower, ATAS, Volumetrica and DeepChart run on dxFeed data) | platform yes | Quantower has a C# strategy API, but it is another GUI app with the same "must stay open" problem and an unproven route into the MFFU account | no gain over NinjaTrader |
| Rithmic R\|API / R\|Protocol | **not listed** by MFFU (help center search "rithmic": 0 articles). One vendor table claims it with no source | broker fees + conformance | yes, if the firm offered it | no (not offered) |
| CQG / ProjectX | not offered (ProjectX = Topstep and others) | | | no |

**MFFU rules for bots** (Fair Play, help center 8444599): automated strategies "tailored to their own specific settings" are
allowed. They must not exploit the sim's favourable fills. No high-frequency trading. Live accounts must follow CME rules.
Section 4 says each trader personally enters their trades, and copying other traders is banned. Our 2-4 trades a week on our own
settings fits. Nothing found bans a VPS (Topstep does ban one). Still open, as already noted in research/lit/mffu_rules.json:
ask support in writing whether NinjaTrader automation via an add-on / ATI is fine. One email the owner can send. Not needed
for the paper work.

**Latency and data.** Every route ends at Tradovate's servers, so the home internet hop (~20-60 ms) is common to all of them.
On the PC, the file watcher adds milliseconds to seconds under OneDrive. The socket measured **p50 0.23 ms, p99 9 ms** round
trip (mono, simulated fills). With 2-4 trades a week on 1-minute bars, latency is not the issue; lost or late orders are.
Bars / ticks / depth stay where they are: LE_Feed (bars, no chart) and LE_TickRec (ticks) inside NinjaTrader with the MFFU login.
Depth can be read the same way later. An outside data API (Tradovate's) would need a CME sub-vendor licence on top.

**Reconnects.** NinjaTrader reconnects Tradovate by itself, and the bot refuses entries while every connection is DISCONNECTED (as today).
The socket client reconnects with a 0.5-5 s backoff. While the bridge does not answer, `tick()` does nothing, so there is no
false "stop missing → flatten" while the bot cannot see. After 60 s with a trade open, the phone gets one alert. When NinjaTrader
restarts, the add-on restarts with it and reads orders and positions back from the Account API.

## 3. Hosting (costs stated honestly)
| Option | Cost | Runs NinjaTrader? | Note |
|---|---|---|---|
| The owner's PC (today) | $0 (+ a UPS ~$60-90, already on the HANDS_FREE list) | yes | auto sign-in + "Connect on startup" + active hours make reboots hands-free |
| Azure free account | $0 for 12 months (B1s: 1 vCPU, 1 GB) | **no** (NinjaTrader minimum 2 GB, 8 GB recommended) | too small |
| AWS free plan | credits (~$100-200 over 6 months) on new accounts | small instances only; the credits run out | not a standing host |
| Oracle Always Free | $0 | **no Windows** | Linux ARM only |
| Windows trading VPS (4-8 GB) | **~$25-60/month** | yes, near Chicago | **paid: only with the owner's yes.** It would remove home-power and internet risk. It is not worth it until the PC's uptime record says so: livegap prices a missed trade at ~$250 at the Jul-Oct pace, but the misses that happened skipped losers |

Headless: NinjaTrader 8 has no service or headless mode. It needs a signed-in desktop session, the same on a VPS. Charts
fall back to software rendering on a VPS. LE_Feed already removes the need for a chart.

## 4. The prototype (built on this branch, paper only)
| File | What |
|---|---|
| `engine/nt_socket.py` | `NtSocketAdapter`, a **subclass of NinjaTraderAdapter**. Only the transport changes: the bracket logic, write-ahead state, caps (max micros, 8 entries a day, message throttle), session / holiday / flat-time gates, kill (account vs global), allowlist, NinjaTrader-restart guard and every OIF line validation are the existing tested code. The same command lines go over `127.0.0.1:36975` instead of `incoming\`. One snapshot per poll replaces `outgoing\`. A PING precedes every order command (a half-open socket is found by a harmless request). A command carries its send time + TTL, and the bridge refuses it when expired. **PAPER_ONLY: any non-Sim account is refused, even fully armed and allowlisted.** `--selftest` (17 checks) runs on a simulated bridge; `--ping` checks the PC |
| `ninjatrader/LE_Bridge.cs` | The NinjaScript add-on: a loopback-only TCP listener that runs PLACE / CHANGE / CANCEL / CLOSEPOSITION / FLATTENEVERYTHING through `Account.CreateOrder / Submit / Change / Cancel / Flatten`. It checks every line of a request before running any of them. Orders must be named LE...; non-Sim accounts are refused; FLATTENEVERYTHING touches Sim accounts only. It reports a flat position as FLAT (NinjaTrader drops it from Account.Positions). C# 5, every call in try/catch. **Never compiled in NinjaTrader** (no install here); the 5 API assumptions are listed at the top of the file |
| `tests/nt_stub/NtStubsBridge.cs` + `tests/test_le_bridge_cs.py` | The **real LE_Bridge.cs compiled with mono** against stub NinjaTrader types and a small order simulator, with the Python adapter trading Sim101 through it: bracket, breakeven, target fill → FLAT, short + exit, kill, and refusals (non-Sim, expired, foreign id, unknown command, one bad line runs nothing). **14/14 pass**; entry → fill → bracket confirmed in 16 ms |
| `tests/test_nt_socket.py` | the adapter's offline self-test, **17/17**: same OIF lines as the file adapter, no files written, bridge down means the entry is refused with nothing sent and tick idles, auto-reconnect, NinjaTrader restart blocks entries + alerts, TTL, paper-only, kill. Both suites are added to `run_area.py pc` |
| `tools/exec_compare.py` | the side-by-side harness: `--pc` alternates file / socket rounds on Sim101 (1 MNQ bracket → breakeven → exit, each step timed), `--report` summarises, `--fake` is a dry run of the tool itself |

The file adapter is untouched (`python -m engine.ninjatrader --selftest`: 81 PASS, 0 FAIL). Nothing is wired into the live bot:
`engine/live.py` does not know "nt-socket" yet (lead: one line in `ADAPTERS`, after the red team).

## 5. Reliability comparison plan (one week, Sim101, market hours)
Setup: LE_Bridge installed (one F5, after 16:00 ET, flat). The file bridge stays as it is; the live bot is not touched.

| # | Test | How | Pass for the socket bridge |
|---|---|---|---|
| R | Routine rounds | `python -X utf8 tools/exec_compare.py --pc --rounds 20` at ~10:00 and ~14:00 ET, 5 sessions (200 rounds per bridge) | 0 failed rounds; entry → protected p95 under the file bridge's; every round ends FLAT |
| D1 | NinjaTrader closed mid-trade | open a round, close NinjaTrader, reopen after 2 min | stop / target still at the broker; bot alerts once at 60 s; after the restart the bracket is seen again and no duplicate order is sent |
| D2 | Internet pulled 60 s | unplug during a protected trade | entries refused while disconnected; no flatten while blind; normal after |
| D3 | OneDrive busy | pause / resume sync on Documents during rounds | socket: no change. File: count lock / withdraw errors (the baseline) |
| D4 | Bot killed mid-trade | kill server.py after the fill, start again | bracket restored from the state file; no second entry |
| D5 | F5 while flat | recompile NinjaScript | the bridge comes back on the same port within seconds; the client reconnects by itself |
| D6 | PC sleep / wake | sleep 2 min while flat | the client reconnects; no stale command runs (TTL) |

Measures: failed rounds, entry → protected ms (p50 / p95 / max), late or duplicate orders (must be 0), false alarms, minutes
to recover after D1-D6, and the file bridge's lock / withdraw counts from the bot log.

## 6. Migration steps, risks, and what the owner does
Steps (each one waits for the previous one to pass):
1. **Red team** `engine/nt_socket.py` + `LE_Bridge.cs` (one helper; known soft spots below).
2. **Lead wires:** `ADAPTERS["nt-socket"]` in `engine/live.py`; self-heal copies `LE_Bridge.cs` into AddOns like LE_TickRec.
3. **Owner, once at the PC:** NinjaScript Editor → F5 (after 16:00 ET, flat). Check: `python -m engine.nt_socket --ping`.
4. **Comparison week** (section 5). Results go in this file.
5. **Promotion (owner yes/no):** remove PAPER_ONLY in both files (a separate change), add a local token so only the bot
   can talk to the port, run ONE account (the smallest eval) on "nt-socket" for 2 weeks. Rollback = `"adapter": "ninjatrader"`
   in that account's config (one word).
6. All accounts, if step 5 is clean.

Risks (honest):
- **The C# calls are unverified on a real NinjaTrader.** A compile error in any NinjaScript file blocks F5 for **all** add-ons
  (LE_Feed / LE_TickRec updates would wait). Mitigation: install only when the owner sits at the PC; if F5 shows an error,
  delete LE_Bridge.cs and press F5 again.
- Threading: the Account API is called from the add-on's socket thread. If NinjaTrader objects, marshal it through its dispatcher
  (noted in the file).
- `OrderAction.Sell` opening a short (vs `SellShort`), and order names surviving a Tradovate reconnect: confirmed only by the Sim week.
- The port is loopback-only but has no password: any program on the PC could send it orders. That is harmless while paper-only;
  a token is required before live (step 5).
- Two bridges at once is double complexity. One account uses one adapter (the existing per-account lock), and the file route
  stays as the fallback.

**Owner to-do now: nothing.** Later: one F5 at the PC (step 3) and one yes/no (step 5). Optional: one email to MFFU support
("Is automated trading through a NinjaTrader add-on on my own settings allowed on Builder / Rapid?"), to have the answer in writing.

## Sources
- MFFU supported platforms (official, Oct 8 2026): https://help.myfundedfutures.com/en/articles/8528335-overview-of-supported-platforms-at-mffu
- MFFU Fair Play / automated trading (official): https://help.myfundedfutures.com/en/articles/8444599
- Tradovate API add-on fee, eligibility, CME licence (vendor summary of Tradovate's article, Nov 2026): https://crosstrade.io/blog/tradovate-api-add-on-fee-cme-license-webhook/
- Tradovate partner API keys go to evaluation partners: https://partner.tradovate.com/overview/quick-setup/api-keys
- Prop accounts and the Tradovate API (community): https://community.tradovate.com/t/api-access-for-propfirm-accounts/10348
- MFFU platforms, "two connections", no ProjectX (competitor page, Sep 2026): https://phidiaspropfirm.com/education/myfundedfutures-platforms
- Prop firms with APIs (vendor; its MFFU "Rithmic" claim has no source): https://blog.pickmytrade.trade/every-prop-firm-with-a-public-trading-api-in-2026/
- MFFU checkout = Tradovate connection (review, Aug 2026): https://proptradingvibes.com/blog/myfundedfutures-rithmic
- ATI DLL vs OIF (NinjaTrader forum): https://forum.ninjatrader.com/forum/ninjatrader-8/add-on-development/1239740-ati-vs-oif
- NinjaTrader 8 minimum system requirements: https://ninjatrader.com/support/helpguides/nt8/minimum_system_requirements.htm
- Webhook bridge prices (vendor pages): https://crosstrade.io/alternatives/traderspost-alternative , https://pickmytrade.io/compare/pickmytrade-vs-traderspost
- Free cloud tiers: https://aws.amazon.com/free/compute , https://github.com/savyasathe/free-vps
