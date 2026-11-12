/* OLYMPUS Gate catalog (2026-11-12): every app in plain words, for the Gate (gate/) and the "Go to..." sheet (olympus/gate-nav.js).
 * Owner: "When I click the dashboard link there's just a shit ton of buttons ... make something that's very easy on how to get to things."
 * One row per app: [id, path from the site root ('' = the dashboard), Greek name, plain label (what the owner reads first), one-line purpose,
 *   district ('start' | 'trading' | 'money' | 'life' | 'worlds' | 'workshop'), section inside the district, extra search words].
 * Order inside a district = most useful first. Classic script (ES5), no network, no DOM: window.OLYMPUS_GATE (and module.exports in node).
 * tests/test_gate_page.py checks every app folder and every row of olympus/apps-list.js is here exactly once. */
(function (g) {
  'use strict';
  var R = [
    // ---- start here (1 tap from the Gate)
    ['today', '', 'Dashboard', 'Today', 'The full NQ dashboard: today, trades, results', 'start', 'start', 'dashboard zenith home main board results today nq bot'],
    ['nq', 'nq/', 'NQ', 'Bots right now', 'Is each bot on, drawdown left, the last trades', 'trading', 'top', 'bots bot status zlarior atlas blitz lit running pc drawdown trades nq ninjatrader'],
    ['jarvis', 'jarvis/', 'Jarvis', 'Jarvis', 'Ask anything: your home screen and the orb', 'start', 'start', 'assistant ask voice home orb chat ai'],
    // ---- trading
    ['helios', 'helios/', 'Helios', 'Morning briefing', 'Today in one scroll: drawdown, deals, the plan', 'trading', 'top', 'morning briefing brief today plan summary sun'],
    ['aegis', 'aegis/', 'Aegis', 'Risk guard', 'Drawdown left, and when to stop for the day', 'trading', 'top', 'drawdown risk stop loss max loss limit safe danger shield guard dll mll'],
    ['pythia', 'pythia/', 'Pythia', 'Risk calendar', 'The next 14 days of news, and what the bots do', 'trading', 'top', 'news events cpi fomc nfp calendar economic week schedule'],
    ['compass', 'compass/', 'Compass', 'What to do next', 'At most five things for today, with why', 'trading', 'top', 'todo to do tasks actions next priorities'],
    ['odeon', 'odeon/', 'Odeon', 'Trade replays', 'Every trade, replayed in 3D', 'trading', 'top', 'trades history replay chart past fills'],
    ['stoa', 'stoa/', 'Stoa', 'Needs you now', 'What needs a look right now', 'trading', 'day', 'attention alerts urgent now'],
    ['delphi', 'delphi/', 'Delphi', 'Go or no-go', 'The plan, the target and go / no-go for today', 'trading', 'day', 'go no go plan target oracle'],
    ['ares', 'ares/', 'Ares', 'War room', 'GO, WAIT or HALT for the bots', 'trading', 'day', 'go wait halt war room status'],
    ['kairos', 'kairos/', 'Kairos', "The bots' day", 'A 24-hour ring: what the bots do now', 'trading', 'day', 'clock schedule hours timeline day'],
    ['hestia', 'hestia/', 'Hestia', 'Today at home', 'What to do right now, at home', 'trading', 'day', 'today home now'],
    ['forum', 'forum/', 'Forum', 'Market morning notes', 'The briefing at the real New York hour', 'trading', 'day', 'market morning briefing new york open'],
    ['chronos', 'chronos/', 'Chronos', 'Session clock', 'Time and the trading sessions', 'trading', 'day', 'time session clock london new york asia hours'],
    ['pheme', 'pheme/', 'Pheme', 'News days', "Releases, and NQ's past moves on them", 'trading', 'day', 'news releases cpi fomc moves reaction'],
    ['oracle', 'oracle/', 'Oracle', 'Market radar', 'The market, live', 'trading', 'day', 'market radar live price vix'],
    ['pantheon', 'pantheon/', 'Pantheon', 'Market mood', 'Rates, liquidity and fear', 'trading', 'day', 'rates liquidity fear vix macro mood'],
    ['journal', 'journal/', 'Mnemosyne', 'Trade journal', 'A 10-second journal: what your habits cost', 'trading', 'back', 'journal diary notes habits mistakes log mnemosyne'],
    ['apollo', 'apollo/', 'Apollo', 'Weekly review', "The week's review and one rule for next week", 'trading', 'back', 'weekly review week lessons rule'],
    ['demeter', 'demeter/', 'Demeter', 'Account health', 'Drawdown dials and payout rules', 'trading', 'back', 'drawdown account health payout rules dials'],
    ['kratos', 'kratos/', 'Kratos', 'Discipline score', 'A 0-100 score a day: plan, stop, size, hours', 'trading', 'back', 'discipline score rules habits'],
    ['nemesis', 'nemesis/', 'Nemesis', 'Losing trades', 'What went wrong, trade by trade', 'trading', 'back', 'losses losers losing mistakes what went wrong'],
    ['argus', 'argus/', 'Argus', 'What to fix', 'The hundred eyes: problems worth fixing', 'trading', 'back', 'fix problems issues bugs health'],
    ['fates', 'fates/', 'Fates', 'Pass odds', 'The odds each eval passes', 'trading', 'eval', 'eval pass odds probability mffu chance'],
    ['moirai', 'moirai/', 'Moirai', 'Eval simulator', 'Pass, bust and time of an eval, simulated', 'trading', 'eval', 'eval simulate monte carlo pass bust'],
    ['labyrinth', 'labyrinth/', 'Labyrinth', 'Size your eval', 'The risk maze: how big to trade', 'trading', 'eval', 'size sizing micros contracts risk eval'],
    ['archive', 'archive/', 'Archive', 'Everything we tested', 'The searchable library of every test', 'trading', 'research', 'research tests backtests library search experiments'],
    ['clio', 'clio/', 'Clio', 'Research in plain words', 'Every study, explained', 'trading', 'research', 'research studies writeups explained'],
    ['tree', 'tree/', 'Daphne', 'Strategy search', 'The strategy tree search', 'trading', 'research', 'strategy search tree daphne'],
    ['prometheus', 'prometheus/', 'Prometheus', 'Strategy forge', 'Strategies tested in the forge', 'trading', 'research', 'strategies forge tested'],
    ['hephaestus', 'hephaestus/', 'Hephaestus', 'Tune the dials', 'Try the settings and see the result', 'trading', 'research', 'tune settings dials parameters'],
    ['observatory', 'observatory/', 'Observatory', 'Data health', 'Data health and research evidence', 'trading', 'research', 'data health evidence'],
    ['pinakes', 'pinakes/', 'Pinakes', 'Every data table', 'Browse and query every table OLYMPUS keeps', 'trading', 'research', 'data tables database query catalogue'],
    ['bridge', 'bridge/', 'Bridge', 'Link ChatGPT', '3 steps to link ChatGPT, and live job status', 'trading', 'research', 'chatgpt gpt openai link ai jobs'],
    // ---- money
    ['mint', 'mint/', 'Mint', 'Money machine', 'Five money streams, one honest estimate', 'money', 'top', 'money income earn streams estimate side'],
    ['ledger', 'ledger/', 'Ledger', 'Your real money', 'Fees, payouts and net profit', 'money', 'top', 'money fees payouts profit net cost spend paid'],
    ['hera', 'hera/', 'Hera', '12-month money plan', 'Payouts, and what to buy next', 'money', 'top', 'money plan payouts budget year buy next'],
    ['kalshi', 'kalshi/', 'Kalshi', 'Kalshi bot', 'Balance, open bets and P&L, from your PC', 'money', 'top', 'kalshi bets prediction market balance'],
    ['chrysos', 'chrysos/', 'Chrysos', 'Prop-firm planner', 'Fees against payouts, break-even', 'money', 'top', 'prop firm mffu accounts fees eval cost fleet'],
    ['pnyx', 'pnyx/', 'Pnyx', 'Rules and risk calculator', 'Prop-firm rules, and stop to micros', 'money', 'top', 'rules calculator micros size contracts stop prop firm'],
    ['sibyl', 'sibyl/', 'Sibyl', 'Prediction-market picks', 'Edges after fees, paper picks only', 'money', 'more', 'kalshi polymarket picks edges prediction'],
    ['dionysus', 'dionysus/', 'Dionysus', 'Kalshi desk', 'Guard, what-if and scan (suggestions only)', 'money', 'more', 'kalshi desk scan what if'],
    ['mercury', 'mercury/', 'Mercury', 'Deals and codes', 'Sales, discount codes, free resets', 'money', 'more', 'discount coupon promo code sale deal reset price'],
    ['oikos', 'oikos/', 'Oikos', 'Household money', 'Leaks, tax set-aside and buckets', 'money', 'more', 'budget tax spending household bills buckets'],
    ['kronos', 'kronos/', 'Kronos', 'Money calendar', 'Daily P&L, best weekday and hour', 'money', 'more', 'pnl calendar days money daily'],
    ['argo', 'argo/', 'Argo', 'Money goals', 'Your goals as islands, honest ETAs', 'money', 'more', 'goals targets savings eta'],
    ['plutus', 'plutus/', 'Plutus', 'Accounts and payouts', 'The money plan: accounts and payouts', 'money', 'more', 'accounts payouts plan'],
    ['hermes', 'hermes/', 'Hermes', 'Money, wrapped', 'Your money story, wrapped', 'money', 'more', 'wrapped story summary year'],
    ['harmonia', 'harmonia/', 'Harmonia', 'Balance check', 'What leans on the NQ bots, and what is left', 'money', 'more', 'balance diversify income spread'],
    ['arbiter', 'arbiter/', 'Arbiter', 'Spreads and funding', 'Paper-only spreads: net yearly return', 'money', 'more', 'spreads funding arbitrage crypto yield'],
    // ---- life
    ['planner', 'planner/', 'Planner', 'Day and week plan', 'Sessions, tasks, habits and notes', 'life', 'top', 'calendar tasks todo habits schedule plan focus'],
    ['inbox', 'inbox/', 'Inbox', 'Inbox', 'Everything that needs a look, in one place', 'life', 'top', 'alerts messages notifications inbox'],
    ['herald', 'herald/', 'Herald', 'Daily paper', 'Who built what, the day, the verdicts', 'life', 'top', 'news newspaper paper today changes what changed'],
    ['settings', 'settings/', 'Settings', 'Settings', 'Look, voice, storage and the tour', 'life', 'top', 'settings theme voice sound storage tour options'],
    ['epilogue', 'epilogue/', 'Epilogue', 'Your week in 60 seconds', 'The Sunday review', 'life', 'more', 'week sunday review summary'],
    ['lyceum', 'lyceum/', 'Lyceum', 'Daily rules quiz', 'Quiz, ranks and the habits that cost money', 'life', 'more', 'quiz learn school rules test'],
    ['athena', 'athena/', 'Athena', 'Strategy library', 'The strategy, the rules and a quiz', 'life', 'more', 'strategy rules lit learn library'],
    ['mind', 'mind/', 'Mind', 'Your notes as a brain', 'Your vault as a living 3D brain', 'life', 'more', 'obsidian notes vault memory brain'],
    ['nike', 'nike/', 'Nike', 'Trophy hall', 'Milestones and wins from real numbers', 'life', 'more', 'trophies wins achievements milestones'],
    ['arena', 'arena/', 'Arena', 'Ranks and XP', 'XP for discipline', 'life', 'more', 'xp level rank game points'],
    ['atlas', 'atlas/', 'Atlas', 'Map of every app', 'Every OLYMPUS app by district', 'life', 'more', 'map apps list all directory'],
    ['pc', 'pc/', 'PC', 'Start the bot on this PC', 'The steps to start the bot on your PC', 'life', 'more', 'pc windows start bot ninjatrader setup install'],
    // ---- worlds (the 3D places)
    ['polis', 'polis/', 'Polis', 'The city', 'Every app a building under the real sky', 'worlds', 'top', 'city 3d world acropolis buildings'],
    ['symposium', 'symposium/', 'Symposium', 'Meet your workers', 'Everyone who works for you; talk to them', 'worlds', 'top', 'characters people agents talk hall'],
    ['ergasterion', 'ergasterion/', 'Ergasterion', 'The workshop floor', 'Every AI worker, what it does and learns', 'worlds', 'top', 'agents workers ai factory workshop'],
    ['cities', 'cities/', 'Cities', 'Cities and Hellas', 'Athens and the city islands of your research', 'worlds', 'top', 'cities hellas athens islands 3d'],
    ['colosseum', 'colosseum/', 'Colosseum', 'Strategy duels', 'Strategies fight on real stored numbers', 'worlds', 'more', 'duel fight strategies battle'],
    ['mintcity', 'mintcity/', 'Mint City', 'Mint City', 'The money machines as a marble city', 'worlds', 'more', 'money city 3d'],
    ['kalshicity', 'kalshicity/', 'Kalshi City', 'Kalshi City', "The Kalshi bot's edges as a night city", 'worlds', 'more', 'kalshi city 3d'],
    ['atlascity', 'atlascity/', 'ATLAS City', 'ATLAS City', "ATLAS's three strategies as a city", 'worlds', 'more', 'atlas strategy city 3d'],
    ['datacity', 'datacity/', 'Data City', 'Data City', 'Every combo tested, as a city', 'worlds', 'more', 'data combos city 3d research'],
    ['tyche', 'tyche/', 'Tyche', 'Fortune wheel', 'The Kalshi bets as a 3D wheel', 'worlds', 'more', 'kalshi wheel bets 3d'],
    ['gallery', 'gallery/', 'Agora Gallery', 'Agora Gallery', 'Every 3D shape on a turning pedestal', 'worlds', 'more', 'shapes 3d gallery models'],
    // ---- the workshop (labs and dev pages: hidden behind the small Workshop link)
    ['agora-lab', 'olympus/agora-lab.html', 'Design Lab', 'Design Lab', 'The look every app shares', 'workshop', 'labs', 'design look lab'],
    ['env-lab', 'olympus/env-lab.html', 'Places Lab', 'Places Lab', 'Marble, stone, bronze, golden light', 'workshop', 'labs', 'places environment lab'],
    ['fx-lab', 'olympus/fx-lab.html', 'Effects Lab', 'Effects Lab', 'Every light, sky, sea, fire and burst', 'workshop', 'labs', 'effects fx lab'],
    ['sfx-lab', 'olympus/sfx-lab.html', 'Sound Lab', 'Sound Lab', 'Every sound, place and harp tune', 'workshop', 'labs', 'sound audio sfx lab'],
    ['people-lab', 'olympus/people-lab.html', 'People Lab', 'People Lab', 'Every character, faces and poses', 'workshop', 'labs', 'people characters lab'],
    ['polis-lab', 'olympus/polis-lab.html', 'Greek Look Kit', 'Greek Look Kit', 'Greek key, columns, pottery, coins', 'workshop', 'labs', 'greek kit polis lab'],
    ['polis-life-lab', 'olympus/polis-life-lab.html', 'Polis Life Lab', 'Polis Life Lab', 'People walking the city', 'workshop', 'labs', 'polis life people lab'],
    ['render-lab', 'olympus/render-lab.html', 'Render Lab', 'Render Lab', 'The 3D render core on test', 'workshop', 'labs', 'render 3d lab']
  ];
  var DISTRICTS = [
    { id: 'trading', name: 'Trading', line: 'The bots, risk, the day and the research', sections: [['top', 'Most useful'], ['day', 'During the day'], ['back', 'Looking back'], ['eval', 'Evals and odds'], ['research', 'Research']] },
    { id: 'money', name: 'Money', line: 'Your real money, plans, deals and Kalshi', sections: [['top', 'Most useful'], ['more', 'More money tools']] },
    { id: 'life', name: 'Life', line: 'Plan, inbox, the daily paper, settings', sections: [['top', 'Most useful'], ['more', 'More']] },
    { id: 'worlds', name: 'Worlds', line: 'The 3D places: city, workers, duels', sections: [['top', 'Most visited'], ['more', 'More worlds']] },
    { id: 'workshop', name: 'Workshop', line: 'Labs and test pages (for building, not daily use)', sections: [['labs', 'Labs']] }
  ];
  var apps = R.map(function (r, i) {
    return Object.freeze({ id: r[0], path: r[1], name: r[2], label: r[3], line: r[4], district: r[5], section: r[6], words: r[7], rank: i });
  });
  var DNAME = {};
  DISTRICTS.forEach(function (d) { DNAME[d.id] = d.name.toLowerCase(); });
  DNAME.start = 'start';
  function norm(s) { return String(s || '').toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9&$]+/g, ' ').replace(/^\s+|\s+$/g, ''); }
  function wordStarts(text, t) { var w = text.split(' '); for (var i = 0; i < w.length; i++) if (w[i].indexOf(t) === 0) return true; return false; }
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
        else if (DNAME[a.district] && DNAME[a.district].indexOf(t) === 0) s = 4;
        if (!s) return;
        score += s;
      }
      if (a.section === 'top' || a.district === 'start') score += 10;
      if (a.district === 'workshop') score -= 12;
      hits.push({ a: a, s: score });
    });
    hits.sort(function (x, y) { return y.s - x.s || x.a.rank - y.a.rank; });
    return hits.slice(0, n || 8).map(function (h) { return h.a; });
  }
  function byId(id) { for (var i = 0; i < apps.length; i++) if (apps[i].id === id) return apps[i]; return null; }
  var out = Object.freeze({ v: 1, apps: Object.freeze(apps), districts: DISTRICTS, start: ['today', 'nq', 'jarvis'], find: find, byId: byId, norm: norm });
  g.OLYMPUS_GATE = out;
  if (typeof module !== 'undefined' && module.exports) module.exports = out;
}(typeof window !== 'undefined' ? window : globalThis));
