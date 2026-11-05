"""Validate skyline geometry and tier budgets without a GPU."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'tools/web_public/kalshicity'


class SkylineTests(unittest.TestCase):
    def test_bounded_city_links_are_static_and_data_grounded(self):
        script = '''
          import assert from 'node:assert/strict';
          import {cityLinks, LINK_SEGMENTS} from 'LINK_MODULE';
          const districts=[{key:'Downtown',cx:0,cz:0},...Array.from({length:15},(_,i)=>({key:'m'+i,cx:i*30+50,cz:i*7,color:'#55ddcc'}))];
          const labs=Array.from({length:15},(_,i)=>({key:'lab'+i,cx:-i*26-50,cz:i*9}));
          const buildings=[{id:'win',x:70,z:4,fullH:30},{id:'loss',x:80,z:8,fullH:6}];
          const L={districts,labs,buildings}, before=JSON.stringify(L);
          const routes=cityLinks(L,{bestId:'win',worstId:'loss'});
          assert.equal(routes.length,23);assert.deepEqual(routes.slice(0,3).map(r=>r.kind),['edge','leak','research']);
          assert.equal(routes.filter(r=>r.kind==='edge').length,1);
          assert.equal(routes.filter(r=>r.kind==='leak').length,1);
          for(const r of routes) {
            assert.equal(r.points.length,LINK_SEGMENTS+1);
            assert.ok(r.points.flatMap(p=>[p.x,p.y,p.z]).every(Number.isFinite));
            assert.ok(r.points[6].y>Math.min(r.points[0].y,r.points[12].y));
          }
          assert.equal(JSON.stringify(L),before);
          assert.ok(cityLinks({...L,buildings:[]},{bestId:'win',worstId:'loss'}).every(r=>!['edge','leak'].includes(r.kind)));
          assert.deepEqual(cityLinks({districts:[],labs:[],buildings:[]}),[]);
        '''.replace('LINK_MODULE', (APP / 'citylinks.js').as_uri())
        result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bot_status_requires_a_fresh_bot_timestamp(self):
        script = '''
          import assert from 'node:assert/strict';
          import {shape, BOT_FEED_MAX_AGE_S} from 'FEED_MODULE';
          const now = 100000, doc = (book) => ({t: now, edges: [], book});
          const fresh = shape(doc({feed_t: now - 60, running: true, status: 'Running'}), null, null, now);
          assert.equal(fresh.book.statusFresh, true);
          assert.equal(fresh.book.running, true);
          const old = shape(doc({feed_t: now - BOT_FEED_MAX_AGE_S - 1, running: true, status: 'Running'}), null, null, now);
          assert.equal(old.book.statusFresh, false);
          assert.equal(old.book.running, null);
          assert.equal(old.book.status, 'Status unverified');
          assert.equal(old.book.lastStatus, 'Running');
          const twentyMinutes = shape(doc({feed_t: now - 20 * 60, running: true, status: 'Running'}), null, null, now);
          assert.equal(twentyMinutes.book.statusFresh, false);
          assert.equal(twentyMinutes.book.running, null);
          const paused = shape(doc({feed_t: now - BOT_FEED_MAX_AGE_S - 1, running: false, status: 'Paused'}), null, null, now);
          assert.equal(paused.book.running, null);
          assert.equal(paused.regime.paused, false);
          const missing = shape(doc({running: true, status: 'Running'}), null, null, now);
          assert.equal(missing.book.feedAge, null);
          assert.equal(missing.book.running, null);
          const skewed = shape(doc({feed_t: now + 301, running: true, status: 'Running'}), null, null, now);
          assert.equal(skewed.book.statusFresh, false);
          console.log('PASS fresh, 20-minute stale running, stale paused, missing and future bot reports');
        '''.replace('FEED_MODULE', (APP / 'cityfeed.js').as_uri())
        result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_district_opens_every_edge_and_searches_without_mutation(self):
        script = '''
          import assert from 'node:assert/strict';
          class Element {
            constructor(tag) {this.tagName=tag;this.children=[];this.className='';this.dataset={};this.value='';this.events={};this.attrs={};}
            append(...nodes){nodes.forEach(n=>{n.parent=this;this.children.push(n);});}
            replaceChildren(...nodes){this.children=[];this.append(...nodes);}
            setAttribute(k,v){this.attrs[k]=v;}
            addEventListener(k,fn){this.events[k]=fn;}
            replaceWith(){}
            getContext(){return null;}
            getBoundingClientRect(){return{width:390,height:360};}
            showModal(){this.open=true;}
            close(){this.open=false;this.events.close?.();}
            remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
          }
          const body=new Element('body'), walk=n=>[n,...n.children.flatMap(walk)];
          globalThis.document={body,documentElement:{dataset:{}},createElement:t=>new Element(t),querySelector:q=>walk(body).find(n=>'.'+n.className===q)};
          globalThis.window={addEventListener:()=>{}}; // no ResizeObserver: older WebKit must still open the atlas
          const {cityAtlas,edgeCountLabel}=await import('ATLAS');
          assert.equal(edgeCountLabel(0),'0 edges');assert.equal(edgeCountLabel(1),'1 edge');assert.equal(edgeCountLabel(2),'2 edges');
          assert.equal(edgeCountLabel(1,'published '),'1 published edge');
          const edges=Array.from({length:72},(_,i)=>({id:'edge'+i,label:'Edge '+i,n:30+i,status:'HOLDING'}));
          const before=JSON.stringify(edges), picked=[];
          const atlas=cityAtlas(new Element('canvas'),{districts:[{name:'Bitcoin',count:edges.length,list:edges}]},id=>picked.push(id),'Test');
          const caption=walk(body).find(n=>n.className==='kc-atlas-caption');caption.children[1].children[0].onclick();
          const dialog=walk(body).find(n=>n.tagName==='dialog'), list=dialog.children[3], search=dialog.children[2];
          assert.equal(dialog.open,true);assert.equal(list.children.length,72);
          search.value='Edge 71';search.oninput();assert.equal(list.children.length,1);list.children[0].onclick();
          assert.deepEqual(picked,['edge71']);assert.equal(dialog.open,false);
          caption.children[1].children[0].onclick();const again=walk(body).find(n=>n.tagName==='dialog');again.children[2].value='not here';again.children[2].oninput();assert.match(again.children[3].children[0].textContent,/No edges match/);
          atlas.update({districts:[{name:'Ethereum',count:1,list:[edges[3]]}]});
          assert.match(caption.children[1].children[0].textContent,/Ethereum · 1/);
          caption.children[1].children[0].onclick();const updated=walk(body).find(n=>n.tagName==='dialog');assert.equal(updated.children[3].children.length,1);updated.children[3].children[0].onclick();
          assert.match(updated.children[1].textContent,/1 published edge/);
          assert.deepEqual(picked,['edge71','edge3']);
          assert.equal(JSON.stringify(edges),before);console.log('PASS72edges, refreshed district, search, empty, no ResizeObserver, source unchanged');
        '''.replace('ATLAS', (APP / 'cityatlas.js').as_uri())
        result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_geometry_and_tier_prefixes(self):
        script = '''
          import {scenery} from 'LAYOUT';
          import {skylinePorts} from 'PORTS';
          const L = {extent: 180};
          const full = scenery(L, 4200), lite = scenery(L, 700);
          if (JSON.stringify(lite) !== JSON.stringify(full.slice(0,700))) throw Error('tier layout changes');
          if (full.some(s => Math.abs(Math.hypot(s.x,s.z) - (L.extent + 36)) < 5)) throw Error('promenade blocked');
          if (full.some(s => ![s.x,s.z,s.w,s.d,s.h].every(Number.isFinite))) throw Error('invalid tower');
          const before = JSON.stringify(full), ports = skylinePorts(full, L.extent);
          if (ports.group.children.length !== 2) throw Error('draw-call regression');
          const [crowns,rail] = ports.group.children;
          ports.setTier(700); const low = crowns.count;
          if (low !== full.slice(0,700).filter(s=>s.seed > .94).length * 3) throw Error('lite crowns mismatch');
          ports.setTier(2600); if (crowns.count < low) throw Error('high count below low');
          ports.setTier(250); if (rail.visible) throw Error('off decoration active');
          if (before !== JSON.stringify(full)) throw Error('source towers mutated');
          if (![...crowns.instanceMatrix.array].every(Number.isFinite)) throw Error('invalid transform');
          const district={cx:0,cz:0,half:12,ex:[1,0],ez:[0,1]}, lab={cx:65,cz:0,half:8,ex:[1,0],ez:[0,1]};
          const road={x0:0,z0:0,x1:120,z1:0,w:3.4};
          const urban=scenery({extent:180,downHalf:12,districts:[district],labs:[lab],roads:[road]},700);
          const infill=urban.filter(s=>s.kind==='infill');
          if(infill.length<150)throw Error('night blocks too sparse');
          for(const s of infill){
            if(s.h>9.4||Math.abs(Math.hypot(s.x,s.z)-216)<6)throw Error('low-rise/promendade bound');
            for(const p of [district,lab])if(Math.abs(s.x-p.cx)<p.half+4&&Math.abs(s.z-p.cz)<p.half+4)throw Error('scenery on real data pad');
            if(s.x>=0&&s.x<=120&&Math.abs(s.z)<road.w*.5+3.1)throw Error('scenery blocks avenue');
          }
        '''.replace('LAYOUT', (APP / 'citylayout.js').as_uri()).replace('PORTS', (APP / 'skylineports.js').as_uri())
        subprocess.run(['node', '--input-type=module', '-e', script], check=True, capture_output=True)

    def test_fallback_retains_existing_cards_and_no_idle_loop(self):
        source = (APP / 'cityatlas.js').read_text()
        self.assertIn('L.buildings', source)
        self.assertIn('openDistrict(d)', source)
        self.assertIn("'City atlas districts'", source)
        self.assertIn('outer skyline is scenery', source)
        self.assertNotIn('innerHTML', source)
        self.assertNotIn('requestAnimationFrame', source)
        self.assertNotIn('fetch(', source)


if __name__ == '__main__':
    unittest.main()

