// Jarvis's assistant screens (2026-11-02): the Obsidian connect sheet, the proactive line and the free AI key steps. DOM only;
// the logic lives in obsidian.js (the vault), memory.js (what the owner says) and brain.js (the answers). index.html mounts
// each one with a few lines; each part works on its own and never throws into the shell.
//
//   import { mountObsidianSheet, mountProactive, mountKeySteps, mountKeySetup } from './assist-ui.js';
//   const obs = mountObsidianSheet({ vault, toast });     obs.open() · obs.close()
//   const pro = mountProactive({ brain, anchor, onAsk });  pro.render() (on open and on every data change)
//   mountKeySteps(settingsForm)                            the free-key steps above the AI key field
//   const ks = mountKeySetup({ brain, toast, onSaved });  ks.open(provider?): the one-screen free key setup with a Test button

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safe = (f, d) => { try { return f(); } catch (_) { return d; } };
const ls = { get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } } };
let styled = false;
function style() {
  if (styled) return;
  styled = true;
  const s = document.createElement('style');
  s.textContent = `
.jx-pro{display:flex;align-items:flex-start;gap:8px;margin:8px auto 0;max-width:560px;padding:9px 10px 9px 12px;border-radius:14px;
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);text-align:left}
.jx-pro[hidden],.jx-obs[hidden]{display:none}
.jx-pro[data-level=bad]{border-color:rgba(248,113,113,.55);background:rgba(127,29,29,.28)}
.jx-pro[data-level=warn]{border-color:rgba(251,191,36,.5);background:rgba(120,53,15,.25)}
.jx-pro .t{flex:1;font:inherit;font-size:14px;line-height:1.35;color:inherit;background:none;border:0;padding:0;text-align:left;cursor:pointer}
.jx-pro .t small{display:block;opacity:.7;font-size:12px;margin-top:2px}
.jx-pro .x{font:inherit;font-size:18px;line-height:1;color:inherit;opacity:.7;background:none;border:0;padding:2px 4px;cursor:pointer}
.jx-steps{margin:6px 0 10px;padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.05);font-size:13px;line-height:1.45}
.jx-steps ol{margin:6px 0 0;padding-left:20px}.jx-steps li{margin:3px 0}.jx-steps b{font-weight:600}
.jx-steps code{font-size:12px;padding:1px 4px;border-radius:4px;background:rgba(255,255,255,.08);word-break:break-all}
.jx-obs textarea{width:100%;min-height:90px;box-sizing:border-box;font:inherit;font-size:14px;border-radius:10px;padding:8px}
.jx-obs .st{font-size:13px;opacity:.85;margin:4px 0 8px}`;
  document.head.appendChild(s);
}

