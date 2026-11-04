// OLYMPUS Mind: the page's own looks (Look sheet). A skin is the UI accent, the page colour and the three colours of the nebula
// sky behind the brain. 'auto' leaves everything to the OLYMPUS theme (Jarvis's Look sheet); any other skin is applied on top of it.
//   SKINS: [{id, name, accent, bg, sky: [a, b, c]}]      skinById(id) -> the skin ('auto' when unknown)
const DEFAULT_SKY = ['#1d2f7a', '#4a1f86', '#0c5a7a'];

export const SKINS = [
  { id: 'auto', name: 'Follow OLYMPUS', accent: null, bg: null, sky: DEFAULT_SKY },
  { id: 'deep', name: 'Deep Space', accent: '#6ff6ff', bg: '#03040a', sky: DEFAULT_SKY },
  { id: 'aurora', name: 'Aurora', accent: '#58ffb8', bg: '#02080a', sky: ['#0b6b55', '#2a1f86', '#127a6e'] },
  { id: 'ember', name: 'Ember', accent: '#ff9a4d', bg: '#090402', sky: ['#7a2a0c', '#86201f', '#7a5a0c'] },
  { id: 'sakura', name: 'Sakura', accent: '#ff7ac8', bg: '#080309', sky: ['#7a1f6b', '#5a1f86', '#862a4a'] },
  { id: 'matrix', name: 'Matrix', accent: '#3dff7a', bg: '#010603', sky: ['#0b5a22', '#0c4a3a', '#1f6b0c'] },
  { id: 'gold', name: 'Gold', accent: '#f5c451', bg: '#070502', sky: ['#7a5a0c', '#6b3a1f', '#86701f'] },
  { id: 'ice', name: 'Ice', accent: '#a8dcff', bg: '#02060b', sky: ['#1f4a86', '#2a6b8a', '#3a3a86'] },
];

export function skinById(id) {
  return SKINS.find((s) => s.id === id) || SKINS[0];
}
