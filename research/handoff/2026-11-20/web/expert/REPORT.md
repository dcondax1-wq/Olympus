# web-expert (2026-11-20): the website-business expert in Olympus

Owner (13:30 ET): "an expert expert on marketing 3D websites". Branch **day-jarvis** (this session can only push it).

## What it is
- **Agency > Expert** (`tools/web_public/agency/expert/`): one phone page.
  - **Diagnose a prospect in 5 taps** (what they do, their site, their Google reviews, must customers SEE it, how they spend) -> the offer to
    lead with, its $ range and build time, why, what to offer next, and **the exact words to say** (copy button).
  - **14 playbooks** (search): positioning, pricing (three options, middle first), pricing a 3D site, when 3D sells vs gimmick, the 30-second
    cold-call opener, objection answers, local SEO, Google Business Profile, reviews, conversion, small-budget ads, retainers, upsells,
    the build process. Each: what to say, what to do, the $, what to avoid.
  - **3D by trade**: 12 trades with a verdict (sells / maybe / gimmick), the pain, the hook, the offer and the words.
  - **The offers** with $: Starter $1,500-$3,000, Growth $3,500-$6,500, 3D / immersive $6,000-$15,000, care plan $99-$299 a month, local
    growth plan $400-$1,200 a month, Google profile fix $300-$750, ads management $250-$600 a month.
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

## Next
- Fold in the research team's RESEARCH.md when it lands (prices, niches, sources).
- HUB team: a "Website expert" card on the Agency home (LEAD_WIRES.md).