// ------------------------------------------------------------------------------------------------ the Obsidian sheet
export function mountObsidianSheet(o) {
  const vault = o && o.vault, toast = (o && o.toast) || (() => {});
  style();
  const el = document.createElement('div');
  el.className = 'sheet jx-obs'; el.id = 'obsSheet'; el.hidden = true;
  el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); el.setAttribute('aria-labelledby', 'obsT');
  el.innerHTML = `<form class="sheet-in" id="obsF" autocomplete="off">
    <h2 id="obsT">Connect Obsidian</h2>
    <p class="st" id="obsSt"></p>
    <div class="jx-steps"><b>Free, about 5 minutes, once:</b><ol>
      <li>On github.com, make a <b>private</b> repo named <code>obsidian-vault</code> (+ → New repository → Private → Create).</li>
      <li>Make a token: <code>github.com/settings/personal-access-tokens/new</code> → Repository access: <b>Only select repositories</b> → obsidian-vault → Permissions → <b>Contents: Read and write</b> → Generate → Copy.</li>
      <li>In Obsidian, install the community plugin <b>Git</b> and connect it to that repo with the same token (its guide walks you through it). Then paste the repo and the token here.</li>
    </ol></div>
    <label>Repo<input id="obsRepo" type="text" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="demetrades2000-coder/obsidian-vault"></label>
    <label>Token<input id="obsTok" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="github_pat_… (kept on this phone only)"></label>
    <p class="err" id="obsErr"></p>
    <div class="sheet-row"><button class="btn ghost" type="button" id="obsSync">Sync now</button><button class="btn ghost" type="button" id="obsOff">Disconnect</button><button class="btn solid" type="submit" id="obsGo">Connect</button></div>
    <h3>No GitHub yet? Paste a note</h3>
    <label>Title<input id="obsPT" type="text" maxlength="80" placeholder="Morning plan"></label>
    <textarea id="obsPB" placeholder="Paste or share a note here: Jarvis keeps it on this phone and answers from it."></textarea>
    <div class="sheet-row"><button class="btn ghost" type="button" id="obsPaste">Save note on this phone</button><button class="btn ghost" type="button" id="obsX">Close</button></div>
    <p class="note">The token stays on this phone and goes only to api.github.com. Your notes are cached only here. Disconnect wipes both. Jarvis only ever appends, after you say yes.</p>
  </form>`;
  document.body.appendChild(el);
  const $ = (s) => el.querySelector(s);
  function render() {
    const s = safe(() => (vault ? vault.status() : null), null);
    $('#obsSt').textContent = !vault ? 'The vault module did not load: reload Jarvis.'
      : s && s.connected ? `Connected: ${s.repo} · ${s.notes} notes${s.at ? ' · synced ' + new Date(s.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}${s.error ? ' · ' + s.error : ''}`
        : `Not connected${s && s.local ? ` · ${s.local} pasted ${s.local === 1 ? 'note' : 'notes'} on this phone` : ''}${s && s.outbox ? ` · ${s.outbox} waiting to send` : ''}.`;
    $('#obsOff').hidden = !(s && (s.connected || s.local || s.outbox)); $('#obsSync').hidden = !(s && s.connected);
    $('#obsGo').textContent = s && s.connected ? 'Reconnect' : 'Connect';
  }
  $('#obsF').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!vault) return;
    $('#obsErr').textContent = ''; $('#obsGo').disabled = true; $('#obsGo').textContent = 'Connecting…';
    try {
      const s = await vault.connect({ repo: $('#obsRepo').value, token: $('#obsTok').value });
      $('#obsTok').value = '';
      toast(`Obsidian connected: ${s.notes} notes. Ask "what did I write about …".`, 'OBSIDIAN');
    } catch (err) { $('#obsErr').textContent = String((err && err.message) || err); }
    $('#obsGo').disabled = false; render();
  });
  $('#obsSync').addEventListener('click', async () => { $('#obsSync').disabled = true; await safe(() => vault.sync({ force: true }), null); $('#obsSync').disabled = false; render(); });
  $('#obsOff').addEventListener('click', async () => {
    if (!confirm('Disconnect Obsidian? This wipes the token, the cached notes and pasted notes from this phone. Your vault itself is not touched.')) return;
    await safe(() => vault.disconnect(), null); render(); toast('Obsidian disconnected; nothing of it is left on this phone.', 'OBSIDIAN');
  });
  $('#obsPaste').addEventListener('click', () => {
    const r = safe(() => vault.importNote($('#obsPT').value, $('#obsPB').value), { ok: false, error: 'not available' });
    if (r.ok) { $('#obsPT').value = ''; $('#obsPB').value = ''; toast(`Saved “${r.title}” on this phone.`, 'NOTE'); } else $('#obsErr').textContent = r.error || 'Nothing to save.';
    render();
  });
  $('#obsX').addEventListener('click', () => { el.hidden = true; });
  // keep the index fresh while Jarvis is open: every 10 minutes when connected and visible (one call when nothing changed)
  setInterval(() => { if (vault && document.visibilityState === 'visible' && safe(() => vault.status().connected, false)) safe(() => vault.sync(), null); }, 10 * 60e3);
  if (vault && safe(() => vault.status().connected, false)) setTimeout(() => safe(() => vault.sync(), null), 2500);
  return { open() { render(); el.hidden = false; }, close() { el.hidden = true; }, el };
}

// ------------------------------------------------------------------------------------------------ the proactive line
// brain.headline(): the single most important thing right now. Shown once per change: dismissed = hidden until it changes.
const DISMISS = 'jarvis.proDismiss';
export function mountProactive(o) {
  style();
  const brain = () => (o && typeof o.brain === 'function' ? o.brain() : o && o.brain);
  const el = document.createElement('div');
  el.className = 'jx-pro'; el.id = 'proLine'; el.hidden = true; el.setAttribute('role', 'status');
  el.innerHTML = '<button class="t" type="button"></button><button class="x" type="button" aria-label="Dismiss">×</button>';
  if (o && o.anchor && o.anchor.parentNode) o.anchor.parentNode.insertBefore(el, o.anchor); else document.body.appendChild(el);
  let cur = null;
  function render() {
    const b = brain(), h = b && typeof b.headline === 'function' ? safe(() => b.headline(), null) : null;
    cur = h && h.text && h.level !== 'ok' ? h : null;
    if (!cur || ls.get(DISMISS) === cur.key) { el.hidden = true; return; }
    el.dataset.level = cur.level;
    el.querySelector('.t').innerHTML = `${esc(cur.text)}${cur.more ? `<small>+${cur.more} more · tap for what to do</small>` : '<small>tap for what to do</small>'}`;
    el.hidden = false;
  }
  el.querySelector('.t').addEventListener('click', () => { if (o && typeof o.onAsk === 'function') o.onAsk('What should I do now?'); });
  el.querySelector('.x').addEventListener('click', () => { if (cur) ls.set(DISMISS, cur.key); el.hidden = true; });
  return { render, el };
}

