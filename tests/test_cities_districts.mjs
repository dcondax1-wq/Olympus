// Deterministic drilldown, population conservation, money accounting and source-field tests.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { cityDistricts, towerRows, recordFields, fieldText } from '../tools/web_public/cities/district-data.js';
import { loadDataset } from '../tools/web_public/cities/datasets.js';
const dir=new URL('../tools/web_public/cities/',import.meta.url);
const cfg=JSON.parse(await readFile(new URL('cities.json',dir),'utf8'));
const fixture=JSON.parse(await readFile(new URL('fixture.json',dir),'utf8'));
const env={fixture,get:()=>Promise.reject(Error('Offline test: no network'))},cache=new Map();
let cases=0;
for(const spec of cfg.cities){
  const ds=await loadDataset(spec.dataset,env,cache), before=JSON.stringify(ds.items), model=cityDistricts(spec,ds);
  assert.equal(model.count,ds.items.length,spec.id+' source population');
  assert.equal(model.districts.reduce((n,d)=>n+d.count,0),model.count,spec.id+' every record belongs to a district');
  const indices=model.districts.flatMap(d=>d.rows.map(r=>r.index));
  assert.equal(new Set(indices).size,ds.items.length,spec.id+' no duplicate buildings');
  assert.deepEqual([...indices].sort((a,b)=>a-b),ds.items.map((_,i)=>i),spec.id+' no missing source rows');
  for(const d of model.districts){
    const rows=towerRows(d.rows,12);assert.equal(rows.length,Math.min(12,d.count));
    assert.ok(rows.every(r=>Number.isFinite(r.towerHeight)&&r.towerHeight>=12&&r.towerHeight<=90),spec.id+' bounded finite geometry');
    assert.deepEqual(rows,towerRows(d.rows,12),spec.id+' deterministic layout');
    if(d.usd!==null){const actual=d.rows.reduce((s,r)=>s+r.item.f.usd,0);assert.ok(Math.abs(d.usd-actual)<1e-7,spec.id+' dollars equal the source rows');}
    if(rows[0]){const fields=recordFields(model,rows[0]);assert.equal(new Set(fields.map(f=>f.key)).size,fields.length);assert.ok(fields.every(f=>ds.fields.some(fd=>fd.key===f.key)),spec.id+' declared source fields only');}
  }
  assert.equal(JSON.stringify(ds.items),before,spec.id+' source is never mutated');
  assert.equal(model.demo,true,spec.id+' sample status retained');cases++;
}
const spec=cfg.cities[0],ds={demo:false,title:'Published test',source:'fixture',fields:[{key:'usd',label:'Result',fmt:'usd'},{key:'month',label:'Month',fmt:'txt'}],label:i=>i.id,items:[{id:'loss',f:{usd:-50,month:'A'}},{id:'win',f:{usd:75,month:'A'}}]};
const m=cityDistricts({...spec,district_by:'month',height_by:'abs:usd'},ds);
assert.equal(m.demo,false);assert.equal(m.districts[0].usd,25);assert.deepEqual(m.districts[0].rows.map(r=>r.value),[75,-50]);
assert.match(fieldText({fmt:'r'},1.5,{f:{usd:12.5}}),/1\.50R.*\$12\.50/);
assert.match(fieldText({fmt:'r'},1.5,{f:{}}),/\$ unavailable/);
assert.equal(towerRows([],0).length,0);
console.log(`PASS: ${cases} catalogue cities preserve every source record, dollars, deterministic towers and sample labels; signed-money and R/$ checks pass.`);
