/*! Front-desk chat (agency/upsells): answers from the business's own facts. No AI service, tracking, cookies or storage. */
// Source of chat/widget.min.js (the file make_chat.py fills with one client's facts). Rebuild after any edit:
//   python agency/upsells/build_widget.py        (terser 5.39.0 via npx; the test checks the .min file matches this source)
// Plain ES2017 (iPhone Safari 12+): no ?. or ??, no template strings. Every client-given text goes in with textContent.
(function () {
"use strict";
var W = typeof window != "undefined" ? window : globalThis;
if (W.FrontDeskChat) return;
var C = __FDC_CONFIG__;
var D = W.document;
var DAYS = "Sunday Monday Tuesday Wednesday Thursday Friday Saturday".split(" ");

// ---------------------------------------------------------------- words: normalise, stem, fuzzy match (make_chat.py has the same norm/stem/SYN)
var STOP = {}, SYN = {};
"does your what when where which could would will please there this that have with some from they them".split(" ").forEach(function (w) { STOP[w] = 1; });
"u:you r:are ur:your wat:what whats:what_is tmrw:tomorrow tmr:tomorrow tommorow:tomorrow 2day:today tonite:tonight hrs:hours appt:appointment pls:please plz:please thx:thanks ty:thanks"
  .split(" ").forEach(function (p) { p = p.split(":"); SYN[p[0]] = p[1].replace(/_/g, " "); });

function norm(s) {
  s = String(s || "").toLowerCase();
  if (s.normalize) s = s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  return s.replace(/['\u2019\x60]/g, "").replace(/&/g, " and ").replace(/\$/g, " dollar ").replace(/[^a-z0-9]+/g, " ").trim();
}
function stem(w) {
  if (w.length > 4 && w.slice(-3) == "ies") return w.slice(0, -3) + "y";
  var o = w;
  if (w.length > 5 && w.slice(-3) == "ing") w = w.slice(0, -3);
  else if (w.length > 4 && w.slice(-2) == "ed") w = w.slice(0, -2);
  else if (w.length > 3 && w.slice(-1) == "s" && w.slice(-2) != "ss") w = w.slice(0, -1);
  if (w != o && /([b-df-hj-km-np-tv-z])\1$/.test(w) && !/(ll|ss|zz)$/.test(w)) w = w.slice(0, -1);
  if (w.length > 3 && w.slice(-1) == "e") w = w.slice(0, -1);
  return w;
}
function words(s) {
  var out = [];
  norm(s).split(" ").forEach(function (w) {
    if (w) (SYN[w] || w).split(" ").forEach(function (x) { out.push({w: x, s: stem(x)}); });
  });
  return out;
}
function keys(str) {
  var out = [];
  str.split("|").forEach(function (k) {
    var m = /^(.*):([0-9.]+)$/.exec(k), wt = 1, t;
    if (m) { k = m[1]; wt = +m[2]; }
    t = words(k);
    if (t.length) out.push({t: t, w: wt});
  });
  return out.sort(function (a, b) { return b.t.length - a.t.length; });
}
function dist(a, b) {
  var m = a.length, n = b.length, d = [], i, j;
  for (i = 0; i <= m; i++) { d[i] = [i]; for (j = 1; j <= n; j++) d[i][j] = i ? 0 : j; }
  for (i = 1; i <= m; i++) for (j = 1; j <= n; j++) {
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] == b[j - 1] ? 0 : 1));
    if (i > 1 && j > 1 && a[i - 1] == b[j - 2] && a[i - 2] == b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
  }
  return d[m][n];
}
// 1 = same word or stem, 0.8 = a typo of a word of 5+ letters (1 letter off; 2 for 8+ letters), else 0
function sim(q, k) {
  if (q.s == k.s || q.w == k.w) return 1;
  if (STOP[q.w] || STOP[k.w] || q.w.length < 4 || k.w.length < 5 || /\d/.test(q.w + k.w)) return 0;
  var lim = k.w.length > 7 ? 2 : 1;
  return Math.abs(q.w.length - k.w.length) <= lim && (dist(q.w, k.w) <= lim || (k.s.length > 4 && dist(q.s, k.s) <= lim)) ? 0.8 : 0;
}
// one key against the question; a phrase needs its words in order (one stray word allowed between) and scores 1.2 x per word
function hit(q, key, used) {
  var t = key.t, i, j, k, s, f, tot, idx, best = 0, bi = -1;
  if (t.length == 1) {
    for (i = 0; i < q.length; i++) if (!used[i] && (s = sim(q[i], t[0])) > best) { best = s; bi = i; }
    if (bi >= 0) used[bi] = 1;
    return best * key.w;
  }
  for (i = 0; i < q.length; i++) {
    if (used[i] || !(s = sim(q[i], t[0]))) continue;
    tot = s; idx = [i];
    for (j = 1; j < t.length; j++) {
      for (f = -1, k = idx[j - 1] + 1; k <= idx[j - 1] + 2 && k < q.length; k++) if (!used[k] && (s = sim(q[k], t[j]))) { f = k; break; }
      if (f < 0) break;
      tot += s; idx.push(f);
    }
    if (j == t.length) { idx.forEach(function (x) { used[x] = 1; }); return tot * 1.2 * key.w; }
  }
  return 0;
}
function score(q, ks) { var used = {}, s = 0; ks.forEach(function (k) { s += hit(q, k, used); }); return s; }
function pick(list, q) { var b = null, bs = 0.79; list.forEach(function (e) { var s = score(q, e.k); if (s > bs) { bs = s; b = e; } }); return b; }

var INT = C.it.map(function (x) { return {id: x[0], kind: x[1] || (x[4] ? "faq" : x[0]), chip: x[2], k: keys(x[3]), a: x[4], x: x[5] ? x[5].split(" ") : []}; });
var BY = {}; INT.forEach(function (it) { BY[it.id] = it; });
var SV = C.sv.map(function (s) { return {n: s[0], p: s[1], d: s[2], k: keys(s[0] + "|" + s[3])}; });
var AR = C.ar;
var TOWNS = AR ? AR.w.map(function (t) { return {n: t, k: keys(t)}; }) : [];
var DAYW = {sun: 0, mon: 1, tue: 2, tues: 2, wed: 3, thu: 4, thur: 4, thurs: 4, fri: 5, sat: 6};
DAYS.forEach(function (d, i) { DAYW[d.toLowerCase()] = i; });
var HOL = /\b(holiday|christmas|xmas|thanksgiving|easter|new year|july 4|4th of july|memorial day|labor day)/;

// -> {ids: up to 2 intents, sv: a service named, town / zip, day: weekday asked about, rel: today/tomorrow/weekend, hol}
function understand(text) {
  var q = words(text), r = [], m = {sv: pick(SV, q), town: pick(TOWNS, q), zip: null, day: -1, rel: "", hol: HOL.test(norm(text))};
  q.forEach(function (t) {
    var d = DAYW[t.w] != null ? DAYW[t.w] : DAYW[t.s];
    if (/^\d{5}$/.test(t.w)) m.zip = t.w;
    if (d != null) m.day = d;
    if (/^(today|tonight|now)$/.test(t.w)) m.rel = m.rel || "today";
    if (t.w == "tomorrow") m.rel = "tomorrow";
    if (t.s == "weekend") m.rel = "weekend";
  });
  INT.forEach(function (it, i) {
    var s = score(q, it.k);
    if (it.kind == "services" && m.sv) s += 1;
    if (it.kind == "area" && (m.town || m.zip)) s += 1.5;
    if (it.kind == "hours") s += m.hol ? 0.8 : m.day >= 0 ? 0.5 : 0;
    if (s >= 0.8) r.push({it: it, s: s, i: i});
  });
  r.sort(function (a, b) { return b.s - a.s || a.i - b.i; });
  var real = r.filter(function (x) { return !/^(greet|thanks|bye)$/.test(x.it.kind); });
  if (real.length) r = real;
  if (r.length > 1 && r[1].s < r[0].s * 0.75) r = r.slice(0, 1);
  m.ids = r.slice(0, 2).map(function (x) { return x.it.id; });
  return m;
}

// ---------------------------------------------------------------- opening hours, in the business's own time zone
function pad(n) { return (n < 10 ? "0" : "") + n; }
function addDays(ymd, k) { var p = ymd.split("-"); return new Date(Date.UTC(+p[0], p[1] - 1, +p[2] + k)).toISOString().slice(0, 10); }
// the business's local weekday (0 = Sunday), minute of the day and date, whatever the visitor's own time zone (make_chat checks C.tz)
function zoned(dt) {
  var p = {};
  new Intl.DateTimeFormat("en-US", {timeZone: C.tz, weekday: "short", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false})
    .formatToParts(dt || new Date()).forEach(function (x) { p[x.type] = x.value; });
  return {d: "SunMonTueWedThuFriSat".indexOf(p.weekday) / 3, m: (p.hour % 24) * 60 + +p.minute, ymd: p.year + "-" + p.month + "-" + p.day};
}
function fmtT(m) { m %= 1440; var h = Math.floor(m / 60), mi = m % 60; return (h % 12 || 12) + (mi ? ":" + pad(mi) : "") + (h < 12 ? " am" : " pm"); }
function on(d, ymd) { return C.x[ymd] != null ? [] : C.h[d]; }
function state(dt) {
  var z = zoned(dt), t = on(z.d, z.ymd), y = on((z.d + 6) % 7, addDays(z.ymd, -1)), i, k, r, d;
  for (i = 0; i < t.length; i++) if (z.m >= t[i][0] && z.m < t[i][1]) return {open: 1, until: t[i][1], all: t[i][1] - t[i][0] >= 1440, z: z};
  for (i = 0; i < y.length; i++) if (z.m < y[i][1] - 1440) return {open: 1, until: y[i][1], z: z};
  for (k = 0; k < 8; k++) {
    d = (z.d + k) % 7; r = on(d, addDays(z.ymd, k));
    for (i = 0; i < r.length; i++) if (k || r[i][0] > z.m) return {open: 0, next: {k: k, d: d, m: r[i][0]}, z: z};
  }
  return {open: 0, z: z};
}
// next opening: "today at 9 am" / "tomorrow at 9 am" / "on Tuesday at 9 am" (short: "9 am" / "tomorrow 9 am" / "Tue 9 am")
function when(n, short) {
  if (!n) return short ? "" : "soon";
  var day = n.k == 0 ? (short ? "" : "today") : n.k == 1 ? "tomorrow" : (short ? DAYS[n.d].slice(0, 3) : "on " + DAYS[n.d]);
  return (day ? day + (short ? " " : " at ") : "") + fmtT(n.m);
}
function statusLine(st) {
  if (st.open) return st.all ? "We're open 24 hours today." : "We're open now until " + fmtT(st.until) + ".";
  return st.next ? "We're closed right now and open " + when(st.next) + "." : "We're closed for now.";
}
function dayText(d, k, z) {
  var note = C.x[addDays(z.ymd, k)];
  return note != null ? "closed" + (note ? " (" + note + ")" : "") : C.dt[d];
}
function fill(s, st) { return s.replace(/\{status\}/g, statusLine(st)).replace(/\{next_open\}/g, when(st.next)); }

// ---------------------------------------------------------------- answers: {t: text, a: buttons, lead: form, chips: suggestions}
function answerOne(it, m, st) {
  var z = st.z, k, t, bk = C.bk ? ["book"] : ["call"];
  switch (it.kind) {
    case "hours":
      if (m.hol) {
        t = Object.keys(C.x).filter(function (d) { return d >= z.ymd; }).sort().slice(0, 4).map(function (d) { return "• " + (C.x[d] || "Closed") + " (" + +d.slice(5, 7) + "/" + +d.slice(8) + ")"; });
        return {t: t.length ? "We're closed on:\n" + t.join("\n") + "\nOther days we keep our normal hours." : "Holiday hours can change, so please call to check.", a: ["call"]};
      }
      if (m.rel == "weekend") return {t: "This weekend: Saturday " + dayText(6, (6 - z.d + 7) % 7, z) + ", Sunday " + dayText(0, (7 - z.d) % 7, z) + ".", a: bk};
      if (m.day >= 0 || m.rel) {
        k = m.day >= 0 ? (m.day - z.d + 7) % 7 : m.rel == "tomorrow" ? 1 : 0;
        t = dayText((z.d + k) % 7, k, z);
        return {t: (k == 0 ? "Today" : k == 1 ? "Tomorrow" : "On " + DAYS[(z.d + k) % 7]) + " we're " + (t.indexOf("closed") ? "open " : "") + t + "." + (k ? "" : " " + statusLine(st)), a: bk};
      }
      return {t: statusLine(st) + "\n" + C.wk.map(function (l) { return "• " + l; }).join("\n"), a: st.open ? bk : ["lead"]};
    case "prices":
      if (m.sv) return {t: m.sv.n + ": " + m.sv.p + (m.sv.d ? " (about " + m.sv.d + ")" : "") + ".", a: bk};
      if (SV.length) return {t: "Our prices:\n" + SV.slice(0, 9).map(function (s) { return "• " + s.n + ": " + s.p; }).join("\n") + (C.pn ? "\n" + C.pn : ""), a: bk};
      return {t: C.pn || "For prices, please give us a call.", a: C.mu ? ["menu", "call"] : ["call"]};
    case "services":
      return {t: m.sv ? "Yes, we do that: " + m.sv.n + " (" + m.sv.p + ")." : "Here's what we do:\n" + SV.map(function (s) { return "• " + s.n; }).join("\n") + "\nSomething else? Just ask.", a: [C.bk ? "book" : "lead", "call"]};
    case "area":
      return {t: m.town ? "Yes, we serve " + m.town.n + "!" : m.zip && AR.z.length && AR.z.indexOf(m.zip) >= 0 ? "Yes, " + m.zip + " is in our area!"
        : (m.zip && AR.z.length ? m.zip + " may be outside our area. " : "") + "We serve " + AR.t + ". Not sure? Leave your address and we'll check.", a: ["lead", "call"]};
    case "book":
      return C.bk ? {t: "You can do it online in about a minute:", a: ["book", "call"]} : {t: "Call or text us to set up a time, or leave your number and we'll reach out.", a: ["call", "text", "lead"]};
    case "dir":
      return C.ad ? {t: "We're at " + C.ad + "." + (C.dn ? "\n" + C.dn : ""), a: C.mp ? ["map", "call"] : ["call"]} : {t: "We come to you! We serve " + (AR ? AR.t : C.city) + ".", a: ["lead", "call"]};
    case "pay":
      return {t: "We take " + C.pay + "."};
    case "contact":
      return {t: "You can call us at " + C.phl + (C.sm ? " or text " + (C.sm == C.ph ? "the same number" : C.sml) : "") + ". " + statusLine(st), a: ["call", "text", "lead"]};
    case "lead":
      return {t: "Sure! Leave your name and number and we'll get back to you " + (st.open ? "shortly." : when(st.next) + "."), lead: 1};
    case "greet":
      return {t: "Hi! What can I help you with?", chips: 1};
    case "thanks":
      return {t: "You're welcome! Anything else?", chips: 1};
    case "bye":
      return {t: "Thanks for stopping by. Have a great day!"};
  }
  return {t: fill(it.a, st), a: it.x};
}
function answer(text, dt) {
  var m = understand(text), st = state(dt);
  if (!m.ids.length) return [{t: C.fb, a: ["call", "text", "lead"], chips: 1, miss: 1}];
  return m.ids.map(function (id) { var a = answerOne(BY[id], m, st); a.id = id; return a; });
}
function greeting(dt) {
  var st = state(dt);
  return st.open ? {t: fill(C.g, st), chips: 1} : {t: fill(C.ah, st), chips: 1, a: C.em ? ["emergency", "lead"] : ["lead"]};
}

var API = W.FrontDeskChat = {id: C.id, understand: understand, answer: answer, greeting: greeting, state: state, words: words};
if (!D || !D.documentElement.attachShadow) return;

// ---------------------------------------------------------------- the widget, in a shadow root (the site's CSS can't touch it, it can't touch the site)
// The HTML is built from strings: every text from the client file goes through esc() first (the test feeds it hostile text).
var MQ = function (q) { return W.matchMedia && W.matchMedia(q).matches; };
var COARSE = MQ("(pointer: coarse)");
var IC = {chat: '<path d="M4 5h16v11H10l-5 4v-4H4z"/>', call: '<path d="M5 3h4l2 5-3 2a11 11 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
  book: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>', map: '<path d="M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10z"/><circle cx="12" cy="11" r="2"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>', go: '<path d="M12 19V6M6 11l6-6 6 6"/>'};
IC.text = IC.chat; IC.menu = IC.book; IC.lead = IC.emergency = IC.call;
var HREF = {call: "tel:" + C.ph, text: C.sm && "sms:" + C.sm, emergency: "tel:" + (C.em || C.ph), book: C.bk, map: C.mp, menu: C.mu};
var LBL = {call: "Call", text: "Text", emergency: "Emergency line", book: C.bkl, map: "Directions", menu: "Menu", lead: "Leave my number"};
var NUM = {call: C.phl, text: C.sml, emergency: C.eml || C.phl};
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
function svg(n, s) { s = s || 18; return '<svg viewBox="0 0 24 24" width="' + s + '" height="' + s + '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + IC[n] + "</svg>"; }
// a button: tel:/sms: links, the booking / map / menu link (new tab), or the in-chat "leave my number" form
function btn(a) {
  var h = HREF[a], t = svg(a) + esc(LBL[a]);
  if (a == "lead") return "<button class=bt type=button data-a=lead>" + t + "</button>";
  return h ? '<a class=bt href="' + esc(h) + '"' + (/^http/.test(h) ? " target=_blank rel=noopener" : "") + (NUM[a] ? ' aria-label="' + esc(LBL[a] + " " + NUM[a]) + '"' : "") + ">" + t + "</a>" : "";
}
var CSS = ":host{all:initial}*{box-sizing:border-box;margin:0;padding:0;font:inherit;color:inherit}" +
  ".w{font:15px/1.45 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#1f2430}" +
  "button,a{cursor:pointer;-webkit-tap-highlight-color:transparent}.g{display:grid;place-items:center;border:0;border-radius:50%;flex:none}" +
  ".l,.p{position:fixed;right:18px;z-index:2147483000}" +
  ".l{bottom:calc(18px + env(safe-area-inset-bottom));width:62px;height:62px;background:var(--f);color:var(--i);box-shadow:0 10px 28px #0f172a47}" +
  ".on .hs i{background:#22c55e}" +
  ".p{bottom:calc(94px + env(safe-area-inset-bottom));width:min(384px,calc(100vw - 24px));height:min(640px,calc(100vh - 116px));background:#fff;border-radius:20px;" +
  "box-shadow:0 24px 64px #0f172a4d;display:flex;flex-direction:column;overflow:hidden;opacity:0;visibility:hidden;transform:translateY(14px);transition:.18s}" +
  ".open .p{opacity:1;visibility:visible;transform:none}" +
  "@media (max-width:520px){.p{right:0;left:0;top:var(--vt,0);bottom:auto;width:auto;height:var(--vh,100%);border-radius:0}.open .l{display:none}}" +
  ".hd{background:var(--f);color:var(--i);padding:12px 8px 12px 16px;display:flex;gap:12px;align-items:center}" +
  ".av{width:42px;height:42px;background:#ffffff38;font-weight:700}.hn{font-weight:700;font-size:16px}" +
  ".hs{font-size:13px;display:flex;align-items:center;gap:6px}.hs i{width:8px;height:8px;border-radius:50%;background:#cbd2d9}" +
  ".x{margin-left:auto;width:44px;height:44px;background:none}" +
  ".lg{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:16px 14px 10px;display:flex;flex-direction:column;gap:10px}" +
  ".m,.fm{animation:fdcf .25s}@keyframes fdcf{from{opacity:0;transform:translateY(6px)}}" +
  ".m{max-width:88%;padding:10px 13px;border-radius:18px 18px 18px 6px;background:#f1f3f5;align-self:flex-start;overflow-wrap:anywhere}" +
  ".u{background:var(--f);color:var(--i);border-radius:18px 18px 6px;align-self:flex-end}.m>*+*{margin-top:6px}.m ul{padding-left:18px}" +
  ".ac,.ch{display:flex;flex-wrap:wrap;gap:8px}.ac{margin-top:10px}" +
  ".bt,.cp{display:inline-flex;align-items:center;gap:7px;min-height:44px;padding:8px 15px;border:0;border-radius:99px;background:var(--f);color:var(--i);font-weight:600;font-size:14.5px;text-decoration:none}" +
  ".cp{border:1.5px solid var(--a);background:#fff;color:var(--a)}" +
  ".bar{display:flex;gap:8px;padding:10px 12px 0;border-top:1px solid #dfe3e8}.bar .bt{flex:1;justify-content:center;padding:8px 6px;background:var(--s);color:var(--a)}" +
  ".in{display:flex;gap:8px;padding:10px 12px 6px}" +
  "input,textarea{width:100%;min-width:0;height:48px;padding:0 15px;border:1.5px solid #8a94a0;border-radius:16px;background:#fff;color:#1f2430;font-size:16px;font-weight:400}" +
  "input:focus,textarea:focus{border-color:var(--a);outline:none}.go{width:48px;height:48px;background:var(--f);color:var(--i)}" +
  ".ft,small{font-size:12px;color:#5c6573}.ft{text-align:center;padding:2px 14px calc(10px + env(safe-area-inset-bottom))}" +
  ".fm{display:grid;gap:11px;border:1.5px solid #dfe3e8;border-radius:18px;padding:14px}.fm b{font-weight:700}.fm label{display:grid;gap:5px;font-size:13.5px;font-weight:600;color:#5c6573}" +
  "textarea{height:76px;padding:11px 15px}[aria-invalid=true]{border-color:#c62828}.er{color:#b42318}.er:empty,.hp{display:none}" +
  ":focus-visible{outline:3px solid var(--a);outline-offset:2px}.hd :focus-visible{outline-color:var(--i)}" +
  "@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}";

var host = D.createElement("div"), wrap, logEl, input, said = [], opened = 0, greeted = 0;
host.setAttribute("data-frontdesk-chat", C.id);
function $(s) { return wrap.querySelector(s); }
function build() {
  var n = esc(C.n);
  wrap = D.createElement("div");
  wrap.className = "w";
  wrap.innerHTML = "<style>" + CSS + "</style><button class='l g' type=button aria-label=\"Chat with " + n + ": hours, prices, booking\" aria-expanded=false aria-controls=fdc-p>" + svg("chat", 28) + "</button>" +
    "<div class=p id=fdc-p role=dialog aria-label=\"" + n + " front desk chat\"><div class=hd><div class='av g' aria-hidden=true>" +
    esc(C.n.replace(/[^A-Za-z0-9 ]/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase()) +
    "</div><div><h2 class=hn tabindex=-1>" + n + "</h2><div class=hs></div></div><button class='x g' type=button aria-label='Close chat'>" + svg("x", 22) + "</button></div>" +
    "<div class=lg role=log aria-live=polite aria-label=Conversation></div><div class=bar>" + ["call", "text", C.bk ? "book" : C.mu ? "menu" : "lead"].map(btn).join("") + "</div>" +
    "<form class=in><input aria-label='Type your question' placeholder='Type your question…' autocomplete=off enterkeyhint=send maxlength=300><button class='go g' aria-label=Send>" + svg("go", 22) + "</button></form>" +
    "<p class=ft>Instant answers. Nothing you type is kept unless you send your details.</p></div>";
  "fias".split("").forEach(function (v) { wrap.style.setProperty("--" + v, C.col[v]); });
  if (C.font) wrap.style.fontFamily = C.font;
  host.attachShadow({mode: "open"}).appendChild(wrap);
  logEl = $(".lg"); input = $("input");
  $(".l").onclick = function () { opened ? close() : open(); };
  $(".x").onclick = close;
  $("form").onsubmit = function (e) { e.preventDefault(); var v = input.value; input.value = ""; ask(v); };
  D.addEventListener("keydown", function (e) { if (e.key == "Escape") close(); });
  wrap.onclick = function (e) {                                   // the suggested questions and every "leave my number" button
    var b = e.target.closest("[data-q],[data-a]"), it = b && (BY[b.getAttribute("data-q")] || {kind: "lead", chip: LBL.lead});
    if (!it) return;
    user(it.chip);
    if (it.id) said.push(it.chip);
    reply([answerOne(it, {}, status())]);
  };
  status();
  D.body.appendChild(host);
}
function status() {
  var st = state();
  wrap.classList.toggle("on", !!st.open);
  $(".hs").innerHTML = "<i></i>" + esc(st.open ? (st.all ? "Open 24 hours" : "Open now · until " + fmtT(st.until)) : "Closed" + (st.next ? " · opens " + when(st.next, 1) : ""));
  return st;
}
function add(h) { logEl.insertAdjacentHTML("beforeend", h); logEl.scrollTop = logEl.scrollHeight; }
function user(t) { add("<div class='m u'>" + esc(t) + "</div>"); }
// the answers first, then (once) the lead form and the suggested questions they asked for
function reply(list) {
  var lead, chips;
  list.forEach(function (a) {
    var h = "", ul = 0, acts = (a.a || []).map(btn).join("");
    a.t.split("\n").forEach(function (ln) {
      var li = !ln.indexOf("• ");
      h += (li && !ul ? "<ul>" : !li && ul ? "</ul>" : "") + (li ? "<li>" + esc(ln.slice(2)) + "</li>" : "<p>" + esc(ln) + "</p>");
      ul = li;
    });
    add("<div class=m>" + h + (ul ? "</ul>" : "") + (acts ? "<div class=ac>" + acts + "</div>" : "") + "</div>");
    lead = lead || a.lead; chips = chips || a.chips;
  });
  if (lead) leadForm(said[said.length - 1] || "");
  if (chips) add("<div class=ch role=group aria-label='Suggested questions'>" + C.ch.map(function (id) { return "<button class=cp type=button data-q=" + id + ">" + esc(BY[id].chip) + "</button>"; }).join("") + "</div>");
}
function ask(text) {
  text = String(text || "").trim();
  if (!text) return;
  user(text); said.push(text); status();
  reply(answer(text));
}
function leadForm(need) {
  var old = logEl.querySelector(".fm");
  if (old) old.remove();                                           // one form at a time, at the bottom
  add("<form class=fm aria-label='Leave your details' novalidate><b>We'll call or text you back</b><label>Your name<input name=name autocomplete=name></label><label>Phone number<input name=phone type=tel autocomplete=tel></label>" +
    "<label>What do you need?<textarea name=need></textarea></label><input class=hp name=bot-field tabindex=-1 aria-hidden=true><p class=er role=alert></p><button class=bt>Send</button><small>Only " + esc(C.n) +
    " gets your name, number and this chat, to reply to you.</small></form>");
  var f = logEl.lastElementChild, E = f.elements;
  if (need.split(" ").length > 2 && understand(need).ids.join() != "lead") E.need.value = need;
  f.onsubmit = function (e) {
    e.preventDefault();
    var name = E.name.value.trim(), phone = E.phone.value.trim(), bad = phone.replace(/\D/g, "").length < 10, er = f.querySelector(".er"), b = f.querySelector("button");
    E.name.setAttribute("aria-invalid", !name); E.phone.setAttribute("aria-invalid", bad);
    if (!name || bad) { er.textContent = name ? "Please add a phone number we can call (10 digits)." : "Please add your name."; return (name ? E.phone : E.name).focus(); }
    er.textContent = ""; b.disabled = true; b.textContent = "Sending…";
    var data = {"form-name": C.f.n, name: name, phone: phone, need: E.need.value.trim().slice(0, 1000), page: W.location.origin + W.location.pathname, chat: said.slice(-6).join(" | ").slice(0, 600), "bot-field": E["bot-field"].value};
    var done = function () { var st = state(); f.remove(); reply([{t: "Thanks, " + name.split(" ")[0] + "! " + C.n + " will get back to you at " + phone + (st.open ? " shortly." : " " + when(st.next) + ".")}]); };
    if (data["bot-field"]) return done();                          // a bot filled the hidden field: say thanks, send nothing
    send(data).then(done, function () { b.disabled = false; b.textContent = "Try again"; er.textContent = "That didn't go through. Please try again, or call us at " + C.phl + "."; });
  };
  if (!COARSE) E.name.focus();
}
// the one request this widget makes: a urlencoded POST to the site's own Netlify form (cross-site only if form_action is a full URL)
function send(data) {
  var url = C.f.a, cross = /^https?:/.test(url) && url.indexOf(W.location.origin + "/"), body = Object.keys(data).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(data[k]); }).join("&");
  return W.fetch(url, {method: "POST", headers: {"Content-Type": "application/x-www-form-urlencoded"}, body: body, mode: cross ? "no-cors" : "same-origin", credentials: "omit"})
    .then(function (r) { if (!cross && !r.ok) throw Error(r.status); });
}
// phones: the panel fills the visible screen, above the keyboard
function fit() { var v = W.visualViewport; if (v) { wrap.style.setProperty("--vh", v.height + "px"); wrap.style.setProperty("--vt", v.offsetTop + "px"); } }
function open() {
  if (opened) return;
  opened = 1; wrap.classList.add("open"); $(".l").setAttribute("aria-expanded", "true"); status();
  if (!greeted) { greeted = 1; reply([greeting()]); }
  if (MQ("(max-width:520px)")) {
    D.documentElement.style.overflow = "hidden"; fit();
    if (W.visualViewport) W.visualViewport.onresize = W.visualViewport.onscroll = fit;
  }
  setTimeout(function () { $(COARSE ? ".hn" : "input").focus(); }, 60);
}
function close() {
  if (!opened) return;
  opened = 0; wrap.classList.remove("open"); $(".l").setAttribute("aria-expanded", "false"); D.documentElement.style.overflow = "";
  $(".l").focus();
}
API.open = open; API.close = close; API.ask = function (t) { open(); ask(t); };
if (D.readyState == "loading") D.addEventListener("DOMContentLoaded", build); else build();
})();
