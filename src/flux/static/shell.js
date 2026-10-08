/* Shared chrome for the organisation workspace: theme, active project, sidebar projects and connected accounts. */
(()=>{
'use strict';
const ACTIVE_KEY='flux-active-project',THEME_KEY='flux-theme',OPEN_KEY='flux-projects-open',ICON_KEY='flux-project-icons';
const WORKSPACE='/design-v2/03-10-workspace.html';
const NAMES={codex:'Codex',claude:'Claude',gapcode:'GapCode',gemini:'Gemini CLI',antigravity:'Antigravity','deepseek-web':'DeepSeek Web','gemini-web':'Gemini Web',notebooklm:'NotebookLM'};
const root=document.documentElement;
const store={get:k=>{try{return localStorage.getItem(k)}catch(_){return null}},set:(k,v)=>{try{v==null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch(_){}}};
const fa=n=>Number(n).toLocaleString('fa-IR');

/* theme: applied before first paint of the module, remembered across pages */
const savedTheme=store.get(THEME_KEY);if(savedTheme==='light'||savedTheme==='dark')root.dataset.theme=savedTheme;

async function call(path,options){
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options&&options.headers)}});
  let data=null;try{data=await response.json()}catch(_){}
  if(!response.ok)throw new Error((data&&typeof data.detail==='string'&&data.detail)||'انجام نشد.');
  return data;
}
const state={projects:[],activeId:store.get(ACTIVE_KEY)||'',status:null};
const active=()=>state.projects.find(p=>p.id===state.activeId)||null;

/* ---------- project icons: a glyph + colour per project, chosen by name and changeable ---------- */
const GLYPHS={
  shield:['محافظ','#ef6461','<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><circle cx="11.5" cy="11" r="2.6"/><path d="M13.4 12.9l2.6 2.6"/>'],
  core:['هسته','#baed91','<path d="M12 2.5l8.5 5v9L12 21.5l-8.5-5v-9z"/><path d="M12 8l4 2.3v4.4L12 17l-4-2.3v-4.4z"/>'],
  flask:['آزمایشگاه','#f5b74f','<path d="M9 3h6M10 3v6L4.6 18.8A1.5 1.5 0 0 0 5.9 21h12.2a1.5 1.5 0 0 0 1.3-2.2L14 9V3"/><path d="M7.2 15h9.6"/>'],
  flux:['جریان','#5eead4','<path d="M4 5h16l-4 4H4z"/><path d="M4 11h11l-4 4H4z"/><path d="M4 17h6l-4 4H4z"/>'],
  cpu:['سیستم','#7aa2ff','<rect x="6" y="6" width="12" height="12" rx="1.5"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>'],
  plane:['جابه‌جایی','#c084fc','<path d="M21.5 3.5L2.5 11l7 2.5 2.5 7z"/><path d="M9.5 13.5l12-10"/>'],
  globe:['وب','#38bdf8','<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.8 3 2.8 15 0 18M12 3c-2.8 3-2.8 15 0 18"/>'],
  code:['کد','#a3e635','<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>'],
  book:['مستند','#fb923c','<path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z"/>'],
  chart:['داده','#f472b6','<path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/>'],
  box:['محصول','#facc15','<path d="M3 7.5L12 3l9 4.5v9L12 21l-9-4.5z"/><path d="M3 7.5l9 4.5 9-4.5M12 12v9"/>'],
  spark:['ایده','#e879f9','<path d="M12 2.5l2.2 7.3 7.3 2.2-7.3 2.2L12 21.5l-2.2-7.3L2.5 12l7.3-2.2z"/>']
};
const iconChoices=()=>{try{return JSON.parse(store.get(ICON_KEY)||'{}')||{}}catch(_){return {}}};
function iconFor(project){
  const picked=iconChoices()[project.id];if(GLYPHS[picked])return picked;
  const n=(project.name+' '+project.path).toLowerCase();
  const rules=[[/ageis|aegis/,'shield'],[/alchim/,'flask'],[/flux/,'flux'],[/relocat/,'plane'],[/website|\bweb\b|site/,'globe'],[/(^|[\\\/ ])os([\\\/ ]|$)/,'cpu'],[/alacrity|octarine/,'core']];
  for(const [re,id] of rules)if(re.test(n))return id;
  const rest=['code','book','chart','box','spark'];let h=0;for(const c of project.id)h=(h*31+c.charCodeAt(0))>>>0;return rest[h%rest.length];
}
function tile(project,size){
  const id=typeof project==='string'?project:iconFor(project),[,color,body]=GLYPHS[id];
  const span=document.createElement('span');span.className='proj-tile';span.style.setProperty('--tile',color);if(size)span.style.setProperty('--tile-size',size+'px');
  span.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;return span;
}
function setIcon(project,id){const map=iconChoices();map[project.id]=id;store.set(ICON_KEY,JSON.stringify(map));render();window.dispatchEvent(new CustomEvent('flux:project-icons'))}

