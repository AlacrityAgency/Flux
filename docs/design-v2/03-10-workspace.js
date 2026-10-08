 'use strict';
const $=id=>document.getElementById(id), qs=new URLSearchParams(location.search), icons={3:'work',4:'shield',5:'bot',6:'chart',7:'shield',8:'layers',9:'chat',10:'sliders'};
const labels={3:'کارها',4:'تصمیم یک کار',5:'نقش‌ها و عامل‌ها',6:'مصرف حساب‌ها',7:'تأییدها و اختیار',8:'دانش و حافظه',9:'گفتگوها',10:'اتصال‌ها و تنظیمات'};
const statuses=['ثبت‌شده','نیازمند اطلاعات','آماده','در حال اجرا','در حال بازبینی','نیازمند اصلاح','منتظر مجوز','متوقف به علت بودجه','آمادهٔ پذیرش','پذیرفته‌شده','ارجاع‌شده','لغوشده'];
const tasks=[['خروجی‌گرفتن از گزارش سفارش‌ها','Head فنی','آمادهٔ پذیرش','۲٫۰۰ دلار','۳ معیار'],['بررسی فاکتورهای ماه','Head عملیات','نیازمند اطلاعات','۰٫۸۰ دلار','فایل فاکتور مهر موجود نیست'],['به‌روزرسانی مستندات API','Head فنی','نیازمند اصلاح','۱٫۲۰ دلار','تلاش ۲ از ۳ · یک معیار رد شد'],['دستورالعمل پذیرش مشتری','Head عملیات','در حال بازبینی','۰٫۶۰ دلار','بازبین مستقل · ۵ معیار'],['گزارش ماهانهٔ مشتری','Head عملیات','منتظر مجوز','۰٫۳۰ دلار','ارسال بیرونی نیازمند تأیید'],['تجمیع اسناد بازپرداخت','Head عملیات','در حال اجرا','۰٫۴۰ دلار','دو منبع باقی مانده'],['فهرست بدهی‌های معوق','Head فنی','در حال اجرا','۰٫۵۰ دلار','به‌روزرسانی ۳ دقیقه پیش']];
let screen=Number(qs.get('screen'))||3,view='board',filter='همه',filterStatus='همه',approval='در انتظار',layer='پروژه';
const ACCOUNTS=[['codex','Codex'],['claude','Claude'],['gapcode','GapCode'],['gemini','Gemini CLI'],['antigravity','Antigravity'],['deepseek-web','DeepSeek Web'],['gemini-web','Gemini Web']];
const NO_MODEL=new Set(['deepseek-web','gemini-web','notebooklm']);
const DEFAULT_ROLES={central:{provider:'claude',model:'opus'},'tech-head':{provider:'codex',model:''},'test-runner':{provider:'gapcode',model:''},static:{provider:'gapcode',model:''},architect:{provider:'codex',model:''},'sec-head':{provider:'claude',model:'sonnet'},'sec-auditor':{provider:'claude',model:'opus'},'privacy-auditor':{provider:'claude',model:'sonnet'},'sci-head':{provider:'claude',model:'opus'},'sci-auditor':{provider:'gemini',model:''},'docs-auditor':{provider:'gemini',model:''},reviewer:{provider:'codex',model:''}};
let roleAssign={},catalog={connected:{},models:{}},rolesLoaded=false,saveTimer=null;
async function loadRoleData(){
 rolesLoaded=true;
 try{const saved=JSON.parse(localStorage.getItem('flux-role-models')||'null');if(saved)roleAssign=saved}catch(_){}
 try{const [st,rm]=await Promise.all([fetch('/api/local/status').then(r=>r.json()),fetch('/roles/models').then(r=>r.json())]);
  catalog.connected=Object.fromEntries((st.providers||[]).map(p=>[p.id,!!p.authenticated]));catalog.models=st.models||{};
  if(rm.roles&&Object.keys(rm.roles).length)roleAssign=rm.roles;
 }catch(_){}
 if(screen===5)render();
}
function saveRoles(){
 try{localStorage.setItem('flux-role-models',JSON.stringify(roleAssign))}catch(_){}
 clearTimeout(saveTimer);
 saveTimer=setTimeout(async()=>{const el=$('roles-status');try{const r=await fetch('/roles/models',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({roles:roleAssign})});if(!r.ok)throw new Error();if(el)el.textContent='ذخیره شد ✓'}catch(_){if(el)el.textContent='ذخیرهٔ سرور نشد؛ فقط در این مرورگر نگه داشته شد'}},250);
}
function setRole(id,patch){
 const base=roleAssign[id]||DEFAULT_ROLES[id]||{provider:'codex',model:''};
 roleAssign={...roleAssign,[id]:{...base,...patch}};
 saveRoles();
}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=(x)=>`<svg class="ic"><use href="#i-${x}"/></svg>`;
const SAMPLE=new Set([3,4,7,8]);
const sampleTag=()=>SAMPLE.has(screen)?'<span class="sample-tag" title="این بخش هنوز به دادهٔ زندهٔ Flux وصل نیست">دادهٔ نمونه</span>':'';
function metric(title,value,sub=''){return `<div class="metric"><small>${title}</small><b>${value}</b>${sub?`<small>${sub}</small>`:''}</div>`;}
function panel(title,body,extra=''){return `<section class="panel"><div class="panel-head"><h2>${title}</h2>${extra}</div><div class="panel-body">${body}</div></section>`;}
function chip(text,on=false){return `<button type="button" class="chip" aria-pressed="${on}" data-filter="${esc(text)}">${text}</button>`;}

