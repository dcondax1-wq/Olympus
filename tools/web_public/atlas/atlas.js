/* Olympus Atlas: one fast map for every published dashboard. Read-only; no orders or account actions. */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const rows = (window.OLYMPUS_APPS_LIST || []).filter((a) => a && /^[a-z0-9-]+$/.test(a.id) && /^(trading|money|life)$/.test(a.group));
  const fallback = [
    { id:'zenith',name:'Zenith',glyph:'Z',colour:'#a855f7',group:'trading',purpose:'NQ bot dashboard',path:'' },
    { id:'oracle',name:'Oracle',glyph:'Θ',colour:'#7fe9ff',group:'trading',purpose:'Market radar',path:'oracle/' },
    { id:'cities',name:'Cities',glyph:'◈',colour:'#a68bff',group:'trading',purpose:'Explore the city worlds',path:'cities/' },
    { id:'jarvis',name:'Jarvis',glyph:'J',colour:'#e5be83',group:'life',purpose:'Your assistant',path:'jarvis/' }
  ];
  const apps = rows.length ? rows : fallback;
  const key = 'olympus.atlas.v1';
  let saved = { stars: [], recent: [] };
  try { const v = JSON.parse(localStorage.getItem(key)); if (v && typeof v === 'object') saved = { stars: Array.isArray(v.stars) ? v.stars : [], recent: Array.isArray(v.recent) ? v.recent : [] }; } catch (_) { /* private browsing */ }
  saved.stars = saved.stars.filter((id) => apps.some((a) => a.id === id)).slice(0, 30);
  saved.recent = saved.recent.filter((id) => apps.some((a) => a.id === id)).slice(0, 5);
  const store = () => { try { localStorage.setItem(key, JSON.stringify(saved)); } catch (_) { /* private browsing */ } };
  const link = (a) => '../' + (/^(?:[a-z0-9-]+\/)?$/.test(a.path || '') ? a.path : (a.id + '/'));
  let filter = 'all';
  function render() {
    const q = $('#query').value.toLocaleLowerCase().trim();
    const shown = apps.filter((a) => (filter === 'all' || (filter === 'favorites' ? saved.stars.includes(a.id) : a.group === filter)) &&
      (!q || (a.name + ' ' + a.purpose + ' ' + a.group).toLocaleLowerCase().includes(q)));
    const host = $('#results'); host.replaceChildren();
    for (const a of shown) {
      const card = document.createElement('article'); card.className = 'card'; card.style.setProperty('--accent', /^#[0-9a-f]{6}$/i.test(a.colour) ? a.colour : '#e5be83');
      const sigil = document.createElement('span'); sigil.className = 'sigil'; sigil.textContent = a.glyph || a.name.charAt(0); sigil.setAttribute('aria-hidden','true');
      const body = document.createElement('div'); body.className = 'card-body';
      const group = document.createElement('small'); group.textContent = a.group;
      const name = document.createElement('h3'); name.textContent = a.name;
      const purpose = document.createElement('p'); purpose.textContent = a.purpose || 'Open dashboard';
      body.append(group,name,purpose);
      const go = document.createElement('a'); go.className = 'go'; go.href = link(a); go.setAttribute('aria-label','Open ' + a.name); go.addEventListener('click', () => { saved.recent = [a.id, ...saved.recent.filter((id) => id !== a.id)].slice(0,5); store(); });
      const star = document.createElement('button'); star.type = 'button'; star.className = 'star'; star.textContent = saved.stars.includes(a.id) ? '★' : '☆'; star.setAttribute('aria-pressed',String(saved.stars.includes(a.id))); star.setAttribute('aria-label',(saved.stars.includes(a.id) ? 'Remove ' : 'Favorite ') + a.name + (saved.stars.includes(a.id) ? ' from favorites' : ''));
      star.addEventListener('click', () => { saved.stars = saved.stars.includes(a.id) ? saved.stars.filter((id) => id !== a.id) : [...saved.stars,a.id]; store(); render(); });
      card.append(sigil,body,go,star); host.append(card);
    }
    $('#count').textContent = shown.length + ' destinations'; $('#empty').hidden = shown.length > 0;
    const recent = $('#recent'); recent.replaceChildren(); recent.hidden = !saved.recent.length || !!q || filter !== 'all';
    if (!recent.hidden) {
      const label = document.createElement('span'); label.textContent = 'RECENT  '; recent.append(label);
      for (const id of saved.recent) { const a = apps.find((x) => x.id === id); if (!a) continue; const el = document.createElement('a'); el.href = link(a); el.textContent = a.name + ' ↗'; recent.append(el); }
    }
  }
  $('#query').addEventListener('input',render);
  document.querySelectorAll('[data-filter]').forEach((b) => b.addEventListener('click', () => { filter = b.dataset.filter; document.querySelectorAll('[data-filter]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); render(); }));
  document.addEventListener('keydown', (e) => { if (e.key === '/' && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); $('#query').focus(); } else if (e.key === 'Escape' && document.activeElement === $('#query')) { $('#query').value = ''; render(); $('#query').blur(); } });
  render();

  // A projected city, not a video. One low-cost canvas, capped pixels, no network assets or extra WebGL context.
  const canvas = $('#world'), ctx = canvas.getContext('2d'); if (!ctx) return;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let paused = reduced || document.visibilityState === 'hidden', frame = 0, raf = 0, W = 0, H = 0, pixel = 1;
  const rand = (n) => { const x = Math.sin(n * 129.471 + 17.23) * 43857.545; return x - Math.floor(x); };
  const buildings = Array.from({length:180},(_,i) => ({x:(i%18-8.5)*1.42,z:Math.floor(i/18)*1.38+1.3,h:1.2+rand(i)*5.1,w:.45+rand(i+310)*.43,glow:rand(i+910)}));
  function resize() { pixel = Math.min(devicePixelRatio || 1, 1.5); W = canvas.clientWidth; H = canvas.clientHeight; canvas.width = Math.round(W*pixel); canvas.height = Math.round(H*pixel); ctx.setTransform(pixel,0,0,pixel,0,0); draw(); }
  const project = (x,y,z) => { const scale = Math.min(W*.078,58) / (1 + z*.15), center = W < 600 ? W*.69 : W*.71; return [center + (x+z*.22)*scale, H*.76-(y+z*.19)*scale,scale]; };
  function cube(b,t) {
    const {x,z,w,h} = b, p = project(x,0,z), a = project(x,h,z), r = p[2]*w, depth = Math.max(2,r*.35);
    if (p[0] < -50 || p[0] > W+50) return;
    const light = Math.max(.18,1-z*.048), pulse = .72+.28*Math.sin(t*.001+b.x*2);
    ctx.fillStyle = `rgba(27,48,79,${light})`; ctx.beginPath(); ctx.moveTo(p[0]-r,p[1]);ctx.lineTo(p[0]+r,p[1]);ctx.lineTo(a[0]+r,a[1]);ctx.lineTo(a[0]-r,a[1]);ctx.fill();
    ctx.fillStyle=`rgba(11,24,51,${light})`;ctx.beginPath();ctx.moveTo(p[0]+r,p[1]);ctx.lineTo(p[0]+r+depth,p[1]-depth*.45);ctx.lineTo(a[0]+r+depth,a[1]-depth*.45);ctx.lineTo(a[0]+r,a[1]);ctx.fill();
    ctx.fillStyle=`rgba(87,113,158,${light*.5})`;ctx.beginPath();ctx.moveTo(a[0]-r,a[1]);ctx.lineTo(a[0]-r+depth,a[1]-depth*.45);ctx.lineTo(a[0]+r+depth,a[1]-depth*.45);ctx.lineTo(a[0]+r,a[1]);ctx.fill();
    if(b.glow>.38){ctx.fillStyle=`rgba(251,206,124,${light*pulse*.7})`; const floors=Math.min(9,Math.floor((p[1]-a[1])/9));for(let j=1;j<=floors;j++){const yy=a[1]+j*(p[1]-a[1])/(floors+1);ctx.fillRect(a[0]-r*.66,yy,Math.max(1,r*.24),Math.max(1,r*.09));if(b.glow>.7)ctx.fillRect(a[0]+r*.28,yy,Math.max(1,r*.2),Math.max(1,r*.09));}}
  }
  function draw() {
    ctx.clearRect(0,0,W,H); const t = paused ? 0 : frame;
    for(let i=0;i<75;i++){const x=rand(i+400)*W,y=rand(i+700)*H*.62;ctx.fillStyle=`rgba(214,224,255,${.11+rand(i+800)*.5})`;ctx.fillRect(x,y,rand(i+980)>.9?2:1,rand(i+980)>.9?2:1);}
    const glow=ctx.createRadialGradient(W*.78,H*.39,2,W*.78,H*.39,Math.min(W*.4,230));glow.addColorStop(0,'rgba(239,192,104,.24)');glow.addColorStop(1,'rgba(239,192,104,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);
    ctx.strokeStyle='rgba(120,164,232,.18)';ctx.lineWidth=1;for(let z=0;z<20;z+=2){let a=project(-13,0,z),b=project(13,0,z);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();}
    for(let x=-12;x<=12;x+=3){let a=project(x,0,0),b=project(x,0,20);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();}
    [...buildings].sort((a,b)=>b.z-a.z).forEach((b)=>cube(b,t));
    const cx=project(0,0,2);ctx.strokeStyle='rgba(237,202,127,.42)';ctx.beginPath();ctx.ellipse(cx[0],cx[1]+8,Math.min(W*.28,240),25,0,0,Math.PI*2);ctx.stroke();
  }
  function tick(t){frame=t;draw();if(!paused)raf=requestAnimationFrame(tick);}
  function setPause(value){paused=value;cancelAnimationFrame(raf);$('#motion').setAttribute('aria-pressed',String(value));$('#motion').setAttribute('aria-label',value?'Resume city animation':'Pause city animation');$('#motion').textContent=value?'▶':'Ⅱ';if(!paused)raf=requestAnimationFrame(tick);else draw();}
  $('#motion').addEventListener('click',()=>setPause(!paused));document.addEventListener('visibilitychange',()=>{if(document.hidden)setPause(true);});window.addEventListener('resize',resize);resize();setPause(paused);
})();
