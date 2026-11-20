// Cloudflare Pages Function for the concept sites: POST /api/consent (same origin as the page, so no PC address on any public page).
// It only checks and stores the signed "Have our assistant call me" form in the KV namespace bound as CONSENT; the PC's caller pulls
// and deletes the entries (tools/caller/pull.py) and keeps the real record on the PC. Nothing private is stored in this file. Free tier: 1,000 KV writes a day.
// Wiring (PHASE 2, the lead / publisher): copy to functions/api/consent.js of a Pages project, bind a KV namespace named CONSENT, and set
// the variable ALLOWED_ORIGIN to the concept sites' origin (e.g. https://<user>.github.io). The sites are on GitHub Pages, so this is a
// cross-origin POST: only that one origin gets CORS; any other Origin is refused (403) before anything is stored.
const VERSION = "v2-2026-11-20";
const cors = (env) => ({ "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "null", "Access-Control-Allow-Methods": "POST",
                         "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", "Vary": "Origin" });
export async function onRequestOptions({ request, env }) {
  if (!env.ALLOWED_ORIGIN || request.headers.get("Origin") !== env.ALLOWED_ORIGIN) return new Response(null, { status: 403 });
  return new Response(null, { status: 204, headers: cors(env) });
}
export async function onRequestPost({ request, env }) {
  const say = (ok, message, status) => new Response(JSON.stringify({ ok, message }), { status, headers: { "Content-Type": "application/json", ...cors(env) } });
  if (!env.ALLOWED_ORIGIN || request.headers.get("Origin") !== env.ALLOWED_ORIGIN) return say(false, "Not allowed.", 403);
  const raw = await request.text();
  if (raw.length > 4096) return say(false, "Too big.", 413);
  let b;
  try { b = JSON.parse(raw); } catch (e) { return say(false, "Bad form.", 400); }
  const digits = String(b.phone || "").replace(/\D/g, "").replace(/^1(?=\d{10}$)/, "");
  if (digits.length !== 10) return say(false, "That does not look like a US phone number.", 400);
  if (b.agree !== true) return say(false, "Please tick the box to agree.", 400);
  if (String(b.signed_name || "").trim().length < 3) return say(false, "Please type your full name as your signature.", 400);
  if (b.version !== VERSION) return say(false, "This form is out of date; please reload the page.", 400);
  const ip = request.headers.get("CF-Connecting-IP") || "";
  const day = new Date().toISOString().slice(0, 10);
  const rl = "rl:" + day + ":" + ip;
  const n = parseInt((await env.CONSENT.get(rl)) || "0", 10);
  if (n >= 5) return say(false, "Too many requests today. Please call us instead.", 429);
  await env.CONSENT.put(rl, String(n + 1), { expirationTtl: 86400 });
  const keep = ["phone", "signed_name", "email", "window", "business", "lead_id", "agree", "version"];
  const rec = {}; for (const k of keep) rec[k] = typeof b[k] === "string" ? b[k].slice(0, 200) : b[k];
  const key = "c:" + new Date().toISOString() + ":" + crypto.randomUUID().slice(0, 8);
  await env.CONSENT.put(key, JSON.stringify({ form: rec, received: new Date().toISOString(), ip, ua: (request.headers.get("User-Agent") || "").slice(0, 200) }),
                        { expirationTtl: 60 * 60 * 24 * 30 });
  return say(true, "Thank you. Our AI assistant will call you on a weekday between 9 and 5.", 200);
}
