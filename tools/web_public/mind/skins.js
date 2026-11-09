// OLYMPUS Mind: the page's own looks (Look sheet). A skin is the UI accent, the page colour and the three colours of the nebula
// sky behind the brain. 'auto' leaves everything to the OLYMPUS theme (Jarvis's Look sheet); any other skin is applied on top of it.
//   SKINS: [{id, name, accent, bg, sky: [a, b, c]}]      skinById(id) -> the skin ('auto' when unknown)
const DEFAULT_SKY = ['#3a2c3e', '#5a3a2a', '#6b4a28'];   // AGORA dusk: plum-indigo to amber

export const SKINS = [
  { id: 'auto', name: 'Follow OLYMPUS', accent: null, bg: null, sky: DEFAULT_SKY },
  { id: 'deep', name: 'Marble night', accent: '#c8a24a', bg: '#14110e', sky: DEFAULT_SKY },
  { id: 'aurora', name: 'Olive grove', accent: '#a3ad73', bg: '#12140e', sky: ['#3a4a2a', '#4a4a2a', '#5a4a2a'] },
  { id: 'ember', name: 'Terracotta', accent: '#d9785a', bg: '#170f0b', sky: ['#5a2a1c', '#6a3a22', '#7a4a26'] },
  { id: 'sakura', name: 'Rose clay', accent: '#c98f86', bg: '#16100f', sky: ['#4a2a30', '#5a3a36', '#6a4636'] },
  { id: 'matrix', name: 'Laurel', accent: '#8a9a62', bg: '#11130d', sky: ['#2a3a26', '#34432a', '#44482a'] },
  { id: 'gold', name: 'Gold leaf', accent: '#e0b060', bg: '#16120a', sky: ['#5a4420', '#6b5026', '#7a5a2a'] },
  { id: 'ice', name: 'Aegean', accent: '#7fa6c0', bg: '#0f1316', sky: ['#243a4a', '#2a4a5a', '#34485a'] },
];

export function skinById(id) {
  return SKINS.find((s) => s.id === id) || SKINS[0];
}
