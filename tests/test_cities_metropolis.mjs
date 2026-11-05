// Actual three.js geometry and camera math. This never creates a WebGL context.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as THREE from '../tools/web_public/jarvis/three.module.min.js';
import {metropolisPlan,buildMetropolis,METROPOLIS_CAPS} from '../tools/web_public/cities/metropolis.js';
import {generate} from '../tools/web_public/cities/generator.js';
import {loadDataset} from '../tools/web_public/cities/datasets.js';
import {Stage,unitBox5,TIERS,BUDGETS} from '../tools/web_public/cities/scene.js';
import {Rig,makePath,safeFlight} from '../tools/web_public/cities/rig.js';
import {clamp} from '../tools/web_public/cities/util.js';
const dir=new URL('../tools/web_public/cities/',import.meta.url), cfg=JSON.parse(await readFile(new URL('cities.json',dir),'utf8'));
const fixture=JSON.parse(await readFile(new URL('fixture.json',dir),'utf8')), cache=new Map();
const env={fixture,get:async u=>{if(/^https?:/.test(u))throw Error('No external test requests');return JSON.parse(await readFile(new URL(u,dir),'utf8'));}};
globalThis.matchMedia=()=>({matches:false});
const box=unitBox5();assert.equal(box.index.count/3,10);
const geometryStats=group=>{let calls=0,triangles=0;const walk=o=>{if(!o.visible)return;if(o.geometry){calls++;if(o.isMesh){const base=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;triangles+=base*(o.isInstancedMesh?o.count:o.geometry.isInstancedBufferGeometry?o.geometry.instanceCount:1);}}for(const c of o.children)walk(c);};walk(group);return{calls,triangles};};
const table=[];
const app=await readFile(new URL('app.js',dir),'utf8'), cameraSource=app.slice(app.indexOf('function setCam(mode, quiet) {'),app.indexOf('// ------------------------------------------------------------------ chips, dock, quality'));
const labelSource=app.slice(app.indexOf('function placeLabel(e, p, w, h, above = false) {'),app.indexOf('function updateLabels(frame) {'));
const label={offsetWidth:92,offsetHeight:24,style:{}}, mini={getBoundingClientRect:()=>({left:266,right:378,top:106,bottom:218})};
const labelInCity=new Function('S','clamp','mini',labelSource+';return placeLabel;')({mode:'city'},clamp,mini);
labelInCity(label,{x:300,y:198},390,844,true);
assert.ok(Number(label.style.transform.match(/,([0-9]+)px\)/)[1])>=250,'district label clears the phone minimap');
const updateSource=app.slice(app.indexOf('function updateLabels(frame) {'),app.indexOf('function updateTag()'));
const fakeLabels=Array.from({length:8},()=>({offsetWidth:110,offsetHeight:24,style:{},classList:{toggle(){}}}));
const labelStage={project:(x)=>({on:true,x,y:290,z:x})};
const labelState={mode:'city',stage:labelStage,cur:{city:{layout:'districts',districts:[120,250,310].map((cx,i)=>({cx,cz:0,top:0,label:`month ${i}`}))}}};
const update=new Function('S','canvas','farHub','contEls','labelEls','placeLabel','isSeen',updateSource+';return updateLabels;')(
  labelState,{clientWidth:390,clientHeight:844},()=>false,Array.from({length:8},()=>({style:{}})),fakeLabels,
  new Function('S','clamp','mini',labelSource+';return placeLabel;')(labelState,clamp,mini),()=>false);
update(3);
assert.deepEqual(fakeLabels.slice(0,3).map(e=>e.style.display),['block','block','none'],
  'overlapping phone district labels are dropped after nearer labels are placed');
