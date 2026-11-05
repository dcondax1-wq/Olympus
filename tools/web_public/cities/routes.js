// Visual navigation routes only. They do not encode correlation, flow, or a trade signal.
// One local trunk reaches every city; adjacent world trunks are joined in a ring.
export function cityRoutes(islands, worlds) {
  const groups = new Map(worlds.map(w => [w.key, []]));
  for (const is of islands) {
    if (!groups.has(is.cont)) groups.set(is.cont, []);
    groups.get(is.cont).push(is.i);
  }
  const links = [], bridges = [], anchors = [];
  for (const ids of groups.values()) {
    if (!ids.length) continue;
    anchors.push(ids[0]);
    for (let j = 1; j < ids.length; j++) {
      links.push([ids[j - 1], ids[j]]);
      if (j > 2 && j % 3 === 0) links.push([ids[j - 3], ids[j]]);
    }
  }
  for (let j = 0; j < anchors.length; j++) {
    if (anchors.length > 1) bridges.push([anchors[j], anchors[(j + 1) % anchors.length]]);
  }
  return { links: [...links, ...bridges], bridges };
}
