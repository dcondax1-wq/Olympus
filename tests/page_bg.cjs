// The page's EFFECTIVE background (QUALITY 2026-11-20): body's colour when not transparent, else <html>'s (OLYMPUS NIGHT paints
// <html> and leaves <body> transparent). Same rule as tests/page_bg.py. Use inside page.evaluate: `bg: ${PAGE_BG}` in a template,
// or page.evaluate(PAGE_BG_FN).
const PAGE_BG = "(() => { const t = (c) => !c || c === 'transparent' || /rgba\\([^)]*,\\s*0\\)$/.test(c); const b = getComputedStyle(document.body).backgroundColor; return t(b) ? getComputedStyle(document.documentElement).backgroundColor : b; })()";
const NIGHT_BLACKS = ['rgb(0, 0, 0)', 'rgb(4, 3, 5)'];
const nightBlack = (bg) => NIGHT_BLACKS.includes(String(bg || '').trim());
module.exports = { PAGE_BG, NIGHT_BLACKS, nightBlack };
