/* Windows-native behaviour for every Flux page: context menu, text selection, drag/drop, dev shortcuts. */
(()=>{
'use strict';
if(window.__fluxNative)return;window.__fluxNative=true;

const L={undo:'واگرد',cut:'برش',copy:'کپی',paste:'چسباندن',del:'حذف',all:'انتخاب همه',openLink:'باز کردن پیوند',copyLink:'کپی نشانی پیوند',copyBlock:'کپی این بخش',reload:'بارگذاری مجدد',back:'بازگشت'};
const TEXT_INPUTS=new Set(['text','search','url','tel','email','password','number','']);
let app=false;
try{
  if(new URLSearchParams(location.search).has('desktop'))sessionStorage.setItem('flux-app','1');
  app=sessionStorage.getItem('flux-app')==='1'||matchMedia('(display-mode: standalone)').matches||matchMedia('(display-mode: minimal-ui)').matches;
}catch(_){app=matchMedia('(display-mode: standalone)').matches}

/* ---------- styles ---------- */
const link=document.createElement('link');link.rel='stylesheet';link.href='/static/native.css';document.head.appendChild(link);

/* ---------- helpers ---------- */
const isEditable=el=>{
  if(!el||!el.closest)return null;
  const f=el.closest('input,textarea,[contenteditable=""],[contenteditable="true"]');
  if(!f)return null;
  if(f.tagName==='INPUT'&&!TEXT_INPUTS.has((f.getAttribute('type')||'text').toLowerCase()))return null;
  return f;
};
const selectedText=f=>{
  if(f&&'selectionStart' in f&&f.selectionStart!=null)return f.value.slice(f.selectionStart,f.selectionEnd);
  return String(getSelection());
};
async function writeClipboard(text){
  try{await navigator.clipboard.writeText(text);return true}catch(_){}
  const ta=document.createElement('textarea');ta.value=text;ta.style.cssText='position:fixed;opacity:0;inset:0';document.body.appendChild(ta);ta.select();
  const ok=document.execCommand('copy');ta.remove();return ok;
}

let menu=null,prevFocus=null,openedAt=0;
function close(restore=true){
  if(!menu)return;
  try{menu.hidePopover&&menu.hidePopover()}catch(_){}
  menu.remove();menu=null;
  document.removeEventListener('keydown',onKey,true);
  if(restore&&prevFocus&&prevFocus.focus&&document.contains(prevFocus)){try{prevFocus.focus({preventScroll:true})}catch(_){}}
  prevFocus=null;
}
const svgUse=id=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('class','fx-ic');s.setAttribute('viewBox','0 0 24 24');const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#i-'+id);s.appendChild(u);return s};
function build(items,opts={}){
  const m=document.createElement('div');m.className='fx-menu'+(opts.list?' fx-list':'');m.setAttribute('role',opts.list?'listbox':'menu');m.tabIndex=-1;
  m.dir=document.documentElement.dir||'rtl';
  const lead=items.some(it=>it&&typeof it==='object'&&(it.icon||'checked' in it));
  for(const it of items){
    if(it==='-'){const s=document.createElement('div');s.className='fx-sep';s.setAttribute('role','separator');m.appendChild(s);continue}
    if(it.header){const h=document.createElement('div');h.className='fx-head';h.textContent=it.header;m.appendChild(h);continue}
    const b=document.createElement('button');b.type='button';b.className='fx-item'+(it.danger?' fx-danger':'')+(it.checked?' fx-checked':'');b.setAttribute('role',opts.list?'option':'menuitem');b.disabled=!!it.disabled;
    if(opts.list)b.setAttribute('aria-selected',String(!!it.checked));
    if(lead){const c=document.createElement('span');c.className='fx-lead';if(it.checked)c.textContent='✓';else if(it.icon)c.appendChild(svgUse(it.icon));b.appendChild(c)}
    const l=document.createElement('span');l.className='fx-label';l.textContent=it.label;b.appendChild(l);
    if(it.hint){const h=document.createElement('span');h.className='fx-hint';h.textContent=it.hint;b.appendChild(h)}
    if(it.key){const k=document.createElement('span');k.className='fx-key';k.textContent=it.key;b.appendChild(k)}
    b.addEventListener('mousedown',e=>e.preventDefault());           // keep focus and selection in the page
    b.addEventListener('mouseenter',()=>{[...m.querySelectorAll('.fx-item')].forEach(x=>x.dataset.active='false');if(!b.disabled)b.dataset.active='true'});
    b.addEventListener('click',async()=>{const run=it.run;close(true);try{await run()}catch(_){}});
    m.appendChild(b);
  }
  return m;
}
function show(items,x,y,byKeyboard,opts={}){
  close(false);
  prevFocus=document.activeElement;
  menu=build(items,opts);openedAt=performance.now();
  if(opts.minWidth)menu.style.minWidth=Math.max(160,opts.minWidth)+'px';
  // A modal dialog makes the rest of the page inert, so the menu must live inside it.
  const host=[...document.querySelectorAll('dialog[open]')].reverse().find(d=>{try{return d.matches(':modal')}catch(_){return false}})||document.body;
  if('popover' in HTMLElement.prototype){menu.popover='manual';host.appendChild(menu);try{menu.showPopover()}catch(_){}}
  else host.appendChild(menu);
  const r=menu.getBoundingClientRect(),vw=innerWidth,vh=innerHeight;
  let left=opts.alignEnd?x-r.width:x,top=y;
  if(left+r.width>vw-4)left=Math.max(4,x-r.width);
  if(left<4)left=4;
  if(top+r.height>vh-4)top=Math.max(4,(opts.above!=null?opts.above:y)-r.height);
  menu.style.left=left+'px';menu.style.top=top+'px';
  menu.focus({preventScroll:true});
  document.addEventListener('keydown',onKey,true);
  const chosen=menu.querySelector('.fx-checked');
  if(opts.list&&chosen){chosen.dataset.active='true';chosen.scrollIntoView({block:'nearest'})}
  else if(byKeyboard)move(1);
}

/* ---------- styled dropdown for every <select>: same look as the menus, value stays in the real select ---------- */
function openSelect(sel){
  if(sel.disabled||sel.multiple||sel.size>1)return;
  const items=[];
  for(const node of sel.children){
    if(node.tagName==='OPTGROUP'){items.push({header:node.label});for(const o of node.children)items.push(optionItem(sel,o))}
    else if(node.tagName==='OPTION'&&!node.hidden)items.push(optionItem(sel,node));
  }
  if(!items.length)return;
  const r=sel.getBoundingClientRect();
  sel.focus({preventScroll:true});sel.setAttribute('aria-expanded','true');
  show(items,r.right,r.bottom+4,false,{list:true,minWidth:r.width,alignEnd:true,above:r.top-4});
  const m=menu;new MutationObserver((_,o)=>{if(!m.isConnected){sel.removeAttribute('aria-expanded');o.disconnect()}}).observe(m.parentNode,{childList:true});
}
function optionItem(sel,o){
  return {label:o.textContent,checked:o.selected,disabled:o.disabled,run:()=>{
    if(sel.value===o.value&&o.selected)return;
    o.selected=true;sel.dispatchEvent(new Event('input',{bubbles:true}));sel.dispatchEvent(new Event('change',{bubbles:true}));
  }};
}
document.addEventListener('mousedown',e=>{
  const sel=e.target.closest&&e.target.closest('select');
  if(!sel||e.button!==0||sel.multiple||sel.size>1||sel.dataset.native!=null)return;
  e.preventDefault();
  if(menu&&sel.getAttribute('aria-expanded')==='true'){close(true);return}
  openSelect(sel);
},true);
document.addEventListener('keydown',e=>{
  const sel=e.target;if(menu||!sel||sel.tagName!=='SELECT'||sel.multiple||sel.dataset.native!=null)return;
  if(e.key==='Enter'||e.key===' '||e.key==='F4'||(e.altKey&&e.key==='ArrowDown')){e.preventDefault();openSelect(sel)}
},true);
function move(step){
  const items=[...menu.querySelectorAll('.fx-item:not(:disabled)')];if(!items.length)return;
  const cur=items.findIndex(i=>i.dataset.active==='true');
  const next=cur<0?(step>0?0:items.length-1):(cur+step+items.length)%items.length;
  menu.querySelectorAll('.fx-item').forEach(i=>i.dataset.active='false');
  items[next].dataset.active='true';items[next].scrollIntoView({block:'nearest'});
}
function onKey(e){
  if(!menu)return;
  const k=e.key;
  if(k==='Escape'){e.preventDefault();e.stopPropagation();close(true)}
  else if(k==='ArrowDown'){e.preventDefault();move(1)}
  else if(k==='ArrowUp'){e.preventDefault();move(-1)}
  else if(k==='Home'||k==='End'){e.preventDefault();const it=[...menu.querySelectorAll('.fx-item:not(:disabled)')];menu.querySelectorAll('.fx-item').forEach(i=>i.dataset.active='false');(k==='Home'?it[0]:it[it.length-1])?.setAttribute('data-active','true')}
  else if(k==='Enter'||k===' '){const a=menu.querySelector('.fx-item[data-active=true]');if(a){e.preventDefault();e.stopPropagation();a.click()}}
  else if(k==='Tab'){e.preventDefault();close(true)}
}

/* ---------- menu content ---------- */
function itemsFor(target){
  const field=isEditable(target);
  const link=target.closest&&target.closest('a[href]');
  const sel=selectedText(field);
  const out=[];
  if(field){
    const ro=field.readOnly||field.disabled;
    const pw=field.tagName==='INPUT'&&field.type==='password';
    out.push({label:L.undo,key:'Ctrl+Z',disabled:ro,run:()=>{field.focus();document.execCommand('undo')}});
    out.push('-');
    out.push({label:L.cut,key:'Ctrl+X',disabled:ro||pw||!sel,run:()=>{field.focus();document.execCommand('cut')}});
    out.push({label:L.copy,key:'Ctrl+C',disabled:pw||!sel,run:()=>{field.focus();if(!document.execCommand('copy'))writeClipboard(sel)}});
    out.push({label:L.paste,key:'Ctrl+V',disabled:ro,run:async()=>{
      field.focus();
      const txt=await navigator.clipboard.readText();
      if(!txt)return;
      if(!document.execCommand('insertText',false,txt)&&'setRangeText' in field){field.setRangeText(txt,field.selectionStart,field.selectionEnd,'end');field.dispatchEvent(new Event('input',{bubbles:true}))}
    }});
    out.push({label:L.del,key:'Del',disabled:ro||!sel,run:()=>{field.focus();document.execCommand('delete')}});
    out.push('-');
    out.push({label:L.all,key:'Ctrl+A',disabled:!field.value&&!field.textContent,run:()=>{field.focus();if(field.select)field.select();else document.execCommand('selectAll')}});
    return out;
  }
  if(link){
    out.push({label:L.openLink,run:()=>{location.href=link.href}});
    out.push({label:L.copyLink,run:()=>writeClipboard(link.href)});
    out.push('-');
  }
  if(sel.trim()){
    out.push({label:L.copy,key:'Ctrl+C',run:()=>{if(!document.execCommand('copy'))writeClipboard(sel)}});
  }else{
    const block=target.closest&&target.closest('pre,.message-content,.artifact,.card,.workspace-card,.task-card,li,td,p');
    if(block&&block.innerText.trim())out.push({label:L.copyBlock,run:()=>writeClipboard(block.innerText.trim())});
  }
  out.push({label:L.all,key:'Ctrl+A',run:()=>document.execCommand('selectAll')});
  out.push('-');
  out.push({label:L.back,key:'Alt+←',disabled:history.length<=1,run:()=>history.back()});
  out.push({label:L.reload,key:'Ctrl+R',run:()=>location.reload()});
  return out;
}

document.addEventListener('contextmenu',e=>{
  if(e.target.closest&&e.target.closest('.fx-menu')){e.preventDefault();return}
  e.preventDefault();
  const kb=e.button!==2&&e.pointerType!=='mouse'&&e.detail===0;
  let x=e.clientX,y=e.clientY;
  if(kb){const r=(document.activeElement||e.target).getBoundingClientRect();x=r.left+8;y=r.bottom-4}
  // Pages can contribute their own items (e.g. conversations) by listening for fx:menu on the target.
  const ctx={target:e.target,items:[]};
  e.target.dispatchEvent(new CustomEvent('fx:menu',{bubbles:true,detail:ctx}));
  show(ctx.items.length?[...ctx.items,'-',{label:L.reload,key:'Ctrl+R',run:()=>location.reload()}]:itemsFor(e.target),x,y,kb);
},true);
window.fluxMenu={show:(items,x,y,opts)=>show(items,x,y,false,opts||{}),close:()=>close(false)};
const inMenu=t=>t&&t.closest&&t.closest('.fx-menu');
document.addEventListener('mousedown',e=>{if(menu&&!inMenu(e.target)&&!(e.target.closest&&e.target.closest('select[aria-expanded=true]')))close(false)},true);
addEventListener('blur',()=>{if(performance.now()-openedAt>400)close(false)});
addEventListener('resize',()=>close(false));
// layout can nudge a scroll container while the menu opens (focus moves); only later scrolls close it
addEventListener('scroll',e=>{if(!inMenu(e.target)&&performance.now()-openedAt>350)close(false)},true);
addEventListener('wheel',e=>{if(!inMenu(e.target))close(false)},{passive:true,capture:true});

/* ---------- desktop-app behaviour ---------- */
// Dropping a file on the window must not navigate away from Flux.
for(const t of ['dragover','drop'])addEventListener(t,e=>{if(!(e.target.closest&&e.target.closest('input[type=file]')))e.preventDefault()});
if(app){
  addEventListener('keydown',e=>{
    const k=e.key.toLowerCase(),c=e.ctrlKey||e.metaKey;
    if(k==='f12'||(c&&e.shiftKey&&['i','j','c'].includes(k))||(c&&['u','s'].includes(k)&&!e.altKey))e.preventDefault();
  },true);
}
})();
