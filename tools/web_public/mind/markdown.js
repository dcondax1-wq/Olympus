// OLYMPUS Mind: a small markdown-ish preview for the note card. Never HTML: every piece of vault text goes in through
// textContent, so nothing in a note can run. Enough of Obsidian's markdown to read a note at a glance:
//   # / ## / ### headings, - * + bullets, 1. numbers, - [ ] / - [x] tasks, > quotes, ``` fences (shown as code),
//   **bold**, *italic*, `code`, ==highlight==, [[wikilinks|alias]] (a tap flies there when the note exists), #tags
//   mdPreview(text, {maxLines, link(name) -> id | null, onLink(id)}) -> DocumentFragment

const INLINE = /(\*\*[^*]+\*\*|==[^=]+==|`[^`]+`|\[\[[^\]]+\]\]|(?:^|\s)#[\w/-]+|\*[^*\s][^*]*\*)/g;

function inline(parent, text, opt) {
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    let tok = m[0], at = m.index;
    if (/^\s#/.test(tok)) { at += 1; tok = tok.slice(1); }            // a tag keeps the space before it
    if (at > last) parent.append(text.slice(last, at));
    last = at + tok.length;
    let e;
    if (tok.startsWith('**')) e = node('b', tok.slice(2, -2));
    else if (tok.startsWith('==')) e = node('mark', tok.slice(2, -2));
    else if (tok.startsWith('`')) e = node('code', tok.slice(1, -1));
    else if (tok.startsWith('[[')) {
      const [target, alias] = tok.slice(2, -2).split('|');
      const id = opt.link ? opt.link(target.split('#')[0].trim()) : null;
      e = node(id ? 'button' : 'span', (alias || target).trim());
      e.className = 'md-link' + (id ? '' : ' missing');
      if (id) { e.type = 'button'; e.addEventListener('click', () => opt.onLink && opt.onLink(id)); }
    } else if (tok.startsWith('#')) { e = node('span', tok); e.className = 'md-tag'; }
    else e = node('em', tok.slice(1, -1));
    parent.append(e);
  }
  if (last < text.length) parent.append(text.slice(last));
  return parent;
}

function node(tag, text) { const e = document.createElement(tag); if (text != null) e.textContent = text; return e; }

export function mdPreview(text, opt = {}) {
  const out = document.createDocumentFragment(), max = opt.maxLines || 18;
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  let list = null, listTag = '', fence = null, shown = 0;
  const close = () => { list = null; listTag = ''; };
  for (const raw of lines) {
    if (shown >= max) break;
    const line = raw.replace(/\s+$/, '');
    if (/^\s*```/.test(line)) {                                       // a code fence opens or closes
      if (fence) { fence = null; } else { close(); fence = node('pre'); out.append(fence); shown++; }
      continue;
    }
    if (fence) { fence.textContent += (fence.textContent ? '\n' : '') + line; continue; }
    if (!line.trim()) { close(); continue; }
    let m;
    if ((m = /^(#{1,6})\s+(.*)$/.exec(line))) {
      close();
      out.append(inline(node('h' + Math.min(6, m[1].length + 2)), m[2], opt));
    } else if ((m = /^\s*[-*+]\s+\[( |x|X)\]\s+(.*)$/.exec(line))) {
      if (listTag !== 'ul') { list = node('ul'); listTag = 'ul'; out.append(list); }
      const li = node('li'); li.className = 'md-task' + (m[1] !== ' ' ? ' done' : '');
      li.append(node('i'));
      list.append(inline(li, m[2], opt));
    } else if ((m = /^\s*([-*+]|\d+[.)])\s+(.*)$/.exec(line))) {
      const tag = /\d/.test(m[1]) ? 'ol' : 'ul';
      if (listTag !== tag) { list = node(tag); listTag = tag; out.append(list); }
      list.append(inline(node('li'), m[2], opt));
    } else if ((m = /^>\s?(.*)$/.exec(line))) {
      close();
      out.append(inline(node('blockquote'), m[1], opt));
    } else {
      close();
      out.append(inline(node('p'), line, opt));
    }
    shown++;
  }
  return out;
}
