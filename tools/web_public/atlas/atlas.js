/* Olympus Atlas: one fast map for every published dashboard. Read-only; no orders or account actions. */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const rows = (window.OLYMPUS_APPS_LIST || []).filter((a) => a && /^[a-z0-9-]+$/.test(a.id) && /^(trading|money|life)$/.test(a.group));
  const fallback = [
    { id:'zenith',name:'Zenith',glyph:'Z',colour:'#a855f7',group:'trading',purpose:'NQ bot dashboard',path:'' },
    { id:'oracle',name:'Oracle',glyph:'Θ',colour:'#7fe9ff',group:'trading',purpose:'Market radar',path:'oracle/' },
    { id:'cities',name:'Cities',glyph:'◈',colour:'#a68bff',group:'trading',purpose:'Explore the city worlds',path:'cities/' },
    { id:'jarvis',name:'Jarvis',glyph:'J',colour:'#e5be83',group:'life',purpose:'Your assistant',path:'jarvis/' }
  ];
  const apps = rows.length ? rows : fallback;
  const zones = [
    { id:'market', title:'Market & trading', note:'Read the tape, context, and live-facing dashboards.', ids:['zenith','oracle','ares','forum','chronos','cities','odeon','bridge'] },
    { id:'research', title:'Strategies & research', note:'Explore ideas, signals, and your research trail.', ids:['datacity','observatory','tree','prometheus','pantheon','argus','nemesis','hephaestus','athena','journal'] },
    { id:'risk', title:'Money & risk', note:'Review decisions, balances, and prediction markets.', ids:['fates','labyrinth','ledger','kalshi','kalshicity','tyche','hermes','plutus'] },
    { id:'life', title:'Life & command', note:'Plan, reflect, and manage your workspace.', ids:['inbox','settings','planner','mind','arena','atlas'] }
  ];
  const zoneOf = (a) => zones.find((zone) => zone.ids.includes(a.id)) || zones.find((zone) => zone.id === (a.group === 'money' ? 'risk' : a.group === 'life' ? 'life' : 'market'));
  const key = 'olympus.atlas.v1';
  let saved = { stars: [], recent: [] };
  function restoreSaved() {
    try {
      const v = JSON.parse(localStorage.getItem(key));
      saved = {
        stars: (Array.isArray(v && v.stars) ? v.stars : []).filter((id) => apps.some((a) => a.id === id)).slice(0, 30),
        recent: (Array.isArray(v && v.recent) ? v.recent : []).filter((id) => apps.some((a) => a.id === id)).slice(0, 5)
      };
    } catch (_) { /* keep this page's preferences if storage is unavailable */ }
  }
  restoreSaved();
  let storageReady = false;
  try {
    const probe = key + '.probe';
    localStorage.setItem(probe, '1');
    localStorage.removeItem(probe);
    storageReady = true;
  } catch (_) { /* private browsing or full storage */ }
  function updateSaveStatus() {
    const status = $('#saveStatus');
    status.textContent = storageReady ? 'Your map is saved on this device.' : 'This browser cannot save favorites or recent rooms.';
    status.dataset.saveState = storageReady ? 'on' : 'off';
  }
  const store = () => {
    try { localStorage.setItem(key, JSON.stringify(saved)); storageReady = true; }
    catch (_) { storageReady = false; }
    updateSaveStatus();
  };
  updateSaveStatus();
  const recordRecent = (id) => { saved.recent = [id, ...saved.recent.filter((x) => x !== id)].slice(0, 5); store(); };
  const link = (a) => '../' + (/^(?:[a-z0-9-]+\/)?$/.test(a.path || '') ? a.path : (a.id + '/'));
  let filter = 'all';
  // Keep the four visible gates useful after a visit without adding another panel to the phone screen.
  const spotlight = $('.spotlight');
  const featured = [...spotlight.children];
  ['oracle', 'datacity', 'cities', 'kalshicity'].forEach((id, index) => {
    featured[index]?.addEventListener('click', () => recordRecent(id));
  });
  let spotlightKey = '';
  function renderSpotlight() {
    const personalized = saved.stars.length || saved.recent.length;
    const preferred = [...saved.stars.slice(0, 2), ...saved.recent.slice(0, 2),
      ...saved.stars, ...saved.recent, 'oracle', 'datacity', 'cities', 'kalshicity'];
    const selected = [...new Set(preferred)].map((id) => apps.find((a) => a.id === id)).filter(Boolean).slice(0, 4);
    const key = personalized ? selected.map((a) => a.id + (saved.stars.includes(a.id) ? '*' : '')).join('|') : 'featured';
    if (key === spotlightKey) return;
    spotlightKey = key;
    if (!personalized || !selected.length) {
      spotlight.setAttribute('aria-label', 'Featured destinations');
      spotlight.replaceChildren(...featured);
      return;
    }
    spotlight.setAttribute('aria-label', 'Quick launch: favorites and recent dashboards');
    spotlight.replaceChildren();
    for (const a of selected) {
      const gate = document.createElement('a'); gate.href = link(a);
      const label = document.createElement('span');
      label.textContent = saved.stars.includes(a.id) ? '★ Favorite' : saved.recent.includes(a.id) ? '↺ Recent' : zoneOf(a).title;
      const name = document.createElement('strong'); name.textContent = a.name;
      const purpose = document.createElement('small'); purpose.textContent = (a.purpose || 'Open dashboard') + ' ↗';
      gate.append(label, name, purpose); spotlight.append(gate);
      gate.addEventListener('click', () => recordRecent(a.id));
    }
  }
  function render() {
    renderSpotlight();
    const q = $('#query').value.toLocaleLowerCase().trim();
    const shown = apps.filter((a) => (filter === 'all' || (filter === 'favorites' ? saved.stars.includes(a.id) : zoneOf(a).id === filter)) &&
      (!q || (a.name + ' ' + a.purpose + ' ' + a.group + ' ' + zoneOf(a).title).toLocaleLowerCase().includes(q)));
    const host = $('#results'); host.replaceChildren();
    for (const zone of zones) {
      const zoneApps = shown.filter((a) => zoneOf(a).id === zone.id);
      if (!zoneApps.length) continue;
      const section = document.createElement('section'); section.className = 'zone'; section.setAttribute('aria-label', zone.title);
      const heading = document.createElement('div'); heading.className = 'zone-head';
      const title = document.createElement('h3'); title.textContent = zone.title;
      const note = document.createElement('p'); note.textContent = zone.note;
      const tally = document.createElement('span'); tally.textContent = zoneApps.length + ' destinations';
      heading.append(title,note,tally); section.append(heading);
      const grid = document.createElement('div'); grid.className = 'zone-grid'; section.append(grid);
      for (const a of zoneApps) {
      const card = document.createElement('article'); card.className = 'card'; card.style.setProperty('--accent', /^#[0-9a-f]{6}$/i.test(a.colour) ? a.colour : '#e5be83');
      const sigil = document.createElement('span'); sigil.className = 'sigil'; sigil.textContent = a.glyph || a.name.charAt(0); sigil.setAttribute('aria-hidden','true');
      const body = document.createElement('div'); body.className = 'card-body';
      const group = document.createElement('small'); group.textContent = zone.title;
      const name = document.createElement('h3'); name.textContent = a.name;
      const purpose = document.createElement('p'); purpose.textContent = a.purpose || 'Open dashboard';
      body.append(group,name,purpose);
      const go = document.createElement('a'); go.className = 'go'; go.href = link(a); go.setAttribute('aria-label','Open ' + a.name); go.addEventListener('click', () => recordRecent(a.id));
      const star = document.createElement('button'); star.type = 'button'; star.className = 'star'; star.dataset.id = a.id; star.textContent = saved.stars.includes(a.id) ? '★' : '☆'; star.setAttribute('aria-pressed',String(saved.stars.includes(a.id))); star.setAttribute('aria-label',(saved.stars.includes(a.id) ? 'Remove ' : 'Favorite ') + a.name + (saved.stars.includes(a.id) ? ' from favorites' : ''));
      star.addEventListener('click', () => {
        saved.stars = saved.stars.includes(a.id) ? saved.stars.filter((id) => id !== a.id) : [...saved.stars,a.id]; store(); render();
        // render replaces the button; return keyboard focus to the same action, or the Favorites filter if that card disappeared.
        const next = [...document.querySelectorAll('.star')].find((b) => b.dataset.id === a.id) || document.querySelector('[data-filter="favorites"]');
        if (next) next.focus({ preventScroll: true });
      });
      card.append(sigil,body,go,star); grid.append(card);
      }
      host.append(section);
    }
    const resultLabel = shown.length + (shown.length === 1 ? ' destination' : ' destinations');
    $('#count').textContent = rows.length ? resultLabel : resultLabel + ' · limited map (catalog unavailable)'; $('#empty').hidden = shown.length > 0;
    const recent = $('#recent'); recent.replaceChildren(); recent.hidden = !saved.recent.length || !!q || filter !== 'all';
    if (!recent.hidden) {
      const label = document.createElement('span'); label.textContent = 'Recent  '; recent.append(label);
      for (const id of saved.recent) { const a = apps.find((x) => x.id === id); if (!a) continue; const el = document.createElement('a'); el.href = link(a); el.textContent = a.name + ' ↗'; el.addEventListener('click', () => recordRecent(a.id)); recent.append(el); }
    }
  }
  $('#query').addEventListener('input',render);
  document.querySelectorAll('[data-filter]').forEach((b) => b.addEventListener('click', () => { filter = b.dataset.filter; document.querySelectorAll('[data-filter]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); render(); }));
  document.addEventListener('keydown', (e) => { if (e.key === '/' && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); $('#query').focus(); } else if (e.key === 'Escape' && document.activeElement === $('#query')) { $('#query').value = ''; render(); $('#query').blur(); } });
  render();
  // Back/forward cache restores the old DOM without rerunning this script.
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    restoreSaved();
    render();
  });

  // AGORA (2026-11-09): the night-city canvas is gone (calm marble page, nothing animated).
})();
