# web-expert (2026-11-20): the website-business expert in Olympus

Owner (13:30 ET): "an expert expert on marketing 3D websites". Branch **day-jarvis** (this session can only push it).

## What it is
- **Agency > Expert** (`tools/web_public/agency/expert/`): one phone page.
  - **Diagnose a prospect in 5 taps** (what they do, their site, their Google reviews, must customers SEE it, how they spend) -> the offer to
    lead with, its $ range and build time, why, what to offer next, and **the exact words to say** (copy button).
  - **18 playbooks** (search): positioning, pricing (three options, middle first), pricing a 3D site, when 3D sells vs gimmick, the 30-second
    cold-call opener, objection answers, local SEO, Google Business Profile, reviews, conversion, small-budget ads, retainers, upsells,
    the build process. Each: what to say, what to do, the $, what to avoid.
  - **3D by trade**: 12 trades with a verdict (sells / maybe / gimmick), the pain, the hook, the offer and the words.
  - **The offers** with $ (the research team's numbers, research/handoff/2026-11-20/web/research/offers.json): Starter $1,500-$3,000 + care
    $49-$99 a month, Growth $2,500-$5,000, Call engine $500 + $299 a month, Reviews + Google profile engine $199-$399 a month, missed-call
    text-back $199 + $149 a month, accessibility + speed fix $600 + $49 a month (free report as the opener), phone-scan 3D tour $500 + $25 a
    month, 3D product viewer $2,500 + $49 a month, before / after showcase $900, configurator-lite $3,500 + $99 a month, site on a subscription
    $149 a month, Google profile fix $300-$750, ads management $250-$600 a month, custom 3D site $5,000-$15,000 (only later, fixed scope).
- **Jarvis** answers from the same file (`jarvis/biz.js` 'web'): "how do I price a 3D site", "what do I say to a roofer", "best niche for 3D",
  "how do I handle objections", "what should I charge for a website" -> $ first, the words, the source line. The Ask Jarvis button on Agency
  pages offers these six questions.
- One data file: `agency/expert/playbook.json`; the logic: `agency/expert/expertcore.js` (pure, node-tested). Offline, no AI service, sends nothing.

## Honest by design
Prices are typical ranges for a solo studio selling to US local businesses (labelled, not quotes). Scripts say it is a sales call, never invent
clients, reviews or results, stop when asked; fake reviews / review gating / "#1 on Google" are listed as things to avoid.

## Tests
| Suite | Result |
|---|---|
| `python -X utf8 -m tests.test_web_expert` (new, in run_area 'agency') | 28/28 (data, the diagnosis rules in node, the page at 390 x 844 dark + Ivory: 5 taps, search, 44 px, 15 px text, no sideways scroll, no errors) |
| `node tests/test_jarvis_biz.mjs` | 131/131 (incl. the 'web' answers) |
| `python -X utf8 -m tests.test_jarvis_ask` | 15/15 |

Shots: `expert-{dark,ivory}-{1-start,2-diagnosis,3-search}.png` (390 x 844 @2x).

## Research folded in (day-archive 3110fc34)
The diagnosis now sells TEMPLATED 3D (phone-scan tours, model-viewer product pages, before / after sliders) by trade and never a custom 3D
build first; emergency trades get missed-call text-back; a decent site gets the call engine or the reviews engine (results, not a new site);
no site + a tight budget gets the site on a subscription. New playbooks: the accessibility + speed check opener ("common issues fixed",
never "ADA compliant"), text-back, phone-scan tours, what kills small agencies. Facts cited with their source (BrightLocal, Clutch, Level
Access / UsableNet, Shopify's own 3D figure labelled as its own data).

## Agency HQ tile (HUB team)
`agency/expert/summary.json` {n: 18, label: "playbooks, 15 offers with $", next: "Diagnose a prospect in 5 taps"} and, after a diagnosis on
the phone, localStorage `agency.expert.summary` {n: prospects diagnosed, label, next: "Last: <offer>, <price>", t}.
