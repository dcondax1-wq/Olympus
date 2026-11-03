// HERMES share: one card as a 1080 x 1920 PNG (drawn on a canvas, never a screenshot of the page), then the phone's share
// sheet (Web Share API with a file), else the image opens in a new tab to save.
//   renderPNG(spec, colors) -> Promise<Blob>   spec {kicker, title, big, tone 'up'|'down'|'flat', lines: [..], foot, spark?}
//   share(blob, name)       -> Promise<'shared'|'opened'|'cancelled'>

const W = 1080, H = 1920;
const FONT = '-apple-system, "SF Pro Display", system-ui, "Segoe UI", Roboto, sans-serif';
const TONE = { up: '#5ef2a8', down: '#ff7a8a', flat: '#f4f4f6' };

function wrap(ctx, text, maxW) {
  const words = String(text || '').split(' '), lines = [];
  let cur = '';
  for (const w of words) {
    const t = cur ? cur + ' ' + w : w;
    if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t;
  }
  if (cur) lines.push(cur);
  return lines;
}

function fit(ctx, text, maxW, size, weight) {
  let s = size;
  do { ctx.font = `${weight} ${s}px ${FONT}`; s -= 6; } while (ctx.measureText(text).width > maxW && s > 40);
}

function spark(ctx, pts, x, y, w, h, color) {
  if (!Array.isArray(pts) || pts.length < 2) return;
  const lo = Math.min(...pts), hi = Math.max(...pts), r = hi - lo || 1;
  ctx.lineWidth = 10; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = color;
  ctx.shadowColor = color; ctx.shadowBlur = 30;
  ctx.beginPath();
  pts.forEach((p, i) => { const px = x + (i / (pts.length - 1)) * w, py = y + h - ((p - lo) / r) * h; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.stroke(); ctx.shadowBlur = 0;
}

export function drawCard(canvas, spec, colors) {
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const [c0, c1, c2] = colors && colors.length === 3 ? colors : ['#12081f', '#3b1a6b', '#f2c14e'];
  ctx.fillStyle = c0; ctx.fillRect(0, 0, W, H);
  let g = ctx.createRadialGradient(W * 0.2, H * 0.18, 0, W * 0.2, H * 0.18, H * 0.75);
  g.addColorStop(0, c1); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  g = ctx.createRadialGradient(W * 0.9, H * 0.85, 0, W * 0.9, H * 0.85, H * 0.6);
  g.addColorStop(0, c2 + '88'); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = 'rgba(0,0,0,.28)'; ctx.fillRect(0, 0, W, H);
  const L = 96, MW = W - 2 * L;
  ctx.fillStyle = '#ffffff'; ctx.textBaseline = 'alphabetic';
  ctx.font = `800 44px ${FONT}`; ctx.fillText('HERMES · OLYMPUS WRAPPED', L, 190);
  ctx.globalAlpha = 0.75; ctx.font = `600 40px ${FONT}`; ctx.fillText(String(spec.kicker || ''), L, 260); ctx.globalAlpha = 1;
  ctx.font = `800 92px ${FONT}`;
  let y = 520;
  for (const ln of wrap(ctx, spec.title, MW).slice(0, 3)) { ctx.fillText(ln, L, y); y += 104; }
  y += 120;
  fit(ctx, String(spec.big || ''), MW, 230, 900);
  ctx.fillStyle = TONE[spec.tone] || TONE.flat; ctx.fillText(String(spec.big || ''), L, y);
  y += 90;
  if (spec.spark) { spark(ctx, spec.spark, L, y, MW, 260, TONE[spec.tone] || '#ffffff'); y += 360; }
  ctx.fillStyle = '#f4f4f6'; ctx.font = `600 50px ${FONT}`;
  for (const line of (spec.lines || []).slice(0, 5)) {
    for (const ln of wrap(ctx, line, MW).slice(0, 2)) { if (y > H - 260) break; ctx.fillText(ln, L, y); y += 66; }
    y += 18;
  }
  ctx.globalAlpha = 0.7; ctx.font = `600 36px ${FONT}`;
  ctx.fillText(String(spec.foot || 'Paper and eval accounts. Real numbers, losses included.'), L, H - 140);
  ctx.globalAlpha = 1;
  return canvas;
}

export function renderPNG(spec, colors) {
  const c = drawCard(document.createElement('canvas'), spec, colors);
  return new Promise((ok, bad) => c.toBlob((b) => (b ? ok(b) : bad(new Error('no image'))), 'image/png'));
}

export async function share(blob, name = 'olympus-wrapped.png') {
  let file = null;
  try { file = new File([blob], name, { type: 'image/png' }); } catch (_) { file = null; }
  if (file && navigator.canShare && navigator.canShare({ files: [file] }) && navigator.share) {
    try { await navigator.share({ files: [file], title: 'OLYMPUS Wrapped' }); return 'shared'; } catch (e) { return e && e.name === 'AbortError' ? 'cancelled' : 'failed'; }
  }
  const url = URL.createObjectURL(blob);
  const w = window.open(url, '_blank');
  if (w) w.opener = null;
  else {                                                   // pop-up blocked: a download link
    const a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60e3);
  return 'opened';
}