// ------------------------------------------------------------------------------------------------ the free AI key steps
export function mountKeySteps(form) {
  if (!form || form.querySelector('.jx-steps')) return null;
  style();
  const box = document.createElement('div');
  box.className = 'jx-steps';
  box.innerHTML = `<b>Free key, 1 minute (Groq, no card):</b><ol>
    <li>Open <code>console.groq.com/keys</code> in Safari and sign in with Google.</li>
    <li>Tap <b>Create API Key</b>, name it Jarvis, then <b>Copy</b>.</li>
    <li>Paste it in <b>API key</b> below and tap <b>Save</b>. Jarvis switches to Groq by itself.</li>
  </ol><small>Or Google's free Gemini key: <code>aistudio.google.com/apikey</code> → Create API key (starts with AIza), or OpenRouter's free models: <code>openrouter.ai/keys</code> (starts with sk-or-). The key stays on this phone; only your bots' numbers and the question are sent, never other keys.</small>`;
  const anchor = form.querySelector('#setProv') ? form.querySelector('#setProv').closest('label') : null;
  if (anchor) form.insertBefore(box, anchor); else form.appendChild(box);
  return box;
}

// ------------------------------------------------------------------------------------------------ the free key setup (2026-11-03)
// One screen, three steps, a Test button: Groq first (free, fastest), Gemini second, OpenRouter's free models third. The key
// goes to brain.testKey() (one tiny request to that provider only), then brain.setSmart() keeps it on this phone.
//   const ks = mountKeySetup({ brain: () => brain, toast, onSaved });   ks.open(provider?) · ks.close()
const KEY_STEPS = {
  groq: { name: 'Groq', tag: 'free, fastest', rx: /^gsk_/, hint: 'gsk_…', url: 'https://console.groq.com/keys',
    steps: ['Open <b>console.groq.com/keys</b> (button below) and sign in with Google.', 'Tap <b>Create API Key</b>, name it Jarvis, then <b>Copy</b>.', 'Paste it here, tap <b>Test</b>, then <b>Save</b>.'] },
  gemini: { name: 'Gemini', tag: 'free, Google', rx: /^AIza/, hint: 'AIza…', url: 'https://aistudio.google.com/apikey',
    steps: ['Open <b>aistudio.google.com/apikey</b> (button below) and sign in with Google.', 'Tap <b>Create API key</b>, then copy it (it starts with AIza).', 'Paste it here, tap <b>Test</b>, then <b>Save</b>.'] },
  openrouter: { name: 'OpenRouter', tag: 'free models', rx: /^sk-or-/, hint: 'sk-or-…', url: 'https://openrouter.ai/keys',
    steps: ['Open <b>openrouter.ai/keys</b> (button below) and sign in with Google.', 'Tap <b>Create Key</b>, name it Jarvis, then copy it (it starts with sk-or-).', 'Paste it here, tap <b>Test</b>, then <b>Save</b>. Jarvis uses a free model (about 50 questions a day).'] },
};
export function mountKeySetup(o) {
  const brain = () => (o && typeof o.brain === 'function' ? o.brain() : o && o.brain), toast = (o && o.toast) || (() => {});
  style();
  const el = document.createElement('div');
  el.className = 'sheet jx-key'; el.id = 'keySheet'; el.hidden = true;
  el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); el.setAttribute('aria-labelledby', 'keyT');
  el.innerHTML = `<form class="sheet-in" id="keyF" autocomplete="off">
    <h2 id="keyT">Free smart mode</h2>
    <p class="st">Answers to anything, notes into Obsidian, the weather and more, on your own free key. One minute, no card.</p>
    <div class="seg3" id="keyProv" role="group" aria-label="Provider">${Object.keys(KEY_STEPS).map((p) => `<button type="button" data-p="${p}">${esc(KEY_STEPS[p].name)}</button>`).join('')}</div>
    <div class="jx-steps" id="keySteps"></div>
    <div class="sheet-row"><a class="btn ghost" id="keyGo" target="_blank" rel="noopener noreferrer" href="#">Open the key page</a></div>
    <label>Key<input id="keyIn" type="password" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Paste the key (kept on this phone only)"></label>
    <p class="st" id="keyRes" role="status"></p>
    <div class="sheet-row"><button class="btn ghost" type="button" id="keyX">Close</button><button class="btn ghost" type="button" id="keyTest">Test</button><button class="btn solid" type="submit" id="keySave">Save</button></div>
    <p class="note">The key stays on this phone and goes only to that provider's own API. Jarvis asks you before it writes anything to Obsidian.</p>
  </form>`;
  document.body.appendChild(el);
  const $ = (s) => el.querySelector(s);
  let prov = 'groq', okFor = '', busy = false;
  function render() {
    const P = KEY_STEPS[prov], sm = safe(() => brain().smart, null);
    for (const b of $('#keyProv').children) b.setAttribute('aria-pressed', String(b.dataset.p === prov));
    $('#keySteps').innerHTML = `<b>${esc(P.name)} (${esc(P.tag)}), 3 steps:</b><ol>${P.steps.map((s) => `<li>${s}</li>`).join('')}</ol>`;
    $('#keyGo').href = P.url; $('#keyGo').textContent = `Open ${P.url.replace(/^https:\/\//, '')}`;
    $('#keyIn').placeholder = `Paste the key (${P.hint}, kept on this phone only)`;
    if (!busy) $('#keyRes').textContent = sm && sm.keys && sm.keys[prov] ? `A ${P.name} key is saved${sm.provider === prov && sm.active ? ' and in use' : ''}. Paste a new one to replace it, or tap Test.` : `No ${P.name} key yet.`;
  }
  $('#keyProv').addEventListener('click', (e) => { const b = e.target.closest('[data-p]'); if (b) { prov = b.dataset.p; okFor = ''; render(); } });
  $('#keyIn').addEventListener('input', () => {             // the key says which provider it is
    const k = $('#keyIn').value.trim(), g = Object.keys(KEY_STEPS).find((p) => KEY_STEPS[p].rx.test(k));
    if (g && g !== prov) { prov = g; render(); }
    okFor = '';
  });
  async function test() {
    const b = brain(), key = $('#keyIn').value.trim();
    if (!b || typeof b.testKey !== 'function') { $('#keyRes').textContent = 'Smart mode comes with the new Jarvis brain: reload Jarvis.'; return false; }
    busy = true; $('#keyRes').textContent = `Testing ${KEY_STEPS[prov].name}…`; $('#keyTest').disabled = true;
    let r = null;
    try { r = await b.testKey({ provider: prov, key }); } catch (_) { r = null; }
    busy = false; $('#keyTest').disabled = false;
    if (r && r.ok) { okFor = key || 'saved'; $('#keyRes').textContent = `It works: ${KEY_STEPS[prov].name} answered in ${((r.ms || 0) / 1000).toFixed(1)} s.`; return true; }
    $('#keyRes').textContent = `Not working: ${(r && r.error) || 'no answer'}.`;
    return false;
  }
  $('#keyTest').addEventListener('click', () => { test(); });
  $('#keyF').addEventListener('submit', async (e) => {
    e.preventDefault();
    const b = brain(), key = $('#keyIn').value.trim();
    if (!b || typeof b.setSmart !== 'function') return;
    if (key && okFor !== key && !(await test())) return;   // a pasted key is saved only once it answered
    safe(() => b.setSmart(key ? { provider: prov, key, on: true } : { provider: prov, on: true }));
    $('#keyIn').value = ''; okFor = '';
    el.hidden = true;
    toast(`Smart mode is on (${KEY_STEPS[prov].name}). Ask me anything.`, 'AI KEY');
    if (o && typeof o.onSaved === 'function') safe(() => o.onSaved());
  });
  $('#keyX').addEventListener('click', () => { el.hidden = true; });
  return {
    open(p) {
      if (KEY_STEPS[p]) prov = p; else { const sm = safe(() => brain().smart, null); if (sm && KEY_STEPS[sm.provider]) prov = sm.provider; }
      okFor = ''; render(); el.hidden = false;
    },
    close() { el.hidden = true; }, el,
  };
}
