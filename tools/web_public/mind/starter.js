// OLYMPUS Mind: the starter vault (tools/obsidian_pack.py writes starter/starter_pack.js: ~225 markdown notes built from the repo's own
// knowledge). This module is the page's side of it: load the notes, pack them into a .zip, join them into one markdown file, and list
// them with previews. The page NEVER writes into a vault: the owner downloads the zip and opens it in Obsidian through the Files app.
//   loadPack() -> {v, sha, notes: [{path, text}]} | null     the notes, loaded once on demand (a dynamic import, no network call of its own)
//   zipStore(notes, root?) -> Uint8Array                      a store-only .zip (no compression, UTF-8 names, CRC-32 per file), ~60 lines, no library
//   bundleMarkdown(notes) -> string                           one text to paste into Obsidian: every note after a "file:" marker line
//   folderGroups(notes) -> [{folder, notes: [{path, title, words, links, tags}]}]   for the list (top folder first, notes by name)
//   preview(note, n?) -> string                               the first lines as plain words (no frontmatter, no markup)
// ES2020 for iPhone Safari 16: no imports, no DOM, no network, no storage.

let memo = null;

/** The notes, loaded once. Null when the file is not on the site (an older build) or fails to load: the Teach page then says so. */
export async function loadPack() {
  if (memo) return memo;
  try {
    const mod = await import('./starter/starter_pack.js');
    const p = mod && mod.default;
    if (p && Array.isArray(p.notes) && p.notes.length && p.notes.every((n) => n && typeof n.path === 'string' && typeof n.text === 'string')) memo = p;
  } catch (_) { /* not deployed yet */ }
  return memo;
}

// ------------------------------------------------------------------ the zip (PKWARE appnote 4.3: local headers, data, central directory, end record)
const TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = TABLE[(c ^ bytes[i]) & 255] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** A store-only zip of {path, text} notes, every path under `root` (default the folder name the steps tell the owner to look for). */
export function zipStore(notes, root = 'OLYMPUS Starter Vault/') {
  const enc = new TextEncoder();
  const DATE = ((2026 - 1980) << 9) | (11 << 5) | 4;                  // a fixed stamp: the same zip every time
  const chunks = [], central = [];
  let offset = 0;
  const list = notes.slice().sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  for (const n of list) {
    const name = enc.encode(root + n.path), data = enc.encode(n.text), crc = crc32(data);
    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true); local.setUint16(4, 20, true); local.setUint16(6, 0x0800, true);      // version 2.0, flag: UTF-8 names
    local.setUint16(8, 0, true); local.setUint16(10, 0, true); local.setUint16(12, DATE, true);                // method 0 = stored, time 0
    local.setUint32(14, crc, true); local.setUint32(18, data.length, true); local.setUint32(22, data.length, true);
    local.setUint16(26, name.length, true); local.setUint16(28, 0, true);
    const cd = new DataView(new ArrayBuffer(46));
    cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 0x0314, true); cd.setUint16(6, 20, true); cd.setUint16(8, 0x0800, true);   // made by Unix, needs 2.0
    cd.setUint16(10, 0, true); cd.setUint16(12, 0, true); cd.setUint16(14, DATE, true);
    cd.setUint32(16, crc, true); cd.setUint32(20, data.length, true); cd.setUint32(24, data.length, true);
    cd.setUint16(28, name.length, true); cd.setUint32(38, (0o100644 << 16) >>> 0, true); cd.setUint32(42, offset, true);
    chunks.push(new Uint8Array(local.buffer), name, data);
    central.push(new Uint8Array(cd.buffer), name);
    offset += 30 + name.length + data.length;
  }
  const cdSize = central.reduce((s, c) => s + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, list.length, true); end.setUint16(10, list.length, true);
  end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
  const all = chunks.concat(central, [new Uint8Array(end.buffer)]);
  const out = new Uint8Array(offset + cdSize + 22);
  let at = 0;
  for (const c of all) { out.set(c, at); at += c.length; }
  return out;
}

// ------------------------------------------------------------------ one markdown file, the list, the previews
const TITLE = (p) => p.split('/').pop().replace(/\.md$/i, '');
const body = (text) => text.replace(/^---\n[\s\S]*?\n---\n/, '');

/** One text for the clipboard. Each note starts after a line `<!-- file: path -->`, so it can be split back into notes. */
export function bundleMarkdown(notes) {
  const head = `# OLYMPUS Starter Vault (${notes.length} notes)\n\nPaste this whole text into one new note, or better: use the .zip. Every note below starts after a marker line (an HTML comment that says file: and the note's path), so it can be split back into notes.\n`;
  return head + notes.map((n) => `\n<!-- file: ${n.path} -->\n\n${n.text.replace(/\s+$/, '')}\n`).join('\n---\n');
}

export function folderGroups(notes) {
  const map = new Map();
  for (const n of notes) {
    const folder = n.path.includes('/') ? n.path.split('/')[0] : 'Top';
    if (!map.has(folder)) map.set(folder, []);
    const tags = /^tags:\s*\[(.*)\]\s*$/m.exec(n.text);
    map.get(folder).push({ path: n.path, title: TITLE(n.path), words: (n.text.match(/\S+/g) || []).length, links: (n.text.match(/\[\[/g) || []).length,
      tags: tags ? tags[1].split(',').map((t) => t.trim()).filter(Boolean) : [] });
  }
  return [...map.entries()].sort((a, b) => (a[0] === 'Top' ? -1 : b[0] === 'Top' ? 1 : a[0] < b[0] ? -1 : 1))
    .map(([folder, list]) => ({ folder, notes: list.sort((a, b) => (a.title < b.title ? -1 : 1)) }));
}

/** The first lines of a note as plain words (frontmatter, headings marks, quote marks and [[link]] brackets removed). */
export function preview(note, n = 420) {
  const t = body(note.text).replace(/^\s*#{1,6}\s+/gm, '').replace(/^>\s?/gm, '').replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '$2').replace(/\[\[([^\]]+)\]\]/g, '$1')
    .replace(/[*`]/g, '').replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
  return t.length > n ? t.slice(0, n).replace(/\s\S*$/, '') + '...' : t;
}
