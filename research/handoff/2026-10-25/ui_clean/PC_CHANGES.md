# PC dashboard clean-up (2026-10-25)

What it does: the PC dashboard (http://localhost:8766) is calmer and simpler. **Nothing was deleted and no trading
behaviour changed.** Every page is still there, every button still works, and Ctrl+K still finds any page.

Picture: `pc_before_after.png` (before on the left, after on the right, 10 main pages at 1440x900).
Single shots are in `before/` and `after/`. `after/x1..x3` show the lower half of Home, the top-bar "⋯" menu and the
Advanced group opened.

## Sidebar: 6 items instead of 27
| Before | After |
|---|---|
| 6 open groups, 27 links (Home, Accounts, Trading, Results, Operations, More) | **Home, Bot, Chart, Trades, Results, All tools**, plus Settings at the bottom |
| everything visible all the time | the other 24 pages sit in one **Advanced** group, folded until you click it, in 4 short sections: Accounts, Bot, Results, Help |
| Archive (old engine) under Modules | still under Advanced → Help → "Archive (old engine)" and under All tools |
| account box at the bottom opened the old-engine Prop page | it opens Accounts now |

Where each page moved:
- **Advanced → Accounts:** Accounts, ATLAS, Goals, Eval HQ, Eval timeline, Eval cockpit
- **Advanced → Bot:** Today (classic), Bot Brain, Live chart, Trade log, Morning report, NinjaTrader, Bot log, Session timeline
- **Advanced → Results:** Performance, ATLAS per setup, Scaling plan, Experiments
- **Advanced → Help:** Runbook, Audit evidence, Session calendar, Live settings, All features, Archive (old engine)
- "Data" is now called **Results** (same tab strip). "Modules" is now **All tools**.
- To keep Advanced open all the time: Settings → Interface → "Open Advanced in the sidebar".

## Top bar: 5 buttons instead of 12
- Visible: **search (Ctrl+K)**, the news chip, notifications, dark/light, and a **"⋯" menu**.
- Moved into "⋯", each with a plain label: Market (NQ / ES), Reload LIT, Pull latest bars, Risk calculator, Theme switcher,
  Sound alerts, Settings, Keyboard shortcuts.
- The scrolling ticker starts **off** (Settings → Appearance → Ticker tape turns it back on).

## Home (Command center) is the one home page
Top to bottom:
1. **Launch checklist**, until every line is green: red lines first, one short row each, a "Copy fix" button on each red line (3 columns, was 4 big boxes).
2. Day notices (clock change, early close, news) as one-line strips.
3. **What to do now**: one sentence, one main button (Open Bot Control or Copy the fix), and the session phase under it.
4. **Two account cards (LIT 50K, ATLAS 25K)**, each with one big number (% of the way to the target), one line
   (balance · $ to go · session · room), a status chip, one button (Open account / Open ATLAS) and a "⋯" menu
   (Goals, Eval timeline, Eval HQ, Eval cockpit, Bot Brain / ATLAS per setup, Scaling plan). The room meter, today's numbers,
   the open position and the launch anchor fold away under **Details**.
5. **Health**: one row of small lights. Hover = what it says; click = the detail and the fix to copy.
6. **Today: setups, news and the bot log**: folded (it remembers if you leave it open).
7. Footer: refresh time and version; Pause, Copy status, Refresh and links to Brain, Live chart, NinjaTrader, Bot log, News hub, Runbook in its "⋯".

## Look and feel
- 3D background is **off by default** (Settings → Interface → 3D background: Off / Lite / Max). The dotted mesh and strong glow are gone.
- One card look, 8-pt spacing, one type scale; colour means one thing: green = fine, amber = wait or check, red = act now.
- Pages fade in (short, off when Animations are off); loading pages show a grey skeleton with a plain sentence; empty boxes say what that means.
- All tools page: every page in 7 plain sections (Accounts and evals, Running the bot, Help and safety, The strategy,
  Trades and review, Market and business, Results and research, Archive and app) as compact tiles, with a filter.
- Settings page: Interface first (sidebar, Advanced, 3D), then Appearance, Alerts, Themes, phone app.
- Keyboard: Ctrl+K and / still open search; `?` shows the list; G then a letter still jumps; 1-6 now = the six sidebar pages.
- K3 icon unchanged. Service-worker cache bumped to `le-shell-next-v16`, so the PC picks the new look up on the next reload.

## Files
- New: `web_next/css/clean.css`, `web_next/js/next/menu.js` (the "⋯" menu), `tests/shots_ui_clean.py` (these screenshots + sheet).
- Changed: `web_next/js/next/routes.js`, `shell.js`, `cc.js`, `keys.js`, `fx3d.js`, `web_next/js/skins.js`, `web_next/js/app.js`,
  `web_next/index.html`, `web_next/sw.js`, `tests/test_pc_command_center.py` (the sidebar-group check now pins the new layout).
- Not touched: `tools/web_public/` (phone), `secondcore.js` and `tradepics.js` (still byte-identical to the phone copies), every engine / API file.

Redo the screenshots: start the server, then
`python -X utf8 -m tests.shots_ui_clean --pc http://127.0.0.1:8766 --out research/handoff/2026-10-25/ui_clean/after`
and `python -X utf8 -m tests.shots_ui_clean --sheet research/handoff/2026-10-25/ui_clean`.
