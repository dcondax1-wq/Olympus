// Calm layout (phone, 2026-10-25; loaded by index.html with one <script defer> LAST, after features.js; read-only UI).
// The owner: "too many buttons, make it look like a maid swept and cleaned it". Nothing is deleted, only moved:
//   Bottom bar   five tabs: Home · Trades · ATLAS · Money · More (Bot Brain lives under Home; #/brain still opens it)
//   Home         only what matters, in this order: the launch checklist (only while a line is not green), one hero card
//                per account (LIT 50K, ATLAS 25K: ONE big number = $ to the target, one line = room / sessions left, one
//                status chip), today's plan in one line, the last (or open) trade, then a short "One tap away" list.
//                Every card the old Home showed is still on #/homefull ("Full overview").
//   Sub-bar      a tab shows its 2-5 main pages (no long strips); every other page has a "‹ Home" / "‹ More" back button
//   More         one grouped list with search on top, each page once; research / technical pages sit under "Advanced",
//                collapsed by default (opens by itself while searching)
//   Look         calm cards (one style, 8-pt spacing), 44 px tap targets, readable numbers; 3D effects are off by default
//                (Settings > 3D effects turns them back on)
// Classic script that uses the main page's helpers (D, VIEWS, GROUPS, PAGES, P, icon, esc, usd, susd, store, et, cdFmt ...).
// Paper only, read-only: it never arms, routes or changes the bot.
(function () {
  'use strict';
  if (typeof GROUPS === 'undefined' || typeof VIEWS === 'undefined') return;
  window.CLEAN = { version: 1 };
  const HD = () => (typeof D !== 'undefined' && D) || window.HOMEJ || null;
  const nowS = () => Date.now() / 1000;
  const okN = (v) => v != null && v !== '' && !isNaN(v);
  const FRESH_S = 20 * 60;
  const LV = { good: 'good', warn: 'warn', bad: 'bad' };
  const lvOf = (l) => LV[l] || 'idle';
  const money = (v) => (okN(v) ? usd(Math.round(v)) : '—');
  const smoney = (v) => (okN(v) ? susd(Math.round(v)) : '—');

  // ------------------------------------------------------------------ small parts (one card style)
  const chipS = (txt, lvl) => `<span class="cl-chip ${lvOf(lvl)}">${esc(txt)}</span>`;
  const rowLink = (id, label, sub, ic) => `<button type="button" class="cl-row" data-go="${esc(id)}"><span class="cl-ri">${icon(ic || (PAGES[id] && PAGES[id].icon) || 'layers')}</span>
    <span class="cl-rt"><b>${esc(label)}</b>${sub ? `<em>${esc(sub)}</em>` : ''}</span>${icon('right', 'cl-go')}</button>`;

  // ------------------------------------------------------------------ Home: launch checklist (only while not all green)
  function launchCard() {
    const U = window.LaunchUI; if (!U || !U.model) return '';
    let M; try { M = U.model(); } catch (e) { return ''; }
    if (!M || M.all) return '';
    const red = M.items.filter((i) => i.state === 'bad');
    const show = red.slice(0, 3);
    return `<section class="card cl-card cl-launch" aria-label="Launch checklist"><div class="cl-h"><span class="cl-eye">Launch checklist</span>${chipS(`${M.good} of ${M.n} ready`, M.good === M.n ? 'good' : 'warn')}</div>
      <div class="cl-meter"><i style="width:${(M.good / Math.max(1, M.n) * 100).toFixed(1)}%"></i></div>
      <ul class="cl-todo">${show.map((i) => `<li><i class="cl-dot bad"></i><span>${esc(i.label)}</span></li>`).join('')}${red.length > show.length ? `<li class="mut"><i class="cl-dot"></i><span>and ${red.length - show.length} more</span></li>` : ''}</ul>
      <button type="button" class="cl-act" data-go="launch">See the fixes${icon('right')}</button></section>`;
  }

  // ------------------------------------------------------------------ Home: hero cards (LIT 50K, ATLAS 25K)
  function litAcct() {
    const h = HD() || {}, A = (h.accounts || []).filter((a) => a && a.id && !a.error);
    const pc = A.find((a) => a.source === 'pc'), cl = A.find((a) => a.source === 'cloud');
    return (pc && ((pc.conn && pc.conn.connected) || pc.eval)) ? pc : (cl || pc || null);
  }
  function goalsAcct(k) { const G = (HD() || {}).goals; return G && Array.isArray(G.accounts) ? G.accounts.find((a) => a && a.id === k) || null : null; }
  function litHero() {
    const h = HD() || {}, L = h.live || {}, v = L.pc_verdict || {}, a = litAcct(), e = (a && a.eval) || {}, g = goalsAcct('lit50k') || {};
    const target = okN(e.target_balance) && okN(e.start_balance) ? e.target_balance - e.start_balance : (g.profit_target || 3000);
    const toGo = okN(e.to_target) ? e.to_target : g.to_go;
    const prof = okN(e.profit) ? e.profit : g.profit;
    const prog = okN(prof) && target ? Math.max(0, Math.min(1, prof / target)) : 0;
    const room = okN(e.room) ? e.room : g.room;
    const left = okN(e.session) ? Math.max(0, (e.sessions || 10) - e.session + 1) : g.sessions_left;
    const lvl = v.level === 'good' ? 'good' : v.level === 'bad' ? 'bad' : 'warn';
    const status = v.label || (a && a.source === 'cloud' ? 'CLOUD PAPER' : 'CHECKING');
    const passed = okN(toGo) && toGo <= 0;
    const big = passed ? 'Passed' : okN(toGo) ? money(toGo) : '—';
    const line = [okN(room) ? `Room ${money(room)}` : '', okN(left) ? `${left} session${left === 1 ? '' : 's'} left` : ''].filter(Boolean).join(' · ');
    const H = window.HubParts || {};
    let surf = ''; try { surf = H.surfaceLine ? H.surfaceLine() : ''; } catch (er) { surf = ''; }
    const stopped = v.code === 'SILENT' || v.code === 'DISABLED' || (L.pc && L.pc.present && L.pc.running === false);
    return `<button type="button" class="card cl-card cl-hero ${lvl}" data-go="brain" aria-label="LIT 50K: ${esc(big)} to the target, ${esc(status)}">
      <span class="cl-h"><span class="cl-eye">LIT · 50K<em>${esc(a && a.source === 'cloud' ? 'MFFU Builder 50K · cloud paper' : 'MFFU Builder 50K')}</em></span>${chipS(status, lvl)}</span>
      <span class="cl-big"><b>${esc(big)}</b><em>${passed ? 'target reached' : `to the +${money(target)} target`}</em></span>
      <span class="cl-bar"><i style="width:${(prog * 100).toFixed(1)}%"></i></span>
      <span class="cl-line">${esc(line || 'eval not reporting yet')}</span>
      ${surf ? `<span class="cl-surf">${surf}</span>` : ''}
      ${stopped ? `<span class="cl-fix">On the Surface: <b>Bot Control → Start</b>. This app is read-only.</span>` : ''}</button>`;
  }
  function liveCut() { const h = HD(); return (h && h.live && h.live.pc && h.live.pc.second) || null; }
  function brainOf() {
    const h = HD(), U = window.SecondUI; if (!h || !U || !U.brainList) return null;
    const pc = liveCut();
    if (pc && pc.strategies && Object.keys(pc.strategies).length && nowS() - (+pc.t || 0) < FRESH_S) return U.brainList(pc, 'PC bot');
    if (h.second && (h.second.strategies || []).length) return U.brainList(h.second, 'cloud run');
    return pc ? U.brainList(pc, 'PC bot (not live)') : null;
  }
  function atlasHero() {
    const S = (HD() || {}).second || null, U = window.SecondUI, g = goalsAcct('atlas25k') || {};
    let c = null; try { c = U && U.atlasCard ? U.atlasCard(S, liveCut(), brainOf()) : null; } catch (e) { c = null; }
    c = c || { status: 'LOADING', lvl: '', prog: 0, progText: '' };
    const sc = ((S && S.scorecard) || {}).account_b || {};
    const onEval = /to pass/.test(c.progText || '');
    let big, sub, line;
    if (onEval) {
      const m = (c.progText || '').match(/^(\S+) to pass/);
      big = m ? m[1] : money(g.to_go); sub = `to the +${money(g.profit_target || 1500)} target`;
      line = (c.progText || '').replace(/^\S+ to pass\s*·?\s*/, '') || (okN(g.room) ? `Room ${money(g.room)}` : '');
      if (okN(g.room)) line = `Room ${money(g.room)}${line ? ' · ' + line : ''}`;
    } else {
      big = `${sc.n || 0} / ${sc.need || 20}`; sub = 'paper trades before go-live';
      line = g.status === 'not started' || !g.balance ? `25K not started · target +${money(g.profit_target || 1500)}` : (g.sentence || '');
    }
    return `<button type="button" class="card cl-card cl-hero ${lvOf(c.lvl)}" data-go="atlas" aria-label="ATLAS 25K: ${esc(big)} ${esc(sub)}, ${esc(c.status)}">
      <span class="cl-h"><span class="cl-eye">ATLAS · 25K<em>${esc(c.plan || 'MFFU Builder 25K')}</em></span>${chipS(c.status || '—', c.lvl)}</span>
      <span class="cl-big"><b>${esc(big)}</b><em>${esc(sub)}</em></span>
      <span class="cl-bar"><i style="width:${(Math.max(0, Math.min(1, +c.prog || 0)) * 100).toFixed(1)}%"></i></span>
      <span class="cl-line">${esc(line || '')}</span></button>`;
  }

  // ------------------------------------------------------------------ Home: today's plan in one line
  function planLine() {
    const h = HD() || {}, L = h.live || {}, Gs = window.GoalsUI;
    let C = null; try { C = Gs && Gs.todayFacts ? Gs.todayFacts() : null; } catch (e) { C = null; }
    let txt = '', cd = null;
    if (C) {
      if (C.inWin) { txt = `Entry window open · cut-off in `; cd = C.cut; }
      else { txt = `Next LIT window ${et(C.open).wd} 02:00 ET · in `; cd = C.open; }
    } else txt = L.model_state || 'Waiting for the next session';
    const cal = (h.goals && h.goals.calendar) || {}, today = (h.goals && h.goals.today) || et(nowS()).date;
    const newsT = (cal.news || []).filter((n) => n.day === today);
    const news = newsT.length ? `${newsT[0].time} ${newsT[0].event}${newsT.length > 1 ? ` +${newsT.length - 1}` : ''}` : 'no big US news';
    return `<button type="button" class="card cl-card cl-plan" data-go="plan"><span class="cl-ri">${icon('clock')}</span>
      <span class="cl-rt"><span class="cl-eye">Today’s plan</span><b>${esc(txt)}${cd ? `<span data-cd="${cd}">${cdFmt(cd - nowS())}</span>` : ''}</b><em class="${newsT.length ? 'wn' : ''}">${esc(news)}</em></span>${icon('right', 'cl-go')}</button>`;
  }

  // ------------------------------------------------------------------ Home: the open trade, else the last closed one
  function lastTrade() {
    const h = HD() || {}, H = window.HubParts || {};
    let p = null; try { p = H.openPos ? H.openPos() : null; } catch (e) { p = null; }
    if (p) {
      return `<button type="button" class="card cl-card cl-trade on" data-go="trades"><span class="cl-ri ${p.dir === 1 ? 'up' : 'dn'}">${icon(p.dir === 1 ? 'long' : 'short')}</span>
        <span class="cl-rt"><span class="cl-eye">Open trade · ${esc(p.acct || '')}</span><b>${esc(p.side)} ${p.qty ?? '—'} MNQ at ${num(p.entry, 2)}</b><em>stop ${num(p.stop, 2)} · target ${num(p.target, 2)}${p.be ? ' · at breakeven' : ''}</em></span>
        <span class="cl-tv ${okN(p.unrealized_r) ? cls(p.unrealized_r) : ''}">${okN(p.unrealized_r) ? fR(p.unrealized_r) : ''}</span></button>`;
    }
    const A = (h.accounts || []).filter((a) => a && a.id && !a.error);
    const live = A.flatMap((a) => (a.trades || []).map((t) => ({ ...t, _src: a.source === 'pc' ? (a.name || 'PC') : 'cloud paper' })));
    const key = (t) => +t.exit_t || +t.entry_t || Date.parse(t.day || '') / 1000 || 0;
    let t = live.sort((x, y) => key(y) - key(x))[0], src = t ? t._src : '';
    if (!t && h.trades && h.trades.length) { t = h.trades.reduce((b, x) => (key(x) > key(b) ? x : b), h.trades[0]); src = 'backtest'; }
    if (!t) return `<div class="card cl-card cl-empty"><span class="cl-eye">Last trade</span><p>No trades yet. The first one shows here the moment the bot closes it.</p></div>`;
    const day = (() => { try { return new Date(String(t.day) + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: String(t.day) < '2026' ? 'numeric' : undefined }); } catch (e) { return t.day; } })();
    return `<button type="button" class="card cl-card cl-trade" data-go="trades"><span class="cl-ri ${t.side === 'LONG' ? 'up' : 'dn'}">${icon(t.side === 'LONG' ? 'long' : 'short')}</span>
      <span class="cl-rt"><span class="cl-eye">Last trade · ${esc(src)}</span><b>${esc(day)} · ${esc(t.side || '')}${t.qty != null ? ` · ${t.qty} MNQ` : ''}</b><em>${esc(t.exit || t.result || '')}${okN(t.r) ? ' · ' + fR(t.r) : ''}</em></span>
      <span class="cl-tv ${cls(t.pnl)}">${smoney(t.pnl)}</span></button>`;
  }

  // ------------------------------------------------------------------ Home
  function home(el) {
    const M = window.MoreParts || {};
    let ins = ''; try { ins = M.installCard ? M.installCard() : ''; } catch (e) { ins = ''; }
    const built = HD() && HD().built ? new Date(HD().built) : null;
    el.innerHTML = `${ins || ''}${launchCard()}
      <div class="cl-heroes">${litHero()}${atlasHero()}</div>
      ${planLine()}
      ${lastTrade()}
      <section class="card cl-card cl-list" aria-label="One tap away"><span class="cl-eye">One tap away</span>
        ${rowLink('brain', 'Bot Brain', 'What the bot is thinking right now', 'brain')}
        ${rowLink('goals', 'Goals', 'Each eval, this week, this month', 'target')}
        ${rowLink('plan', 'LIT plan and levels', 'Today’s levels, the target band, sweeps seen', 'target')}
        ${rowLink('homefull', 'Full overview', 'Every card the old Home showed: health, radar, why no trade', 'layers')}</section>
      <p class="cl-foot">Paper / eval monitor · read-only${built ? ` · data ${esc(built.toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' }))}` : ''}${HD() && HD().home_only ? ' · loading the rest…' : ''}</p>`;
    if (ins && M.wireInstall) { try { M.wireInstall(el); } catch (e) { /* guide only */ } }
  }

  // ------------------------------------------------------------------ More: one grouped list, Advanced collapsed
  const SECTIONS = [
    ['Today', ['goals', 'brain', 'plan', 'day', 'brief', 'levels', 'radar', 'market', 'news', 'cockpit', 'live', 'homefull']],
    ['Bot and health', ['launch', 'lights', 'ops', 'engine', 'alerts', 'activity', 'remote', 'aiwatch']],
    ['Trades', ['recaps', 'weekcal', 'pnlcal', 'tplay', 'accounts', 'intel']],
    ['Money', ['perf', 'scale', 'curve', 'share', 'evalhq', 'eval']],
    ['Strategy', ['strategy', 'risk', 'mffurules']],
    ['This app', ['settings', 'features']],
  ];
  const ADV = ['lab', 'experiments', 'writeups', 'losses', 'intraday', 'evals', 'setups', 'learned', 'results', 'replays', 'stops', 'execq', 'edge', 'chart', 'sources', 'parts', 'archive'];
  const TAB_MAIN = { trades: ['trades', 'last10', 'journal', 'stats', 'weekly'], atlas: ['atlas', 'atstats'], money: ['money', 'evaltl', 'props', 'whatif'] };
  function moreView(el) {
    const used = new Set(['today', 'system']);
    const row = (id) => {
      const p = PAGES[id]; if (!p || used.has(id)) return ''; used.add(id);
      return `<button type="button" class="cl-row" data-go="${esc(id)}" data-s="${esc((p.label + ' ' + (p.desc || '') + ' ' + id).toLowerCase())}"><span class="cl-ri">${icon(p.icon) || icon('layers')}</span>
        <span class="cl-rt"><b>${esc(p.label)}</b>${p.desc ? `<em>${esc(p.desc)}</em>` : ''}</span>${icon('right', 'cl-go')}</button>`;
    };
    // the tabs' own main pages are found by search only (they are one tap away on their tab)
    const tabRows = Object.values(TAB_MAIN).flat().map(row).join('');
    const secs = SECTIONS.map(([t, ids]) => { const r = ids.map(row).join(''); return r ? `<section class="cl-sec"><h4>${esc(t)}</h4><div class="card cl-card cl-list">${r}</div></section>` : ''; }).join('');
    const advIds = ADV.slice();
    Object.keys(PAGES).forEach((id) => { if (!used.has(id) && !advIds.includes(id)) advIds.push(id); });   // anything new lands in Advanced
    const adv = advIds.map(row).join('');
    const open = !!store.get('clean.adv', false);
    el.innerHTML = `<div class="cl-search"><label>${icon('search')}<input id="clQ" type="search" placeholder="Search every page" autocomplete="off" aria-label="Search every page"></label></div>
      <section class="cl-sec cl-tabs" hidden><h4>On the tabs</h4><div class="card cl-card cl-list">${tabRows}</div></section>
      ${secs}
      <details class="cl-sec cl-adv"${open ? ' open' : ''}><summary><h4>Advanced<span>research, backtests and technical pages</span></h4>${icon('down', 'cl-chev')}</summary><div class="card cl-card cl-list">${adv}</div></details>
      <p class="cl-none" hidden>No page matches. Try “eval”, “news” or “risk”.</p>`;
    const inp = el.querySelector('#clQ'), det = el.querySelector('.cl-adv');
    det.addEventListener('toggle', () => { if (!inp.value.trim()) store.set('clean.adv', det.open); });
    const filt = () => {
      const s = inp.value.trim().toLowerCase();
      let any = 0;
      el.querySelectorAll('.cl-sec').forEach((sec) => {
        let n = 0;
        sec.querySelectorAll('.cl-row').forEach((r) => { const on = !s || r.dataset.s.includes(s); r.hidden = !on; n += on; });
        sec.hidden = sec.classList.contains('cl-tabs') ? !s || !n : !n;
        any += n;
      });
      if (s) det.open = true; else det.open = !!store.get('clean.adv', false);
      el.querySelector('.cl-none').hidden = !!any;
    };
    inp.oninput = filt;
    filt();
    const tt = document.getElementById('title'); if (tt) tt.textContent = 'More'; document.title = 'More · Liquidity Engine';
  }

  // ------------------------------------------------------------------ the sub-bar under the header
  function installSubBar() {
    if (typeof subBar !== 'function' || subBar.__clean) return;
    const sb0 = subBar;
    const back = (to, label) => `<div class="modbar"><button class="chipbtn back" type="button" data-go="${to}">${icon('back')}<span>${label}</span></button></div>`;
    subBar = function (p, g) { // eslint-disable-line no-global-assign
      const sub = document.getElementById('sub');
      if (typeof DETAIL !== 'undefined' && DETAIL[p]) return sb0(p, g);
      if (p === 'today' || p === 'system') { sub.className = 'sub'; sub.innerHTML = ''; return; }
      if (g === 'today') { sub.className = 'sub mb'; sub.innerHTML = back('today', 'Home'); return; }
      if (g === 'system') { sub.className = 'sub mb'; sub.innerHTML = back('system', 'More'); return; }
      const L = TAB_MAIN[g]; if (!L) return sb0(p, g);
      const ids = L.filter((id) => PAGES[id]);
      if (!ids.includes(p)) { sub.className = 'sub mb'; sub.innerHTML = back(ids[0] || 'system', (PAGES[ids[0]] || {}).label || 'Back'); return; }
      sub.className = 'sub grp';
      sub.innerHTML = `<div class="strip cl-strip">${ids.map((id) => `<button type="button" data-go="${id}" class="${id === p ? 'on' : ''}">${esc(PAGES[id].label)}</button>`).join('')}</div>`;
    };
    subBar.__clean = true;
  }

  // ------------------------------------------------------------------ install
  function install() {
    if (typeof P !== 'undefined') {
      P.home = '<path d="M4 10.5L12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z"/>';
      if (!P.wallet) P.wallet = '<rect x="3.5" y="6" width="17" height="13" rx="2.5"/><path d="M16 12.5h4.5"/><path d="M6 6l9-2.5 1 2.5"/>';
    }
    // 1. five tabs: Brain folds into Home (its page and deep link stay), any other extra tab folds into More
    const H = GROUPS.find((g) => g.id === 'today'), M = GROUPS.find((g) => g.id === 'system');
    if (H && M) {
      for (let i = GROUPS.length - 1; i >= 0; i--) {
        const g = GROUPS[i];
        if (['today', 'trades', 'atlas', 'money', 'system'].includes(g.id)) continue;
        const into = g.id === 'brain' ? H : M;
        g.pages.forEach((p) => { if (!into.pages.some((q) => q[0] === p[0])) into.pages.splice(1, 0, p); if (PAGES[p[0]]) PAGES[p[0]].group = into.id; });
        if (typeof DETAIL !== 'undefined') Object.values(DETAIL).forEach((d) => { if (d.group === g.id) d.group = into.id; });
        GROUPS.splice(i, 1);
      }
      const order = ['today', 'trades', 'atlas', 'money', 'system'];
      GROUPS.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
      const LBL = { today: ['Home', 'home'], trades: ['Trades', 'trades'], atlas: ['ATLAS', 'atlas'], money: ['Money', 'wallet'], system: ['More', 'modules'] };
      GROUPS.forEach((g) => { if (LBL[g.id]) { g.label = LBL[g.id][0]; g.icon = LBL[g.id][1]; } });
      // the tab opens its main page first
      GROUPS.forEach((g) => { const main = { today: 'today', trades: 'trades', atlas: 'atlas', money: 'money', system: 'system' }[g.id]; const k = g.pages.findIndex((p) => p[0] === main); if (k > 0) g.pages.unshift(g.pages.splice(k, 1)[0]); });
    }
    // 2. the old Home lives on as Home > Full overview
    const old = VIEWS.today;
    if (old && !old.__clean) {
      VIEWS.homefull = old;
      if (H && !H.pages.some((p) => p[0] === 'homefull')) H.pages.push(['homefull', 'Full overview', 'layers', 'Every card the old Home showed: goals, health, plan, radar, why no trade']);
      PAGES.homefull = { id: 'homefull', label: 'Full overview', icon: 'layers', desc: 'Every card the old Home showed: goals, health, plan, radar, why no trade', group: 'today' };
      if (typeof SCENE !== 'undefined') SCENE.homefull = 'today';
      if (typeof LK_PAGES !== 'undefined' && !LK_PAGES.includes('homefull')) LK_PAGES.push('homefull');
      if (typeof ALIAS !== 'undefined') { delete ALIAS.homefull; Object.assign(ALIAS, { oldhome: 'homefull', fullhome: 'homefull', everything: 'homefull' }); }
      VIEWS.today = home; VIEWS.today.__clean = true;
      // the cards that hooked into the old Home still look for these flags
      ['__launch', '__goals', '__atlas', '__brain'].forEach((k) => { VIEWS.today[k] = true; });
    }
    // 3. More: one grouped list (the six-section hub stays reachable as More > All features / All parts)
    if (VIEWS.system && !VIEWS.system.__clean) { VIEWS.morehub = VIEWS.system; VIEWS.system = moreView; VIEWS.system.__clean = true; }
    if (PAGES.system) { PAGES.system.label = 'More'; PAGES.system.desc = 'Every page, grouped, with search'; }
    installSubBar();
    // 4. calm by default: 3D effects are off unless chosen in Settings (index.html fxPref, default 'off' since 2026-10-25)
    document.documentElement.dataset.clean = 'on';
    const st = document.createElement('style'); st.id = 'clean-css'; st.textContent = CSS; document.head.appendChild(st);
    if (typeof nav === 'function') {
      nav();
      // the tab bar: icon + label, five items
      if (typeof route === 'function') route();
    }
  }

  const CSS = `
:root[data-clean="on"]{--r:16px;--cl-gap:12px}
:root[data-clean="on"] body{background-image:none}
:root[data-clean="on"]:not([data-fx="max"]):not([data-fx="lite"]) .card{background:var(--surface)}
:root[data-clean="on"] .card{box-shadow:none;backdrop-filter:none;-webkit-backdrop-filter:none;border:1px solid var(--line);border-radius:16px;padding:16px;margin-bottom:var(--cl-gap)}
:root[data-clean="on"] .card .card{background:var(--surface-2)}
:root[data-clean="on"] .card-h{margin-bottom:12px}
:root[data-clean="on"] .card-h h3{font-size:15px;font-weight:650;display:flex;align-items:center;gap:8px}
:root[data-clean="on"] .hero{margin:0 0 16px}
:root[data-clean="on"] .hero h2{font-size:22px;letter-spacing:-.01em}
:root[data-clean="on"] .hero p{font-size:14px;line-height:1.5}
:root[data-clean="on"] .eyebrow{letter-spacing:.06em}
:root[data-clean="on"] .page{animation:cl-in .24s var(--ease)}
@keyframes cl-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
:root[data-clean="on"] .skel{border-radius:16px;background:linear-gradient(90deg,var(--surface) 25%,var(--surface-2) 50%,var(--surface) 75%);background-size:200% 100%}
:root[data-clean="on"] .empty{padding:24px 16px;text-align:center;color:var(--ink-2);line-height:1.5}
/* tap targets: 44 px */
:root[data-clean="on"] .btn,:root[data-clean="on"] .chipbtn,:root[data-clean="on"] .seg button{min-height:44px}
:root[data-clean="on"] .strip button{min-height:40px}
@media (max-width:760px){
  :root[data-clean="on"] .chipbtn{width:44px;height:44px}:root[data-clean="on"] .chipbtn.back{width:auto;height:40px;min-height:40px;padding:0 14px 0 10px}
  :root[data-clean="on"] .page{padding:12px 16px calc(104px + env(safe-area-inset-bottom))}
  :root[data-clean="on"] .tabs{left:8px;right:8px;height:64px;padding:6px;border-radius:20px;background:color-mix(in srgb,var(--surface) 94%,transparent);box-shadow:0 8px 30px rgba(0,0,0,.35)}
  :root[data-clean="on"] .tabs a{font-size:11px;gap:4px;border-radius:14px}
  :root[data-clean="on"] .tabs a.on{background:color-mix(in srgb,var(--accent) 14%,transparent);box-shadow:none}
  :root[data-clean="on"] .tabs a .ico{width:22px;height:22px}
  :root[data-clean="on"] .sub{background:color-mix(in srgb,var(--page) 94%,transparent)}
}
.cl-strip{gap:4px}.cl-strip button{padding:0 14px;font-weight:600}
/* the calm cards */
.cl-card{display:block;width:100%;text-align:left;font:inherit;color:inherit}
button.cl-card{cursor:pointer;transition:transform .15s var(--ease),border-color .2s}button.cl-card:active{transform:scale(.985)}
.cl-eye{display:flex;flex-direction:column;font-size:12px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2)}
.cl-eye em{font-style:normal;text-transform:none;letter-spacing:0;font-weight:500;font-size:12px;color:var(--muted);margin-top:2px}
.cl-h{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px}
.cl-chip{flex:none;display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border-radius:99px;font:650 11px var(--sans);letter-spacing:.04em;background:var(--surface-3);color:var(--ink-2);white-space:nowrap;max-width:60%;overflow:hidden;text-overflow:ellipsis}
.cl-chip::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--muted)}
.cl-chip.good{background:color-mix(in srgb,var(--good) 14%,transparent);color:var(--good)}.cl-chip.good::before{background:var(--good)}
.cl-chip.warn{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.cl-chip.warn::before{background:var(--warn)}
.cl-chip.bad{background:color-mix(in srgb,var(--bad) 14%,transparent);color:var(--bad)}.cl-chip.bad::before{background:var(--bad)}
.cl-heroes{display:flex;flex-direction:column;gap:0}
.cl-hero{display:flex;flex-direction:column;gap:8px}
.cl-hero.bad{border-color:color-mix(in srgb,var(--bad) 40%,var(--line))}.cl-hero.warn{border-color:color-mix(in srgb,var(--warn) 30%,var(--line))}
.cl-big{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.cl-big b{font:750 40px/1.05 var(--sans);letter-spacing:-.02em;font-variant-numeric:tabular-nums}.cl-big em{font-style:normal;font-size:14px;color:var(--ink-2)}
.cl-bar{display:block;height:6px;border-radius:99px;background:var(--surface-3);overflow:hidden}.cl-bar i{display:block;height:100%;border-radius:99px;background:var(--good);transition:width .8s var(--ease)}
.cl-line{font-size:15px;color:var(--ink)}
.cl-surf .hb-surface{margin:4px 0 0;padding:8px 0 0;border:0;border-top:1px solid var(--line);border-radius:0;background:none;gap:8px}
.cl-surf .hb-surface b,.cl-surf .hb-surface.bad b{font-size:13px;color:var(--ink-2);font-weight:600}.cl-surf .hb-surface.bad b{color:var(--bad)}.cl-surf .hb-surface em{font-size:12px;color:var(--muted)}
.cl-fix{font-size:13px;color:var(--ink-2)}
.cl-meter{height:6px;border-radius:99px;background:var(--surface-3);overflow:hidden;margin:4px 0 12px}.cl-meter i{display:block;height:100%;background:var(--good);border-radius:99px}
.cl-launch{border-color:color-mix(in srgb,var(--warn) 35%,var(--line))}
.cl-todo{list-style:none;margin:0 0 8px;padding:0}.cl-todo li{display:flex;align-items:center;gap:10px;min-height:32px;font-size:15px}
.cl-dot{flex:none;width:8px;height:8px;border-radius:50%;background:var(--muted)}.cl-dot.bad{background:var(--bad)}.cl-dot.good{background:var(--good)}
.cl-act{display:flex;align-items:center;justify-content:center;gap:6px;width:100%;min-height:44px;margin-top:4px;border-radius:12px;border:1px solid var(--line);background:var(--surface-2);color:var(--ink);font-weight:650;font-size:15px}
.cl-act .ico{width:18px;height:18px}
.cl-plan,.cl-trade{display:flex;align-items:center;gap:12px;min-height:72px}
.cl-ri{flex:none;width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:var(--surface-2);color:var(--ink-2)}.cl-ri .ico{width:20px;height:20px}
.cl-ri.up{color:var(--good)}.cl-ri.dn{color:var(--bad)}
.cl-rt{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.cl-rt b{font-size:15px;font-weight:600;line-height:1.35}.cl-rt em{font-style:normal;font-size:13px;color:var(--muted);line-height:1.4}
.cl-rt .cl-eye{margin-bottom:2px}
.cl-go{flex:none;width:18px;height:18px;color:var(--muted)}
.cl-tv{flex:none;font:700 17px var(--sans);font-variant-numeric:tabular-nums}
.cl-empty p{margin:8px 0 0;color:var(--ink-2);line-height:1.5}
:root[data-clean="on"] .card.cl-list{padding:4px 0}.cl-list>.cl-eye{padding:12px 16px 4px}
.cl-row{display:flex;align-items:center;gap:12px;width:100%;min-height:56px;padding:8px 16px;border:0;border-top:1px solid var(--line);background:none;text-align:left;font:inherit;color:inherit;cursor:pointer}
.cl-list>.cl-row:first-child,.cl-list>.cl-eye+.cl-row{border-top:0}.cl-row[hidden]{display:none}
.cl-row:active{background:var(--hover)}.cl-row .cl-ri{width:36px;height:36px;border-radius:10px}.cl-row .cl-rt b{font-size:15px}
.cl-foot{margin:8px 4px 0;font-size:12px;color:var(--muted);text-align:center}
.cl-search{position:sticky;top:calc(60px + env(safe-area-inset-top));z-index:20;padding:0 0 12px;background:var(--page)}
.cl-search label{display:flex;align-items:center;gap:10px;min-height:48px;padding:0 14px;border-radius:14px;border:1px solid var(--line);background:var(--surface)}
.cl-search input{flex:1;min-width:0;border:0;background:none;outline:0;font-size:16px;height:46px}.cl-search .ico{width:20px;height:20px;color:var(--muted)}
.cl-sec{margin:0 0 16px}.cl-sec[hidden]{display:none}.cl-sec h4{margin:0 4px 8px;font-size:12px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2)}
.cl-sec>.cl-card{margin:0}
.cl-adv summary{list-style:none;display:flex;align-items:center;justify-content:space-between;min-height:44px;cursor:pointer;padding:0 4px}.cl-adv summary::-webkit-details-marker{display:none}
.cl-adv summary h4{margin:0;display:flex;flex-direction:column;gap:2px}.cl-adv summary h4 span{text-transform:none;letter-spacing:0;font-weight:500;color:var(--muted)}
.cl-adv .cl-chev{width:20px;height:20px;color:var(--muted);transition:transform .2s}.cl-adv[open] .cl-chev{transform:rotate(180deg)}.cl-adv[open] summary{margin-bottom:8px}
.cl-none{text-align:center;color:var(--muted);padding:24px 0}
html[data-theme="light"] .cl-search{background:var(--page)}
`;
  install();
})();
