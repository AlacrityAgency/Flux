/* Motion layer: entrance stagger, count-up numbers, graph particles, splash. Pure enhancement; the app works without it. */
(()=>{
'use strict';
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const root=document.documentElement;
if(reduce)return;
root.dataset.intro='1';setTimeout(()=>delete root.dataset.intro,1800);

/* ---------- splash (once per app session) ---------- */
try{
  if(!sessionStorage.getItem('flux-splash')){
    sessionStorage.setItem('flux-splash','1');
    const s=document.createElement('div');s.className='fx-splash';s.setAttribute('aria-hidden','true');
    s.innerHTML='<svg viewBox="36 30 196 204"><g fill="currentColor"><polygon points="48,40 220,40 192,84 92,84 92,180 64,224 48,224"/><polygon points="106,110 178,110 150,154 106,154"/></g><polygon points="150,180 218,180 190,224 122,224"/></svg>';
    document.body.appendChild(s);setTimeout(()=>s.remove(),1700);
  }
}catch(_){}

/* ---------- staggered entrance ---------- */
const REVEAL='.metric,.panel,.task-card,.usage-card,.role-assignment,.card,.provider-row,.project-row,.kanban-col,.approval-row,.knowledge-row,.node,.summary-card,.module-head,.engine,.composer-wrap,.mh-group,.notice';
const SKIP='#c9-log,.side,#mh-list,.fx-menu,dialog,.fx-toast,.fx-splash';
let queue=0,timer=0;
function reveal(el){
  if(el.dataset.m||!el.matches||el.closest(SKIP))return;
  el.dataset.m='1';el.style.setProperty('--mi',Math.min(queue++,14));el.classList.add('m-in');
  clearTimeout(timer);timer=setTimeout(()=>{queue=0},120);
  el.addEventListener('animationend',()=>{el.classList.remove('m-in');el.style.removeProperty('--mi')},{once:true});
}
function scan(node){
  if(node.nodeType!==1)return;
  if(node.matches(REVEAL))reveal(node);
  node.querySelectorAll&&node.querySelectorAll(REVEAL).forEach(reveal);
  node.querySelectorAll&&node.querySelectorAll('.metric b').forEach(countUp);
  if(node.matches('.metric b'))countUp(node);
  if(node.matches&&(node.matches('svg.edges')||node.querySelector('svg.edges')))particles();
}

/* ---------- count-up for the first number inside a metric ---------- */
const FA='۰۱۲۳۴۵۶۷۸۹',toEn=s=>s.replace(/[۰-۹]/g,d=>FA.indexOf(d)).replace(/٫/g,'.').replace(/٬/g,'');
function countUp(el){
  if(el.dataset.c)return;const text=el.textContent;
  const m=/[0-9۰-۹][0-9۰-۹٬,]*(?:[.٫][0-9۰-۹]+)?/.exec(text);if(!m)return;
  const target=parseFloat(toEn(m[0]).replace(/,/g,''));if(!isFinite(target)||target===0||Math.abs(target)>1e9)return;
  const decimals=(/[.٫]([0-9۰-۹]+)/.exec(m[0])||[,''])[1].length,persian=/[۰-۹٫]/.test(m[0]);
  el.dataset.c='1';const start=performance.now(),dur=900,before=text.slice(0,m.index),after=text.slice(m.index+m[0].length);
  const fmt=v=>{const s=v.toFixed(decimals);return persian?s.replace(/[0-9]/g,d=>FA[d]).replace('.','٫'):s};
  const step=now=>{const t=Math.min(1,(now-start)/dur),e=1-Math.pow(1-t,3);el.textContent=before+fmt(target*e)+after;if(t<1&&el.isConnected&&el.dataset.c==='1')requestAnimationFrame(step);else el.textContent=text};
  requestAnimationFrame(step);
}

/* ---------- particles riding the org-graph edges ---------- */
let particled=false;
function particles(){
  const svg=document.querySelector('svg.edges');if(!svg||svg.dataset.p)return;svg.dataset.p='1';
  const NS='http://www.w3.org/2000/svg';
  svg.querySelectorAll('.edge.run,.edge.wait').forEach((path,i)=>{
    if(!path.id)path.id='edge-'+i;
    const wait=path.classList.contains('wait');
    for(let k=0;k<(wait?1:2);k++){
      const c=document.createElementNS(NS,'circle');c.setAttribute('r','3.2');c.setAttribute('class','particle'+(wait?' wait':''));
      const a=document.createElementNS(NS,'animateMotion');a.setAttribute('dur',(wait?6:3.4+i*.35)+'s');a.setAttribute('repeatCount','indefinite');a.setAttribute('begin',(k*1.6+i*.3)+'s');
      const mp=document.createElementNS(NS,'mpath');mp.setAttributeNS('http://www.w3.org/1999/xlink','href','#'+path.id);mp.setAttribute('href','#'+path.id);
      a.appendChild(mp);c.appendChild(a);svg.appendChild(c);
    }
  });
}

/* ---------- theme fade ---------- */
document.addEventListener('click',e=>{
  if(e.target.closest&&e.target.closest('#theme')){root.classList.add('theme-fade');setTimeout(()=>root.classList.remove('theme-fade'),500)}
},true);

/* ---------- observe ---------- */
const css=document.createElement('link');css.rel='stylesheet';css.href='/static/motion.css';document.head.appendChild(css);
new MutationObserver(list=>{for(const m of list){for(const n of m.addedNodes)scan(n);const t=m.target;if(t&&t.matches&&t.matches('.metric b')&&!t.dataset.c)countUp(t)}}).observe(document.documentElement,{childList:true,subtree:true});
const boot=()=>{scan(document.body);particles()};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
window.fluxMotion={countUp,reveal};
})();
