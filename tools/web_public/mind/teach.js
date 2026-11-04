// OLYMPUS Mind: Teach Jarvis. The ONE place this page writes, and only into Jarvis's own three keys, in exactly the formats
// Jarvis writes them (jarvis/assistant.js and jarvis/obsidian.js), so Jarvis knows it the next time she opens:
//   jarvis.assistant.v1      a fact:  {id, t (ms), text, key: '', how: 'told'} appended to `facts` (the rest of the object is kept as it was)
//   jarvis.vault.local       a note:  {path: 'Pasted/<title>.md', text, t (ms)}  (what importNote() keeps; Jarvis indexes it)
//   jarvis.vault.learned     a line:  {t (unix s), kind: 'import', text, note: path}  (what the "learned" feed shows)
// It never touches the vault's connection key, never sends anything, and refuses passwords, keys and card numbers like Jarvis does.
//   screen(text) -> '' or the reason it will not be kept
//   teach({kind: 'fact' | 'note', text, title?}, {storage, now}) -> {ok, kind, text, path?} | {ok: false, error}
const ASSIST_KEY = 'jarvis.assistant.v1', LEARNED_KEY = 'jarvis.vault.learned', LOCAL_KEY = 'jarvis.vault.local';
const MAX_FACTS = 400, KEEP_LOCAL = 199, KEEP_LEARNED = 199;
// passwords, API keys, card numbers: never kept (the same list Jarvis uses)
const PRIVATE = /\b(pass ?word|pass ?code|pin code|pin is|api key|private key|seed phrase|recovery phrase|ssn|social security)\b|\b(gsk_|sk-|sk_live|AIza|github_pat_|ghp_|xox[bp]-)[A-Za-z0-9_-]{6,}|\b(?:\d[ -]?){13,19}\b/i;
const oneLine = (s, n) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim().slice(0, n);
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export function screen(text) {
  return PRIVATE.test(String(text || '')) ? "I won't keep logins, keys or card numbers. Your phone's keychain is the place for those." : '';
}

function read(st, key, fallback) {
  const raw = st.getItem(key);
  if (raw == null || raw === '') return fallback;
  return JSON.parse(raw);                              // throws on a half-written key: the caller refuses to overwrite it
}

function tell(storage) {                                // the same-tab poll hears a storage event; other Jarvis pages hear the channel
  try { window.dispatchEvent(new StorageEvent('storage', { key: ASSIST_KEY })); } catch (_) { /* no events */ }
  try {
    if (!storage && typeof BroadcastChannel === 'function') { const c = new BroadcastChannel('jarvis-vault'); c.postMessage({ t: Date.now() }); c.close(); }
  } catch (_) { /* no channel */ }
}

export function teach(input, { storage, now } = {}) {
  const st = storage || (() => { try { return localStorage; } catch (_) { return null; } })();
  if (!st) return { ok: false, error: 'This phone is blocking storage, so nothing can be saved.' };
  const t = typeof now === 'function' ? now() : Date.now();
  const kind = input && input.kind === 'note' ? 'note' : 'fact';
  const text = kind === 'note' ? String(input.text == null ? '' : input.text).replace(/\r/g, '').trim().slice(0, 4000) : oneLine(input && input.text, 300);
  if (!text) return { ok: false, error: kind === 'note' ? 'Write something in the note first.' : 'Tell Jarvis something first.' };
  const bad = screen(text) || screen(input && input.title);
  if (bad) return { ok: false, error: bad };
  try {
    if (kind === 'fact') {
      const d = read(st, ASSIST_KEY, {});
      const D = d && typeof d === 'object' && !Array.isArray(d) ? d : {};
      const facts = Array.isArray(D.facts) ? D.facts.slice() : [];
      if (!facts.some((f) => f && typeof f.text === 'string' && f.text.toLowerCase() === text.toLowerCase())) {
        facts.push({ id: t.toString(36) + 'm' + Math.floor(Math.random() * 1296).toString(36), t, text: cap(text), key: '', how: 'told' });
      }
      st.setItem(ASSIST_KEY, JSON.stringify({ ...D, v: 1, facts: facts.slice(-MAX_FACTS), todos: D.todos || [], notes: D.notes || [] }));
      tell(storage);
      return { ok: true, kind, text: cap(text) };
    }
    const title = oneLine(input.title, 80).replace(/[\\/:*?"<>|#^[\]]/g, ' ').replace(/\s+/g, ' ').replace(/\.+$/, '').trim()
      || 'Mind note ' + new Date(t).toISOString().slice(0, 10);
    const path = `Pasted/${title}.md`;
    const local = read(st, LOCAL_KEY, []);
    const learned = read(st, LEARNED_KEY, []);
    const keepLocal = (Array.isArray(local) ? local : []).filter((n) => n && typeof n === 'object' && n.path !== path).slice(-KEEP_LOCAL);
    const keepLearned = (Array.isArray(learned) ? learned : []).filter((n) => n && typeof n === 'object').slice(-KEEP_LEARNED);
    keepLocal.push({ path, text, t });
    keepLearned.push({ t: Math.floor(t / 1000), kind: 'import', text: 'Imported the note ' + title, note: path });
    st.setItem(LOCAL_KEY, JSON.stringify(keepLocal));
    st.setItem(LEARNED_KEY, JSON.stringify(keepLearned));
    tell(storage);
    return { ok: true, kind, text: title, path };
  } catch (e) {
    return { ok: false, error: e instanceof SyntaxError ? "Jarvis's memory on this phone looks damaged. Open Jarvis once, then try again." : 'This phone could not save that (storage is full or blocked).' };
  }
}
