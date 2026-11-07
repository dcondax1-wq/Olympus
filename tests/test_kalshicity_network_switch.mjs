import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { layout, scenery } from '../tools/web_public/kalshicity/citylayout.js';
import { districtCamera, districtOptionLabel, districtTitle } from '../tools/web_public/kalshicity/citynav.js';
import { cardFreshness, cardBotStatus } from '../tools/web_public/kalshicity/cityfeed.js';
import { atlasProvenance } from '../tools/web_public/kalshicity/cityatlas.js';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const html = read('../tools/web_public/kalshicity/index.html');
const css = read('../tools/web_public/kalshicity/kalshicity.css');
const page = read('../tools/web_public/kalshicity/kalshicity.js');
const scene = read('../tools/web_public/kalshicity/cityscene.js');
const atlas = read('../tools/web_public/kalshicity/cityatlas.js');

assert.match(html, /href="\.\.\/cities\/"/);
assert.match(html, /href="\.\.\/datacity\/"/);
assert.match(html, /href="\.\/" aria-current="page"/);
assert.match(html, /id="networkToggle"[^>]+aria-expanded="false"/);
assert.match(html, /id="districtSelect"[^>]+aria-label="Switch market district"/);
assert.match(html, /kalshicity\.css\?v=k14/);
assert.match(html, /kalshicity\.js\?v=k18/);
assert.match(css, /\.district-control select[^}]*min-height:44px/);
assert.match(css, /\.network-links a\[aria-current="page"\]/);
assert.match(css, /\.network-panel-head button[^}]*width:44px; height:44px/, 'network close target stays phone-safe');
assert.match(css, /\.dock \.cams \{[^}]*align-items:stretch/, 'phone camera rail stretches every view control');
assert.match(css, /\.dock \.cams button \{[^}]*width:100%; min-width:44px; min-height:46px/, 'phone camera controls remain at least 44px wide and tall');
assert.match(css, /path\[data-kind\^="ward-"\]/);
assert.match(page, /cityscene\.js\?v=night4/);
assert.match(page, /cityfeed\.js\?v=bot18/);
assert.match(page, /cityatlas\.js\?v=skyline7/);
assert.match(page, /cityAtlas\([\s\S]*S\.demo\);/, 'demo provenance reaches the 2D fallback');
assert.match(page, /freshness = cardFreshness\(m, S\.demo\)/, 'the Jarvis card uses verified source freshness');
assert.match(page, /cardBotStatus\(bk, freshness\.sourceVerified, S\.demo\)/, 'the bot status line is explicitly source-qualified');
assert.doesNotMatch(page, /`Bot \$\{bk\.status \|\| bk\.mode\}/, 'stale running/paused text is never presented as current');
assert.match(page, /status: freshness\.status/);
assert.match(page, /t: freshness\.t,[\s\S]*stale_after: freshness\.stale_after/);
assert.doesNotMatch(page, /stale_after:\s*259200/, 'the old three-day card freshness window is removed');
assert.match(page, /road\.kind\.startsWith\('ward-'\)/);
assert.match(page, /function switchDistrict\(key\)/);
assert.match(page, /Scenic wards are not market data/);
assert.match(page, /3D moves camera · map opens edge list/);
assert.match(page, /If WebGL is unavailable, it opens the selected market’s edge list/);
assert.match(page, /else if \(S\.atlas\) S\.atlas\.focusDistrict\(d\.key\)/, 'the no-WebGL route remains wired to district details');
assert.match(atlas, /focusDistrict\(key\) \{ const d = L\.districts\.find\(\(item\) => item\.key === key\); if \(!d\) return false; openDistrict\(d\); return true; \}/, 'map fallback opens the district edge list');
assert.doesNotMatch(page, /camera only/, 'the map fallback is not mislabeled as camera-only');
assert.match(scene, /focusDistrict\(key\)/);
assert.match(scene, /'MARKET HQ'/);
assert.match(atlas, /focusDistrict\(key\)/);
assert.match(atlas, /copy\.edgeLabel/);
assert.match(atlas, /copy\.linkLabel/);
assert.match(atlas, /copy\.countPrefix/);
assert.match(atlas, /kc-atlas-source/);

const demoCopy = atlasProvenance(true);
assert.match(demoCopy.badge, /DEMO.*SAMPLE/);
assert.match(demoCopy.edgeLabel, /demo\/sample/);
assert.doesNotMatch(demoCopy.edgeLabel, /published/i);
assert.match(demoCopy.linkLabel, /not published/i);
const publishedCopy = atlasProvenance(false);
assert.equal(publishedCopy.badge, 'PUBLISHED DATA');
assert.equal(publishedCopy.edgeLabel, 'published edges');

const now = 1_800_000_000;
const staleBot = cardFreshness({ t: now, book: { feedT: now - 901, statusFresh: false, status: 'running', lastStatus: 'running' }, regime: { state: 'clear' }, counts: { doMore: 4, stop: 1 } }, false, now);
assert.equal(staleBot.status.level, 'warn', 'stale bot evidence cannot produce a green Jarvis card');
assert.equal(staleBot.status.label, 'Source unverified');
assert.equal(staleBot.t, now - 901, 'card timestamp is anchored to the stale source, not page render time');
assert.equal(staleBot.stale_after, 15 * 60, 'card expires using the feed verification window');
assert.equal(staleBot.sourceVerified, false);
assert.equal(cardBotStatus({ status: 'running', lastStatus: 'running' }, staleBot.sourceVerified), 'Last reported bot status: running (current state not confirmed by this snapshot)');
const stalePaused = cardFreshness({ t: now, book: { feedT: now - 901, statusFresh: false, status: 'Status unverified', lastStatus: 'paused' }, regime: { state: 'clear' }, counts: {} }, false, now);
assert.equal(cardBotStatus({ status: 'Status unverified', lastStatus: 'paused' }, stalePaused.sourceVerified), 'Last reported bot status: paused (current state not confirmed by this snapshot)');

const missingBotTime = cardFreshness({ t: now, book: { feedT: null, statusFresh: false }, regime: { state: 'clear' }, counts: {} }, false, now);
assert.equal(missingBotTime.status.level, 'warn');
assert.equal(missingBotTime.t, 0, 'missing source timestamp is not replaced by now');
const staleEdges = cardFreshness({ t: now - 901, book: { feedT: now - 30, statusFresh: true }, regime: { state: 'clear' }, counts: {} }, false, now);
assert.equal(staleEdges.status.level, 'warn', 'an old published edge snapshot cannot look green with a fresh bot feed');
assert.equal(staleEdges.t, now - 901);
const freshCard = cardFreshness({ t: now - 20, book: { feedT: now - 10, statusFresh: true }, regime: { state: 'clear' }, counts: { doMore: 2, stop: 1 } }, false, now);
assert.equal(freshCard.status.level, 'ok');
assert.equal(freshCard.sourceVerified, true);
assert.equal(cardBotStatus({ status: 'running' }, freshCard.sourceVerified), 'Latest verified bot status report: running');
assert.equal(freshCard.t, now - 20, 'the older of both source timestamps drives card freshness');
assert.equal(freshCard.stale_after, 15 * 60);
const demoCard = cardFreshness({ t: now, book: { feedT: now, statusFresh: true }, regime: { state: 'clear' }, counts: {} }, true, now);
assert.equal(demoCard.status.level, 'off');
assert.equal(demoCard.status.label, 'Demo data');
assert.equal(demoCard.t, 0, 'sample data is never stamped as a current published card');
assert.equal(cardBotStatus({ status: 'running' }, demoCard.sourceVerified, true), 'Demo fixture; no current bot status');

const edge = (id, market, ev) => ({
  id, label: `${market} sample`, dims: ['*', market, '*', '*', '*'], size: 1,
  n: 60, small: false, ev, status: 'HOLDING', since: '2026-11-05', first: '2026-10-01', w: 0.7,
  win: { d7: { n: 20, w: 0.7 }, d30: { n: 60, w: 0.7 }, led: { n: 60 } },
});
const model = { edges: [edge('btc-1', 'Bitcoin', 0.08), edge('eth-1', 'Ethereum', 0.04), edge('sol-1', 'Solana', 0.02)], evMax: 0.08, day: '2026-11-05', hyp: null };
const L = layout(model);
assert.equal(L.neighborhoods.length, 40, 'one capital has 40 scenery-only satellite wards');
assert.equal(L.neighborhoods.filter((ward) => ward.kind === 'scenery').length, 40);
assert.equal(L.roads.filter((road) => road.kind === 'ward-spoke').length, 5);
assert.equal(L.roads.filter((road) => road.kind === 'ward-ring').length, 40);
assert.equal(L.roads.filter((road) => road.kind === 'ward-link').length, 5);
const city = scenery(L, 4200);
const wardBlocks = city.filter((block) => block.kind === 'ward');
assert.ok(wardBlocks.length >= 40 * 4, `each ward has at least four visible buildings; got ${wardBlocks.length} blocks`);
assert.ok(wardBlocks.length <= 40 * 6, 'ward visuals stay within the instancing budget');
assert.ok(city.length <= 4200, 'the requested scenery tier is respected');
const wardCounts = new Map(L.neighborhoods.map((ward) => [ward.key, 0]));
wardBlocks.forEach((block) => wardCounts.set(block.ward, wardCounts.get(block.ward) + 1));
assert.equal(wardCounts.size, 40);
for (const [key, count] of wardCounts) assert.ok(count >= 4 && count <= 6, `${key} has a visible 4–6 block cluster, got ${count}`);
assert.equal(new Set(wardBlocks.map((block) => block.ward)).size, 40);
const wardRoads = L.roads.filter((road) => road.kind.startsWith('ward-'));
assert.ok(wardRoads.length > 0, 'the neighborhood road network is rendered');
for (const block of wardBlocks) for (const road of wardRoads) {
  const vx = road.x1 - road.x0, vz = road.z1 - road.z0;
  const t = Math.max(0, Math.min(1, ((block.x - road.x0) * vx + (block.z - road.z0) * vz) / (vx * vx + vz * vz)));
  const gap = Math.hypot(block.x - road.x0 - vx * t, block.z - road.z0 - vz * t);
  assert.ok(gap >= road.w * 0.5 + 1.25, `scenery block ${block.ward} leaves a visible road gap`);
}

const busyMarkets = ['Bitcoin', 'Ethereum', 'Solana', 'Dogecoin', 'XRP', 'HYPE', 'BNB', 'Gold', 'Other'];
const busyLayout = layout({ edges: busyMarkets.map((market, i) => edge(`market-${i}`, market, 0.08)), evMax: 0.08, day: '2026-11-05', hyp: null });
const busyWardBlocks = scenery(busyLayout, 225).filter((block) => block.kind === 'ward');
const busyCounts = new Map(busyLayout.neighborhoods.map((ward) => [ward.key, 0]));
busyWardBlocks.forEach((block) => busyCounts.set(block.ward, busyCounts.get(block.ward) + 1));
assert.equal(busyLayout.neighborhoods.length, 40);
for (const [key, count] of busyCounts) assert.ok(count >= 4 && count <= 6, `${key} stays visible with nine market districts, got ${count}`);

const hq = L.districts.find((d) => d.key === 'Downtown');
const btc = L.districts.find((d) => d.key === 'Bitcoin');
assert.equal(districtTitle(hq), 'Market HQ');
assert.match(districtOptionLabel(btc), /published edge/);
assert.match(districtOptionLabel(btc, true), /demo edge/);
const camera = districtCamera(btc);
assert.equal(camera.x, btc.cx);
assert.equal(camera.z, btc.cz);
assert.ok(camera.radius >= 30 && camera.radius <= 170);
assert.ok(camera.phi > 0 && camera.phi < Math.PI / 2);
console.log(`Kalshi City network: ${L.districts.length} data districts, ${L.neighborhoods.length} scenery wards, ${wardBlocks.length} instanced ward blocks, ${L.roads.length} roads; navigation checks passed.`);
