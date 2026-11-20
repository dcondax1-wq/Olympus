# WEB LEADS (Agency): local businesses with no website, from OpenStreetMap (day-kalshi session, slice "leads", 2026-11-20)

## $ first
The lead finder is free: OpenStreetMap + the public Overpass API, no key, no paid service. In Maryland towns most small businesses
on the map have no website tag. Each one is a cold call for a $500-$2,000 site (the offers team sets prices). The tool and the
phone list are done and tested. **A first real list is published (partial):** a second try from the cloud got Frederick's food, health, gym and auto businesses (3 of 6 query types answered via the maps.mail.ru mirror): **67 businesses with no website tag, 2 hot** (agency/leads/leads.json, one chain removed by name). Before that, from this cloud machine every public Overpass server failed
today (overpass-api.de and kumi: connection closed / timeout; the maps.mail.ru mirror: one tiny query worked, then 504 within 1 s).
I did not invent businesses. The owner's PC (home internet) makes the full list (shops, trades, offices too, + Annapolis and Hagerstown) in about a minute:

    python tools/web_leads.py                       # Frederick, Annapolis, Hagerstown
    python tools/web_leads.py --town "Bel Air" --bbox 39.50,-76.38,39.57,-76.31   # any town: its map box

## What it does
| Part | What |
|---|---|
| `tools/web_leads.py` | Per town, 6 small Overpass queries (shops, trades, offices, health, gyms, food/auto amenities), main server first, mirrors only after a failure, >= 1.1 s between any two requests, a User-Agent that names only the tool. Keeps named businesses with **no website tag** (a Facebook page alone = "no real site"); leaves out chains (brand tags), closed, nameless, duplicates. Score: no site 4 (Facebook-only 3) + phone 2 + hours 1 + street 1 + niche value 0-2; hot >= 8, warm >= 6. Each lead: name, niche, town, phone (301) 555-0101 format, address, hours, why hot, best offer, the call app's trade, the OSM link. Writes `tools/web_public/agency/leads/leads.json` with the ODbL credit. Every server failing = exit 2, old file kept. |
| `agency/leads/` | The phone list: tiles (to call / hot / called / interested), filters (town, kind, heat, status, only with a phone), per business: why, offer, hours, **Call with script**, the dial link, Map, and Called / Interested / Not interested (kept on the phone only, localStorage). 44 px taps, rem text, no sideways scroll. No list = one plain sentence with the PC command. |
| `agency/call.js` (+6 lines, ?v c2) | `call.html?handoff=1&lead=<id>`: imports the business handed over by the list (the call app's own import + merge, so never a duplicate; Do Not Call, legal hours and opt-outs still apply), clears the hand-off, opens its call screen on the trade's script. |

## Policy (cited in the tool's docstring)
- Overpass API public instances: https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances (main instance: well below
  10,000 queries and 1 GB a day). This tool: 6 queries per town.
- OSM data licence ODbL, attribution "(c) OpenStreetMap contributors": https://www.openstreetmap.org/copyright (in leads.json + the page foot).
- OSMF operations policies: https://operations.osmfoundation.org/policies/ .
- Business listings only (OSM maps businesses, not people); the tool never contacts anyone; calls are dialled by the owner through the
  call app, which checks the legal hours, Do Not Call and opt-outs.

## Tests
`python -X utf8 -m tests.test_web_leads` 21/21 (FICTIONAL fixture `tests/fixtures/web_leads_overpass.json`, 555 numbers): finder rules,
politeness (query count, server order, >= 1 s gaps, UA), stale-beats-invented, the page in node Playwright (filters, a mark kept after a
reload, Call with script -> the call app on the plumber with the contractor script, no-file sentence, 44 px, no JS error). Registered in
tests/run_area.py AREAS["agency"] (own line above main()). Screenshots: leads-list.png, leads-call.png (fictional fixture).

## Update (lead relays)
- Best offer per lead now carries the research team's prices (RESEARCH.md on day-archive): starter site $1,500 (gym: site + phone-scan
  3D tour $2,500) + the right monthly add-on (reviews & Google profile $199-$399/mo, missed-call text-back $97-$149/mo for trades,
  a $300-$800 3D tour for salons). `offer_usd` = the build price.
- The Agency HQ tile: the page writes localStorage `agency.leads.summary` {n, label "67 leads found", next, t, pipe {leads, called}}
  on every change; the finder also writes a static `agency/leads/summary.json` of the same shape (called 0: the marks live on the phone).
- Tests 23/23.