/* ---------- actions ---------- */
function setActive(project,{silent=false}={}){
  state.activeId=project?project.id:'';store.set(ACTIVE_KEY,project?project.id:null);
  render();
  window.dispatchEvent(new CustomEvent('flux:project',{detail:{project}}));
  if(!silent&&project)toast('پروژهٔ «'+project.name+'» فعال شد');
}
async function refresh(){
  try{state.projects=(await call('/projects')).filter(p=>!p.archived)}catch(_){state.projects=[]}
  if(!active()){state.activeId=state.projects.length?state.projects[0].id:'';store.set(ACTIVE_KEY,state.activeId||null)}
  render();
  window.dispatchEvent(new CustomEvent('flux:projects',{detail:{projects:state.projects,active:active()}}));
}
const confirmBox=opts=>window.fluxChats?window.fluxChats.ask(opts):Promise.resolve(confirm(opts.title));
async function archive(project){
  if(!await confirmBox({title:'بایگانی پروژه',message:'«'+project.name+'» از فهرست پنهان می‌شود؛ پوشه و حافظه‌اش دست نمی‌خورد و از «اتصال‌ها و تنظیمات» برمی‌گردد.',confirmLabel:'بایگانی'}))return;
  try{await call('/projects/'+encodeURIComponent(project.id),{method:'PATCH',body:JSON.stringify({archived:true})});if(state.activeId===project.id)state.activeId='';await refresh()}
  catch(e){toast(e.message)}
}
async function removeProject(project){
  if(!await confirmBox({title:'حذف پروژه از Flux',message:'«'+project.name+'» از Flux حذف می‌شود. پوشه و فایل‌هایت روی دیسک ('+project.path+') دست نمی‌خورند. اگر فقط نمی‌خواهی در فهرست ببینی، بایگانی کن.',confirmLabel:'حذف',danger:true}))return;
  try{await call('/projects/'+encodeURIComponent(project.id),{method:'DELETE'});if(state.activeId===project.id)state.activeId='';await refresh();toast('«'+project.name+'» حذف شد')}
  catch(e){toast(e.message)}
}
async function renameProject(project){
  const name=window.fluxChats?await window.fluxChats.ask({title:'تغییر نام پروژه',input:project.name,confirmLabel:'ذخیره'}):prompt('نام تازه',project.name);
  if(!name||name===project.name)return;
  try{await call('/projects/'+encodeURIComponent(project.id),{method:'PATCH',body:JSON.stringify({name})});await refresh()}catch(e){toast(e.message)}
}
function addProject(){
  return new Promise(resolve=>{
    const d=document.createElement('dialog');d.className='fx-dialog proj-dialog';
    d.innerHTML=`<h2>پروژهٔ تازه</h2><p>یک پوشهٔ موجود روی همین دستگاه را به Flux اضافه کن.</p>
      <label>مسیر پوشه<div class="proj-path"><input name="path" dir="ltr" required maxlength="1000" placeholder="D:\\project\\..." autocomplete="off"><button type="button" class="pick">انتخاب پوشه…</button></div></label>
      <label>نام<input name="name" required maxlength="120" autocomplete="off"></label>
      <label>توضیح کوتاه<input name="desc" maxlength="5000" autocomplete="off" placeholder="اختیاری"></label>
      <p class="proj-error" role="alert" hidden></p>
      <div class="fx-dialog-actions"><button type="button" class="cancel">انصراف</button><button type="button" class="primary ok">افزودن پروژه</button></div>`;
    const f=n=>d.querySelector(`[name=${n}]`),err=d.querySelector('.proj-error');
    const fillName=()=>{if(!f('name').value.trim()){const base=f('path').value.trim().replace(/[\\\/]+$/,'').split(/[\\\/]/).pop();if(base)f('name').value=base}};
    f('path').addEventListener('change',fillName);
    d.querySelector('.pick').onclick=async e=>{e.target.disabled=true;try{const r=await call('/filesystem/pick-folder',{method:'POST',body:'{}'});if(r.path){f('path').value=r.path;fillName();f('name').focus()}}catch(x){err.textContent=x.message;err.hidden=false}finally{e.target.disabled=false}};
    d.querySelector('.cancel').onclick=()=>d.close();
    d.querySelector('.ok').onclick=async e=>{
      err.hidden=true;fillName();const path=f('path').value.trim(),name=f('name').value.trim();
      if(!path){f('path').focus();return}if(!name){f('name').focus();return}
      e.target.disabled=true;
      try{const folder=await call('/filesystem/validate-path?path='+encodeURIComponent(path));if(!folder.exists||!folder.is_dir)throw new Error('این پوشه روی دستگاه پیدا نشد.');
        if(state.projects.some(p=>p.path.toLowerCase()===path.toLowerCase()))throw new Error('این پوشه قبلاً به‌عنوان پروژه ثبت شده است.');
        const p=await call('/projects',{method:'POST',body:JSON.stringify({name,path,description:f('desc').value.trim()})});
        await refresh();setActive(p);d.close();resolve(p);}
      catch(x){err.textContent=x.message;err.hidden=false}finally{e.target.disabled=false}};
    d.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.tagName==='INPUT'){e.preventDefault();d.querySelector('.ok').click()}});
    d.addEventListener('close',()=>{d.remove();resolve(null)});
    document.body.appendChild(d);d.showModal();f('path').focus();
  });
}
const manage=()=>{location.href=WORKSPACE+'?screen=10#projects'};
function iconMenu(project,x,y){
  const cur=iconFor(project);
  window.fluxMenu.show(Object.entries(GLYPHS).map(([id,[label]])=>({label,icon:id,checked:id===cur,run:()=>setIcon(project,id)})),x,y);
}
function menuFor(project,at){
  return [
    {label:project.id===state.activeId?'پروژهٔ فعال':'فعال کردن این پروژه',icon:'check',disabled:project.id===state.activeId,run:()=>setActive(project)},
    {label:'گفتگوی تازه در این پروژه',icon:'chat',run:()=>{setActive(project,{silent:true});location.href=WORKSPACE+'?screen=9'}},
    {label:'درخواست کار برای این پروژه',icon:'work',run:()=>{setActive(project,{silent:true});location.href='/design-v2/02-request-contract.html'}},
    '-',
    {label:'باز کردن پوشه',icon:'folder',run:()=>call('/filesystem/open-folder',{method:'POST',body:JSON.stringify({path:project.path})}).catch(e=>toast(e.message))},
    {label:'کپی مسیر پوشه',icon:'clip',run:()=>navigator.clipboard&&navigator.clipboard.writeText(project.path).then(()=>toast('مسیر کپی شد'))},
    {label:'تغییر نام…',icon:'log',key:'F2',run:()=>renameProject(project)},
    {label:'تغییر آیکون…',icon:'spark-i',run:()=>iconMenu(project,at.x,at.y)},
    '-',
    {label:'افزودن پروژهٔ تازه…',icon:'plus',run:addProject},
    {label:'بایگانی…',icon:'layers',run:()=>archive(project)},
    {label:'حذف از Flux…',icon:'x',key:'Del',danger:true,run:()=>removeProject(project)}
  ];
}
function switcherItems(){
  const items=state.projects.map(p=>({label:p.name,checked:p.id===state.activeId,hint:'',run:()=>setActive(p)}));
  if(!items.length)items.push({label:'هنوز پروژه‌ای ثبت نشده',disabled:true});
  return [{header:'پروژهٔ فعال'},...items,'-',{label:'افزودن پروژهٔ تازه…',icon:'plus',run:addProject},{label:'مدیریت پروژه‌ها…',icon:'sliders',run:manage}];
}

