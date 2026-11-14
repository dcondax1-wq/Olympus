/* OLYMPUS Gate catalog v2 (2026-11-14, docs/OLYMPUS_IA_V2.md): every app in plain words, filed under NINE HUBS named after the owner's jobs.
 * Owner: "Make it very organized. I keep saying this but it always looks the same: 'Trading', 'Money', 'Life' subcategories. I want something more organized."
 * v1 had 82 rows in 4 districts (Trading 33 / Money 16 / Life 12 / Worlds 11) + a Workshop. v2: the districts ARE the hubs (so the theme engine's
 * per-district "mix" follows the hubs): Today, Bots & Evals, Kalshi, My Money, Plan & Day, Research, Jarvis, Worlds, Settings & Help.
 * Inside a hub, a section = one job. The FIRST app of a section is its best version ("best"); an app whose 9th column names another app is a duplicate
 * folded into that one (shown under "Other views of the same", never removed). Every old app URL stays: hubs only link / embed them.
 * One row per app: [id, path from the site root ('' = the dashboard), Greek name, plain label (what the owner reads first), one-line purpose,
 *   hub, section inside the hub, extra search words, folded into (id of the best version, or '')].
 * Classic script (ES5), no network, no DOM: window.OLYMPUS_GATE (and module.exports in node).
 * tests/test_gate_page.py + tests/test_hubs.py check every app folder and every row of olympus/apps-list.js is here exactly once. */
