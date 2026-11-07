import assert from 'node:assert/strict';
import { normalize } from '../tools/web_public/oracle/data.js';

const FUTURE_S = 5 * 60;

const now = 1_800_000_000;
const source = (t, extra = {}) => ({
  kind: 'le-live',
  t,
  price: 20_000,
  pc: { brain: { price: 20_000, stage: { key: 'levels', label: 'Levels' } } },
  board: { map: { price: 20_000, levels: [] }, lit: {} },
  ...extra,
});

assert.equal(normalize(source(now), now)?.age_s, 0, 'a current publisher remains valid');
assert.equal(normalize(source(now - 1_201), now)?.age_s, 1_201, 'an old publisher remains visible for LAST SEEN handling');
assert.ok(normalize(source(now + FUTURE_S), now), 'the documented small clock-skew allowance is accepted');
assert.equal(normalize(source(now + FUTURE_S + 1), now), null,
  'a farther-ahead publisher cannot claim current data or outrank a valid source');
assert.ok(normalize(source(now + FUTURE_S + 1, { demo: true }), now),
  'historical/sample replay documents keep their own replay clock');

console.log('oracle future-source freshness: 5/5');