/* ---------- rendering ---------- */
function addSymbols(){
  const sprite=document.querySelector('body>svg');if(!sprite||sprite.querySelector('#i-folder'))return;
  sprite.insertAdjacentHTML('beforeend','<symbol id="i-folder" viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></symbol><symbol id="i-spark-i" viewBox="0 0 24 24"><path d="M12 2.5l2.2 7.3 7.3 2.2-7.3 2.2L12 21.5l-2.2-7.3L2.5 12l7.3-2.2z"/></symbol>');
}
function renderCrumb(){
  for(const btn of document.querySelectorAll('.crumb .proj:not(#project-toggle)')){
    const label=btn.querySelector('span');if(label)label.textContent=active()?active().name:'انتخاب پروژه';
    btn.querySelector('.proj-tile')?.remove();if(active())btn.prepend(tile(active(),18));
    btn.removeAttribute('href');btn.removeAttribute('data-s');btn.setAttribute('aria-haspopup','menu');btn.title=active()?active().path:'پروژهٔ فعال را انتخاب کن';
    if(!btn.dataset.shell){btn.dataset.shell='1';btn.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();const r=btn.getBoundingClientRect();window.fluxMenu&&window.fluxMenu.show(switcherItems(),r.right,r.bottom+6,{alignEnd:true,minWidth:220})},true)}
  }
  const home=document.getElementById('project-toggle');
  if(home){const l=document.getElementById('project-label');if(l)l.textContent=active()?active().name:'انتخاب پروژه';home.querySelector('.proj-tile')?.remove();if(active())home.prepend(tile(active(),18))}
}
function renderSidebar(){
  const chats=document.querySelector('.side .recent:not(.proj-list)');if(!chats)return;
  const chatsLabel=chats.previousElementSibling;
  let box=document.querySelector('.side .proj-list');
  if(!box){
    const label=document.createElement('button');label.type='button';label.className='nav-label proj-label';
    box=document.createElement('div');box.className='recent proj-list';box.setAttribute('aria-label','پروژه‌ها');
    (chatsLabel&&chatsLabel.classList.contains('nav-label')?chatsLabel:chats).before(label,box);
    label.onclick=()=>{const open=store.get(OPEN_KEY)==='0';store.set(OPEN_KEY,open?'1':'0');render()};
    const generic=e=>{if(!e.detail.items.length)e.detail.items.push({label:'افزودن پروژهٔ تازه…',icon:'plus',run:addProject},{label:'مدیریت پروژه‌ها…',icon:'sliders',run:manage})};
    label.addEventListener('fx:menu',generic);box.addEventListener('fx:menu',generic);
  }
  const open=store.get(OPEN_KEY)!=='0',label=box.previousElementSibling;
  label.setAttribute('aria-expanded',String(open));
  const add=Object.assign(document.createElement('span'),{className:'proj-add',title:'افزودن پروژهٔ تازه',textContent:'+'});
  add.setAttribute('role','button');add.onclick=e=>{e.stopPropagation();addProject()};
  label.replaceChildren(Object.assign(document.createElement('span'),{textContent:'پروژه‌ها'}),Object.assign(document.createElement('em'),{textContent:state.projects.length?fa(state.projects.length):''}),add);
  box.replaceChildren();box.hidden=!open;
  for(const p of state.projects){
    const a=document.createElement('a');a.href='#';a.className='proj-row';a.title=p.path;a.dataset.projectId=p.id;
    if(p.id===state.activeId)a.setAttribute('aria-current','true');
    const name=document.createElement('span');name.className='proj-name';name.textContent=p.name;a.append(tile(p),name);
    a.addEventListener('click',e=>{e.preventDefault();if(p.id!==state.activeId)setActive(p)});
    a.addEventListener('fx:menu',e=>{const r=a.getBoundingClientRect();e.detail.items.push(...menuFor(p,{x:r.left,y:r.bottom}))});
    a.addEventListener('keydown',e=>{if(e.key==='Delete'){e.preventDefault();removeProject(p)}else if(e.key==='F2'){e.preventDefault();renameProject(p)}});
    box.appendChild(a);
  }
  if(!state.projects.length){const e=document.createElement('a');e.href='#';e.className='proj-row proj-empty';e.onclick=ev=>{ev.preventDefault();addProject()};e.append(Object.assign(document.createElement('span'),{textContent:'+ افزودن پروژه'}));box.appendChild(e)}
}
function renderAccounts(){
  const s=state.status;if(!s)return;
  const linked=(s.providers||[]).filter(p=>NAMES[p.id]&&p.authenticated);
  for(const q of document.querySelectorAll('.side .quota')){
    q.replaceChildren();q.classList.add('accounts');
    const head=document.createElement('div');head.className='row';head.append(Object.assign(document.createElement('span'),{textContent:'حساب‌های متصل'}),Object.assign(document.createElement('b'),{className:'num',textContent:fa(linked.length)}));
    const list=document.createElement('div');list.className='acct-list';
    for(const p of linked)list.appendChild(Object.assign(document.createElement('span'),{className:'acct',textContent:NAMES[p.id]}));
    if(!linked.length)list.appendChild(Object.assign(document.createElement('span'),{className:'acct off',textContent:'هیچ حسابی وصل نیست'}));
    q.append(head,list);
  }
  for(const chip of document.querySelectorAll('.budget-chip')){
    if(chip.querySelector('#connected-count')){chip.querySelector('#connected-count').textContent=fa(linked.length);continue}
    chip.replaceChildren(Object.assign(document.createElement('span'),{className:'source-label',textContent:'حساب‌های متصل'}),Object.assign(document.createElement('b'),{className:'num',textContent:fa(linked.length)}));
    chip.title=linked.map(p=>NAMES[p.id]).join('، ')||'هیچ حسابی وصل نیست';
  }
}
/* brand mark: the angular F (structure + heads) with the green output block, drawn inline so it follows the theme */
const MARK='<svg viewBox="36 30 196 204" aria-hidden="true"><g fill="currentColor"><polygon points="48,40 220,40 192,84 92,84 92,180 64,224 48,224"/><polygon points="106,110 178,110 150,154 106,154"/></g><polygon class="mark-flow" points="150,180 218,180 190,224 122,224"/></svg>';
function renderBrand(){
  for(const m of document.querySelectorAll('.brand .mark:not(.fx-mark)')){
    const s=document.createElement('span');s.className='mark fx-mark';s.setAttribute('role','img');s.setAttribute('aria-label','Flux');s.innerHTML=MARK;m.replaceWith(s);
  }
}
function render(){addSymbols();renderBrand();renderCrumb();renderSidebar()}

let toastTimer;
function toast(message){
  let t=document.querySelector('.fx-toast');
  if(!t){t=document.createElement('div');t.className='fx-toast';t.setAttribute('role','status');document.body.appendChild(t)}
  t.textContent=message;t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),2600);
}

function bindChrome(){
  const theme=document.getElementById('theme');
  if(theme)theme.onclick=e=>{e.stopImmediatePropagation();root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';store.set(THEME_KEY,root.dataset.theme)};
}
async function loadStatus(){
  try{state.status=await call('/api/local/status')}catch(_){state.status={providers:[]}}
  renderAccounts();window.dispatchEvent(new CustomEvent('flux:status',{detail:state.status}));
}

const css=document.createElement('link');css.rel='stylesheet';css.href='/static/shell.css';document.head.appendChild(css);
window.fluxShell={state,call,refresh,setActive,active,toast,addProject,removeProject,renameProject,archive,tile,iconFor,names:NAMES,status:()=>state.status};
function start(){bindChrome();render();refresh();loadStatus()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