/* ---------- real conversations (screen 9): same local runtime and accounts as the classic chat ---------- */
const C9={chat:null,status:null,timer:null,sending:false,project:null};
const C9_STATES={queued:'در صف اجرا',running:'در حال انجام کار…',completed:'',failed:'خطای اجرا',cancelled:'متوقف شد',interrupted:'اجرا قطع شد',needs_input:'نیاز به بررسی شما'};
const C9_ACTIVE=new Set(['queued','running']);
const c9=id=>document.getElementById(id);
const c9api=(path,options)=>window.fluxChats.call(path,options);
function chatShell(){
  return `<header class="module-head"><div><h1 id="c9-title">گفتگوی تازه با مدل‌ها</h1><p id="c9-sub">با حساب‌های متصل خودت کار کن؛ هیچ API پولی استفاده نمی‌شود.</p></div><div class="module-actions" id="c9-actions"></div></header>
  <div class="panel" id="c9-setup" hidden><div class="panel-head"><h2>تنظیم گفتگو</h2></div><div class="panel-body"><div class="c9-grid">
    <label>حساب<select id="c9-provider"></select></label>
    <label>مدل<select id="c9-model"></select></label>
    <label>دسترسی<select id="c9-access"><option value="read">فقط خواندن</option><option value="work">خواندن، ویرایش و اجرا</option></select></label>
    <label class="c9-wide">پوشهٔ کار<input id="c9-cwd" dir="ltr" placeholder="D:\\project\\..."></label></div>
    <p class="role-note" id="c9-setup-note"></p></div></div>
  <div class="panel"><div class="panel-body"><div class="chat-log" id="c9-log" aria-live="polite"></div>
    <div id="c9-error" class="notice" role="alert" hidden></div>
    <div class="composer"><textarea id="c9-input" rows="2" placeholder="پیام برای مدل… (Enter ارسال، Shift+Enter خط جدید)"></textarea><button class="primary" id="c9-send">ارسال</button></div></div></div>`;
}
function c9bubble(kind,text,label){
  const d=document.createElement('div');d.className='bubble'+(kind==='user'?' user':'');
  if(label){const b=document.createElement('b');b.textContent=label;d.appendChild(b)}
  if(kind==='user'){const md=document.createElement('div');md.className='md';md.appendChild(window.fluxMarkdown?window.fluxMarkdown.render(text):document.createTextNode(text));d.appendChild(md);return d}
  const md=document.createElement('div');md.className='md';md.appendChild(window.fluxMarkdown?window.fluxMarkdown.render(text):document.createTextNode(text));d.appendChild(md);d.classList.add('assistant');
  if(text&&text.length>1&&navigator.clipboard){const row=document.createElement('div');row.className='bubble-tools';const cp=document.createElement('button');cp.type='button';cp.textContent='کپی پاسخ';cp.onclick=()=>navigator.clipboard.writeText(text).then(()=>{cp.textContent='کپی شد ✓';setTimeout(()=>cp.textContent='کپی پاسخ',1400)});row.appendChild(cp);d.appendChild(row)}
  return d;
}
function c9render(){
  const chat=C9.chat,log=c9('c9-log');if(!log)return;
  const atEnd=log.scrollHeight-log.scrollTop-log.clientHeight<80;
  log.replaceChildren();
  const turns=chat?chat.turns:[];
  if(!turns.length){const e=document.createElement('div');e.className='c9-empty';e.innerHTML='<svg viewBox=\"0 0 64 64\" aria-hidden=\"true\"><g fill=\"currentColor\"><polygon class=\"flowbar\" points=\"10,12 54,12 47,22 10,22\"/><polygon class=\"flowbar\" points=\"10,27 38,27 31,37 10,37\"/><polygon class=\"flowbar\" points=\"10,42 26,42 19,52 10,52\"/></g></svg>';const t=document.createElement('p');t.className='role-note';t.textContent='پیام اول را بنویس؛ همان گفتگو با همین حساب و پوشه ادامه پیدا می‌کند.';e.appendChild(t);log.appendChild(e)}
  for(const t of turns){
    log.appendChild(c9bubble('user',t.prompt));
    const who=(C9.status&&chat?C9.names[chat.provider]:'')||'دستیار';
    const state=C9_STATES[t.state]||'';
    const body=t.text||'';
    const bub=c9bubble('assistant',body||(C9_ACTIVE.has(t.state)?'':(t.error||'')),who);
    if(!body&&C9_ACTIVE.has(t.state)){const md=bub.querySelector('.md');if(md){md.replaceChildren();const ty=document.createElement('span');ty.className='typing';ty.setAttribute('aria-label','در حال نوشتن');ty.innerHTML='<i></i><i></i><i></i>';md.appendChild(ty)}}
    if(state&&t.state!=='completed'){const s=document.createElement('small');s.className='c9-state';s.textContent=state;bub.appendChild(s)}
    if(t.state==='failed'&&t.error&&t.text){const er=document.createElement('p');er.className='c9-err';er.textContent=t.error;bub.appendChild(er)}
    log.appendChild(bub);
  }
  if(atEnd)log.scrollTop=log.scrollHeight;
  const running=turns.some(t=>C9_ACTIVE.has(t.state));
  const btn=c9('c9-send');btn.textContent=running?'توقف':'ارسال';btn.dataset.mode=running?'stop':'send';
  if(chat)c9('c9-input').disabled=false;
}
async function c9poll(){
  clearTimeout(C9.timer);
  if(!C9.chat)return;
  try{C9.chat=await c9api('/api/local/chats/'+C9.chat.id);c9render();}catch(e){c9error(e.message)}
  if(C9.chat&&C9.chat.turns.some(t=>C9_ACTIVE.has(t.state)))C9.timer=setTimeout(c9poll,900);
  else window.fluxChats.refresh();
}
function c9error(msg){const e=c9('c9-error');if(!e)return;e.textContent=msg||'';e.hidden=!msg}
function c9header(){
  const chat=C9.chat,box=c9('c9-actions');if(!box)return;box.replaceChildren();
  c9('c9-title').textContent=chat?chat.title:'گفتگوی تازه با مدل‌ها';
  if(!chat)return;
  const names=C9.names||{};
  const sub=c9('c9-sub');sub.replaceChildren();sub.className='c9-meta';for(const [t,ltr] of [[names[chat.provider]||chat.provider,1],[chat.model||'مدل پیش‌فرض حساب',!!chat.model],[chat.cwd,1],[chat.access==='read'?'فقط خواندن':'خواندن و ویرایش',0]]){const sp=document.createElement('span');sp.textContent=t;if(ltr)sp.dir='ltr';sub.appendChild(sp)}
  for(const [label,fn] of [['تغییر نام',()=>window.fluxChats.rename(chat)],['بایگانی',()=>window.fluxChats.setArchived(chat,true)],['حذف',()=>window.fluxChats.remove(chat)]]){
    const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=fn;box.appendChild(b)}
}
function c9fillModels(){
  const prov=c9('c9-provider').value,list=(C9.status.models||{})[prov]||[],sel=c9('c9-model');
  sel.replaceChildren(new Option('پیش‌فرض حساب',''));
  for(const m of list)sel.appendChild(new Option(m,m));
  sel.disabled=['deepseek-web','gemini-web','notebooklm'].includes(prov);
  const web=['deepseek-web','gemini-web'].includes(prov);
  c9('c9-access').value=web?'read':c9('c9-access').value;c9('c9-access').disabled=web;
  c9('c9-setup-note').textContent=web?'حساب وب ابزار فایل ندارد و فقط متن می‌خواند و می‌نویسد.':'';
}
async function initChat(){
  // chats-nav.js is deferred; wait until its helpers exist
  await new Promise(done=>{const t=()=>window.fluxChats?done():setTimeout(t,25);t()});
  clearTimeout(C9.timer);C9.chat=null;C9.sending=false;
  const id=new URLSearchParams(location.search).get('chat')||'';
  try{C9.status=await c9api('/api/local/status')}catch(e){c9error('وضعیت حساب‌ها خوانده نشد: '+e.message);C9.status={providers:[],models:{}}}
  const NAMES={codex:'Codex',claude:'Claude',gapcode:'GapCode',gemini:'Gemini CLI',antigravity:'Antigravity','deepseek-web':'DeepSeek Web','gemini-web':'Gemini Web',notebooklm:'NotebookLM'};
  C9.names=NAMES;
  const send=c9('c9-send'),input=c9('c9-input');
  send.onclick=()=>c9submit();
  input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();c9submit()}};
  if(id){
    try{C9.chat=await c9api('/api/local/chats/'+id)}catch(e){c9error('این گفتگو پیدا نشد؛ شاید حذف یا بایگانی شده باشد.');c9('c9-input').disabled=true;c9('c9-send').disabled=true;return}
    c9header();c9render();if(C9.chat.turns.some(t=>C9_ACTIVE.has(t.state)))c9poll();input.focus();return;
  }
  // new conversation: choose among connected accounts only
  const order=['codex','claude','gapcode','gemini','antigravity','deepseek-web','gemini-web'];
  const ready=order.filter(p=>(C9.status.providers||[]).some(x=>x.id===p&&x.authenticated));
  const provider=c9('c9-provider');
  for(const p of order){const o=new Option(NAMES[p]+((ready.includes(p))?'':' · وصل نیست'),p);o.disabled=!ready.includes(p);provider.appendChild(o)}
  if(!ready.length){c9error('هیچ حساب متصلی آماده نیست؛ از «اتصال‌ها و تنظیمات» یک حساب وصل کن.');send.disabled=true}
  else provider.value=ready[0];
  provider.onchange=c9fillModels;c9fillModels();
  c9('c9-cwd').value=C9.status.default_cwd||'';
  try{const pid=localStorage.getItem('flux-active-project')||'';if(pid){const proj=await c9api('/projects/'+encodeURIComponent(pid));if(proj&&!proj.archived){C9.project=proj;c9('c9-cwd').value=proj.path;c9('c9-cwd').readOnly=true;c9('c9-setup-note').textContent='پروژهٔ «'+proj.name+'» فعال است؛ حافظه و پوشهٔ همین پروژه استفاده می‌شود.'}}}catch(_){}
  c9('c9-setup').hidden=false;c9header();c9render();
  try{const draft=sessionStorage.getItem('flux-chat-draft');if(draft){sessionStorage.removeItem('flux-chat-draft');input.value=draft}}catch(_){}
  input.focus();
}
window.addEventListener('flux:project',e=>{const p=e.detail.project;if(screen!==9||C9.chat||!p||!c9('c9-cwd'))return;C9.project=p;c9('c9-cwd').value=p.path;c9('c9-cwd').readOnly=true;c9('c9-setup-note').textContent='پروژهٔ «'+p.name+'» فعال است؛ حافظه و پوشهٔ همین پروژه استفاده می‌شود.'});
async function c9submit(){
  const input=c9('c9-input'),btn=c9('c9-send');
  if(btn.dataset.mode==='stop'){
    const running=C9.chat.turns.find(t=>C9_ACTIVE.has(t.state));
    try{await c9api('/api/local/turns/'+running.id+'/cancel',{method:'POST',body:'{}'});c9poll()}catch(e){c9error(e.message)}return;
  }
  const prompt=input.value.trim();if(!prompt||C9.sending)return;
  C9.sending=true;btn.disabled=true;c9error('');
  try{
    if(!C9.chat){
      const spec={title:prompt.replace(/\s+/g,' ').slice(0,60),provider:c9('c9-provider').value,model:c9('c9-model').value,cwd:c9('c9-cwd').value.trim(),access:c9('c9-access').value,notebook_id:'',project_id:C9.project?C9.project.id:''};
      C9.chat=await c9api('/api/local/chats',{method:'POST',body:JSON.stringify(spec)});
      history.replaceState({},'',location.pathname+'?screen=9&chat='+encodeURIComponent(C9.chat.id));
      c9('c9-setup').hidden=true;c9header();window.fluxChats.refresh();
    }
    await c9api('/api/local/chats/'+C9.chat.id+'/turns',{method:'POST',body:JSON.stringify({prompt,request_key:crypto.randomUUID(),use_memory:true})});
    input.value='';await c9poll();
  }catch(e){c9error(e.message)}
  finally{C9.sending=false;btn.disabled=false}
}


