// Calm, premium phone app (2026-10-30 night, owner: "more very useful features ... then clean it up, organized, clean ...
// then the UI, quality, the effects ... I wanna be shocked"; read-only UI, links only). Loaded LAST (after blitz.js).
//   Home     one status bar ("is everything OK right now?"), the three accounts (eval ring, $ to the target, room, today's
//            real $, a sparkline, the day in one line), what matters now, the Sunday open card (weekends), four quick
//            tiles; every older Home card is still there under "Everything else on Home" (one tap, remembered)
//   bot tabs Zlarior · ATLAS · BLITZ open on the same account card, in the bot's own colour (blue / orange / purple)
//   palette  search every page, section and number from the header (or "/" and Ctrl/Cmd+K on a keyboard)
//   motion   page transitions, card entrances, count-ups, press states; reduced motion = none
//   sky      the static sky drifts a little with scroll and tilt (the 3D scene gets the same via FX.parallax)
// Classic script on the main page's helpers (VIEWS, PAGES, GROUPS, PAGE, ARG, render, store, icon, esc). Never arms,
// routes or changes the bot.
(function () {
  'use strict';
  if (typeof VIEWS === 'undefined' || typeof PAGES === 'undefined' || !window.StatusUI) return;
  const SU = window.StatusUI, PD = window.PhoneData || {}, BU = window.BlitzUI;
  window.POLISH = { version: 1 };
  const HD = () => (typeof D !== 'undefined' && D) || window.HOMEJ || null;
  const nowS = () => Date.now() / 1000;
  const okN = (v) => typeof v === 'number' && Number.isFinite(v);
  const calm = () => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches || store.get('motion', true) === false; } catch (e) { return false; } };
  const BOTG = { lit: 'lit', atlas: 'atlas', blitz: 'blitz' };
  SU.css();

  // ------------------------------------------------------------------ the data (the same picks as board.js / mission.js / blitz.js)
  function board() {
    if (PD.board) { try { return PD.board(); } catch (e) { /* fall through */ } }
    const h = HD() || {}; return h.board && !h.board.error ? h.board : null;
  }
  function alerts() {
    const b = document.getElementById('apBan'), out = [];
    if (b && b.offsetParent !== null) { const t = (b.querySelector('b') || b).textContent.trim(); if (t) out.push({ lvl: 'bad', text: t.replace(/\s*·\s*tap Got it\s*$/i, '') }); }
    return out;
  }
  function model() {
    const h = HD() || {};
    let bl = null;
    try { if (BU && PD.bModel) bl = BU.line(PD.bModel()); } catch (e) { bl = null; }
    let news = [];
    try { news = PD.news ? PD.news() : []; } catch (e) { news = []; }
    return { now: nowS(), where: 'phone', board: board(), lv: (window.LVP && window.LVP.d) || null, news, cloud: h.live && h.live.last_run ? { t: +h.live.last_run } : null,
      cal: (h.goals || {}).calendar || null, blitz: bl, alerts: alerts() };
  }
  window.POLISH.model = model;

  // ------------------------------------------------------------------ Home
  const ic = (n) => (typeof icon === 'function' ? icon(n) : '');
  function nowCard(M) {
    const MU = window.MissionUI, rows = [];
    let As = [];
    try { As = MU ? MU.accounts(M).filter((a) => a && !a.placeholder) : []; } catch (e) { As = []; }
    const money = (v) => (okN(v) ? (v < 0 ? '−' : '') + '$' + Math.abs(Math.round(v)).toLocaleString('en-US') : '—');
    const smoney = (v) => (okN(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + money(Math.abs(v)).replace('−', '') : '—');
    const tm = (t) => { try { return new Date(t * 1000).toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }) + ' ET'; } catch (e) { return ''; } };
    for (const A of As) {
      if (!A.pos) continue;
      rows.push(`<a class="pl-now-r" data-go="${A.key === 'lit' ? 'lit' : A.key}" style="--c:${SU.COLOR[A.key] || '#8aa0ff'}"><i class="pl-now-i live">${ic(A.pos.dir === 1 ? 'long' : 'short')}</i>
        <span><b>${esc(A.name)} is in a ${esc(A.pos.side)} · ${A.pos.qty || ''} MNQ</b><em>at ${A.pos.entry != null ? A.pos.entry.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '—'} · stop ${okN(A.pos.atStop) ? money(A.pos.atStop) : '—'} · target ${okN(A.pos.atTgt) ? '+' + money(A.pos.atTgt) : '—'}</em></span>
        <strong class="${okN(A.pos.unreal) ? (A.pos.unreal >= 0 ? 'up' : 'dn') : ''}">${okN(A.pos.unreal) ? smoney(A.pos.unreal) : ''}</strong></a>`);
    }
    // the next window (or the open one)
    const S = SU.summary(M), nx = S.next;
    if (nx && nx.t) rows.push(`<a class="pl-now-r" data-go="deck"><i class="pl-now-i">${ic('clock')}</i><span><b>${esc(nx.label)} · ${esc(nx.detail.split(':')[0])}</b><em>${esc(nx.detail.replace(/^[^:]*:\s*/, ''))}</em></span><strong><span class="st-cd" data-st-cd="${Math.round(nx.t)}"></span></strong></a>`);
    // the next high-impact news in 24 h
    const nw = (M.news || []).filter((n) => okN(n.t) && n.t > M.now - 600 && n.t < M.now + 86400 && /high|fomc/i.test(n.impact || 'high')).sort((a, b) => a.t - b.t)[0];
    rows.push(nw ? `<a class="pl-now-r" data-go="news"><i class="pl-now-i warn">${ic('news')}</i><span><b>${esc(nw.title)}</b><em>${esc(tm(nw.t))} · high-impact news</em></span><strong><span class="st-cd" data-st-cd="${Math.round(nw.t)}"></span></strong></a>`
      : `<a class="pl-now-r" data-go="news"><i class="pl-now-i">${ic('news')}</i><span><b>No big US news in the next 24 h</b><em>The calendar the bots read</em></span></a>`);
    // the last real trade (NinjaTrader fills only)
    const B = M.board || {}, lt = (B.trades || []).filter((t) => t && t.src === 'live' && t.open === false).sort((a, b) => (+b.exit_t || 0) - (+a.exit_t || 0))[0];
    if (lt) {
      const nm = (SU.NAME[lt.acct] || lt.acct || '');
      rows.push(`<a class="pl-now-r" data-go="real" style="--c:${SU.COLOR[lt.acct] || '#8aa0ff'}"><i class="pl-now-i">${ic(lt.side === 'LONG' ? 'long' : 'short')}</i><span><b>Last real trade · ${esc(nm)}</b><em>${esc(tm(+lt.exit_t || +lt.entry_t))} · ${esc(lt.side)} ${lt.qty || ''} MNQ · ${esc(lt.exit || '')}${okN(+lt.r) ? ' · ' + (+lt.r > 0 ? '+' : '') + (+lt.r).toFixed(2) + 'R' : ''}</em></span><strong class="${+lt.usd > 0 ? 'up' : +lt.usd < 0 ? 'dn' : ''}">${smoney(+lt.usd)}</strong></a>`);
    } else rows.push(`<a class="pl-now-r" data-go="real"><i class="pl-now-i">${ic('results')}</i><span><b>No real trade yet</b><em>The first NinjaTrader fill shows here within a minute</em></span></a>`);
    return `<section class="pl-now" aria-label="What matters now"><h3 class="pl-h3">What matters now</h3>${rows.join('')}</section>`;
  }
  function quick() {
    const T = [['liveview', 'Live View', 'chart', 'live chart'], ['holo', 'Holodeck', 'layers', 'fills in 3D'], ['mission', 'Mission', 'radar', 'control'], ['mind', 'Mind', 'brain', 'game plans']];
    return `<nav class="pl-quick" aria-label="Quick">${T.filter(([id]) => PAGES[id]).map(([id, l, i, s]) => `<a data-go="${id}"><i>${ic(i)}</i><b>${l}</b><em>${s}</em></a>`).join('')}</nav>`;
  }
  const FOLD_NAMES = [['.mc-strip', 'Mission Control'], ['.rc-homebox', 'real accounts in full'], ['.rc-wrap', 'safety'], ['.bd-homecut', 'right now per bot'], ['.cl-launch', 'launch checklist'],
    ['.bz-home', 'trader\'s deck + Mind'], ['.cl-plan', 'today\'s plan'], ['.cl-list', 'one tap away']];
  function paintHome(el, first) {
    el.querySelectorAll(':scope > .pl-home, :scope > .pl-fold').forEach((x) => x.remove());
    const M = model();
    const box = document.createElement('div'); box.className = 'pl-home';
    const more = `<a class="pl-btn" data-go="mission">Mission Control</a><a class="pl-btn" data-go="board">Live board</a><a class="pl-btn" data-go="launch">Launch checklist</a>`;
    box.innerHTML = SU.bar(M, { open: SU.isOpen(), more, where: 'phone' }) + SU.accounts(M, { where: 'phone' }) + nowCard(M) + SU.sunday(M) + quick();
    el.prepend(box);
    // no live board yet (the PC never reported, an older data.json): the account cards come from clean.js's hero cards
    // (eval tracker + goals + ATLAS card), placed where the board's cards would be; BLITZ keeps its paper card
    const have = new Set([...box.querySelectorAll('.st-acct')].map((a) => a.dataset.bot));
    const heroes = el.querySelector(':scope > .cl-heroes');
    if (heroes && !(have.has('lit') && have.has('atlas'))) {
      heroes.hidden = false; heroes.classList.add('pl-fallback');
      const at = box.querySelector('.st-accts'); if (at) at.before(heroes); else box.querySelector('.st-bar')?.after(heroes);
    }
    const all = !!store.get('pl.homeAll', false);
    el.classList.add('pl-h'); el.classList.toggle('pl-all', all);
    const fold = document.createElement('button'); fold.type = 'button'; fold.className = 'pl-fold'; fold.setAttribute('aria-expanded', String(all));
    const names = FOLD_NAMES.filter(([s]) => el.querySelector(':scope > ' + s)).map((x) => x[1]);
    fold.innerHTML = `<span><b>${all ? 'Hide' : 'Everything else on Home'}</b><em>${esc(names.length ? names.join(' · ') : 'Mission Control, the real accounts in full, safety, the deck, the Mind')}</em></span><i class="pl-chev"></i>`;
    fold.onclick = () => { const on = !el.classList.contains('pl-all'); el.classList.toggle('pl-all', on); store.set('pl.homeAll', on); fold.setAttribute('aria-expanded', String(on)); fold.querySelector('b').textContent = on ? 'Hide' : 'Everything else on Home'; if (on) enter(el, ':scope > .pl-fold ~ *'); };
    box.after(fold);
    SU.wire(el); SU.tick(box);
    if (first) { box.classList.add('pl-first'); countUp(box); enter(box, ':scope > *'); }   // rings / sparklines draw in once, not on every live redraw
  }
  const h0 = VIEWS.today;
  if (h0 && !h0.__pl) {
    const w = function (el) {
      const first = !el.querySelector(':scope > .pl-home');
      h0.apply(this, arguments);
      try { paintHome(el, first); } catch (e) { console.warn('polish home', e); }
    };
    Object.keys(h0).forEach((k) => { w[k] = h0[k]; });
    w.__pl = true;
    VIEWS.today = w;
  }

  // ------------------------------------------------------------------ the bot tabs: the same account card on top of Today
  function botTop(el, soft) {
    const g = typeof groupOf === 'function' ? groupOf(PAGE) : '';
    const today = (PAGE === 'lit') || ((PAGE === 'atlas' || PAGE === 'blitz') && (!ARG || ARG === 'today'));
    el.querySelectorAll(':scope > .pl-bot').forEach((x) => x.remove());
    if (!BOTG[g] || !today) return;
    const M = model(), k = g === 'lit' ? 'lit' : g;
    let A = null;
    try { A = (window.MissionUI.accounts(M) || []).find((a) => a.key === k) || null; } catch (e) { A = null; }
    if (!A) return;
    const box = document.createElement('div'); box.className = 'pl-bot' + (soft ? '' : ' pl-first');
    box.innerHTML = SU.acctCard(A, M, { where: 'phone', go: () => `data-go="${k === 'lit' ? 'evalhq' : k}"${k === 'lit' ? '' : ' data-arg="results"'}` });
    const after = [...el.children].filter((c) => c.classList.contains('mo-strip')).pop();
    if (after) after.after(box); else el.prepend(box);
    SU.tick(box);
  }

  // ------------------------------------------------------------------ every page: the page / bot on <html>, entrances, count-ups
  const r0 = typeof render === 'function' ? render : null;
  if (r0 && !r0.__pl) {
    render = function (soft) { // eslint-disable-line no-global-assign
      const root = document.documentElement, g = typeof groupOf === 'function' ? groupOf(PAGE) : '';
      root.dataset.page = PAGE || ''; root.dataset.bot = BOTG[g] || '';
      const el = document.getElementById('page');
      if (el && PAGE !== 'today') el.classList.remove('pl-h', 'pl-all');
      const out = r0.apply(this, arguments);
      try { if (el) { botTop(el, soft); if (!soft && PAGE !== 'today') enter(el, ':scope > *'); } } catch (e) { console.warn('polish render', e); }
      return out;
    };
    render.__pl = true;
  }
  // card entrances: the first 10 visible children rise in, 40 ms apart (a class, so nothing is left half-drawn)
  function enter(root, sel) {
    if (calm() || !root) return;
    const L = [...root.querySelectorAll(sel)].filter((c) => c.offsetParent !== null).slice(0, 10);
    L.forEach((c, i) => { c.classList.remove('pl-in'); c.style.setProperty('--d', (i * 40) + 'ms'); void c.offsetWidth; c.classList.add('pl-in'); });
    setTimeout(() => L.forEach((c) => { c.classList.remove('pl-in'); c.style.removeProperty('--d'); }), 900);
  }
  // count-ups: $ numbers roll up from 0 on the first paint (600 ms, ease-out), the final text is the real one
  function countUp(root) {
    if (calm()) return;
    root.querySelectorAll('[data-st-count]').forEach((e) => {
      const v = +e.dataset.stCount; if (!e.dataset.stCount || !okN(v) || v === 0) return;
      const fin = e.textContent, t0 = performance.now(), D_ = 650;
      const f = (t) => { const k = Math.min(1, (t - t0) / D_), x = 1 - Math.pow(1 - k, 3); e.textContent = k < 1 ? '$' + Math.round(v * x).toLocaleString('en-US') : fin; if (k < 1) requestAnimationFrame(f); };
      requestAnimationFrame(f);
    });
  }

  // ------------------------------------------------------------------ the command palette
  const SECS = { lit: [['Today', 'lit'], ['Brain', 'brain'], ['Trades', 'trades'], ['Results', 'perf'], ['Rules', 'strategy']],
    atlas: [['Today', 'atlas'], ['Brain', 'atlas/brain'], ['Trades', 'atlas/trades'], ['Results', 'atlas/results'], ['Rules', 'atlas/setups']],
    blitz: [['Today', 'blitz'], ['Brain', 'blitz/brain'], ['Trades', 'blitz/trades'], ['Results', 'blitz/results'], ['Rules', 'blitz/rules']] };
  function palItems() {
    const out = [], seen = new Set();
    for (const [b, L] of Object.entries(SECS)) for (const [s, id] of L) { out.push({ id, t: `${SU.NAME[b]} · ${s}`, d: `${SU.NAME[b]}'s ${s.toLowerCase()}`, k: 'bot', bot: b }); seen.add(id); }
    for (const id of Object.keys(PAGES)) {
      const p = PAGES[id]; if (!p || seen.has(id)) continue;
      const G = (typeof GROUPS !== 'undefined' ? GROUPS : []).find((g) => g.id === p.group);
      out.push({ id, t: p.label, d: p.desc || '', g: G ? G.label : '', k: 'page' });
    }
    // live numbers: the answer itself, one tap to its page
    try {
      const M = model(), As = window.MissionUI.accounts(M) || [];
      for (const A of As) {
        if (A.placeholder) { out.unshift({ id: 'blitz', t: 'BLITZ: paper only', d: 'off until its own 25K', k: 'num', bot: 'blitz' }); continue; }
        if (okN(A.toTarget)) out.unshift({ id: A.key === 'lit' ? 'lit' : A.key, t: `${A.name}: $${Math.round(A.toTarget).toLocaleString('en-US')} to the target`, d: `room $${Math.round(A.room || 0).toLocaleString('en-US')} · today ${okN(A.today) ? (A.today >= 0 ? '+' : '−') + '$' + Math.abs(Math.round(A.today)) : '—'}`, k: 'num', bot: A.key });
      }
    } catch (e) { /* numbers are optional */ }
    return out;
  }
  const norm = (s) => String(s || '').toLowerCase();
  function score(it, q) {
    if (!q) return 1;
    const t = norm(it.t), d = norm(it.d + ' ' + (it.g || '') + ' ' + it.id);
    if (t.startsWith(q)) return 100; if (t.includes(q)) return 60; if (d.includes(q)) return 30;
    let i = 0; for (const ch of t) if (ch === q[i]) i++; return i === q.length ? 10 : 0;   // the letters in order
  }
  function palette(open) {
    let P = document.getElementById('plPal');
    if (!open) { if (P) { P.classList.remove('on'); setTimeout(() => P && !P.classList.contains('on') && P.remove(), 220); } return; }
    if (P) return;
    P = document.createElement('div'); P.id = 'plPal'; P.className = 'pl-pal'; P.setAttribute('role', 'dialog'); P.setAttribute('aria-label', 'Search');
    P.innerHTML = `<div class="pl-pal-bg" data-pl-x></div><div class="pl-pal-in"><label class="pl-pal-q">${ic('search')}<input id="plQ" type="search" placeholder="Search pages, bots, numbers" autocomplete="off" enterkeyhint="go" aria-label="Search"><button type="button" class="pl-pal-x" data-pl-x>Close</button></label><ul class="pl-pal-l" id="plL" role="listbox"></ul></div>`;
    document.body.appendChild(P);
    const inp = P.querySelector('#plQ'), L = P.querySelector('#plL'), items = palItems();
    let sel = 0, cur = [];
    const recent = () => { try { return (store.get('pl.recent', []) || []).slice(0, 5); } catch (e) { return []; } };
    const draw = () => {
      const q = norm(inp.value.trim());
      if (!q) { const R = recent(); cur = R.map((id) => items.find((x) => x.id === id)).filter(Boolean).concat(items.filter((x) => x.k === 'num' || x.k === 'bot').slice(0, 12)); }
      else cur = items.map((x) => [score(x, q), x]).filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0]).slice(0, 30).map((x) => x[1]);
      const uniq = []; const u = new Set(); for (const x of cur) { const key = x.id + '|' + x.t; if (!u.has(key)) { u.add(key); uniq.push(x); } } cur = uniq;
      sel = Math.min(sel, Math.max(0, cur.length - 1));
      L.innerHTML = cur.length ? cur.map((x, i) => `<li role="option" aria-selected="${i === sel}" class="${i === sel ? 'on' : ''}" data-i="${i}"${x.bot ? ` style="--c:${SU.COLOR[x.bot]}"` : ''}><i class="pl-pal-k ${x.k}"></i><span><b>${esc(x.t)}</b><em>${esc(x.d || x.g || '')}</em></span></li>`).join('')
        : '<li class="pl-pal-none"><span><b>No match</b><em>Try “eval”, “trades”, “news” or a bot name</em></span></li>';
    };
    const go = (x) => { if (!x) return; try { const R = recent().filter((id) => id !== x.id); R.unshift(x.id); store.set('pl.recent', R.slice(0, 8)); } catch (e) { /* private */ } palette(false); location.hash = '#/' + x.id; };
    inp.oninput = () => { sel = 0; draw(); };
    inp.onkeydown = (e) => {
      if (e.key === 'ArrowDown') { sel = Math.min(cur.length - 1, sel + 1); draw(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); draw(); e.preventDefault(); }
      else if (e.key === 'Enter') { go(cur[sel]); e.preventDefault(); }
      else if (e.key === 'Escape') palette(false);
    };
    P.addEventListener('click', (e) => { if (e.target.closest('[data-pl-x]')) { palette(false); return; } const li = e.target.closest('li[data-i]'); if (li) go(cur[+li.dataset.i]); });
    draw();
    requestAnimationFrame(() => { P.classList.add('on'); inp.focus({ preventScroll: true }); });
  }
  window.POLISH.palette = palette;
  function headerButton() {
    const top = document.querySelector('header.top'), ref = document.getElementById('refresh');
    if (!top || !ref || document.getElementById('plFind')) return;
    const b = document.createElement('button'); b.id = 'plFind'; b.type = 'button'; b.className = 'iconbtn'; b.title = 'Search'; b.setAttribute('aria-label', 'Search every page');
    b.innerHTML = ic('search'); b.onclick = () => palette(true);
    ref.before(b);
  }
  addEventListener('keydown', (e) => {
    const t = e.target, typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
    if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); palette(true); }
  });

  // ------------------------------------------------------------------ the sky: a little parallax with scroll and tilt
  function sky() {
    const S = document.querySelector('.space-css'); if (!S || calm()) return;
    let tx = 0, ty = 0, sy = 0, raf = 0;
    const put = () => {
      raf = 0;
      S.style.setProperty('--px', tx.toFixed(2)); S.style.setProperty('--py', (ty + sy).toFixed(2));
      const F = typeof FX !== 'undefined' ? FX : null; if (F && typeof F.parallax === 'function') F.parallax(tx / 12, (ty + sy) / 12);
    };
    const q = () => { if (!raf) raf = requestAnimationFrame(put); };
    addEventListener('scroll', () => { sy = Math.max(-12, -scrollY / 60); q(); }, { passive: true });
    addEventListener('deviceorientation', (e) => { if (e.gamma == null) return; tx = Math.max(-10, Math.min(10, e.gamma / 4)); ty = Math.max(-10, Math.min(10, (e.beta - 45) / 6)); q(); }, { passive: true });
    addEventListener('pointermove', (e) => { if (e.pointerType !== 'mouse') return; tx = (e.clientX / innerWidth - 0.5) * 12; ty = (e.clientY / innerHeight - 0.5) * 8; q(); }, { passive: true });
  }

  // ------------------------------------------------------------------ the intro line (index.html draws the intro itself)
  function introLine() {
    const el = document.getElementById('spLine'); if (!el) return;
    try {
      const M0 = model(); if (!M0.board) return;
      const S = SU.summary(M0), h = new Date().toLocaleString('en-US', { timeZone: 'America/New_York', hour: '2-digit', hour12: false });
      const hi = +h < 12 ? 'Good morning' : +h < 18 ? 'Good afternoon' : 'Good evening';
      el.innerHTML = `<b>${hi}.</b> ${esc(S.title)}${S.next ? ' · ' + esc(S.next.label.toLowerCase()) + ' ' + esc(S.next.value) : ''}`;
      el.classList.add('on'); el.dataset.lvl = S.lvl;
    } catch (e) { /* the intro shows without it */ }
  }
  window.POLISH.introLine = introLine;

  // ------------------------------------------------------------------ Money = real money only
  // Real results first, then "Accounts today" (the real-account cards Home used to show in full) and the eval timeline;
  // the research $ pages (Money plan, prop firms, what-if, scale, accounts) move to More and keep their links.
  function viewRealToday(el) {
    el.innerHTML = head('Money · real', 'Accounts today', 'Both real MFFU accounts right now: today\'s real trades, balance, room to the floor, $ to the target, daily loss, and the safety lights. NinjaTrader fills only, never paper $.')
      + '<div class="rc-host"><div class="skel" style="height:240px"></div></div>';
    const RP = window.RealPages || {};
    const draw = () => {
      const r = el.querySelector('.rc-host'); if (!r || !window.RealUI) return;
      const B = RP.board ? RP.board() : board(), o = RP.opts ? RP.opts() : { where: 'phone', go: (id) => `data-go="${id}"` };
      r.innerHTML = B ? window.RealUI.today(B, o) + window.RealUI.safety(B, o) : SU.empty('real', model());
      try { window.RealUI.wire(r, B, o); } catch (e) { /* static */ }
    };
    if (RP.core) RP.core(draw); else draw();
  }
  function moneyTab() {
    const Mo = GROUPS.find((g) => g.id === 'money'), Sy = GROUPS.find((g) => g.id === 'system');
    if (!Mo || !Sy) return;
    const desc = 'Both real MFFU accounts today: balance, room, $ to the target, daily loss, safety (real $ only)';
    PAGES.realtoday = { id: 'realtoday', label: 'Accounts today', icon: 'wallet', desc, group: 'money' };
    VIEWS.realtoday = viewRealToday;
    if (!Mo.pages.some((p) => p[0] === 'realtoday')) Mo.pages.push(['realtoday', 'Accounts today', 'wallet', desc]);
    const keep = ['real', 'realtoday', 'evaltl'];
    Mo.pages = Mo.pages.filter((p) => {
      if (keep.includes(p[0])) return true;
      if (PAGES[p[0]]) PAGES[p[0]].group = 'system';
      if (!Sy.pages.some((q) => q[0] === p[0])) Sy.pages.push(p);
      return false;
    });
    Mo.pages.sort((a, b) => keep.indexOf(a[0]) - keep.indexOf(b[0]));
    if (typeof SCENE !== 'undefined') SCENE.realtoday = 'results';
    if (typeof ALIAS !== 'undefined') Object.assign(ALIAS, { accountstoday: 'realtoday', realnow: 'realtoday', today_real: 'realtoday' });
  }

  // ------------------------------------------------------------------ install
  function install() {
    try { moneyTab(); } catch (e) { console.warn('polish money', e); }
    if (typeof nav === 'function') nav();
    headerButton();
    sky();
    document.documentElement.dataset.polish = 'on';
    introLine();
    if (typeof render === 'function' && typeof PAGE !== 'undefined' && PAGE && HD()) render(true);
  }
  install();
})();