let clearanceCases=0;
for(const id of ['trades-city','ideas-city','canyon','months-city']){
  const spec=cfg.cities.find(s=>s.id===id), dataset=await loadDataset(spec.dataset,env,cache);
  for(const tier of ['low','high','ultra']){
    const city=generate(spec,dataset,{cap:TIERS[tier].cap}), before=city.x.slice();
    const canonical=metropolisPlan(city,spec), again=metropolisPlan(city,spec);
    assert.deepEqual(canonical,again,'scenery is deterministic');
    assert.ok(canonical.every(b=>[b.x,b.z,b.w,b.d,b.h,b.seed].every(Number.isFinite)));
    assert.ok(canonical.some(b=>b.infill),'unused ground cells receive decorative low rises');
    assert.ok(canonical.every(b=>{
      for(let k=0;k<city.n;k++) if(Math.abs(b.x-city.x[k])<(b.w+city.w[k])/2+1.4 && Math.abs(b.z-city.z[k])<(b.d+city.d[k])/2+1.4) return false;
      return true;
    }),'scenery clears every measured tower footprint');
    const stage=Object.create(Stage.prototype);stage.cityRec=null;stage.cityG=new THREE.Group();stage.box5=box;stage.caps=()=>TIERS[tier];stage.tier=()=>tier;stage.U={uGrow:{value:1}};
    stage.pick=(...names)=>Object.fromEntries(names.map(n=>[n,{value:1}]));
    stage.buildCity(spec,city);
    const civic=stage.cityRec.metropolis, stats=geometryStats(stage.cityG);
    assert.equal(civic.count,METROPOLIS_CAPS[tier]);assert.ok(civic.calls<=3);
    assert.equal(civic.triangles,civic.count*10);
    assert.ok(stats.triangles<BUDGETS[tier].tris,`${id}/${tier}: geometry exceeds scene budget`);
    assert.ok(stats.calls+20<BUDGETS[tier].calls,`${id}/${tier}: no postprocessing call headroom`);
    assert.deepEqual(city.x,before,'data geometry preserved');
    civic.update(12);const aircraft=civic.group.children[2];assert.equal(aircraft.material.uniforms.uTime.value,tier==='low'?0:12);
    assert.equal(aircraft.visible,tier!=='low');
    table.push({id,tier,data:city.n,scenery:civic.count,geometryCalls:stats.calls,geometryTriangles:stats.triangles});stage.clearCity();
    if(tier==='high'&&['trades-city','ideas-city'].includes(id)){
      const camera=new THREE.PerspectiveCamera(), rig=new Rig(camera,{addEventListener(){}}), S={cur:{city},rig};
      const choose=new Function('S','document','clamp','makePath','safeFlight','caption',cameraSource+';return setCam;')(S,{querySelectorAll:()=>[]},clamp,makePath,safeFlight,()=>{});
      for(const mode of ['skim','drone','grand']){
        choose(mode,true);assert.ok(rig.path.clearanceSamples>=256);let hits=0;
        for(let i=0;i<200;i++){
          const p=rig.path.pos.getPointAt(i/200);assert.ok(p.toArray().every(Number.isFinite));
          for(let k=0;k<city.n;k++)if(Math.abs(p.x-city.x[k])<city.w[k]/2+1&&Math.abs(p.z-city.z[k])<city.d[k]/2+1&&p.y<city.y0[k]+city.h[k]+2){hits++;break;}
        }
        assert.equal(hits,0,`${id}/${mode} flies through a measured tower`);clearanceCases++;
      }
    }
  }
}
const sample=generate(cfg.cities[0],await loadDataset(cfg.cities[0].dataset,env,cache),{cap:300});
for(const tier of ['high','low','off']){
  const civic=buildMetropolis(sample,cfg.cities[0],box,new THREE.MeshBasicMaterial(),tier,true);
  assert.equal(civic.calls,tier==='off'?0:2);if(tier!=='off')assert.equal(civic.group.children[2].visible,false);civic.dispose();
}
// The same real orbit/glide/path rig the page uses: finite motion, ground floor,
// manual takeover and shortest-way yaw. Neither a canvas nor a renderer is made.
const dom={addEventListener(){},setPointerCapture(){},getBoundingClientRect(){return{left:0,top:0};}};
const camera=new THREE.PerspectiveCamera(56,390/844,.5,5000), rig=new Rig(camera,dom);
const start=camera.position.clone();rig.flyTo({x:20,y:4,z:10,dist:120,yaw:Math.PI*5,pitch:.3},1);for(let i=0;i<70;i++)rig.update(1/60);
assert.equal(rig.fly,null);assert.ok(camera.position.distanceTo(start)>10);assert.ok(Math.abs(rig.yaw-.4)<=Math.PI);
for(const mode of ['skim','drone','grand']){
  const path=makePath([[0,12,40],[40,28,0],[0,8,-40],[-40,20,0]],[[0,8,0],[0,12,0],[0,8,0],[0,10,0]]);
  rig.follow(path,30,true,mode);rig.update(1/60);const old=camera.position.clone();for(let i=0;i<120;i++)rig.update(1/60);
  assert.equal(rig.mode,mode);assert.ok(camera.position.distanceTo(old)>5);assert.ok(camera.position.y>=2.5);assert.ok(camera.position.toArray().every(Number.isFinite));rig._touched();assert.equal(rig.mode,'orbit');assert.equal(rig.path,null);
}
rig.reduced=true;const still=camera.position.clone();rig.auto=1;rig.update(30);assert.ok(camera.position.toArray().every(Number.isFinite));const second=camera.position.clone();rig.update(30);assert.ok(camera.position.distanceTo(second)<1e-8,'reduced motion disables idle orbit');
console.table(table);console.log(`PASS: real city geometry fits static triangle budgets; ${clearanceCases} actual page flight paths clear measured towers; scenery tiers, motion gates and camera mathematics. GPU rendering and actual postprocessing calls remain unverified.`);
