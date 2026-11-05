// Cities' front door remains useful before a GPU, a live feed or a camera is ready.
// These skylines are illustrations. Counts and details always come from the catalogue / dataset.
const NS = 'http://www.w3.org/2000/svg';
import { cityRoutes } from './routes.js?v=r1';
const node = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const svgNode = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
export const WORLDS = [
  ['trading', 'Trading', '#66c8ff', 125, 110], ['research', 'Research', '#b89aff', 325, 110],
  ['money', 'Money', '#ffd781', 510, 110], ['kalshi', 'Kalshi', '#5ef5cc', 510, 300],
  ['life', 'Life', '#9aeda7', 125, 300], ['obsidian', 'Obsidian', '#f0b4ec', 325, 300],
];
export function skyline(seed = 0, color = '#b89aff', compact = false) {
  const svg = svgNode('svg', { viewBox: '0 0 180 110', 'aria-hidden': 'true', focusable: 'false' });
  svg.classList.add('atlas-skyline');
  svg.append(svgNode('ellipse', { cx: 90, cy: 94, rx: 78, ry: 10, fill: color, opacity: '.12' }));
  for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) {
    const k = (seed * 17 + r * 31 + c * 23) % 71, x = 32 + c * 22 - r * 8, y = 67 + r * 9 + c * 2, h = 12 + k * .63;
    svg.append(svgNode('path', { d: `M${x},${y}v-${h}l12,-5 9,5v${h}l-9,5z`, fill: '#101b33', stroke: color, 'stroke-opacity': '.52', 'stroke-width': '.65' }));
    svg.append(svgNode('path', { d: `M${x},${y-h}l12,-5 9,5 -9,5z`, fill: color, opacity: '.5' }));
    svg.append(svgNode('path', { d: `M${x+12},${y-h+5}v${h}`, stroke: color, opacity: '.45' }));
    if (!compact) for (let w = 7; w < h - 2; w += 9) svg.append(svgNode('path', { d: `M${x+3},${y-w}h5m7,-2h3`, stroke: color, 'stroke-width': '1.7', opacity: (k+w)%3 ? '.85' : '.2' }));
  }
  svg.append(svgNode('path', { d: 'M12 94L156 66M24 104L165 76M40 64L140 103', stroke: color, 'stroke-width': '1', opacity: '.5', 'stroke-dasharray': '3 5' }));
  return svg;
}
function worldMap(specs) {
  const map = svgNode('svg', { viewBox: '0 0 650 430', role: 'img', 'aria-label': `${specs.length} cities connected by decorative navigation routes across six worlds. Use the city cards to explore; routes do not represent data flow.` });
  map.classList.add('atlas-map');
  map.append(svgNode('ellipse', { cx: 320, cy: 218, rx: 292, ry: 185, fill: '#0b1028', stroke: '#7185b9', 'stroke-width': '1.4', 'stroke-opacity': '.38' }));
  for (let i=0; i<45; i++) map.append(svgNode('circle', { cx: 18+(i*113)%615, cy: 18+(i*59)%380, r: i%4 ? '.7':'1.4', fill: '#d4d6ff', opacity: '.4' }));
  // A real route for every catalogue city, rendered behind the illustrated world hubs.
  const positions = [], groupPaths = new Map(WORLDS.map(w => [w[0], []]));
  for (const [key,,color,cx,cy] of WORLDS) {
    const ids = specs.map((s,i) => s.group === key ? i : -1).filter(i => i >= 0);
    ids.forEach((id,j) => {
      const angle = j * 2.399963, radius = 24 + 5.5 * Math.sqrt(j);
      positions[id] = [cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius, color];
    });
  }
  const network = cityRoutes(specs.map((s,i) => ({ i, cont:s.group })), WORLDS.map(w => ({ key:w[0] })));
  const cross = new Set(network.bridges.map(([a,b]) => `${a}:${b}`));
  for (const [a,b] of network.links) {
    const p = positions[a], q = positions[b]; if (!p || !q) continue;
    const midx = (p[0]+q[0])/2, midy = (p[1]+q[1])/2 - (cross.has(`${a}:${b}`) ? 35 : 7);
    groupPaths.get(specs[a].group).push(`M${p[0].toFixed(1)},${p[1].toFixed(1)}Q${midx.toFixed(1)},${midy.toFixed(1)} ${q[0].toFixed(1)},${q[1].toFixed(1)}`);
  }
  // Non-scaling strokes stay legible when the 650-unit atlas fits a 390px phone.
  for (const [key,,color] of WORLDS) map.append(svgNode('path',{d:groupPaths.get(key).join(' '),fill:'none',stroke:color,'stroke-width':'1.3','vector-effect':'non-scaling-stroke',opacity:'.3'}));
  positions.forEach(p => { if (p) map.append(svgNode('circle',{cx:p[0].toFixed(1),cy:p[1].toFixed(1),r:'3',fill:p[2],stroke:'#f5f6ff','stroke-width':'.8','vector-effect':'non-scaling-stroke',opacity:'.94'})); });
  for (let i=0; i<WORLDS.length; i++) {
    const a=WORLDS[i], b=WORLDS[(i+1)%WORLDS.length], d=`M${a[3]},${a[4]}Q325,20 ${b[3]},${b[4]}`;
    map.append(svgNode('path', { d, fill: 'none', stroke: a[2], 'stroke-width': '2.2', 'vector-effect':'non-scaling-stroke', opacity: '.62' }));
    const flight=svgNode('path',{ d, fill:'none',stroke:a[2],'stroke-width':'2.2','vector-effect':'non-scaling-stroke','stroke-dasharray':'3 100','stroke-linecap':'round' }); flight.classList.add('atlas-flight'); map.append(flight);
  }
  WORLDS.forEach(([key,name,color,x,y],i)=>{
    const g=svgNode('g',{transform:`translate(${x-85} ${y-85})`});
    g.append(svgNode('path',{d:'M5 100L90 63 175 100 90 137Z',fill:'#0c1728',stroke:color,'stroke-opacity':'.5'}));
    const city=skyline(i+5,color); city.setAttribute('width','180');city.setAttribute('height','110');g.append(city);
    const title=svgNode('text',{x:90,y:153,'text-anchor':'middle',fill:color,'font-size':'19','font-weight':'800','letter-spacing':'.5',stroke:'#050918','stroke-width':'2','paint-order':'stroke'});title.textContent=name.toUpperCase();g.append(title);
    const count=svgNode('text',{x:90,y:178,'text-anchor':'middle',fill:'#e0e9ff','font-size':'15','font-weight':'700',stroke:'#050918','stroke-width':'2','paint-order':'stroke'});count.textContent=specs.filter(s=>s.group===key).length+' cities';g.append(count);map.append(g);
  });
  return map;
}
export function mountWorld(specs, { fallback = false, onCity, onDistrict, onExplore, describe } = {}) {
  document.querySelector('.world-lobby')?.remove();
  const box=node('section', 'world-lobby'+(fallback?' fallback':'')); box.setAttribute('aria-label',fallback?'Explore the city atlas':'Featured cities');
  const hero=node('div','atlas-hero'), eyebrow=node('p','atlas-kicker','OLYMPUS / THE LIVING ATLAS');
  hero.append(eyebrow,node('h2',null,'Your numbers. A whole world.'),node('p','atlas-lead',fallback?'Explore every city below. Illuminated routes connect the catalogue visually; they do not represent data flow.':'Pick a skyline and land inside the data. Every city has a route in the night world; routes are for navigation, not data flow.'));
  const stats=node('p','atlas-stats'); stats.append(node('b',null,String(specs.length)),document.createTextNode(' cities  /  '),node('b',null,'6'),document.createTextNode(' districts'));hero.append(stats); box.append(hero);
  if(!fallback){const districts=node('div','atlas-districts');districts.setAttribute('role','group');districts.setAttribute('aria-label','Fly to a district');WORLDS.forEach(([id,name,color])=>{const b=node('button',null,name);b.type='button';b.style.setProperty('--district',color);b.onclick=()=>onDistrict?.(id);districts.append(b);});hero.append(districts);}
  if(fallback) box.append(worldMap(specs));
  const featured=node('div','atlas-featured');
  const picked=['trading','research','money'].map(g=>specs.find(s=>s.group===g)).filter(Boolean);
  picked.forEach((s,i)=>{
    const b=node('button','atlas-portal'); b.type='button';b.style.setProperty('--district',WORLDS.find(w=>w[0]===s.group)?.[2]||'#a68bff');
    b.append(skyline(i+2,WORLDS.find(w=>w[0]===s.group)?.[2]),node('small',null,'START EXPLORING'),node('strong',null,s.name),node('span',null,s.motto),node('em',null,fallback?'Open the numbers ↗':'Land in this city ↗'));
    b.addEventListener('click',()=>open(s));featured.append(b);
  });box.append(featured);
  const detail=node('section','atlas-detail');detail.hidden=true;detail.setAttribute('aria-live','polite');box.append(detail);
  function open(s){
    if(!fallback){onCity?.(s.id);return;}
    if(onExplore){onExplore(s.id);return;}
    const d=describe?.(s);
    detail.hidden=false;detail.replaceChildren(node('p','atlas-kicker','CITY RECORD / '+(d?.demo===false?'PUBLISHED DATA':'SAMPLE DATA')),node('h3',null,s.name),node('p',null,s.motto));
    if(d) {detail.append(node('p','atlas-record',d.line));if(d.note)detail.append(node('p','atlas-source',d.note));}
    detail.append(node('p','atlas-source','Landmark: '+s.landmark.label+'. The skyline is an illustration; the record above is the dataset.'));
    const close=node('button','atlas-close','Close city record');close.type='button';close.onclick=()=>{detail.hidden=true;};detail.append(close);detail.scrollIntoView({block:'nearest',behavior:'auto'});
  }
  if(fallback){
    const catalog=node('section','atlas-catalog');catalog.append(node('h3',null,'Find your next city'));
    const search=node('input');search.type='search';search.placeholder='Search cities or data';search.setAttribute('aria-label','Search the city atlas');catalog.append(search);
    const filters=node('div','atlas-filters');filters.setAttribute('role','group');filters.setAttribute('aria-label','Filter by district');let group='';
    const list=node('div','atlas-city-list'), empty=node('p','atlas-empty','No city matches. Try a different name or district.');empty.hidden=true;
    const rows=specs.map(s=>{const b=node('button','atlas-city');b.type='button';const color=WORLDS.find(w=>w[0]===s.group)?.[2]||'#a68bff';b.style.setProperty('--district',color);b.append(node('strong',null,s.name),node('span',null,s.motto),node('small',null,(WORLDS.find(w=>w[0]===s.group)?.[1]||s.group)+' / '+s.region));b.onclick=()=>open(s);list.append(b);return{s,b};});
    const filter=()=>{const term=search.value.trim().toLowerCase();let n=0;rows.forEach(({s,b})=>{b.hidden=!!((group&&group!==s.group)||(term&&!`${s.name} ${s.motto} ${s.dataset} ${s.region}`.toLowerCase().includes(term)));if(!b.hidden)n++;});empty.hidden=n>0;};
    [['','All districts'],...WORLDS.map(w=>[w[0],w[1]])].forEach(([id,name])=>{const b=node('button','atlas-filter',name);b.type='button';b.setAttribute('aria-pressed',String(!id));b.onclick=()=>{group=id;[...filters.children].forEach(e=>e.setAttribute('aria-pressed',String(e===b)));filter();};filters.append(b);});
    search.addEventListener('input',filter);catalog.append(filters,list,empty);box.append(catalog);
  }
  document.body.append(box);return box;
}