(function (g) {
  'use strict';
  var R = [
    // ---- Today: what is happening, and what do I do now
    ['compass', 'compass/', 'Compass', 'What to do next', 'At most five things for today, with why', 'today', 'now', 'todo to do tasks actions next priorities', ''],
    ['ares', 'ares/', 'Ares', 'Go, wait or halt', 'The pre-trade check: GO, WAIT or HALT', 'today', 'now', 'go wait halt war room status checklist', ''],
    ['inbox', 'inbox/', 'Inbox', 'Inbox', 'Everything that needs a look, in one place', 'today', 'now', 'alerts messages notifications inbox', ''],
    ['stoa', 'stoa/', 'Stoa', 'Needs you now', 'What needs a look right now', 'today', 'now', 'attention alerts urgent now', 'compass'],
    ['hestia', 'hestia/', 'Hestia', 'Today at home', 'What to do right now, at home', 'today', 'now', 'today home now', 'compass'],
    ['helios', 'helios/', 'Helios', 'Morning briefing', 'Today in one scroll: drawdown, deals, the plan', 'today', 'brief', 'morning briefing brief today plan summary sun', ''],
    ['herald', 'herald/', 'Herald', 'Daily paper', 'Who built what, the day, the verdicts', 'today', 'brief', 'news newspaper paper today changes what changed', ''],
    ['delphi', 'delphi/', 'Delphi', 'Go or no-go', 'The plan, the target and go / no-go for today', 'today', 'brief', 'go no go plan target oracle', 'helios'],
    ['forum', 'forum/', 'Forum', 'Market morning notes', 'The briefing at the real New York hour', 'today', 'brief', 'market morning briefing new york open', 'helios'],
    ['pythia', 'pythia/', 'Pythia', 'Risk calendar', 'The next 14 days of news, and what the bots do', 'today', 'market', 'news events cpi fomc nfp calendar economic week schedule', ''],
    ['kairos', 'kairos/', 'Kairos', "The bots' day", 'A 24-hour ring: what the bots do now', 'today', 'market', 'clock schedule hours timeline day window', ''],
    ['oracle', 'oracle/', 'Oracle', 'Market radar', 'The market, live', 'today', 'market', 'market radar live price vix', ''],
    ['pantheon', 'pantheon/', 'Pantheon', 'Market mood', 'Rates, liquidity and fear', 'today', 'market', 'rates liquidity fear vix macro mood', ''],
    ['pheme', 'pheme/', 'Pheme', 'News days', "Releases, and NQ's past moves on them", 'today', 'market', 'news releases cpi fomc moves reaction', 'pythia'],
    ['chronos', 'chronos/', 'Chronos', 'Session clock', 'Time and the trading sessions', 'today', 'market', 'time session clock london new york asia hours', 'kairos'],
    // ---- Bots & Evals: each account, its drawdown, trades and pass odds
    ['nq', 'nq/', 'NQ', 'Bots right now', 'Is each bot on, drawdown left, the last trades', 'bots', 'bots', 'bots bot status zlarior atlas blitz lit running pc drawdown trades nq ninjatrader', ''],
    ['today', '', 'Dashboard', 'Full NQ dashboard', 'The full NQ dashboard: today, trades, results', 'bots', 'bots', 'dashboard zenith home main board results today nq bot', ''],
    ['argus', 'argus/', 'Argus', 'What to fix', 'The hundred eyes: problems worth fixing', 'bots', 'bots', 'fix problems issues bugs health lights', ''],
    ['aegis', 'aegis/', 'Aegis', 'Risk guard', 'Drawdown left, and when to stop for the day', 'bots', 'risk', 'drawdown risk stop loss max loss limit safe danger shield guard dll mll', ''],
    ['pnyx', 'pnyx/', 'Pnyx', 'Rules and risk calculator', 'Prop-firm rules, and stop to micros', 'bots', 'risk', 'rules calculator micros size contracts stop prop firm', ''],
    ['labyrinth', 'labyrinth/', 'Labyrinth', 'Size your eval', 'The risk maze: how big to trade', 'bots', 'risk', 'size sizing micros contracts risk eval', ''],
    ['demeter', 'demeter/', 'Demeter', 'Account health', 'Drawdown dials and payout rules', 'bots', 'risk', 'drawdown account health payout rules dials', 'aegis'],
    ['fates', 'fates/', 'Fates', 'Pass odds', 'The odds each eval passes', 'bots', 'odds', 'eval pass odds probability mffu chance', ''],
    ['moirai', 'moirai/', 'Moirai', 'Eval simulator', 'Pass, bust and time of an eval, simulated', 'bots', 'odds', 'eval simulate monte carlo pass bust', ''],
    ['odeon', 'odeon/', 'Odeon', 'Trade replays', 'Every trade, replayed in 3D', 'bots', 'trades', 'trades history replay chart past fills', ''],
    ['nemesis', 'nemesis/', 'Nemesis', 'Losing trades', 'What went wrong, trade by trade', 'bots', 'trades', 'losses losers losing mistakes what went wrong', ''],
    ['kronos', 'kronos/', 'Kronos', 'P&L calendar', 'Daily P&L, best weekday and hour', 'bots', 'trades', 'pnl calendar days money daily', ''],
    ['apollo', 'apollo/', 'Apollo', 'Weekly review', "The week's review and one rule for next week", 'bots', 'review', 'weekly review week lessons rule', ''],
    ['journal', 'journal/', 'Mnemosyne', 'Trade journal', 'A 10-second journal: what your habits cost', 'bots', 'review', 'journal diary notes habits mistakes log mnemosyne', ''],
    ['kratos', 'kratos/', 'Kratos', 'Discipline score', 'A 0-100 score a day: plan, stop, size, hours', 'bots', 'review', 'discipline score rules habits', ''],
    ['epilogue', 'epilogue/', 'Epilogue', 'Your week in 60 seconds', 'The Sunday review', 'bots', 'review', 'week sunday review summary', 'apollo'],
    // ---- Kalshi: the Kalshi bot, its bets and its edges
    ['kalshi', 'kalshi/', 'Kalshi', 'Kalshi bot', 'Balance, open bets and P&L, from your PC', 'kalshi', 'bot', 'kalshi bets prediction market balance', ''],
    ['dionysus', 'dionysus/', 'Dionysus', 'Kalshi desk', 'Guard, what-if and scan (suggestions only)', 'kalshi', 'edges', 'kalshi desk scan what if guard', ''],
    ['sibyl', 'sibyl/', 'Sibyl', 'Prediction-market picks', 'Edges after fees, paper picks only', 'kalshi', 'edges', 'kalshi polymarket picks edges prediction', 'dionysus'],
    // ---- My Money: cash, payouts, plans, net worth
    ['ledger', 'ledger/', 'Ledger', 'Your real money', 'Fees, payouts and net profit', 'money', 'real', 'money fees payouts profit net cost spend paid scoreboard cash net worth', ''],
    ['harmonia', 'harmonia/', 'Harmonia', 'Balance check', 'What leans on the NQ bots, and what is left', 'money', 'real', 'balance diversify income spread', ''],
    ['hermes', 'hermes/', 'Hermes', 'Money, wrapped', 'Your money story, wrapped', 'money', 'real', 'wrapped story summary year', 'ledger'],
    ['hera', 'hera/', 'Hera', '12-month money plan', 'Payouts, and what to buy next', 'money', 'plan', 'money plan payouts budget year buy next', ''],
    ['chrysos', 'chrysos/', 'Chrysos', 'Prop-firm planner', 'Fees against payouts, break-even', 'money', 'plan', 'prop firm mffu accounts fees eval cost fleet', ''],
    ['argo', 'argo/', 'Argo', 'Money goals', 'Your goals as islands, honest ETAs', 'money', 'plan', 'goals targets savings eta', ''],
    ['plutus', 'plutus/', 'Plutus', 'Accounts and payouts', 'The money plan: accounts and payouts', 'money', 'plan', 'accounts payouts plan', 'hera'],
    ['oikos', 'oikos/', 'Oikos', 'Household money', 'Leaks, tax set-aside and buckets', 'money', 'home', 'budget tax spending household bills buckets', ''],
    ['mint', 'mint/', 'Mint', 'Money machine', 'Five money streams, one honest estimate', 'money', 'ideas', 'money income earn streams estimate side', ''],
    ['mercury', 'mercury/', 'Mercury', 'Deals and codes', 'Sales, discount codes, free resets', 'money', 'ideas', 'discount coupon promo code sale deal reset price', ''],
    ['arbiter', 'arbiter/', 'Arbiter', 'Spreads and funding', 'Paper-only spreads: net yearly return', 'money', 'ideas', 'spreads funding arbitrage crypto yield', ''],
    // ---- Plan & Day: calendar, shifts, tasks, habits
    ['planner', 'planner/', 'Planner', 'Day and week plan', 'Sessions, shifts, tasks, habits and notes', 'plan', 'plan', 'calendar tasks todo habits schedule plan focus shift work', ''],
    ['mind', 'mind/', 'Mind', 'Your notes as a brain', 'Your vault as a living 3D brain', 'plan', 'plan', 'obsidian notes vault memory brain', ''],
    ['lyceum', 'lyceum/', 'Lyceum', 'Daily rules quiz', 'Quiz, ranks and the habits that cost money', 'plan', 'habits', 'quiz learn school rules test', ''],
    ['nike', 'nike/', 'Nike', 'Trophy hall', 'Milestones and wins from real numbers', 'plan', 'habits', 'trophies wins achievements milestones', ''],
    ['arena', 'arena/', 'Arena', 'Ranks and XP', 'XP for discipline', 'plan', 'habits', 'xp level rank game points', 'lyceum'],
    // ---- Research: backtests, edges, write-ups
    ['archive', 'archive/', 'Archive', 'Everything we tested', 'The searchable library of every test', 'research', 'library', 'research tests backtests library search experiments', ''],
    ['clio', 'clio/', 'Clio', 'Research in plain words', 'Every study, explained', 'research', 'library', 'research studies writeups explained', ''],
    ['athena', 'athena/', 'Athena', 'Strategy library', 'The strategy, the rules and a quiz', 'research', 'library', 'strategy rules lit learn library', ''],
    ['hephaestus', 'hephaestus/', 'Hephaestus', 'Tune the dials', 'Try the settings and see the result', 'research', 'search', 'tune settings dials parameters backtest', ''],
    ['prometheus', 'prometheus/', 'Prometheus', 'Strategy forge', 'Strategies tested in the forge', 'research', 'search', 'strategies forge tested', ''],
    ['tree', 'tree/', 'Daphne', 'Strategy search', 'The strategy tree search', 'research', 'search', 'strategy search tree daphne', ''],
    ['observatory', 'observatory/', 'Observatory', 'Data health', 'Data health and research evidence', 'research', 'data', 'data health evidence', ''],
    ['pinakes', 'pinakes/', 'Pinakes', 'Every data table', 'Browse and query every table OLYMPUS keeps', 'research', 'data', 'data tables database query catalogue', ''],
    // ---- Jarvis: ask anything, your AI team
    ['jarvis', 'jarvis/', 'Jarvis', 'Jarvis', 'Ask anything: your home screen and the orb', 'jarvis', 'ask', 'assistant ask voice home orb chat ai', ''],
    ['bridge', 'bridge/', 'Bridge', 'Link ChatGPT', '3 steps to link ChatGPT, and live job status', 'jarvis', 'ask', 'chatgpt gpt openai link ai jobs', ''],
    ['ergasterion', 'ergasterion/', 'Ergasterion', 'Your AI workers', 'Every AI worker, what it does and learns', 'jarvis', 'team', 'agents workers ai factory workshop floor', ''],
    ['symposium', 'symposium/', 'Symposium', 'Meet your workers', 'Everyone who works for you; talk to them', 'jarvis', 'team', 'characters people agents talk hall', 'ergasterion'],
    // ---- Worlds: the 3D places (optional)
    ['polis', 'polis/', 'Polis', 'The city', 'Every app a building under the real sky', 'worlds', 'top', 'city 3d world acropolis buildings', ''],
    ['cities', 'cities/', 'Cities', 'Cities and Hellas', 'Athens and the city islands of your research', 'worlds', 'top', 'cities hellas athens islands 3d', ''],
    ['colosseum', 'colosseum/', 'Colosseum', 'Strategy duels', 'Strategies fight on real stored numbers', 'worlds', 'top', 'duel fight strategies battle', ''],
    ['kalshicity', 'kalshicity/', 'Kalshi City', 'Kalshi City', "The Kalshi bot's edges as a night city", 'worlds', 'views', 'kalshi city 3d', ''],
    ['tyche', 'tyche/', 'Tyche', 'Fortune wheel', 'The Kalshi bets as a 3D wheel', 'worlds', 'views', 'kalshi wheel bets 3d', 'kalshicity'],
    ['mintcity', 'mintcity/', 'Mint City', 'Mint City', 'The money machines as a marble city', 'worlds', 'views', 'money city 3d', ''],
    ['datacity', 'datacity/', 'Data City', 'Data City', 'Every combo tested, as a city', 'worlds', 'views', 'data combos city 3d research', ''],
    ['atlascity', 'atlascity/', 'ATLAS City', 'ATLAS City', "ATLAS's three strategies as a city", 'worlds', 'views', 'atlas strategy city 3d', ''],
    // ---- Settings & Help: look, the PC, every app, the workshop
    ['settings', 'settings/', 'Settings', 'Settings', 'Look, voice, storage and the tour', 'settings', 'settings', 'settings theme voice sound storage tour options look', ''],
    ['pc', 'pc/', 'PC', 'Start the bot on this PC', 'The steps to start the bot on your PC', 'settings', 'settings', 'pc windows start bot ninjatrader setup install', ''],
    ['atlas', 'atlas/', 'Atlas', 'The old map of apps', 'Every OLYMPUS app by the old districts', 'settings', 'help', 'map apps list all directory', ''],
    ['gallery', 'gallery/', 'Agora Gallery', 'Agora Gallery', 'Every 3D shape on a turning pedestal', 'settings', 'workshop', 'shapes 3d gallery models', ''],
    ['agora-lab', 'olympus/agora-lab.html', 'Design Lab', 'Design Lab', 'The look every app shares', 'settings', 'workshop', 'design look lab', ''],
    ['env-lab', 'olympus/env-lab.html', 'Places Lab', 'Places Lab', 'Marble, stone, bronze, golden light', 'settings', 'workshop', 'places environment lab', ''],
    ['fx-lab', 'olympus/fx-lab.html', 'Effects Lab', 'Effects Lab', 'Every light, sky, sea, fire and burst', 'settings', 'workshop', 'effects fx lab', ''],
    ['sfx-lab', 'olympus/sfx-lab.html', 'Sound Lab', 'Sound Lab', 'Every sound, place and harp tune', 'settings', 'workshop', 'sound audio sfx lab', ''],
    ['people-lab', 'olympus/people-lab.html', 'People Lab', 'People Lab', 'Every character, faces and poses', 'settings', 'workshop', 'people characters lab', ''],
    ['polis-lab', 'olympus/polis-lab.html', 'Greek Look Kit', 'Greek Look Kit', 'Greek key, columns, pottery, coins', 'settings', 'workshop', 'greek kit polis lab', ''],
    ['polis-life-lab', 'olympus/polis-life-lab.html', 'Polis Life Lab', 'Polis Life Lab', 'People walking the city', 'settings', 'workshop', 'polis life people lab', ''],
    ['render-lab', 'olympus/render-lab.html', 'Render Lab', 'Render Lab', 'The 3D render core on test', 'settings', 'workshop', 'render 3d lab', '']
  ];
  /* the nine hubs, in the order of the home screen. q = the question the hub answers (the owner's words); legacy = the v1 district it mostly
     replaces (for a theme that still keys on the old four); see = apps filed in another hub that also belong here (shown as "In other hubs") */
  var HUBS = [
    { id: 'today', name: 'Today', q: 'What is happening, and what do I do now?', line: 'Do now, the morning brief, news and the clock', icon: 'sun', legacy: 'trading',
      sections: [['now', 'Do now', 'The few things that need you today'], ['brief', 'Morning brief', 'How today looks, in one read'], ['market', 'News and market', 'News days, the clock and the market mood']],
      see: ['nq', 'aegis', 'planner'] },
    { id: 'bots', name: 'Bots & Evals', q: 'Are my bots on, and how is each eval doing?', line: 'Each account: drawdown, trades, pass odds', icon: 'bots', legacy: 'trading',
      sections: [['bots', 'Bots now', 'On or off, the last report, what to fix'], ['risk', 'Risk', 'Drawdown left, when to stop, how big to trade'], ['odds', 'Pass odds', 'The odds each eval passes, and how fast'],
        ['trades', 'Trades', 'Every trade, the losers, the P&L by day'], ['review', 'Review', 'The weekly review, the journal, discipline']],
      see: ['pythia', 'ledger'] },
    { id: 'kalshi', name: 'Kalshi', q: 'How is the Kalshi bot doing, and where is an edge?', line: 'The Kalshi bot, its bets and its edges', icon: 'kalshi', legacy: 'money',
      sections: [['bot', 'The bot', 'Balance, open bets and P&L'], ['edges', 'Edges', 'Where the bot could do better (suggestions only)']],
      see: ['kalshicity', 'tyche'] },
    { id: 'money', name: 'My Money', q: 'What have I really made and spent, and what is next?', line: 'Cash, payouts, plans and net worth', icon: 'money', legacy: 'money',
      sections: [['real', 'Real money', 'Fees, payouts, net: cash only'], ['plan', 'Plan and payouts', 'The 12-month plan, prop-firm costs, goals'], ['home', 'Household', 'Bills, leaks and tax set-aside'],
        ['ideas', 'Ideas and deals', 'Side streams and discount codes (estimates, not cash)']],
      see: ['kalshi', 'mintcity'] },
    { id: 'plan', name: 'Plan & Day', q: "What is on my calendar and my list?", line: 'Calendar, shifts, tasks, habits, notes', icon: 'plan', legacy: 'life',
      sections: [['plan', 'Calendar and tasks', 'Your day, week, shifts and notes'], ['habits', 'Habits and progress', 'The daily quiz, trophies and ranks']],
      see: ['pythia', 'kratos'] },
    { id: 'research', name: 'Research', q: 'What have we tested, and what works?', line: 'Backtests, edges and write-ups', icon: 'research', legacy: 'trading',
      sections: [['library', 'Library', 'Every test and every study, in plain words'], ['search', 'Strategy search', 'Tune the dials, the forge, the tree'], ['data', 'Data', 'Data health and every table']],
      see: ['colosseum', 'datacity', 'atlascity'] },
    { id: 'jarvis', name: 'Jarvis', q: 'Ask anything. Who works for me?', line: 'Ask anything; your AI team', icon: 'jarvis', legacy: 'life',
      sections: [['ask', 'Ask', 'Jarvis, and the link to ChatGPT'], ['team', 'Your AI team', 'Every AI worker and what it learns']],
      see: ['mind'] },
    { id: 'worlds', name: 'Worlds', q: 'The 3D places (optional, for fun)', line: 'The 3D city, duels and night cities', icon: 'worlds', legacy: 'worlds',
      sections: [['top', 'Most visited', 'The city, the islands, the duels'], ['views', 'Numbers as places', 'Kalshi, money, data and ATLAS as cities']],
      see: ['odeon', 'symposium'] },
    { id: 'settings', name: 'Settings & Help', q: 'Change the look, start the PC, find any app', line: 'Look, the PC, every app, the workshop', icon: 'settings', legacy: 'life',
      sections: [['settings', 'Settings', 'Look, voice, storage, and the PC'], ['help', 'Help and every app', 'Every app A to Z, and the old map'], ['workshop', 'Workshop', 'Labs and test pages (for building, not daily use)']],
      see: [] }
  ];
  var apps = R.map(function (r, i) {
    return Object.freeze({ id: r[0], path: r[1], name: r[2], label: r[3], line: r[4], district: r[5], hub: r[5], section: r[6], words: r[7], fold: r[8] || '', rank: i });
  });
  var BY = {}, HB = {}, BEST = {};
  apps.forEach(function (a) { BY[a.id] = a; var k = a.hub + '/' + a.section; if (!BEST[k] && !a.fold) BEST[k] = a.id; });
  HUBS.forEach(function (h) { HB[h.id] = h; h.count = apps.filter(function (a) { return a.hub === h.id; }).length; Object.freeze(h); });
  var DNAME = {};
  HUBS.forEach(function (h) { DNAME[h.id] = h.name.toLowerCase(); });
  function norm(s) { return String(s || '').toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9&$]+/g, ' ').replace(/^\s+|\s+$/g, ''); }
  function wordStarts(text, t) { var w = text.split(' '); for (var i = 0; i < w.length; i++) if (w[i].indexOf(t) === 0) return true; return false; }
  function isBest(a) { return !!a && BEST[a.hub + '/' + a.section] === a.id; }
  /** search by name, plain label, purpose and synonyms. Every word typed must match somewhere; best first. -> [app] */
  function find(q, n) {
    var toks = norm(q).split(' ').filter(function (t) { return t.length > 0; });
    if (!toks.length) return [];
    var hits = [];
    apps.forEach(function (a) {
      var label = norm(a.label), name = norm(a.name), line = norm(a.line), words = norm(a.words + ' ' + a.id), score = 0;
      for (var i = 0; i < toks.length; i++) {
        var t = toks[i], s = 0;
        if (label.indexOf(t) === 0 || name.indexOf(t) === 0) s = 40;
        else if (wordStarts(label, t) || wordStarts(name, t)) s = 26;
        else if (wordStarts(words, t)) s = 16;
        else if (t.length > 2 && (line.indexOf(t) >= 0 || label.indexOf(t) >= 0 || name.indexOf(t) >= 0)) s = 9;
        else if (DNAME[a.hub] && wordStarts(DNAME[a.hub], t)) s = 4;
        if (!s) return;
        score += s;
      }
      if (isBest(a)) score += 10;
      if (a.fold) score -= 3;
      if (a.section === 'workshop') score -= 12;
      hits.push({ a: a, s: score });
    });
    hits.sort(function (x, y) { return y.s - x.s || x.a.rank - y.a.rank; });
    return hits.slice(0, n || 8).map(function (h) { return h.a; });
  }
  function byId(id) { return BY[id] || null; }
  function hubOf(id) { var a = BY[id]; return a ? HB[a.hub] : null; }      // the hub an APP lives in
  function hub(id) { return HB[id] || null; }                               // a hub by its own id
  /** one hub, laid out: [{ id, title, blurb, best, peers: [app], folded: [app] }] (best = the section's best version; folded = its duplicates) */
  function layout(hid) {
    var h = HB[hid]; if (!h) return [];
    return h.sections.map(function (s) {
      var list = apps.filter(function (a) { return a.hub === hid && a.section === s[0]; });
      var best = BY[BEST[hid + '/' + s[0]]] || list[0] || null;
      return { id: s[0], title: s[1], blurb: s[2], best: best, peers: list.filter(function (a) { return a !== best && !a.fold; }), folded: list.filter(function (a) { return !!a.fold; }) };
    });
  }
  /** where an app sits: the hub page link (relative to the site root) and the words of the breadcrumb */
  function crumbOf(id) {
    var a = BY[id], h = a && HB[a.hub]; if (!h) return null;
    var sec = null; for (var i = 0; i < h.sections.length; i++) if (h.sections[i][0] === a.section) sec = h.sections[i];
    return { hub: h.id, hubName: h.name, section: a.section, sectionName: sec ? sec[1] : '', path: 'hub/index.html?h=' + h.id + '&t=' + a.section, app: a.label };
  }
  var out = Object.freeze({ v: 2, apps: Object.freeze(apps), districts: HUBS, hubs: HUBS, start: ['nq', 'today', 'jarvis'],
    find: find, byId: byId, norm: norm, hub: hub, hubOf: hubOf, layout: layout, crumbOf: crumbOf, isBest: isBest, mixOf: function (id) { var h = hubOf(id); return h ? h.id : ''; } });
  g.OLYMPUS_GATE = out;
  if (typeof module !== 'undefined' && module.exports) module.exports = out;
}(typeof window !== 'undefined' ? window : globalThis));