/* ---------- screen 10: real model probes (explicit click only; each probe is one tiny request) ---------- */
const MH={rows:[],results:{},running:false,status:null};
const MH_ACCOUNTS=['codex','claude','gapcode','gemini','gemini-api'];
const MH_NOTE={gapcode:'از کیف پول GapGPT کم می‌شود',gemini:'از سهمیهٔ حساب Google',codex:'از سهمیهٔ اشتراک',claude:'از سهمیهٔ اشتراک','gemini-api':'از کلید دستی Gemini API'};
const MH_NAMES={codex:'Codex',claude:'Claude',gapcode:'GapCode',gemini:'Gemini CLI','gemini-api':'Gemini API'};
const mhName=id=>MH_NAMES[id]||id;
async function initHealth(){
  const list=$('mh-list');if(!list)return;
  try{
    const [st,h]=await Promise.all([fetch('/api/local/status').then(r=>r.json()),fetch('/api/local/health').then(r=>r.json())]);
    MH.status=st;MH.results={};for(const r of h.results)MH.results[r.provider+'|'+r.model]=r;
    MH.rows=[];
    for(const id of MH_ACCOUNTS){
      const p=(st.providers||[]).find(x=>x.id===id);if(!p||!p.authenticated)continue;
      const models=(st.models||{})[id]||[];const cands=((st.candidates||{})[id])||[];
      for(const m of (models.length?models:[''])) MH.rows.push({provider:id,model:m,candidate:false});
      for(const m of cands) MH.rows.push({provider:id,model:m,candidate:true});
    }
  }catch(e){list.innerHTML='<div class="notice">فهرست مدل‌ها خوانده نشد.</div>';return}
  $('mh-all').onclick=()=>runHealth(MH.rows);
  drawHealth();
}
function mhRow(r){
  const res=MH.results[r.provider+'|'+r.model],busy=r._busy;
  const li=document.createElement('div');li.className='mh-row'+(busy?' busy':res?(res.ok?' ok':' bad'):'');li.dataset.key=r.provider+'|'+r.model;
  const name=document.createElement('div');name.className='mh-name';
  const b=document.createElement('b');b.textContent=r.model||'مدل پیش‌فرض';b.dir='ltr';
  const small=document.createElement('small');small.textContent=mhName(r.provider)+(r.candidate?' · نامزد (در کاتالوگ سایت نیست)':'');name.append(b,small);
  const state=document.createElement('div');state.className='mh-state';
  if(busy){state.innerHTML='<span class="spin" aria-hidden="true"></span><span>در حال آزمون…</span>'}
  else if(res){const t=document.createElement('span');t.className='mh-badge '+(res.ok?'ok':'bad');t.textContent=res.ok?'کار می‌کند':'خطا';state.append(t);
    const lat=document.createElement('span');lat.className='mh-lat';lat.textContent=(res.latency_ms/1000).toLocaleString('fa-IR',{maximumFractionDigits:1})+' ثانیه';state.append(lat)}
  else{state.innerHTML='<span class="mh-badge idle">آزمون نشده</span>'}
  const detail=document.createElement('div');detail.className='mh-detail';
  if(res&&!busy)detail.textContent=res.ok?('پاسخ: '+res.reply):res.error;detail.title=detail.textContent;
  const act=document.createElement('button');act.type='button';act.textContent=res?'آزمون دوباره':'آزمون';act.disabled=MH.running;act.onclick=()=>runHealth([r]);
  li.append(name,state,detail,act);return li;
}
function drawHealth(){
  const list=$('mh-list');if(!list)return;list.replaceChildren();
  if(!MH.rows.length){list.innerHTML='<p class="role-note">هیچ حساب متصلی برای آزمون نیست.</p>';return}
  let group='';
  for(const r of MH.rows){
    if(r.provider!==group){group=r.provider;const h=document.createElement('div');h.className='mh-group';const t=document.createElement('span');t.textContent=mhName(group);const n=document.createElement('small');n.textContent=MH_NOTE[group]||'';h.append(t,n);list.appendChild(h)}
    list.appendChild(mhRow(r));
  }
  const done=Object.values(MH.results),ok=done.filter(x=>x.ok).length;
  $('mh-sub').textContent=done.length?('آخرین نتیجه: '+ok.toLocaleString('fa-IR')+' مدل سالم از '+done.length.toLocaleString('fa-IR')+' مدل آزمون‌شده'):'هر مدل یک درخواست کوچک می‌گیرد تا ببینی واقعاً جواب می‌دهد یا نه.';
}
async function runHealth(rows){
  if(MH.running||!rows.length)return;
  const wallet=rows.filter(r=>r.provider==='gapcode').length;
  const yes=await window.fluxChats.ask({title:'اجرای آزمون مدل‌ها',message:'برای '+rows.length.toLocaleString('fa-IR')+' مدل، هرکدام یک پیام کوتاه («فقط بنویس OK») فرستاده می‌شود. '+(wallet?wallet.toLocaleString('fa-IR')+' مورد از کیف پول GapGPT کم می‌شود (چند سنت در مجموع)؛ بقیه از سهمیهٔ همان حساب. ':'از سهمیهٔ همان حساب‌ها کم می‌شود. ')+'ادامه بدهم؟',confirmLabel:'بله، آزمون کن'});
  if(!yes)return;
  MH.running=true;$('mh-all').disabled=true;const bar=$('mh-progress');bar.hidden=false;const fill=bar.firstElementChild;fill.style.width='0%';
  let n=0;
  for(const r of rows){
    r._busy=true;drawHealth();document.querySelector('.mh-row.busy')?.scrollIntoView({block:'nearest',behavior:'smooth'});
    try{
      const res=await fetch('/api/local/probe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:r.provider,model:r.model})});
      const data=await res.json();
      MH.results[r.provider+'|'+r.model]=res.ok?data:{provider:r.provider,model:r.model,ok:false,latency_ms:0,reply:'',error:(typeof data.detail==='string'&&data.detail)||'درخواست آزمون ناموفق بود.'};
    }catch(e){MH.results[r.provider+'|'+r.model]={provider:r.provider,model:r.model,ok:false,latency_ms:0,reply:'',error:'سرویس محلی پاسخ نداد.'}}
    r._busy=false;n++;fill.style.width=Math.round(n/rows.length*100)+'%';drawHealth();
  }
  MH.running=false;$('mh-all').disabled=false;setTimeout(()=>{bar.hidden=true},900);drawHealth();
}

/* ---------- screen 10: projects of this device ---------- */
const P10={archived:false,list:[],gone:[]};
async function initProjects(){
  await new Promise(done=>{const t=()=>window.fluxShell?done():setTimeout(t,25);t()});
  const call=window.fluxShell.call;
  const load=async()=>{try{const all=await call('/projects?archived=true');P10.list=all.filter(p=>!p.archived);P10.gone=all.filter(p=>p.archived)}catch(e){P10.list=[];P10.gone=[]}drawProjects()};
  $('project-new').onclick=async()=>{if(await window.fluxShell.addProject())load()};
  
  $('project-show-archived').onclick=e=>{P10.archived=!P10.archived;e.target.setAttribute('aria-pressed',String(P10.archived));drawProjects()};
  P10.load=load;window.addEventListener('flux:project',drawProjects);window.addEventListener('flux:project-icons',drawProjects);window.addEventListener('flux:projects',()=>load());await load();
  if(location.hash==='#projects')$('projects').scrollIntoView({block:'start'});
}
function drawProjects(){
  const box=$('project-list');if(!box)return;const call=window.fluxShell.call,active=window.fluxShell.active();
  const rows=P10.archived?P10.gone:P10.list;
  const m=document.querySelectorAll('#module .metric b')[2];if(m)m.textContent=P10.list.length.toLocaleString('fa-IR');
  box.replaceChildren();
  if(!rows.length){box.innerHTML=`<p class="role-note">${P10.archived?'پروژهٔ بایگانی‌شده‌ای نیست.':'هنوز پروژه‌ای ثبت نشده؛ با «پروژهٔ تازه» یک پوشه اضافه کن.'}</p>`;return}
  for(const p of rows){
    const row=document.createElement('article');row.className='project-row'+(active&&active.id===p.id?' active':'');
    row.innerHTML=`<div class="project-copy"><b></b><small dir="ltr"></small><p></p></div><div class="module-actions"></div>`;row.prepend(window.fluxShell.tile(p,38));row.addEventListener('fx:menu',e=>{if(!P10.archived)e.detail.items.push({label:'تغییر نام…',run:()=>window.fluxShell.renameProject(p)},{label:'باز کردن پوشه',run:()=>call('/filesystem/open-folder',{method:'POST',body:JSON.stringify({path:p.path})})},'-',{label:'افزودن پروژهٔ تازه…',run:()=>window.fluxShell.addProject()},{label:'حذف از Flux…',danger:true,run:()=>window.fluxShell.removeProject(p)})});
    row.querySelector('b').textContent=p.name;row.querySelector('small').textContent=p.path;row.querySelector('p').textContent=p.description||'';
    const actions=row.querySelector('.module-actions');
    const btn=(label,fn,cls='')=>{const b=document.createElement('button');b.type='button';b.textContent=label;if(cls)b.className=cls;b.onclick=fn;actions.appendChild(b)};
    if(P10.archived){btn('بازگردانی',async()=>{await call('/projects/'+p.id,{method:'PATCH',body:JSON.stringify({archived:false})});await window.fluxShell.refresh();P10.load()});btn('حذف',async()=>{await window.fluxShell.removeProject(p);P10.load()},'danger');}
    else{
      if(active&&active.id===p.id){const t=document.createElement('span');t.className='state ok';t.textContent='پروژهٔ فعال';actions.appendChild(t)}
      else btn('فعال کن',()=>window.fluxShell.setActive(p),'primary');
      btn('گفتگو',()=>{window.fluxShell.setActive(p,{silent:true});location.href='03-10-workspace.html?screen=9'});
      btn('بایگانی',()=>window.fluxShell.archive(p));btn('حذف',()=>window.fluxShell.removeProject(p),'danger');
    }
    box.appendChild(row);
  }
}

/* ---------- screen 6: usage per account (local turns + quota windows reported by each CLI) ---------- */
const U_NAMES={codex:'Codex',claude:'Claude',gapcode:'GapCode',gemini:'Gemini CLI',antigravity:'Antigravity','deepseek-web':'DeepSeek Web','gemini-web':'Gemini Web',notebooklm:'NotebookLM','gemini-api':'Gemini API'};
const faN=n=>Number(n||0).toLocaleString('fa-IR');
const compact=n=>{n=Number(n||0);return n>=1e6?(n/1e6).toLocaleString('fa-IR',{maximumFractionDigits:1})+'M':n>=1e3?(n/1e3).toLocaleString('fa-IR',{maximumFractionDigits:1})+'K':faN(n)};
function ago(iso){if(!iso)return 'هنوز استفاده نشده';const m=Math.round((Date.now()-new Date(iso))/60000);return m<1?'همین الان':m<60?faN(m)+' دقیقه پیش':m<1440?faN(Math.round(m/60))+' ساعت پیش':faN(Math.round(m/1440))+' روز پیش'}
function resetIn(ts){if(!ts)return '';const m=Math.round((ts*1000-Date.now())/60000);if(m<=0)return 'به‌زودی تازه می‌شود';return 'تازه‌شدن تا '+(m<60?faN(m)+' دقیقه':m<1440?faN(Math.round(m/60))+' ساعت':faN(Math.round(m/1440))+' روز')}
async function loadUsage(fresh){
  const box=$('usage-cards');if(!box)return;const btn=$('usage-refresh');if(btn&&fresh){btn.disabled=true;btn.textContent='در حال خواندن…'}
  const getJson=u=>fetch(u).then(r=>{if(!r.ok)throw Error();return r.json()});
  try{
    const [st,sum]=await Promise.all([getJson('/api/local/status'),getJson('/api/local/usage/summary')]);
    const conn=Object.fromEntries((st.providers||[]).map(p=>[p.id,p]));const u=Object.fromEntries((sum.accounts||[]).map(a=>[a.provider,a]));
    const ids=Object.keys(U_NAMES).filter(id=>id!=='gemini-api'||u[id]).filter(id=>conn[id]&&(conn[id].authenticated||u[id]));
    ids.sort((a,b)=>((u[b]||{}).turns||0)-((u[a]||{}).turns||0)||(!!(conn[b]||{}).authenticated)-(!!(conn[a]||{}).authenticated));
    const tot=(sum.accounts||[]).reduce((t,a)=>({turns:t.turns+a.turns,today:t.today+a.turns_today,inp:t.inp+a.input_tokens,out:t.out+a.output_tokens}),{turns:0,today:0,inp:0,out:0});
    const mb=document.querySelectorAll('#module .metric b');
    if(mb[0])mb[0].textContent=faN(tot.turns);if(mb[1])mb[1].textContent=faN(tot.today)+' پیام';if(mb[2])mb[2].textContent=compact(tot.inp)+' / '+compact(tot.out);if(mb[3])mb[3].textContent=faN((sum.accounts||[]).filter(a=>a.turns).length)+' از '+faN(ids.length);
    const draw=quota=>{
      const q=Object.fromEntries(((quota&&quota.providers)||[]).map(p=>[p.id,p]));
      box.innerHTML=ids.map(id=>{const a=u[id]||{turns:0,turns_today:0,input_tokens:0,output_tokens:0,cached_tokens:0,chats:0,failed:0,estimated_cost_usd:0,last_used:''},c=conn[id]||{},w=(q[id]||{}).windows||[];
        const bars=!quota?'<div class="skeleton" style="min-height:44px"></div>':w.length?w.map(x=>{const left=Math.max(0,Math.min(100,x.remaining_percent));return `<div class="quota-row"><div class="quota-top"><span>${esc(x.label)}</span><b>${faN(left)}٪ مانده</b></div><div class="quota-bar ${left<15?'low':left<40?'mid':''}"><i style="width:${100-left}%"></i></div><small>${resetIn(x.resets_at)}</small></div>`}).join(''):`<p class="quota-none">${esc((q[id]||{}).detail||'این حساب سهمیهٔ قابل‌خواندن گزارش نمی‌کند.')}</p>`;
        return `<article class="usage-card ${c.authenticated?'':'off'}"><header><span class="provider-mark ${c.authenticated?'ok':''}">${esc(U_NAMES[id].slice(0,2).toUpperCase())}</span><div><b>${esc(U_NAMES[id])}</b><small>${c.authenticated?'متصل':'وصل نیست'} · ${ago(a.last_used)}</small></div></header>
          <div class="usage-stats"><div><small>پیام‌ها</small><b>${faN(a.turns)}</b><em>امروز ${faN(a.turns_today)}</em></div><div><small>گفتگوها</small><b>${faN(a.chats)}</b><em>${a.failed?faN(a.failed)+' ناموفق':'بدون خطا'}</em></div><div><small>توکن ورودی</small><b>${compact(a.input_tokens)}</b><em>${a.cached_tokens?compact(a.cached_tokens)+' از حافظهٔ نهان':'—'}</em></div><div><small>توکن خروجی</small><b>${compact(a.output_tokens)}</b><em>${a.estimated_cost_usd?'برآورد سرویس '+a.estimated_cost_usd.toLocaleString('fa-IR',{maximumFractionDigits:2})+' دلار':'اشتراکی'}</em></div></div>
          <div class="usage-quota">${bars}</div></article>`}).join('')||'<p class="role-note">هیچ حساب متصلی پیدا نشد.</p>';
    };
    draw(null);
    try{draw(await getJson('/api/local/usage'+(fresh?'?refresh=true':'')))}catch(_){draw({providers:[]})}
  }catch(e){box.innerHTML='<div class="notice">مصرف حساب‌ها خوانده نشد؛ سرویس محلی در دسترس نیست.</div>'}
  finally{if(btn){btn.disabled=false;btn.textContent='به‌روزرسانی سهمیه‌ها'}}
}
function render(){
 const module=$('module');$('crumb-page').textContent=labels[screen];document.title='Flux — '+labels[screen];document.querySelectorAll('.nav a[href]').forEach(a=>a.removeAttribute('aria-current'));document.querySelector(`.nav a[href*="screen=${screen}"]`)?.setAttribute('aria-current','page');
 const heads={3:'صف کارها',4:'تصمیم‌گیری و پذیرش',5:'نقش‌ها و مرز اختیار',6:'دفتر بودجه و مصرف',7:'تأییدها و اختیار روشن',8:'دانش و حافظهٔ سازمان',9:'گفتگو با گره‌های کار',10:'اتصال‌ها و تنظیمات'};
 let body='';
 if(screen===3){const visible=tasks.filter(t=>(filter==='همه'||t[1]===filter)&&(filterStatus==='همه'||t[2]===filterStatus)&&(approval!=='فقط نیازمند اقدام'||['نیازمند اطلاعات','نیازمند اصلاح','منتظر مجوز','آمادهٔ پذیرش'].includes(t[2])));body=`<header class="module-head"><div><h1>کارها${sampleTag()}</h1><p>وضعیت، علت توقف و زمان هر کار را در یک صف ببین.</p></div><div class="module-actions"><button class="chip" id="board-view" aria-pressed="${view==='board'}">کانبان</button><button class="chip" id="table-view" aria-pressed="${view==='table'}">جدول</button><a class="primary button" href="/design-v2/02-request-contract.html">+ درخواست تازه</a></div></header><div class="metrics">${metric('کل کارها','۷','۲ نیازمند اقدام')}${metric('در حال اجرا','۲')}${metric('آمادهٔ پذیرش','۱')}${metric('توقف‌شده','۱')}</div><div class="chips"><label>مسئول <select id="head-filter" class="filter-select"><option>همه</option><option>Head فنی</option><option>Head عملیات</option></select></label><label>وضعیت <select id="status-filter" class="filter-select">${['همه',...statuses].map(x=>`<option>${x}</option>`).join('')}</select></label><button class="chip" id="action-filter" aria-pressed="${approval==='فقط نیازمند اقدام'}">نیازمند اقدام من</button></div><div style="height:12px"></div>`;
 if(view==='board'){body+=`<div class="kanban">${['ثبت‌شده','در حال اجرا','نیازمند اطلاعات','آمادهٔ پذیرش'].map(st=>`<section class="kanban-col" data-state="${st}"><h3><span>${st}</span><em>${visible.filter(t=>t[2]===st).length.toLocaleString('fa-IR')}</em></h3>${visible.filter(t=>t[2]===st).map(t=>`<article class="task-card" data-task="${esc(t[0])}" tabindex="0"><h3>${esc(t[0])}</h3><p>${esc(t[4])}</p><div class="task-meta"><span>${esc(t[1])}</span><span>${t[3]}</span></div></article>`).join('')||'<p class="kanban-empty">کاری در این ستون نیست</p>'}</section>`).join('')}</div>`;}else{body+=panel('فهرست کارها',`<div class="table-scroll"><table class="table"><thead><tr><th>کار</th><th>Head</th><th>وضعیت</th><th>علت / اقدام</th><th>هزینه</th></tr></thead><tbody>${visible.map(t=>`<tr><td><button class="ghost" data-task="${esc(t[0])}">${esc(t[0])}</button></td><td>${t[1]}</td><td>${t[2]}</td><td>${t[4]}</td><td>${t[3]}</td></tr>`).join('')}</tbody></table></div>`);}}
 if(screen===4){body=`<header class="module-head"><div><h1>خروجی‌گرفتن از گزارش سفارش‌ها${sampleTag()}</h1><p>نسخهٔ ۳ · کار Head فنی · مالک انسانی: شما</p></div><span class="state ok">آمادهٔ پذیرش</span></header><div class="timeline">${['ثبت','تأیید','تقسیم','اجرا','بازبینی','اصلاح / ارجاع','پذیرش'].map((x,i)=>`<div class="timeline-step ${i<5?'done':''}">${i+1}<br>${x}</div>`).join('')}</div><div class="metrics">${metric('هزینهٔ واقعی','۰٫۴۸ دلار','از سقف ۲٫۰۰')}${metric('تلاش','۲ از ۳')}${metric('معیارها','۵ از ۵','تأییدشده با شاهد')}${metric('ایراد باز','۰')}</div><div class="decision-grid"><div>${panel('نسخهٔ خروجی',`<div class="artifact">گزارش سفارش‌ها — نمونهٔ تحویل\n\nستون‌ها: شناسه، تاریخ، وضعیت، مبلغ، واحد پول، منبع داده\n\nموارد ناقص با برچسب «نیازمند بررسی» نمایش داده می‌شوند. هیچ مقدار گمشده‌ای حدس زده نشده است.\n\nقالب: CSV با UTF-8 و سرستون ثابت</div><p class="task-meta">SHA-256 · 91e7…a42c · نسخهٔ ۳</p>`)}${panel('معیارهای پذیرش',`<div class="evidence-row">✓ همهٔ ستون‌های لازم موجود <span>شاهد: خروجی CSV</span></div><div class="evidence-row">✓ ترتیب سفارش حفظ شده <span>شاهد: آزمون</span></div><div class="evidence-row">✓ موارد ناقص مشخص‌اند <span>بازبین مستقل</span></div>`)}</div><div>${panel('بازبینی مستقل',`<div class="notice">۵ از ۵ معیار تأیید شد · بدون ایراد مسدودکننده</div><p>بازبین: Qwen · بررسی به همین نسخه و هش خروجی متصل است.</p>`)}${panel('هزینه و منابع',`<div class="evidence-row">اجرای تولید <b>۰٫۳۹ دلار</b></div><div class="evidence-row">بازبینی <b>۰٫۰۹ دلار</b></div><div class="evidence-row">رزرو باقی‌مانده <b>۰٫۶۲ دلار</b></div>`)}<div class="module-actions"><button class="primary" data-action="accept">پذیرش این نسخه</button><button data-action="revise">درخواست اصلاح</button><button data-action="refer">ارجاع</button></div></div></div>`;}
 if(screen===5){
 const roleSpecs=[
  {id:'central',group:'هماهنگی',title:'Head مرکزی',description:'تقسیم مسیرها، ادغام و ارجاع · بدون نمره و یافته'},
  {id:'tech-head',group:'مسیر فنی و معماری',title:'Head فنی و معماری',description:'یکپارچگی مسیر فنی · محدود به بودجه و دامنهٔ فنی'},
  {id:'test-runner',group:'مسیر فنی و معماری',title:'عامل اجرای آزمون',description:'فقط pytest و npm test · بدون نصب بسته و تغییر فایل'},
  {id:'static',group:'مسیر فنی و معماری',title:'عامل تحلیل ایستا',description:'پیچیدگی، اندازه و بوی کد · اسکریپت فقط‌خواندنی'},
  {id:'architect',group:'مسیر فنی و معماری',title:'عامل معماری',description:'لایه‌بندی و جفت‌شدگی · هر یافته با فایل:خط'},
  {id:'sec-head',group:'مسیر امنیت و حریم',title:'Head امنیت و حریم',description:'تجمیع امنیت و حریم خصوصی · بدون اجرای حمله'},
  {id:'sec-auditor',group:'مسیر امنیت و حریم',title:'ممیز امنیت',description:'مرز اعتماد، احراز هویت، IPC و CSP'},
  {id:'privacy-auditor',group:'مسیر امنیت و حریم',title:'ممیز حریم خصوصی',description:'چرخهٔ عمر داده، رضایت، رمزگذاری و حذف'},
  {id:'sci-head',group:'مسیر علمی و انطباق',title:'Head علمی و انطباق',description:'تفکیک «ثابت‌شده» از «ادعا» · بدون تأیید ادعای بالینی'},
  {id:'sci-auditor',group:'مسیر علمی و انطباق',title:'ممیز اعتبار علمی',description:'مقایسهٔ ادعاها با شواهد داخل مخزن'},
  {id:'docs-auditor',group:'مسیر علمی و انطباق',title:'ممیز مستندات و ادعا',description:'تناقض میان مستندات، ADR و کد'},
  {id:'reviewer',group:'کنترل مستقل',title:'بازبین مستقل',description:'خانوادهٔ مدل جدا از نویسندهٔ یافته · تکرار شواهد · بدون اصلاح پنهانی'}
 ];
 const current=role=>roleAssign[role.id]||DEFAULT_ROLES[role.id];
 const providerOk=id=>!!catalog.connected[id];
 const accountSelect=role=>{const cur=current(role);return `<label class="pick"><span>حساب</span><select data-role-account="${role.id}" aria-label="حساب ${esc(role.title)}">${ACCOUNTS.map(([id,name])=>`<option value="${id}" ${id===cur.provider?'selected':''}>${esc(name)}${providerOk(id)?'':' · وصل نیست'}</option>`).join('')}</select></label>`};
 const modelPick=role=>{const cur=current(role),list=catalog.models[cur.provider]||[],known=list.includes(cur.model),custom=!!cur.model&&!known;
  if(NO_MODEL.has(cur.provider))return `<label class="pick"><span>مدل</span><select disabled><option>مدل خود سرویس</option></select></label>`;
  return `<label class="pick"><span>مدل</span><select id="m-${role.id}" data-role-select="${role.id}"><option value="">پیش‌فرض حساب</option>${list.map(m=>`<option value="${esc(m)}" ${m===cur.model?'selected':''}>${esc(m)}</option>`).join('')}<option value="__custom" ${custom?'selected':''}>${custom?esc(cur.model):'مدل دلخواه…'}</option></select></label><input class="pick-custom" data-role-custom="${role.id}" dir="ltr" maxlength="100" placeholder="شناسهٔ دقیق مدل" aria-label="شناسهٔ دقیق مدل برای ${esc(role.title)}" value="${custom?esc(cur.model):''}" hidden>`};
 const health=role=>{const ok=providerOk(current(role).provider);return `<span class="role-health ${ok?'ok':'off'}" title="${ok?'حساب این نقش متصل است':'حساب این نقش وصل نیست؛ از «اتصال‌ها و تنظیمات» وصلش کن یا حساب دیگری انتخاب کن'}">${ok?'آماده':'وصل نیست'}</span>`};
 let lastGroup='';const roleRows=roleSpecs.map(role=>{const head=role.group!==lastGroup?`<h3 class="role-group">${role.group}</h3>`:'';lastGroup=role.group;return head+`<article class="role-assignment" data-role-assignment="${role.id}"><div class="role-identity"><span class="role-avatar ${role.title.startsWith('Head')?'head':''}">${role.title.startsWith('Head')?'H':'A'}</span><span class="role-copy"><b>${role.title}</b><small>${role.description}</small></span></div><div class="role-picks">${accountSelect(role)}${modelPick(role)}${health(role)}</div></article>`}).join('');
 const connectedCount=ACCOUNTS.filter(([id])=>providerOk(id)).length,broken=roleSpecs.filter(r=>!providerOk(current(r).provider)).length,customCount=roleSpecs.filter(r=>{const c=current(r);return c.model&&!(catalog.models[c.provider]||[]).includes(c.model)}).length;
 body=`<header class="module-head"><div><h1>نقش‌ها و عامل‌ها</h1><p>برای هر نقش مشخص کن با کدام حساب متصل و کدام مدل کار کند.</p></div><div class="module-actions"><span id="roles-status" role="status" class="role-note"></span><button id="roles-reset">بازگشت به پیش‌فرض</button></div></header><div class="metrics">${metric('نقش‌ها',roleSpecs.length.toLocaleString('fa-IR'),'۴ Head · ۸ عامل')}${metric('حساب‌های متصل',rolesLoaded&&Object.keys(catalog.connected).length?connectedCount.toLocaleString('fa-IR'):'…','از '+ACCOUNTS.length.toLocaleString('fa-IR')+' حساب')}${metric('نقش بدون حساب آماده',broken.toLocaleString('fa-IR'),broken?'حسابشان را عوض کن':'همه آماده‌اند')}${metric('مدل دلخواه',customCount.toLocaleString('fa-IR'))}</div>${panel('چارت اختیار',`<div class="role-chart"><article class="role-assignment role-human"><div class="role-identity"><span class="role-avatar human">ش</span><span class="role-copy"><b>مدیر انسانی</b><small>هدف، اختیار، بودجه و پذیرش نهایی</small></span></div><span class="role-owner-badge">مالک · شما</span></article>${roleRows}</div><p class="role-chart-note">تنظیم‌ها روی همین دستگاه ذخیره می‌شوند و فقط از حساب‌های متصل استفاده می‌کنند؛ هیچ API پولی در کار نیست.</p>`)}`;
}if(screen===6){body=`<header class="module-head"><div><h1>مصرف حساب‌ها</h1><p>هر حساب متصل چقدر کار کرده و چقدر از سهمیه‌اش مانده است.</p></div><div class="module-actions"><button id="usage-refresh">به‌روزرسانی سهمیه‌ها</button></div></header><div class="metrics">${metric('پیام‌های اجراشده','…')}${metric('امروز','…')}${metric('توکن ورودی / خروجی','…')}${metric('حساب‌های فعال','…')}</div><div id="usage-cards" class="usage-grid"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div><p class="role-note usage-foot">عددها همان چیزی است که خود هر حساب گزارش می‌دهد؛ Flux چیزی را حدس نمی‌زند. حساب‌های اشتراکی هزینهٔ دلاری جدا ندارند و «برآورد سرویس» فقط برای اطلاع است.</p>`;}
 if(screen===7){const approvals=[['قرارداد کار Head فنی','خروجی‌گرفتن از گزارش سفارش‌ها','سقف ۲ دلار · ۳ تلاش · ۵ معیار پذیرش'],['پذیرش خروجی Head عملیات','دستورالعمل پذیرش مشتری — نسخهٔ ۳','بازبین مستقل ۵/۵ · هزینه ۰٫۴۸ دلار'],['اقدام حساس Head عملیات','ارسال گزارش ماهانه به مشتری','گیرنده: یک مشتری · ارسال بیرونی']];body=`<header class="module-head"><div><h1>تأییدها و اختیار${sampleTag()}</h1><p>مجوزها زمان‌دار، محدود به دامنه و در هر لحظه قابل لغو هستند.</p></div><button class="primary" data-action="delegate">+ اختیار تازه</button></header><div class="chips">${chip('در انتظار',approval==='در انتظار')}${chip('اختیار فعال',approval==='اختیار فعال')}${chip('همه',approval==='همه')}</div><div style="height:14px"></div><div class="metrics">${metric('تصمیم منتظر','۳')}${metric('اختیار فعال','۲','قابل لغو')}${metric('خارج از ساعت','۱','در صف · بدون حدس')}${metric('مسیر جایگزین','مبینا · COO')}</div>`;
 if(approval!=='اختیار فعال')body+=panel('صندوق تصمیم‌ها',approvals.map((a,i)=>`<article class="approval-row"><div><span class="state ${i===2?'bad':''}">${a[0]}</span><h3>${a[1]}</h3><p>${a[2]}</p></div><div class="module-actions"><button class="primary" data-action="approve">${i===1?'پذیرش نسخه':i===2?'مجاز می‌کنم':'تأیید و شروع'}</button><button data-action="revise">اصلاح</button><button data-action="reject">رد</button></div></article>`).join(''));
 body+=panel('اختیار روشن فعال',`<div class="approval-row"><div><b>عملیات تکراری عملیات تا ۲ دلار</b><p>محدود به پروژهٔ نمونه · تا امشب ۲۳:۰۰ · لغوپذیر</p></div><button data-action="revoke">لغو اختیار</button></div><div class="notice">کار منتظر تصمیم بیرونی می‌ماند. فوری بودن فقط مسیر اعلان را عوض می‌کند، نه مرز اختیار را.</div>`);}
 if(screen===8){const records=[['راهنمای لحن برند','شرکت','سارا · نسخهٔ ۴ · امروز','فعال'],['سیاست بازپرداخت','بخش عملیات','مبینا · نسخهٔ ۲ · ۲۸ سپتامبر','فعال'],['طرح اتصال گزارش سفارش','پروژه','سعید · نسخهٔ ۱ · امروز','پیشنهاد'],['تصمیم ارسال CSV','کار جاری','شما · نسخهٔ ۳ · امروز','در انتظار تأیید']];body=`<header class="module-head"><div><h1>دانش و حافظه${sampleTag()}</h1><p>چهار لایه با منبع، مالک و نسخه؛ پیشنهاد دانش پیش از تأیید فعال نمی‌شود.</p></div><button class="primary" data-action="knowledge-add">+ منبع دانش</button></header><div class="chips">${['شرکت','بخش','پروژه','کار جاری'].map(x=>chip(x,layer===x)).join('')}</div><div style="height:14px"></div><div class="metrics">${metric('منابع فعال','۴۸')}${metric('پیشنهاد در انتظار','۳')}${metric('نسخهٔ منقضی','۱','نیازمند بازبینی')}${metric('پوشش این پروژه','۸۴٪')}</div>${panel(`لایهٔ ${layer}`,records.filter(r=>layer==='پروژه'||layer==='شرکت'||r[1]===layer||layer==='کار جاری').map((r,i)=>`<article class="knowledge-row"><div><b>${r[0]}</b><p>${r[1]} · ${r[2]}</p><span class="source-tag">منبع: ${i===2?'تصمیم ثبت‌شده':'سند تأییدشده'}</span></div><div class="module-actions"><span class="state ${r[3]==='فعال'?'ok':''}">${r[3]}</span>${r[3]!=='فعال'?'<button class="primary" data-action="knowledge-approve">تأیید انسانی</button>':''}<button data-action="edit">جزئیات</button></div></article>`).join(''))}${panel('مرز حافظه',`<div class="notice">تغییر پروژه، داده را خودکار بین لایه‌ها جابه‌جا نمی‌کند. منبع و مجوز هر یادداشت پیش از بازیابی بررسی می‌شود.</div>`)}`;}
 if(screen===9){body=chatShell();}
 if(screen===10){body=`<header class="module-head"><div><h1>اتصال‌ها و تنظیمات</h1><p>حساب‌های متصل و پروژه‌های این دستگاه را ببین و مدیریت کن.</p></div><div class="module-actions"><button id="refresh-providers">به‌روزرسانی وضعیت</button></div></header><div class="metrics">${metric('حساب‌های متصل','…')}${metric('مدل‌های شناخته‌شده','…')}${metric('پروژه‌ها','…')}${metric('اجرا','روی همین دستگاه','بدون API پولی')}</div>${panel('حساب‌ها و ارائه‌دهندگان',`<div id="providers"><div class="skeleton" style="min-height:64px"></div><div class="skeleton" style="min-height:64px;margin-top:8px"></div></div><p class="role-note settings-foot">اتصال آماده، دسترسی به همهٔ مدل‌ها یا سهمیه را تضمین نمی‌کند. کلید یا فایل نشست را هرگز در گفتگو نفرست.</p>`)}<section class="panel" id="model-health"><div class="panel-head"><div><h2>آزمون واقعی مدل‌ها</h2><p class="role-note" id="mh-sub">هر مدل یک درخواست کوچک می‌گیرد تا ببینی واقعاً جواب می‌دهد یا نه.</p></div><div class="module-actions"><button id="mh-all" class="primary">آزمون همهٔ مدل‌های حساب‌های متصل</button></div></div><div class="panel-body"><div id="mh-progress" class="mh-progress" hidden><i></i></div><div id="mh-list" class="mh-list"><p class="role-note">فهرست مدل‌ها بارگذاری می‌شود…</p></div></div></section><section class="panel" id="projects"><div class="panel-head"><h2>پروژه‌ها</h2><div class="module-actions"><button id="project-show-archived" class="chip" aria-pressed="false">بایگانی‌شده‌ها</button><button class="primary" id="project-new">+ پروژهٔ تازه</button></div></div><div class="panel-body"><div id="project-list"><p class="role-note">پروژه‌ها بارگذاری می‌شوند…</p></div></div></section>`;}
 module.innerHTML=`<div>${body}</div>`;renderDesk();bind();if(screen===9)initChat();if(screen===10){initProjects();initHealth();}if(screen===6){loadUsage(false);$('usage-refresh').onclick=()=>loadUsage(true);}if(screen===3){$('head-filter').value=filter;$('status-filter').value=filterStatus;$('head-filter').onchange=e=>{filter=e.target.value;render();};$('status-filter').onchange=e=>{filterStatus=e.target.value;render();};$('action-filter').onclick=()=>{approval=approval==='فقط نیازمند اقدام'?'همه':'فقط نیازمند اقدام';render();};}
}
function renderDesk(){const info={3:['صف کارها','۵ کار در مسیر','Head فنی · ۲ · Head عملیات · ۳'],4:['نسخه و بازبینی','۵ از ۵ معیار','شاهدها به هش همین خروجی وصل‌اند'],5:['نقش‌ها','۱۲ نقش','هر نقش با یک حساب متصل و یک مدل مشخص کار می‌کند'],6:['مصرف حساب‌ها','فقط حساب‌های متصل','عددها از گزارش خود هر حساب خوانده می‌شود'],7:['تصمیم‌های منتظر','۳ تصمیم','اقدام بیرونی مجوز جدا می‌خواهد'],8:['منابع مرتبط','۴ لایه','پیشنهاد تازه تا تأیید فعال نیست'],9:['گفتگو','گفتگوی مستقیم با مدل‌ها','فقط حساب‌های متصل · بدون API پولی'],10:['حساب‌ها و پروژه‌ها','روی همین دستگاه','وضعیت اتصال و پروژه‌ها مستقیم از Flux خوانده می‌شود']}[screen];$('desk-title').textContent=info[0];$('desk-subtitle').textContent=info[1];$('desk').innerHTML=`<article class="summary-card"><h3>${info[0]}</h3><div class="live-title">${info[1]}</div><p>${info[2]}</p></article><article class="summary-card"><h3>مسیر تصمیم</h3><ul class="policy-list"><li>${icon('user')}<span>مالک انسانی، تأیید نهایی را انجام می‌دهد.</span></li><li>${icon('shield')}<span>معیار یا بودجه بدون اختیار تغییر نمی‌کند.</span></li><li>${icon('log')}<span>تغییر وضعیت باید علت و زمان داشته باشد.</span></li></ul></article>${SAMPLE.has(screen)?'<p class="preview-note">اعداد این بخش نمونه‌اند و هنوز از کارهای واقعی Flux خوانده نمی‌شوند.</p>':''}`;}
function bind(){document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{const f=b.dataset.filter;if(f==='Head فنی'||f==='Head عملیات')filter=filter===f?'همه':f;else if(f==='نیازمند اقدام')approval=approval==='فقط نیازمند اقدام'?'همه':'فقط نیازمند اقدام';else if(f==='در انتظار'||f==='اختیار فعال'||f==='همه')approval=f;else layer=f;render();});$('board-view')?.addEventListener('click',()=>{view='board';render();});$('table-view')?.addEventListener('click',()=>{view='table';render();});document.querySelectorAll('button[href]:not(.proj)').forEach(button=>button.onclick=()=>{location.href=new URL(button.getAttribute('href'),location.href).href;});document.querySelectorAll('[data-task]').forEach(x=>x.onclick=()=>{screen=4;history.pushState({},'',`03-10-workspace.html?screen=4`);render();});document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{const a=b.dataset.action;if(a==='accept'||a==='approve'||a==='knowledge-approve'){b.textContent=a==='knowledge-approve'?'فعال شد':'ثبت شد';b.disabled=true;b.classList.remove('primary');}else if(a==='reject'||a==='revise'||a==='refer'||a==='revoke'){b.textContent=a==='revoke'?'لغو شد':'ثبت شد';b.disabled=true;}else if(a==='add-role'||a==='budget'||a==='delegate'||a==='knowledge-add')b.insertAdjacentText('afterend',' · پیش‌نویس تازه');});document.querySelectorAll('[data-role-account]').forEach(sel=>sel.onchange=()=>{const id=sel.dataset.roleAccount,prov=sel.value,cur=roleAssign[id]||DEFAULT_ROLES[id]||{};setRole(id,{provider:prov,model:(catalog.models[prov]||[]).includes(cur.model)?cur.model:''});setTimeout(render,0);});document.querySelectorAll('[data-role-select]').forEach(sel=>sel.onchange=()=>{const id=sel.dataset.roleSelect,box=document.querySelector(`[data-role-custom="${id}"]`);if(sel.value==='__custom'){box.hidden=false;box.focus();return}box.hidden=true;box.value='';setRole(id,{model:sel.value});setTimeout(render,0);});document.querySelectorAll('[data-role-custom]').forEach(inp=>inp.onchange=()=>{const v=inp.value.trim();if(v&&!/^[A-Za-z0-9_.:\/\-\[\]]{1,100}$/.test(v)){inp.setCustomValidity('فقط حروف لاتین، عدد و . _ - : / مجاز است');inp.reportValidity();return}inp.setCustomValidity('');setRole(inp.dataset.roleCustom,{model:v});setTimeout(render,0);});$('roles-reset')&&($('roles-reset').onclick=()=>{roleAssign={};saveRoles();setTimeout(render,0);});$('attempt-value')&&document.querySelector('[type=range]')?.addEventListener('input',e=>{$('attempt-value').textContent=e.target.value+' تلاش';});$('chat-send')?.addEventListener('click',()=>{const val=$('chat-input').value.trim();if(!val)return;const b=document.createElement('div');b.className='bubble user';b.textContent=val;$('chat-log').append(b);$('chat-input').value='';});$('refresh-providers')?.addEventListener('click',()=>loadProviders(true));}
async function loadProviders(fresh){const box=$('providers');if(!box)return;const btn=$('refresh-providers');if(btn&&fresh){btn.disabled=true;btn.textContent='در حال بررسی…'}try{const response=await fetch('/api/local/status'+(fresh?'?refresh=true':''));if(!response.ok)throw Error();const d=await response.json();const shown=d.providers.filter(p=>['codex','claude','gapcode','gemini','antigravity','deepseek-web','gemini-web','notebooklm','gemini-api'].includes(p.id));const accounts=shown.filter(p=>p.id!=='gemini-api');const online=accounts.filter(p=>p.authenticated).length;const mb=document.querySelectorAll('#module .metric b');if(mb[0])mb[0].textContent=online.toLocaleString('fa-IR')+' از '+accounts.length.toLocaleString('fa-IR');if(mb[1])mb[1].textContent=Object.values(d.models||{}).reduce((n,l)=>n+l.length,0).toLocaleString('fa-IR');const NAMES={codex:'Codex',claude:'Claude',antigravity:'Antigravity','deepseek-web':'DeepSeek Web','gemini-web':'Gemini Web',notebooklm:'NotebookLM',gapcode:'GapCode',gemini:'Gemini CLI','gemini-api':'Gemini API (دستی)'};box.innerHTML=shown.sort((a,b)=>b.authenticated-a.authenticated).map(p=>`<div class="provider-row"><span class="provider-mark ${p.authenticated?'ok':''}">${esc((NAMES[p.id]||p.id).slice(0,2).toUpperCase())}</span><div class="provider-copy"><b>${esc(NAMES[p.id]||p.id)}</b><small>${esc(p.detail||p.version||p.billing||'')}</small></div><span class="state ${p.authenticated?'ok':p.auth_error==='region_restricted'?'bad':''}">${(p.auth_error==='region_restricted'||p.error_code==='region_restricted')?'محدودیت منطقه':p.authenticated?'متصل':'وصل نیست'}</span></div>`).join('');}catch{box.innerHTML='<div class="notice">سرویس محلی در دسترس نیست.</div>';}finally{if(btn){btn.disabled=false;btn.textContent='به‌روزرسانی وضعیت'}}}
$('new-request').onclick=()=>location.href='02-request-contract.html';document.querySelectorAll('[data-s]:not([href])').forEach(a=>a.onclick=()=>location.href='03-10-workspace.html?screen=9');window.onpopstate=()=>{screen=Number(new URLSearchParams(location.search).get('screen'))||3;render();};render();if(screen===10)loadProviders();
if(screen===5&&!rolesLoaded)loadRoleData();
