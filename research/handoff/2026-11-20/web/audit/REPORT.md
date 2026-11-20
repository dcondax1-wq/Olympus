# Web slice: AUDIT (day-web-audit, 2026-11-20)

**What it is:** the owner's sales weapon. One command checks a prospect's home page the way Google tests mobile pages and writes a
one-page report a shop owner understands, with a grade, "3 things that lose you customers" ($ framing + the source of every number),
and every measurement. Send the link or the file.

    python -X utf8 tools/site_audit.py https://their-site.com                     -> tools/web_public/agency/audit/<name>.html + .png
    python -X utf8 tools/site_audit.py https://their-site.com --visitors 1500 --value 120     + "$ a month" estimate

| What | Result |
|---|---|
| Phone check | pre-installed Chromium, 390 x 844, touch, CPU x4, Lighthouse's mobile line (562 ms round trip, 1.44 Mbit/s): one page, 8 s settle |
| Measured | main content (LCP, names the biggest thing on screen), first paint, layout jumps (CLS + what moved), blocking time, MB + files, pinch-zoom, sideways scroll, tap targets < 44 px, text < 12 px |
| Basics | HTTPS, title, search description, tap-to-call, map / directions, opening hours, Google Business Profile link, schema.org business data, site icon, share picture |
| Accessibility | axe-core (already vendored for the A11Y team, tools/a11y/axe.min.js), WCAG 2 A/AA, a 0-100 score + top problems |
| 3 losses | ranked; each cites Google / SOASTA 2017 (bounce +32 % at 3 s ... +123 % at 10 s), Google 2016 (53 % abandon > 3 s), Deloitte 2020 (0.1 s = +8.4 % retail conversions), Think with Google 2016 (76 % visit within a day, 28 % buy), web.dev Core Web Vitals, WebAIM Million 2024 (95.9 %) |
| Report | self-contained: no script, no tracking, no font / image from another site (test-checked), noindex, dark mode, the screenshot next to it |
| Polite | robots.txt read and obeyed (agency/audit.robots_ok), one page once, no crawling, never contacts anyone; a bot wall (403 / "Access Denied" / "Just a moment") = **no report written** (McDonald's answered 403: correctly refused) |
| Index | tools/web_public/agency/audit/index.html: every audit (grade, speed, jumps, access) + how to run one from the PC |
| Demo (big brands only) | Starbucks: D (main content 7.8 s, jumps 0.24, access 100/100); IKEA US: D (35 s: the biggest thing on screen, the shelf photo, arrives late on a slow line; access 100/100) |
| Tests | tests.test_web_audit 17/17 (area agency): curve, basics, score, grade, losses + sources, $ only with inputs, bot wall, report has no tracking / external file, a real local phone run, demos = big brands only |

Screenshots: index.png, ikea-com.png, starbucks-com-dark.png (this folder).
Honest limits: a bot-protected site cannot be checked from a datacenter (the tool says so; run it from the PC's home line); numbers move
a little run to run; the $ estimate is labeled an estimate and only appears when the owner gives visitors + customer value.
