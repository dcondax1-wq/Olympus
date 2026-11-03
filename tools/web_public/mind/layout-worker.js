// OLYMPUS Mind: the layout's worker. Receives a graph ({pos, cluster, edges, sizes, center, alpha, gen}), runs layout.js
// until it sleeps and posts {pos, asleep, gen} after each ~12 ms slice. A newer graph stops the older run.
import { Layout, drive } from './layout.js';

const layout = new Layout();
let stop = null;

self.onmessage = (e) => {
  const g = e.data;
  if (stop) stop();
  layout.setGraph(g);
  stop = drive(layout, (pos, asleep) => {
    const out = pos.slice();
    self.postMessage({ pos: out, asleep, gen: g.gen }, [out.buffer]);
  }, 12);
};
