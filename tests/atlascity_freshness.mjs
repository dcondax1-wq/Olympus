import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';

const source=readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../tools/web_public/atlascity/city.js'),'utf8');
async function render(payload){
 const el=()=>({textContent:'',className:'',children:[],style:{setProperty(){}},dataset:{},addEventListener(){},setAttribute(){},replaceChildren(){this.children=[]},append(...nodes){this.children.push(...nodes)}});
 const ids=Object.fromEntries(['quality','city','number','title','status','hours','window','state','outposts','freshness','room','target','answer','left','right','home','scene'].map(id=>[id,el()]));
 const keys=['ema_lon_vix','macd_sweep','sr_nyreclaim'].map(key=>Object.assign(el(),{dataset:{key}}));
 const window={};
 const context={window,document:{documentElement:{dataset:{}},hidden:false,getElementById:id=>ids[id],querySelectorAll:()=>keys,createElement:el},location:{search:''},matchMedia:()=>({matches:false}),URLSearchParams,Date,AbortController,setTimeout:()=>1,clearTimeout(){},setInterval(){},fetch:async()=>({ok:true,json:async()=>payload})};
 vm.runInNewContext(source,context,{filename:'city.js'});
 await new Promise(setImmediate);
 return {ids,state:window.ATLAS_CITY.state()};
}
const now=Date.now();
const atlas={room:1700,mll:2000,to_target:4300,members:[{key:'ema_lon_vix',stage:'armed',short:'EMA',label:'EMA setup',text:'Forming',hours:'',window:{text:''}}]};
const data={built:new Date(now).toISOString(),board:{data_t:Math.floor((now-2*60*60000)/1000),atlas}};
const stale=await render(data);
assert.equal(stale.state.snapshotOld,true,'fresh page build cannot refresh old account source');
assert.equal(stale.ids.room.textContent,'—','stale drawdown figure must not look current');
assert.equal(stale.ids.target.textContent,'—','stale target figure must not look current');
assert.match(stale.ids.freshness.textContent,/Old · .*min since source/);
assert.match(stale.ids.answer.textContent,/old or unavailable/);

const unknown=await render({...data,board:{atlas}});
assert.equal(unknown.state.snapshotOld,true);
assert.equal(unknown.ids.freshness.textContent,'Old · Source time unknown');
assert.equal(unknown.ids.room.textContent,'—');

const skewed=await render({...data,board:{data_t:Math.floor((now+10*60000)/1000),atlas}});
assert.equal(skewed.state.snapshotOld,true,'a source timestamp far in the future is not fresh');
assert.equal(skewed.ids.freshness.textContent,'Old · Source time unknown');
assert.equal(skewed.ids.target.textContent,'—');

const fresh=await render({...data,built:new Date(now-2*60*60000).toISOString(),board:{data_t:Math.floor(now/1000),atlas}});
assert.equal(fresh.state.snapshotOld,false,'old page build cannot stale a fresh account source');
assert.equal(fresh.ids.room.textContent,'$1,700 / $2,000');
assert.equal(fresh.ids.target.textContent,'$4,300');

const noPaper=await render({...data,board:{data_t:Math.floor(now/1000),atlas},
 second:{strategies:[{key:'research-only',label:'Unrouted idea',route:false,paper:null}]}});
assert.equal(noPaper.state.snapshotOld,false,'a missing research paper sample cannot reset the published ATLAS state');
assert.equal(noPaper.ids.outposts.children.length,1);
assert.equal(noPaper.ids.outposts.children[0].children[2].textContent,'No paper sample published');
console.log('ATLAS City source freshness regression PASS');
