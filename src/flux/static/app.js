"use strict";
const paths = {
  plus:'M12 5v14M5 12h14', close:'m6 6 12 12M18 6 6 18', search:'m21 21-5-5M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15',
  panel:'M9 3v18M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2',
  memory:'M9 3a3 3 0 0 0-3 3 4 4 0 0 0-2 7 4 4 0 0 0 5 7 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3Zm6 0a3 3 0 0 1 3 3 4 4 0 0 1 2 7 4 4 0 0 1-5 7 3 3 0 0 1-3-3M6 10h2m8 0h2M7 16h2m6 0h2',
  chart:'M4 4v16h16M8 15v-3m5 3V8m5 7V5', settings:'m9 3-1 3-3 1v4l2 1v2l-2 1v4l3 1 1 2h6l1-2 3-1v-4l-2-1v-2l2-1V7l-3-1-1-3ZM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
  chevron:'m8 10 4 4 4-4', sun:'M12 3V1m0 22v-2M3 12H1m22 0h-2M5 5 3 3m18 18-2-2M5 19l-2 2M21 3l-2 2M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10',
  moon:'M20.8 13A9 9 0 0 1 11 3.2 9 9 0 1 0 9.8 9.8Z', sparkles:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4',
  plan:'M8 6h12M8 12h12M8 18h8M3 5l1 1 2-2M3 11l1 1 2-2M3 17l1 1 2-2', code:'m8 6-6 6 6 6m8-12 6 6-6 6m-3-14-2 16', file:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8m-8 4h6',
  arrow:'M19 12H5m6-6-6 6 6 6', up:'M12 19V5m-6 6 6-6 6 6', down:'M12 5v14m-6-6 6 6 6-6', lock:'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5Zm7 5v2',
  sliders:'M4 7h8m4 0h4M4 17h3m4 0h9M12 4v6M7 14v6', download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5', copy:'M8 8h12v13H8ZM4 16H2V2h13v2', check:'m5 12 4 4L19 6',
  stop:'M6 6h12v12H6Z', edit:'m15 4 5 5M4 16 16 4a2 2 0 0 1 4 4L8 20H4Z', archive:'M3 3h18v5H3Zm2 5v13h14V8m-10 4h6', trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
  clock:'M12 7v5l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18', shield:'m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Zm-5 10 3 3 7-7', eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
  folder:'M4 4h6l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  grid:'M3 3h7v7H3zm11 0h7v7h-7zm0 11h7v7h-7zM3 14h7v7H3z',
  play:'m5 3 14 9-14 9V3z',
  external:'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6m4-3h6v6m-11 5L21 3'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
const $ = id => document.getElementById(id);
const esc = text => String(text ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fa = value => new Intl.NumberFormat('fa-IR').format(value || 0);
const money = (value, digits=4) => '$'+Number(value ?? 0).toFixed(digits);
const activeStates = new Set(['NEW','VALIDATING','PLANNING','QUEUED','RUNNING','VERIFYING']);
const statusText = {NEW:'در صف شروع',VALIDATING:'بررسی درخواست',PLANNING:'برنامه‌ریزی',QUEUED:'در صف اجرا',RUNNING:'در حال آماده‌سازی',VERIFYING:'بازبینی مستقل',ACCEPT_CANDIDATE:'آمادهٔ بررسی شما',COMPLETED:'پذیرفته‌شده',REVISE:'نیازمند اصلاح',NEEDS_INPUT:'نیازمند توضیح شما',ESCALATED:'نیازمند تصمیم شما',PAUSED_BUDGET:'توقف به دلیل بودجه',FAILED:'اجرا متوقف شد',REJECTED:'پذیرفته نشد',CANCELLED:'متوقف‌شده',PENDING:'در انتظار'};
const roles = [
 {key:'head',name:'مدیر Agentها',short:'مدیر',model:'claude-fable-5',icon:'sparkles',color:'amber',description:'فهم درخواست و انتخاب مسیر کار'},
 {key:'opus',name:'برنامه‌ریز',short:'برنامه‌ریز',model:'claude-opus-5',icon:'plan',color:'violet',description:'تبدیل هدف به مراحل مشخص'},
 {key:'sol',name:'متخصص فنی',short:'فنی',model:'gpt-5.6-sol',icon:'code',color:'blue',description:'تحلیل راه‌حل و محدودیت‌های فنی'},
 {key:'luna',name:'مجری',short:'مجری',model:'gpt-5.6-luna',icon:'file',color:'',description:'آماده‌کردن متن و خروجی پیشنهادی'},
 {key:'verification',name:'بازبین مستقل',short:'بازبین',model:'gapgpt-qwen-3.6-thinking',icon:'shield',color:'violet',description:'تطبیق خروجی با معیارهای شما'}
];
const state = {
  chatId:null,chat:null,history:[],memories:[],projects:[],currentProjectId:null,
  activeProjectTab:'all',openProjectTabs:[],activeChatProjectId:null,
  view:'chat',epoch:0,timer:null,signature:'',sending:false,workflow:'low',
  budget:.5,useMemory:true,attachments:[],memoryEdit:null,projectEdit:null,
  taskEdit:null,prefs:{daily_budget:5,default_budget:.5,theme:'dark'},
  models:null,agentSettings:{model_overrides:{},custom_agents:[]},usage:null,renameId:null,deferredPrompt:null,
  selectedAgentRole:null,currentAgentRawOutput:'',currentAgentOutputMeta:null
};
let toastTimer, pathValidateTimer;

function hydrateIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,3400);}
function reportError(error){toast(error.message || 'ارتباط با برنامه برقرار نشد.');}
async function api(path, options={}){
  const res=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`خطای ارتباط با سرور (${res.status})`);
  }
  if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'اطلاعات واردشده معتبر نیست.');
  return data;
}
const post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});

function markdown(raw){
  const blocks=[];
  let text=String(raw??'').replace(/```[^\n]*\n([\s\S]*?)```/g,(_,code)=>{blocks.push(`<pre><code>${esc(code.trimEnd())}</code></pre>`);return `\nFLUXCODEBLOCK${blocks.length-1}\n`;});
  const inline=s=>esc(s).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  let html='',list=null;
  for(const line of text.split('\n')){
    const code=line.match(/^FLUXCODEBLOCK(\d+)$/),heading=line.match(/^(#{1,3})\s+(.+)/),li=line.match(/^\s*(?:[-*]|\d+[.)])\s+(.+)/);
    if(!li&&list){html+=`</${list}>`;list=null;}
    if(code){html+=blocks[Number(code[1])];continue;}
    if(heading){html+=`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`;continue;}
    if(li){const type=/^\s*\d/.test(line)?'ol':'ul';if(list!==type){if(list)html+=`</${list}>`;html+=`<${type}>`;list=type;}html+=`<li>${inline(li[1])}</li>`;}
    else if(line.trim()){html+=`<p>${inline(line)}</p>`;}
  }
  if(list)html+=`</${list}>`;
  return html;
}

function roleState(run,key){
  const calls=(run?.calls||[]).filter(c=>c.agent_role===key);
  if(run?.status==='NEEDS_INPUT'&&key!=='head')return 'blocked';
  if(calls.some(c=>c.status==='pending')&&activeStates.has(run.status))return 'running';
  if(calls.length&&calls.at(-1).status==='completed')return 'done';
  if(calls.length)return 'error';
  return 'idle';
}

function outputText(run){
 const outputs=(run.subtasks||[]).filter(s=>s.status==='completed');
 const chosen=outputs.filter(s=>s.assigned_agent==='luna');
 return (chosen.length?chosen:outputs).map(s=>s.output?.content || s.summary || JSON.stringify(s.output,null,2)).join('\n\n');
}

function getActiveRun(){return state.chat?.runs?.find(r=>activeStates.has(r.status));}
function updateSend(){const busy=getActiveRun();$('send-button').classList.toggle('stop',!!busy);$('send-button').innerHTML=icon(busy?'stop':'up');$('send-button').disabled=state.sending||(!busy&&!$('prompt').value.trim());$('send-button').setAttribute('aria-label',busy?'توقف اجرای جاری':'ارسال پیام');}
function autoSize(){$('prompt').style.height='auto';$('prompt').style.height=Math.min(190,Math.max(56,$('prompt').scrollHeight))+'px';updateSend();}
function applyTheme(theme){document.documentElement.dataset.theme=theme;$('theme-toggle').innerHTML=icon(theme==='dark'?'sun':'moon');localStorage.setItem('flux-theme',theme);}
async function toggleTheme(){state.prefs.theme=state.prefs.theme==='dark'?'light':'dark';applyTheme(state.prefs.theme);try{await api('/preferences',{method:'PUT',body:JSON.stringify(state.prefs)});}catch(e){reportError(e);}}
function mobileClose(){$('sidebar').classList.remove('mobile-open');$('sidebar-backdrop').hidden=true;}
function toggleSidebar(){if(innerWidth<=1100){const open=$('sidebar').classList.toggle('mobile-open');$('sidebar-backdrop').hidden=!open;}else{const closed=$('sidebar').classList.toggle('collapsed');document.body.classList.toggle('sidebar-closed',closed);}}

function showView(view){
  state.view=view;
  $('chat-view').hidden=view!=='chat';
  $('projects-view').hidden=view!=='projects';
  $('memory-view').hidden=view!=='memory';
  $('usage-view').hidden=view!=='usage';
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  mobileClose();
  if(view==='projects')loadProjects().catch(reportError);
  if(view==='memory')loadMemories().catch(reportError);
  if(view==='usage')loadUsage().catch(reportError);
}

function newChat(){
  if(state.sending){toast('درخواست در حال ثبت است؛ یک لحظه صبر کن.');return;}
  state.epoch++;clearTimeout(state.timer);state.chatId=null;state.chat=null;state.signature='';
  localStorage.removeItem('flux-chat');$('messages').replaceChildren();$('welcome').hidden=false;
  $('conversation-title').textContent='فضایی برای فکر کردن و ساختن';$('prompt').value='';state.attachments=[];
  renderAttachments();$('composer-error').hidden=true;showView('chat');renderHistory();renderAgents();autoSize();$('prompt').focus();
}

async function loadHistory(){state.history=await api('/conversations');renderHistory();}
function renderHistory(){
 const q=$('history-search').value.trim().toLowerCase();const rows=state.history.filter(c=>c.title.toLowerCase().includes(q));
 $('history-count').textContent=state.history.length?fa(state.history.length):'';
 $('history-list').innerHTML=rows.length?rows.map(c=>`<div class="history-row ${c.id===state.chatId?'active':''}"><button class="history-select" data-chat="${esc(c.id)}" title="${esc(c.title)}">${esc(c.title)}</button><span class="history-actions"><button class="icon-btn" data-rename="${esc(c.id)}" aria-label="تغییر نام گفت‌وگو" title="تغییر نام">${icon('edit')}</button><button class="icon-btn" data-archive="${esc(c.id)}" aria-label="بایگانی گفت‌وگو" title="بایگانی">${icon('archive')}</button></span></div>`).join(''):`<p class="sidebar-empty">${q?'گفت‌وگویی با این عنوان پیدا نشد.':'اولین گفت‌وگو از همین‌جا شروع می‌شود.'}</p>`;
}

async function selectChat(id){
 const epoch=++state.epoch;clearTimeout(state.timer);state.chatId=id;state.chat=null;state.signature='';showView('chat');$('welcome').hidden=true;$('messages').innerHTML='<div class="thinking-lines" aria-label="در حال دریافت گفت‌وگو"><span></span><span></span></div>';renderHistory();localStorage.setItem('flux-chat',id);
 try{await refreshChat(epoch,true);}catch(e){if(epoch===state.epoch){$('messages').textContent=e.message;reportError(e);}}
}

async function refreshChat(epoch=state.epoch,scroll=false){
 if(!state.chatId)return;
 const chat=await api('/conversations/'+encodeURIComponent(state.chatId));if(epoch!==state.epoch)return;
 state.chat=chat;$('conversation-title').textContent=chat.title;
 const signature=JSON.stringify(chat);
 if(signature!==state.signature){state.signature=signature;renderChat(scroll);renderAgents();}
 clearTimeout(state.timer);
 if(chat.runs.some(r=>activeStates.has(r.status))){state.timer=setTimeout(()=>refreshChat(epoch).catch(e=>{if(epoch===state.epoch){reportError(e);state.timer=setTimeout(()=>refreshChat(epoch).catch(reportError),3500);}}),650);}
 else{loadHistory().catch(reportError);loadUsage().catch(reportError);}
 updateSend();
}

function renderChat(forceScroll=false){
 const container=$('chat-scroll');const nearBottom=container.scrollHeight-container.scrollTop-container.clientHeight<140;const oldTop=container.scrollTop;
 const opened=new Set([...$('messages').querySelectorAll('details[open]')].map(d=>d.dataset.key));
 $('welcome').hidden=!!state.chat?.runs.length;
 $('messages').innerHTML=(state.chat?.runs||[]).map(run=>{
  const busy=activeStates.has(run.status),failed=['FAILED','REJECTED','PAUSED_BUDGET','REVISE','ESCALATED'].includes(run.status);
  const progress=teamRoles(run).filter(r=>roleState(run,r.key)!=='idle'||(r.key==='verification'&&busy));
  const text=outputText(run);
  const secondary=(run.subtasks||[]).filter(s=>s.assigned_agent!=='luna'&&s.status==='completed');
  const contexts=run.task.context||[];
  return `<article class="message-turn" data-run="${esc(run.run_id)}"><div class="user-message" dir="auto">${esc(run.objective)}</div><div class="user-meta"><span>سقف این پیام <bdi>${money(run.budget_cap_usd,2)}</bdi></span>${contexts.length?`<span>${fa(contexts.length)} منبع زمینه</span>`:''}</div><div class="assistant-head"><img src="/static/flux.svg" alt=""><strong>Flux</strong>${run.demo?'<span class="demo-label">پاسخ آزمایشی</span>':''}<span class="run-status ${busy?'busy':failed?'error':''}">${busy?'<i class="pulse-dot"></i>':''}${esc(statusText[run.status]||run.status)}</span></div><div class="agent-progress">${progress.map(r=>`<span class="step-pill ${roleState(run,r.key)}">${icon(roleState(run,r.key)==='done'?'check':r.icon)}${esc(r.short)}</span>`).join('')}</div>${secondary.map(s=>`<details class="output-details" data-key="${esc(run.run_id+s.subtask_id)}" ${opened.has(run.run_id+s.subtask_id)?'open':''}><summary>${esc(roles.find(r=>r.key===s.assigned_agent)?.name||s.assigned_agent)} · ${esc(s.summary||'خروجی')}</summary><div class="markdown">${markdown(s.output?.content||JSON.stringify(s.output,null,2))}</div></details>`).join('')}${text?`<div class="markdown" dir="auto">${markdown(text)}</div>`:busy?'<div class="thinking-lines"><span></span><span></span><span></span></div>':''}${!busy?`<div class="result-notice ${failed?'error':''}">${esc(run.reason||statusText[run.status])}</div>`:''}${run.decision?.blocking_issues?.length?`<details class="output-details" data-key="${esc(run.run_id)}issues"><summary>ایرادهای نیازمند توجه · ${fa(run.decision.blocking_issues.length)}</summary>${run.decision.blocking_issues.map(i=>`<div class="check-item"><strong>${esc(i.criterion)}</strong><span>${esc(i.evidence)}</span><span>${esc(i.required_change)}</span></div>`).join('')}</details>`:''}${contexts.length?`<details class="output-details" data-key="${esc(run.run_id)}context"><summary>${fa(contexts.length)} منبع استفاده‌شده در این درخواست</summary>${contexts.map(c=>`<div class="check-item">${esc(c.title||c.ref)}<span>${esc(String(c.content||'').slice(0,220))}</span></div>`).join('')}</details>`:''}${!busy&&text?`<div class="result-actions"><button class="icon-btn" data-copy="${esc(run.run_id)}" title="کپی پاسخ" aria-label="کپی پاسخ">${icon('copy')}</button><button class="icon-btn" data-export="${esc(run.run_id)}" title="دریافت پاسخ" aria-label="دریافت پاسخ">${icon('download')}</button><button class="action-label" data-remember="${esc(run.run_id)}">${icon('memory')}ذخیره در حافظه</button><button class="action-label" data-inspect="${esc(run.run_id)}">${icon('chart')}<bdi>${money(run.spent_cost_usd)}</bdi> · جزئیات${run.unknown_cost_usd>0?' + هزینهٔ نامعلوم':''}</button>${run.acceptance?`<span class="accepted-label">${icon('check')}تأییدشده توسط شما</span>`:run.status==='ACCEPT_CANDIDATE'?`<button class="action-label" data-accept="${esc(run.run_id)}">${icon('check')}پذیرش این نسخه</button>`:''}</div>`:''}</article>`;
 }).join('');
 if(forceScroll||nearBottom)requestAnimationFrame(()=>container.scrollTo({top:container.scrollHeight,behavior:'instant'}));else container.scrollTop=oldTop;
 updateSend();
}

function renderAgents(inspected){
 const run=inspected||state.chat?.runs?.at(-1);
 $('agent-count').textContent=fa(teamRoles().length)+' Agent';
 $('agent-roster').innerHTML=teamRoles(run).map(r=>{
   const st=roleState(run,r.key);
   const isActive=state.selectedAgentRole===r.key?' active':'';
   return `<div class="agent-card${isActive}" data-agent-role="${r.key}" role="button" tabindex="0" title="مشاهدهٔ خروجی ${esc(r.name)}"><span class="agent-symbol ${r.color}">${icon(r.icon)}</span><div class="agent-info"><div><strong>${esc(r.name)}</strong><small>${({idle:'در انتظار',done:'پاسخ ثبت شد',running:'در حال اجرا',error:'متوقف',blocked:'منتظر توضیح شما'})[st]}</small></div><p>${esc(r.description)}</p><span class="agent-model">${esc(modelFor(r,run))}</span></div></div>`;
 }).join('');
 if(!run){
   $('run-inspector').innerHTML='<p class="muted">با شروع یک کار، مراحل و مصرف آن را اینجا می‌بینی.</p>';
   return;
 }
 $('run-inspector').innerHTML=`<div class="inspector-row"><span>فراخوانی‌ها</span><b>${fa(run.total_calls)} / ۲۰</b></div><div class="inspector-row"><span>${run.demo?'هزینهٔ شبیه‌سازی‌شده':'هزینهٔ ثبت‌شده'}</span><b dir="ltr">${money(run.spent_cost_usd)}</b></div><div class="inspector-row"><span>رزرو فعال</span><b dir="ltr">${money(run.reserved_cost_usd)}</b></div><div class="inspector-row"><span>هزینهٔ نامعلوم</span><b dir="ltr">${money(run.unknown_cost_usd)}</b></div><div class="inspector-row"><span>ماندهٔ بودجه</span><b dir="ltr">${money(run.usage.remaining_budget_usd)}</b></div><div class="drawer-separator"></div><h3>بررسی‌های ثبت‌شده</h3>${run.checks.length?run.checks.map(c=>`<div class="check-item ${esc(c.status)}" data-check-name="${esc(c.name)}">${esc(c.name)}<span>${esc(c.evidence)}</span></div>`).join(''):'<p class="muted">هنوز بررسی ثبت نشده است.</p>'}<details class="output-details"><summary>رویدادهای اجرا</summary>${run.events.map(e=>`<div class="check-item" data-event-state="${esc(e.to_state)}"><strong>${esc(statusText[e.to_state]||e.to_state)}</strong><span>${esc(e.reason)}</span></div>`).join('')}</details>`;

 if(state.selectedAgentRole){
   showAgentOutput(state.selectedAgentRole, run, false);
 }
}

function showAgentOutput(roleKey, currentRun, scrollIntoView=true){
  const run=currentRun||state.chat?.runs?.at(-1);
  state.selectedAgentRole=roleKey;
  const roleObj=teamRoles(run).find(r=>r.key===roleKey)||{name:roleKey,model:'',description:''};
  
  document.querySelectorAll('#agent-roster .agent-card').forEach(card=>{
    card.classList.toggle('active', card.dataset.agentRole===roleKey);
  });
  
  const viewer=$('agent-output-viewer');
  if(!viewer) return;
  viewer.hidden=false;
  
  let eyebrow='نقش ' + roleObj.name;
  let title='گزارش عامل';
  let metaHtml=`<span>مدل: <code>${esc(modelFor(roleObj,run))}</code></span>`;
  let content='';
  
  if(!run){
    content='هنوز اجرایی برای این گفت‌وگو ثبت نشده است.';
  } else if(roleKey==='head'){
    eyebrow='مدیر Agentها (ارکستراتور)';
    title='مأموریت و تفکیک وظایف';
    const subtaskList=(run.subtasks||[]).map((s, idx)=>{
      const ag=roles.find(r=>r.key===s.assigned_agent)?.name||s.assigned_agent;
      return `${idx+1}. **${s.subtask_id}** [عامل: ${ag}]:\n   - هدف: ${s.objective}\n   - وضعیت: ${s.status==='completed'?'✅ تکمیل‌شده':s.status==='RUNNING'?'⏳ در حال اجرا':'در صف'}`;
    }).join('\n\n');
    
    content=`### مأموریت تعریف‌شده\n**هدف:** ${run.objective||'تعریف‌نشده'}\n\n`+
      `### معیارهای پذیرش\n${(run.task?.acceptance_criteria||[]).map(c=>'- '+c).join('\n')||'تعیین‌نشده'}\n\n`+
      `### محدودهٔ کار\n${(run.task?.scope||[]).map(s=>'- '+s).join('\n')||'تعیین‌نشده'}\n\n`+
      `### برنامه و تفکیک وظایف تیم\n${subtaskList||'بدون زیرتسک'}`;
      
  } else if(roleKey==='opus'||roleKey==='sol'||roleKey==='luna'||roleKey.startsWith('custom_')){
    const subtask=(run.subtasks||[]).find(s=>roleKey.startsWith('custom_')?s.subtask_id===roleKey:s.assigned_agent===roleKey&&!s.subtask_id.startsWith('custom_'));
    const call=(run.calls||[]).filter(c=>c.agent_role===roleKey).at(-1);
    
    if(call&&call.latency_ms){
      metaHtml+=`<span>مدت اجرا: <b>${(call.latency_ms/1000).toFixed(1)} ثانیه</b></span>`;
    }
    
    if(subtask){
      title=`${roleObj.name} · ${subtask.subtask_id}`;
      if(subtask.status==='completed'){
        metaHtml+=`<span class="badge-done">✅ تکمیل‌شده</span>`;
        content=subtask.output?.content||subtask.summary||(typeof subtask.output==='object'?JSON.stringify(subtask.output,null,2):'')||'خروجی متنی ثبت نشده است.';
      } else if(subtask.status==='RUNNING'){
        metaHtml+=`<span class="badge-running">⏳ در حال پردازش...</span>`;
        content=`عامل **${roleObj.name}** هم‌اکنون در حال پردازش و تولید خروجی برای هدف زیر است:\n\n> ${subtask.objective}`;
      } else if(subtask.status==='QUEUED'){
        metaHtml+=`<span>در صف اجرا</span>`;
        content=`این نقش در صف قرار دارد و پس از پایان مراحل وابسته اجرا خواهد شد.\n\n**هدف تعریف‌شده:**\n> ${subtask.objective}`;
      } else {
        metaHtml+=`<span class="badge-error">${subtask.status}</span>`;
        content=subtask.summary||'اطلاعاتی در دسترس نیست.';
      }
    } else {
      content=`در این اجرا، زیرتسکی به نقش **${roleObj.name}** تخصیص داده نشده است.`;
    }
    
  } else if(roleKey==='verification'){
    eyebrow='بازبین مستقل (داوری نهایی)';
    title='گزارش تطبیق و کیفیت';
    const dec=run.decision;
    if(dec){
      metaHtml+=`<span>نتیجه: <b>${statusText[dec.decision]||dec.decision}</b></span>`;
      metaHtml+=`<span>ضریب اطمینان: <b>${dec.confidence||'۱۰۰%'}</b></span>`;
      
      let sec=`### تصمیم بازبین مستقل: ${statusText[dec.decision]||dec.decision}\n\n`;
      sec+=`**ضریب اطمینان:** ${dec.confidence||'۱۰۰%'}\n\n`;
      
      if(dec.passed_criteria?.length){
        sec+=`#### معیارهای تأییدشده:\n${dec.passed_criteria.map(c=>'- ✅ '+c).join('\n')}\n\n`;
      }
      if(dec.failed_criteria?.length){
        sec+=`#### معیارهای ردشده:\n${dec.failed_criteria.map(c=>'- ❌ '+c).join('\n')}\n\n`;
      }
      if(dec.blocking_issues?.length){
        sec+=`#### اشکالات بحرانی / نیازمند توجه:\n`;
        dec.blocking_issues.forEach(b=>{
          sec+=`- **معیار:** ${b.criterion}\n  - **شواهد:** ${b.evidence}\n  - **اصلاح لازم:** ${b.required_change}\n`;
        });
        sec+='\n';
      }
      if(run.checks?.length){
        sec+=`#### چک‌لیست ارزیابی:\n`;
        run.checks.forEach(c=>{
          sec+=`- **${c.name}** (${c.status}): ${c.evidence||'بدون توضیح'}\n`;
        });
      }
      content=sec;
    } else {
      content=`بازبین مستقل پس از تکمیل پاسخ مجری وارد کار می‌شود و تطابق خروجی با معیارها را ارزیابی می‌کند.`;
    }
  }
  
  $('agent-output-role-name').textContent=eyebrow;
  $('agent-output-title').textContent=title;
  $('agent-output-meta').innerHTML=metaHtml;
  $('agent-output-content').innerHTML=markdown(content);
  state.currentAgentRawOutput=content;
  state.currentAgentOutputMeta={eyebrow,title,metaHtml};
  
  if(scrollIntoView){
    viewer.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
}

function showCheckDetail(checkName, currentRun){
  const run=currentRun||state.chat?.runs?.at(-1);
  if(!run) return;
  const ch=(run.checks||[]).find(c=>c.name===checkName);
  if(!ch) return;
  
  state.selectedAgentRole=null;
  document.querySelectorAll('#agent-roster .agent-card').forEach(c=>c.classList.remove('active'));
  
  const viewer=$('agent-output-viewer');
  if(!viewer) return;
  viewer.hidden=false;
  
  const eyebrow='بررسی ثبت‌شده در اجرا';
  const title=ch.name;
  const metaHtml=`<span class="${ch.status==='passed'?'badge-done':'badge-error'}">${ch.status==='passed'?'✅ تأیید':'❌ رد'}</span>`;
  const content=`### بررسی: ${ch.name}\n\n**وضعیت:** ${ch.status}\n\n**شواهد و توضیحات:**\n${ch.evidence||'توضیحاتی ثبت نشده است.'}`;
  
  $('agent-output-role-name').textContent=eyebrow;
  $('agent-output-title').textContent=title;
  $('agent-output-meta').innerHTML=metaHtml;
  $('agent-output-content').innerHTML=markdown(content);
  state.currentAgentRawOutput=content;
  state.currentAgentOutputMeta={eyebrow,title,metaHtml};
  viewer.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function openAgentOutputDialog(){
  if(!state.currentAgentRawOutput) return;
  $('dialog-agent-role').textContent=state.currentAgentOutputMeta?.eyebrow||'نقش عامل';
  $('dialog-agent-title').textContent=state.currentAgentOutputMeta?.title||'خروجی عامل';
  $('dialog-agent-meta').innerHTML=state.currentAgentOutputMeta?.metaHtml||'';
  $('dialog-agent-content').innerHTML=markdown(state.currentAgentRawOutput);
  $('agent-output-dialog').showModal();
}

function toggleAgents(open){$('agent-drawer').hidden=open===undefined?!$('agent-drawer').hidden:!open;$('agents-toggle').classList.toggle('active',!$('agent-drawer').hidden);}
const workflowLabels={low:'Low · کم‌هزینه',medium:'Medium · متعادل',high:'High · کامل',auto:'خودکار (قدیمی)',team:'تیم پنج Agent (قدیمی)'};
function teamRoles(run){
 const config=run?.task?.agent_settings||state.agentSettings;
 return [...roles,...(config.custom_agents||[]).filter(a=>a.enabled).map(a=>({key:a.id,name:a.name,short:a.name,model:a.model_id,description:a.instructions,icon:'sparkles',color:'blue'}))];
}
function modelFor(role,run){
 const config=run?.task?.agent_settings||state.agentSettings;
 return run?.calls?.filter(c=>c.agent_role===role.key).at(-1)?.model_id || config.custom_agents?.find(a=>a.id===role.key)?.model_id || config.model_overrides?.[role.key] || state.models?.profiles?.[run?.task?.workflow||state.workflow]?.[role.key] || (state.workflow==='low'?'gpt-5.6-luna':role.model);
}
function setWorkflow(value){
 state.workflow=value;
 const index=Math.max(0,['low','medium','high'].indexOf(value));
 $('effort-range').value=index;$('effort-range').setAttribute('aria-valuetext',value);
 $('effort-range').dataset.level=value;
 $('effort-label').textContent=value[0].toUpperCase()+value.slice(1);
 $('workflow-toggle').innerHTML=esc($('effort-label').textContent)+icon('chevron');
 const models=[...new Set(teamRoles().map(r=>modelFor(r)))];
 $('effort-model').textContent=models.length===1?models[0]:`${models[0]} + ${fa(models.length-1)}`;
 $('effort-model').title=models.join(' · ');
 renderAgents();
}
function showEffort(open){$('effort-popover').hidden=!open;$('workflow-toggle').setAttribute('aria-expanded',String(open));}
function modelOptions(selected,automatic=false){return (automatic?'<option value="">طبق سطح مصرف</option>':'')+Object.keys(state.models?.models||{}).map(m=>`<option value="${esc(m)}" ${selected===m?'selected':''}>${esc(m)}</option>`).join('');}
function addAgentEditor(agent){
 const wrapper=document.createElement('div');wrapper.className='custom-agent-editor';wrapper.dataset.agentId=agent.id;
 wrapper.innerHTML=`<div class="custom-editor-top"><label><input type="checkbox" data-field="enabled" ${agent.enabled?'checked':''}> فعال</label><button type="button" class="icon-btn" data-remove-agent aria-label="حذف Agent">${icon('trash')}</button></div><label>نام Agent<input data-field="name" aria-label="نام Agent" value="${esc(agent.name)}" maxlength="60" required></label><label>نوع نقش<select data-field="role" aria-label="نوع نقش">${[['luna','مجری'],['opus','برنامه‌ریز'],['sol','متخصص فنی']].map(([v,l])=>`<option value="${v}" ${agent.role===v?'selected':''}>${l}</option>`).join('')}</select></label><label>مدل<select data-field="model_id" aria-label="مدل Agent">${modelOptions(agent.model_id)}</select></label><label>دستور کار<textarea data-field="instructions" aria-label="دستور کار Agent" required minlength="5" maxlength="3000" rows="3">${esc(agent.instructions)}</textarea></label>`;
 $('custom-agent-editors').append(wrapper);
 $('add-custom-agent').disabled=$('custom-agent-editors').children.length>=5;
}
async function openAgents(){
 [state.models,state.agentSettings]=await Promise.all([api('/models/status'),api('/settings/agents')]);
 $('base-agent-editors').innerHTML=roles.map(r=>`<label class="base-agent-editor"><span>${esc(r.name)}</span><select data-base-role="${r.key}" aria-label="مدل ${esc(r.name)}">${modelOptions(state.agentSettings.model_overrides[r.key],true)}</select></label>`).join('');
 $('custom-agent-editors').innerHTML='';state.agentSettings.custom_agents.forEach(addAgentEditor);
 $('add-custom-agent').disabled=state.agentSettings.custom_agents.length>=5;
 $('agents-error').hidden=true;showEffort(false);$('agents-dialog').showModal();
}
async function saveAgents(e){
 e.preventDefault();const button=$('save-agents');button.disabled=true;
 try{
 const model_overrides=Object.fromEntries([...document.querySelectorAll('[data-base-role]')].filter(e=>e.value).map(e=>[e.dataset.baseRole,e.value]));
 const custom_agents=[...$('custom-agent-editors').children].map(row=>({id:row.dataset.agentId,...Object.fromEntries([...row.querySelectorAll('[data-field]')].map(e=>[e.dataset.field,e.type==='checkbox'?e.checked:e.value.trim()]))}));
 state.agentSettings=await api('/settings/agents',{method:'PUT',body:JSON.stringify({model_overrides,custom_agents})});
 $('agents-dialog').close();setWorkflow(state.workflow);toast('تنظیمات ذخیره شد؛ از اجرای بعدی اعمال می‌شود.');
 }catch(error){$('agents-error').textContent=error.message;$('agents-error').hidden=false;}finally{button.disabled=false;}
}

const templates={plan:['برای ساخت یک دموی شخصی Flux، یک برنامهٔ اجرایی مرحله‌به‌مرحله بنویس.','مراحل به ترتیب وابستگی باشند.\nبرای هر مرحله، خروجی و معیار پایان مشخص باشد.','low'],technical:['معماری یک نرم‌افزار شخصی با پنج Agent، حافظهٔ محلی و کنترل هزینه را بررسی کن و یک پیشنهاد فنی بنویس.','نقش پنج Agent و ارتباطشان توضیح داده شود.\nمحدودیت‌ها و ریسک‌های فنی مشخص باشند.','medium'],document:['از ایدهٔ نرم‌افزار شخصی Flux یک معرفی کوتاه و روشن بنویس.','متن فارسی، روشن و دارای بخش‌های مشخص باشد.\nامکانات فعلی و برنامه‌های آینده تفکیک شوند.','low']};
function useTemplate(type){const [prompt,criteria,workflow]=templates[type];$('prompt').value=prompt;$('criteria-input').value=criteria;setWorkflow(workflow);autoSize();$('prompt').focus();}
function renderAttachments(){$('attachment-list').innerHTML=state.attachments.map((a,i)=>`<span class="attachment-chip">${icon('file')}<span>${esc(a.title)}</span><button type="button" class="icon-btn" data-remove-file="${i}" aria-label="حذف پیوست">${icon('close')}</button></span>`).join('');}

async function readFiles(files){
 for(const file of files){if(state.attachments.length>=3){toast('حداکثر سه فایل متنی در هر پیام.');break;}if(file.size>16000){toast('هر فایل باید حداکثر ۱۶ کیلوبایت باشد.');continue;}if(!/\.(txt|md|json|csv|py|js|ts|html|css)$/i.test(file.name)){toast('این نسخه فقط فایل متنی می‌پذیرد.');continue;}const content=await file.text();if(content.includes('\u0000')){toast('فایل باید متنی باشد.');continue;}state.attachments.push({ref:'attachment:'+file.name,title:file.name,content:content.slice(0,10000)});}
 renderAttachments();$('file-input').value='';
}

async function submit(event){
 event.preventDefault();if(state.sending)return;
 const running=getActiveRun();if(running){try{await post(`/runs/${running.run_id}/cancel`,{});await refreshChat();}catch(e){reportError(e);}return;}
 const objective=$('prompt').value.trim();if(objective.length<5){$('composer-error').textContent='هدفت را در حداقل پنج نویسه توضیح بده.';$('composer-error').hidden=false;return;}
 const criteria=$('criteria-input').value.split('\n').map(s=>s.trim()).filter(Boolean);
 if(!criteria.length){$('options-dialog').showModal();$('criteria-input').focus();return;}
 state.sending=true;updateSend();$('composer-error').hidden=true;
 try{
  if(!state.chatId){const chat=await post('/conversations',{title:objective.slice(0,80)});state.chatId=chat.id;state.chat=chat;localStorage.setItem('flux-chat',chat.id);}
  const id='task_'+crypto.randomUUID();
  const projId=state.activeChatProjectId||'personal';
  const task={task_id:id,root_id:id,project_id:projId,human_owner:'Me',objective,scope:['پاسخ به درخواست در محدودهٔ دموی شخصی'],out_of_scope:['اقدامات خارج از محدودهٔ تعریف‌شده'],acceptance_criteria:criteria,dependencies:[],allowed_tools:[],allowed_paths:[],artifact_refs:[],budget_cap_usd:state.budget,max_attempts:3,priority:'P2',data_class:'internal',workflow:state.workflow,context:state.attachments};
  await post('/runs?background=true',{task,idempotency_key:'ui_'+id,conversation_id:state.chatId,project_id:state.activeChatProjectId,use_memory:state.useMemory});
  $('prompt').value='';state.attachments=[];renderAttachments();autoSize();await selectChat(state.chatId);await loadHistory();
 }catch(e){$('composer-error').textContent=e.message;$('composer-error').hidden=false;}
 finally{state.sending=false;updateSend();}
}

// ==================== Project & Folder Management ====================

async function loadProjects(){
  state.projects = await api('/projects');
  $('projects-count').textContent = fa(state.projects.length);
  renderProjectTabs();
  if(state.activeProjectTab === 'all'){
    $('projects-overview').hidden = false;
    $('project-detail-view').hidden = true;
    renderProjectsOverview();
  } else if(state.currentProjectId){
    $('projects-overview').hidden = true;
    $('project-detail-view').hidden = false;
    await loadProjectDetail(state.currentProjectId);
  }
}

function renderProjectTabs(){
  const container = $('project-tabs-list');
  const allTab = `<button class="project-tab ${state.activeProjectTab==='all'?'active':''}" data-tab-id="all" role="tab"><span data-icon="grid"></span><span>همهٔ پروژه‌ها</span></button>`;
  const openTabs = state.openProjectTabs.map(p => `
    <button class="project-tab ${state.activeProjectTab===p.id?'active':''}" data-tab-id="${esc(p.id)}" role="tab" title="${esc(p.name)}">
      <span data-icon="folder"></span>
      <span>${esc(p.name)}</span>
      <span class="close-tab" data-close-tab="${esc(p.id)}" title="بستن تب">&times;</span>
    </button>
  `).join('');
  container.innerHTML = allTab + openTabs;
  hydrateIcons(container);
}

function selectProjectTab(tabId){
  state.activeProjectTab = tabId;
  if(tabId === 'all'){
    state.currentProjectId = null;
    $('projects-overview').hidden = false;
    $('project-detail-view').hidden = true;
    renderProjectTabs();
    renderProjectsOverview();
  } else {
    state.currentProjectId = tabId;
    $('projects-overview').hidden = true;
    $('project-detail-view').hidden = false;
    renderProjectTabs();
    loadProjectDetail(tabId).catch(reportError);
  }
}

function openProjectInTab(project){
  if(!state.openProjectTabs.some(p => p.id === project.id)){
    state.openProjectTabs.push(project);
  }
  selectProjectTab(project.id);
}

function closeProjectTab(tabId, event){
  if(event) event.stopPropagation();
  state.openProjectTabs = state.openProjectTabs.filter(p => p.id !== tabId);
  if(state.activeProjectTab === tabId){
    const next = state.openProjectTabs.at(-1);
    selectProjectTab(next ? next.id : 'all');
  } else {
    renderProjectTabs();
  }
}

function renderProjectsOverview(){
  const q = $('projects-search').value.trim().toLowerCase();
  const rows = state.projects.filter(p => (p.name + ' ' + p.path + ' ' + (p.description || '')).toLowerCase().includes(q));
  const container = $('projects-grid');
  if(!rows.length){
    container.innerHTML = `<div class="empty-state"><span data-icon="folder"></span><h3>${q?'پروژه‌ای پیدا نشد.':'هنوز پروژه‌ای ثبت نشده است'}</h3><p>${q?'عبارت دیگری جست‌وجو کنید.':'برای شروع کار با فایل‌های سیستم، یک پروژهٔ جدید تعریف کنید.'}</p><button class="primary-button" id="empty-add-project"><span data-icon="plus"></span>تعریف اولین پروژه</button></div>`;
    hydrateIcons(container);
    return;
  }
  container.innerHTML = rows.map(p => `
    <article class="project-card">
      <div class="project-card-top">
        <h3><span data-icon="folder"></span>${esc(p.name)}</h3>
      </div>
      <div class="project-card-path" title="${esc(p.path)}">${esc(p.path)}</div>
      ${p.description ? `<p class="project-card-desc">${esc(p.description)}</p>` : ''}
      <div class="project-card-stats">
        <span><b>${fa(p.task_count)}</b> تسک</span>
        <span><b>${fa(p.completed_task_count)}</b> انجام‌شده</span>
        <span>هزینه: <bdi>${money(p.spent_cost_usd)}</bdi></span>
      </div>
      <div class="project-card-actions">
        <button class="secondary-button mini" data-open-explorer="${esc(p.path)}" title="باز کردن در Explorer">${icon('external')}Explorer</button>
        <button class="secondary-button mini" data-edit-proj="${esc(p.id)}" title="ویرایش">${icon('edit')}</button>
        <button class="danger-button mini" data-delete-proj="${esc(p.id)}" title="حذف">${icon('trash')}</button>
        <button class="primary-button mini" data-open-proj="${esc(p.id)}">مشاهده و تسک‌ها</button>
      </div>
    </article>
  `).join('');
  hydrateIcons(container);
}

async function loadProjectDetail(projectId){
  const data = await api('/projects/' + encodeURIComponent(projectId));
  $('proj-detail-title').textContent = data.name;
  $('proj-detail-desc').textContent = data.description || 'بدون توضیحات اضافی';
  $('proj-folder-name').textContent = data.folder.name || 'پوشه';
  $('proj-folder-path').textContent = data.path;

  const badge = $('proj-folder-badge');
  if(data.folder.exists && data.folder.is_dir){
    badge.className = 'folder-status-pill connected';
    badge.innerHTML = `<i class="dot"></i>متصل روی سیستم · ${fa(data.folder.total_files)} فایل`;
    const filesList = $('folder-files-list');
    filesList.innerHTML = (data.folder.entries || []).map(e => `
      <span class="folder-file-chip ${e.type==='dir'?'is-dir':''}">
        ${icon(e.type==='dir'?'folder':'file')}
        <span>${esc(e.name)}</span>
      </span>
    `).join('') || '<span class="muted">پوشه خالی است</span>';
    hydrateIcons(filesList);
  } else {
    badge.className = 'folder-status-pill error';
    badge.innerHTML = `<i class="dot"></i>${esc(data.folder.error || 'پوشه یافت نشد')}`;
    $('folder-files-list').innerHTML = '<span class="muted">امکان نمایش فایل‌ها وجود ندارد</span>';
  }

  // Render Tasks
  const tasksContainer = $('project-tasks-grid');
  const tasks = data.tasks || [];
  if(!tasks.length){
    tasksContainer.innerHTML = `<div class="empty-state"><span data-icon="plan"></span><h3>هنوز تسکی برای این پروژه ثبت نشده است</h3><p>تسک‌های این پروژه را اضافه کنید تا توسط تیم ۵ Agent اجرا شوند.</p><button class="primary-button" id="empty-add-task"><span data-icon="plus"></span>افزودن اولین تسک</button></div>`;
    hydrateIcons(tasksContainer);
    return;
  }
  tasksContainer.innerHTML = tasks.map(t => {
    const isRunning = t.status === 'RUNNING';
    const isDone = t.status === 'COMPLETED' || t.status === 'ACCEPT_CANDIDATE';
    return `
      <article class="task-card" data-task-id="${esc(t.id)}">
        <div class="task-card-top">
          <div class="task-card-title">
            <span class="badge-priority ${esc(t.priority)}">${esc(t.priority)}</span>
            <strong>${esc(t.title)}</strong>
          </div>
          <div class="task-card-badges">
            <span class="run-status ${isRunning?'busy':''}">${isRunning?'<i class="pulse-dot"></i>':''}${esc(statusText[t.status]||t.status)}</span>
          </div>
        </div>
        <div class="task-objective" dir="auto">${esc(t.objective)}</div>
        ${t.acceptance_criteria?.length ? `
          <div class="task-criteria">
            ${t.acceptance_criteria.map(c => `<div class="task-criteria-item">${icon('check')}<span>${esc(c)}</span></div>`).join('')}
          </div>
        ` : ''}
        <div class="task-card-foot">
          <span>سقف بودجه: <bdi>${money(t.budget_cap_usd, 2)}</bdi> · جریان: ${workflowLabels[t.workflow]||t.workflow}</span>
          <div class="task-card-actions">
            <button class="primary-button mini" data-run-ptask="${esc(t.id)}" ${isRunning?'disabled':''}>${icon(isRunning?'stop':'play')}${isRunning?'در حال اجرا…':'اجرای تسک'}</button>
            ${t.last_run_id ? `<button class="secondary-button mini" data-view-chat-run="${esc(t.last_run_id)}">${icon('sparkles')}گفت‌وگو</button>` : ''}
            <button class="icon-btn" data-edit-ptask="${esc(t.id)}" title="ویرایش تسک">${icon('edit')}</button>
            <button class="icon-btn" data-delete-ptask="${esc(t.id)}" title="حذف تسک">${icon('trash')}</button>
          </div>
        </div>
      </article>
    `;
  }).join('');
  hydrateIcons(tasksContainer);
}

function openProjectDialog(project=null){
  state.projectEdit = project ? project.id : null;
  $('project-dialog-title').textContent = project ? 'ویرایش پروژه' : 'تعریف پروژهٔ جدید';
  $('proj-name-input').value = project ? project.name : '';
  $('proj-path-input').value = project ? project.path : '';
  $('proj-desc-input').value = project ? (project.description || '') : '';
  $('proj-criteria-input').value = project ? (project.default_criteria || '') : '';
  $('proj-budget-input').value = project ? project.default_budget : 0.50;
  $('proj-path-feedback').innerHTML = '';
  $('project-error').hidden = true;
  $('project-dialog').showModal();
  $('proj-name-input').focus();
  if(project && project.path){
    validateProjectPath(project.path);
  }
}

async function validateProjectPath(pathVal){
  if(!pathVal.trim()){
    $('proj-path-feedback').innerHTML = '';
    return;
  }
  try{
    const res = await api('/filesystem/validate-path?path=' + encodeURIComponent(pathVal.trim()));
    if(res.exists && res.is_dir){
      $('proj-path-feedback').innerHTML = `<span class="path-feedback success">✔ پوشه در سیستم تأیید شد (${fa(res.total_files)} فایل، ${fa(res.total_dirs)} پوشه)</span>`;
    } else {
      $('proj-path-feedback').innerHTML = `<span class="path-feedback error">❌ ${esc(res.error || 'پوشه پیدا نشد.')}</span>`;
    }
  }catch(e){
    $('proj-path-feedback').innerHTML = `<span class="path-feedback error">❌ ${esc(e.message)}</span>`;
  }
}

async function saveProject(event){
  event.preventDefault();
  const name = $('proj-name-input').value.trim();
  const path = $('proj-path-input').value.trim();
  const description = $('proj-desc-input').value.trim();
  const default_criteria = $('proj-criteria-input').value.trim();
  const default_budget = Number($('proj-budget-input').value) || 0.50;

  if(!name || !path){
    $('project-error').textContent = 'نام و مسیر پروژه الزامی هستند.';
    $('project-error').hidden = false;
    return;
  }

  try{
    if(state.projectEdit){
      await api('/projects/' + encodeURIComponent(state.projectEdit), {
        method: 'PATCH',
        body: JSON.stringify({name, path, description, default_criteria, default_budget})
      });
      toast('پروژه به‌روزرسانی شد.');
    } else {
      const created = await post('/projects', {name, path, description, default_criteria, default_budget});
      openProjectInTab(created);
      toast('پروژهٔ جدید ایجاد شد.');
    }
    $('project-dialog').close();
    await loadProjects();
  }catch(err){
    $('project-error').textContent = err.message;
    $('project-error').hidden = false;
  }
}

function openTaskDialog(task=null){
  if(!state.currentProjectId){
    toast('ابتدا پروژه را انتخاب کنید.');
    return;
  }
  const proj = state.projects.find(p => p.id === state.currentProjectId);
  state.taskEdit = task ? task.id : null;
  $('ptask-proj-name').textContent = proj ? proj.name : 'پروژه';
  $('project-task-dialog-title').textContent = task ? 'ویرایش تسک' : 'افزودن تسک جدید';
  $('ptask-title-input').value = task ? task.title : '';
  $('ptask-objective-input').value = task ? task.objective : '';
  $('ptask-criteria-input').value = task ? (Array.isArray(task.acceptance_criteria) ? task.acceptance_criteria.join('\n') : task.acceptance_criteria) : (proj?.default_criteria || '');
  $('ptask-budget-input').value = task ? task.budget_cap_usd : (proj?.default_budget || 0.50);
  $('ptask-priority-input').value = task ? task.priority : 'P1';
  $('ptask-workflow-input').value = task ? task.workflow : 'low';
  $('project-task-error').hidden = true;
  $('project-task-dialog').showModal();
  $('ptask-title-input').focus();
}

async function saveTask(event){
  event.preventDefault();
  const title = $('ptask-title-input').value.trim();
  const objective = $('ptask-objective-input').value.trim();
  const criteria = $('ptask-criteria-input').value.split('\n').map(s=>s.trim()).filter(Boolean);
  const budget_cap_usd = Number($('ptask-budget-input').value) || 0.50;
  const priority = $('ptask-priority-input').value;
  const workflow = $('ptask-workflow-input').value;

  if(!title || !objective || !criteria.length){
    $('project-task-error').textContent = 'عنوان، هدف و حداقل یک معیار پذیرش الزامی هستند.';
    $('project-task-error').hidden = false;
    return;
  }

  try{
    if(state.taskEdit){
      await api(`/projects/${state.currentProjectId}/tasks/${state.taskEdit}`, {
        method: 'PATCH',
        body: JSON.stringify({title, objective, acceptance_criteria: criteria, budget_cap_usd, priority, workflow})
      });
      toast('تسک به‌روزرسانی شد.');
    } else {
      await post(`/projects/${state.currentProjectId}/tasks`, {
        title, objective, acceptance_criteria: criteria, budget_cap_usd, priority, workflow
      });
      toast('تسک جدید به پروژه اضافه شد.');
    }
    $('project-task-dialog').close();
    await loadProjectDetail(state.currentProjectId);
  }catch(err){
    $('project-task-error').textContent = err.message;
    $('project-task-error').hidden = false;
  }
}

async function runProjectTask(taskId){
  if(!state.currentProjectId) return;
  try{
    const res = await post(`/projects/${state.currentProjectId}/tasks/${taskId}/run`, {});
    toast('تسک با زمینهٔ فایل‌های پروژه در صف ۵ Agent قرار گرفت.');
    await loadProjectDetail(state.currentProjectId);
    if(res.conversation_id){
      await selectChat(res.conversation_id);
    }
  }catch(err){
    reportError(err);
  }
}

async function openExplorer(pathVal){
  try{
    await post('/filesystem/open-folder', {path: pathVal});
  }catch(err){
    reportError(err);
  }
}

function openProjectPicker(){
  const list = $('project-picker-list');
  const noneItem = `
    <div class="project-picker-item ${!state.activeChatProjectId?'active':''}" data-select-proj="">
      <strong>فضای شخصی و عمومی (بدون پروژه)</strong>
      <small>بدون ارجاع به پوشهٔ خاص</small>
    </div>
  `;
  const items = state.projects.map(p => `
    <div class="project-picker-item ${state.activeChatProjectId===p.id?'active':''}" data-select-proj="${esc(p.id)}">
      <strong>${esc(p.name)}</strong>
      <small dir="ltr">${esc(p.path)}</small>
    </div>
  `).join('');
  list.innerHTML = noneItem + items;
  $('project-select-dialog').showModal();
}

function setChatProject(projectId){
  state.activeChatProjectId = projectId || null;
  const proj = state.projects.find(p => p.id === projectId);
  $('composer-project-name').textContent = proj ? `پروژه: ${proj.name}` : 'بدون پروژه';
  $('project-select-dialog').close();
  if(proj && state.workflow==='low'){
    setWorkflow('medium');
    toast(`پروژهٔ «${proj.name}» متصل شد؛ برای تحلیل پوشه سطح Medium انتخاب شد.`);
  }else{
    toast(proj ? `پروژهٔ «${proj.name}» برای گفت‌وگو انتخاب شد.` : 'حالت بدون پروژه فعال شد.');
  }
}

// ==================== End Projects ====================

async function loadMemories(){state.memories=await api('/memories');$('memory-count').textContent=fa(state.memories.length);renderMemories();}
function renderMemories(){const q=$('memory-search').value.trim();const items=state.memories.filter(m=>(m.title+' '+m.content).includes(q));$('memory-grid').innerHTML=items.length?items.map(m=>`<article class="memory-card ${m.enabled?'':'disabled'}"><div class="memory-card-top"><h3>${esc(m.title)}</h3><span class="memory-state">${m.enabled?'فعال':'غیرفعال'}</span></div><p>${esc(m.content)}</p><div class="memory-card-bottom"><span>نسخهٔ ${fa(m.revision)} · ذخیرهٔ محلی</span><div class="memory-controls"><button class="icon-btn" data-edit-memory="${esc(m.id)}" title="ویرایش" aria-label="ویرایش یادداشت">${icon('edit')}</button><button class="icon-btn" data-delete-memory="${esc(m.id)}" title="حذف" aria-label="حذف یادداشت">${icon('trash')}</button></div></div></article>`).join(''):`<div class="empty-state">${icon('memory')}<h3>${q?'یادداشتی پیدا نشد.':'فضایی برای چیزهای مهم'}</h3><p>${q?'عبارت دیگری را امتحان کن.':'ترجیحات، قواعد پروژه یا تصمیم‌هایت را اضافه کن تا دوباره توضیحشان ندهی.'}</p>${q?'':'<button class="primary-button" id="empty-add-memory">اولین یادداشت را بنویس</button>'}</div>`;}
function openMemory(item=null,content='',title=''){state.memoryEdit=item?.id||null;$('memory-title').value=item?.title||title;$('memory-content').value=item?.content||content;$('memory-enabled').checked=item?!!item.enabled:true;$('memory-dialog-title').textContent=item?'ویرایش یادداشت':'یادداشت جدید';$('memory-error').hidden=true;$('memory-dialog').showModal();$('memory-title').focus();}
async function saveMemory(event){event.preventDefault();const button=event.submitter;button.disabled=true;try{const payload={title:$('memory-title').value.trim(),content:$('memory-content').value.trim(),enabled:$('memory-enabled').checked};await api('/memories'+(state.memoryEdit?'/'+state.memoryEdit:''),{method:state.memoryEdit?'PUT':'POST',body:JSON.stringify(payload)});$('memory-dialog').close();await loadMemories();toast('یادداشت در حافظهٔ محلی ذخیره شد.');}catch(e){$('memory-error').textContent=e.message;$('memory-error').hidden=false;}finally{button.disabled=false;}}
async function loadUsage(){state.usage=await api('/usage');const u=state.usage;$('daily-amount').textContent=money(u.spent,2)+' / '+money(u.cap,2);$('daily-meter').style.width=Math.min(100,(u.spent+u.reserved+u.unknown)/u.cap*100)+'%';$('daily-budget-input').value=u.cap;$('usage-description').textContent='اعداد این صفحه مصرف شبیه‌سازی‌شده‌اند؛ هیچ API پولی متصل نیست و هزینه‌ای پرداخت نمی‌شود.';
 $('usage-stats').innerHTML=[['هزینهٔ ثبت‌شده',money(u.spent),'در '+fa(u.calls)+' فراخوانی'],['بودجهٔ باقی‌مانده',money(u.remaining),'از سقف '+money(u.cap,2)],['رزرو فعال',money(u.reserved),'پیش از دریافت پاسخ'],['هزینهٔ نامعلوم',money(u.unknown),'رزرو حفظ‌شده تا تعیین مصرف']].map(([label,value,sub])=>`<div class="stat-card"><span>${label}</span><strong>${value}</strong><small>${sub}</small></div>`).join('');
 $('model-usage').innerHTML=u.models.length?`<table class="usage-table"><thead><tr><th>مدل</th><th>توکن ورودی</th><th>توکن خروجی</th><th>هزینه</th></tr></thead><tbody>${u.models.map(m=>`<tr><td>${esc(m.model_id)}</td><td>${fa(m.input_tokens)}</td><td>${fa(m.output_tokens)}</td><td><bdi>${money(m.cost)}</bdi></td></tr>`).join('')}</tbody></table>`:'<div class="empty-state"><p>امروز هنوز مصرفی ثبت نشده است.</p></div>';
}
function download(text,name,type='text/plain;charset=utf-8'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);}
function confirmAction(title,message,action,label='حذف'){$('confirm-title').textContent=title;$('confirm-message').textContent=message;$('confirm-action').textContent=label;$('confirm-action').onclick=async()=>{$('confirm-dialog').close();try{await action();}catch(e){reportError(e);}};$('confirm-dialog').showModal();}
async function openSettings(){
  state.models = await api('/models/status');
  const demo = state.models.demo;
  $('connection-info').innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between">
      <strong><i class="dot"></i>حالت آزمایشی؛ بدون API پولی</strong>
    </div>
    <p>این نسخهٔ قدیمی فقط با پاسخ‌های نمونه کار می‌کند. کار واقعی از گفتگو و میز سازمان با حساب‌های متصل Codex و Claude انجام می‌شود.</p>
  `;
  $('settings-models').innerHTML = roles.map(r => `
    <div class="settings-model-row">
      <div style="display:flex;flex-direction:column;gap:2px">
        <span>${esc(r.name)}</span>
        <small style="color:var(--muted);font-size:10px">${esc(r.description)}</small>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <code>${esc(modelFor(r))}</code>
        <span style="font-size:10px;padding:2px 6px;border-radius:5px;background:${demo ? 'var(--raised)' : 'rgba(168,230,207,0.15);color:var(--accent)'}">${demo ? 'آزمایشی' : 'زنده'}</span>
      </div>
    </div>
  `).join('');
  $('settings-dialog').showModal();
}

function setupEvents(){
 $('new-chat').onclick=newChat;const contractDesign=$('open-contract-design');if(contractDesign)contractDesign.onclick=()=>location.href='/design-v2/02-request-contract.html';$('workspace-home').onclick=newChat;$('open-sidebar').onclick=toggleSidebar;$('collapse-sidebar').onclick=()=>{if(innerWidth<=1100)mobileClose();else toggleSidebar();};$('sidebar-backdrop').onclick=mobileClose;
 document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>showView(b.dataset.view));
 $('theme-toggle').onclick=toggleTheme;$('settings-theme').onclick=toggleTheme;$('open-settings').onclick=()=>openSettings().catch(reportError);
 $('search-chat').onclick=()=>{$('history-search-wrap').hidden=!$('history-search-wrap').hidden;$('history-search').focus();};$('history-search').oninput=renderHistory;
 $('history-list').onclick=event=>{const chat=event.target.closest('[data-chat]'),rename=event.target.closest('[data-rename]'),archive=event.target.closest('[data-archive]');if(chat)selectChat(chat.dataset.chat);if(rename){state.renameId=rename.dataset.rename;$('rename-input').value=state.history.find(c=>c.id===state.renameId).title;$('rename-dialog').showModal();}if(archive){const id=archive.dataset.archive;confirmAction('بایگانی این گفت‌وگو؟','گفت‌وگو از نوار کناری کنار می‌رود؛ داده‌های اجرا و مصرف حفظ می‌شوند.',async()=>{await api('/conversations/'+id,{method:'PATCH',body:JSON.stringify({archived:true})});if(state.chatId===id)newChat();await loadHistory();toast('گفت‌وگو بایگانی شد.');},'بایگانی');}};
 $('rename-form').onsubmit=async e=>{e.preventDefault();try{await api('/conversations/'+state.renameId,{method:'PATCH',body:JSON.stringify({title:$('rename-input').value.trim()})});$('rename-dialog').close();await loadHistory();if(state.chatId===state.renameId)await refreshChat();}catch(err){reportError(err);}};
  $('agents-toggle').onclick=()=>toggleAgents();$('close-agents').onclick=()=>toggleAgents(false);
  $('agent-roster').onclick=e=>{
    const card=e.target.closest('[data-agent-role]');
    if(card) showAgentOutput(card.dataset.agentRole);
  };
  $('run-inspector').onclick=e=>{
    const check=e.target.closest('[data-check-name]');
    if(check) showCheckDetail(check.dataset.checkName);
  };
  $('close-agent-output').onclick=()=>{
    $('agent-output-viewer').hidden=true;
    state.selectedAgentRole=null;
    document.querySelectorAll('#agent-roster .agent-card').forEach(c=>c.classList.remove('active'));
  };
  $('copy-agent-output').onclick=async()=>{
    if(state.currentAgentRawOutput){
      await navigator.clipboard.writeText(state.currentAgentRawOutput);
      toast('متن خروجی کپی شد.');
    }
  };
  $('dialog-expand-output').onclick=()=>openAgentOutputDialog();
  $('dialog-copy-agent-output').onclick=async()=>{
    if(state.currentAgentRawOutput){
      await navigator.clipboard.writeText(state.currentAgentRawOutput);
      toast('گزارش کپی شد.');
    }
  };
 document.querySelectorAll('[data-template]').forEach(b=>b.onclick=()=>useTemplate(b.dataset.template));
 $('prompt').oninput=autoSize;$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('composer').requestSubmit();}};$('composer').onsubmit=submit;
 $('memory-toggle').onclick=()=>{state.useMemory=!state.useMemory;$('memory-toggle').classList.toggle('active',state.useMemory);$('memory-toggle').setAttribute('aria-pressed',String(state.useMemory));$('memory-toggle').innerHTML=icon('memory')+`<span>حافظه ${state.useMemory?'روشن':'خاموش'}</span>`;};
 $('workflow-toggle').onclick=()=>showEffort($('effort-popover').hidden);
 $('effort-range').oninput=e=>setWorkflow(['low','medium','high'][Number(e.target.value)]);
 $('effort-reset').onclick=()=>setWorkflow('low');
 document.addEventListener('click',e=>{if(!e.target.closest('.effort-control'))showEffort(false);});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')showEffort(false);});
 for(const id of ['manage-agents','settings-agents','effort-agents'])$(id).onclick=()=>openAgents().catch(reportError);
 $('agents-cancel').onclick=()=>$('agents-dialog').close();
 $('agents-form').onsubmit=saveAgents;
 $('add-custom-agent').onclick=()=>{if($('custom-agent-editors').children.length<5)addAgentEditor({id:'custom_'+crypto.randomUUID().replaceAll('-','').slice(0,12),name:'',role:'luna',model_id:'gpt-5.6-luna',instructions:'',enabled:true});};
 $('custom-agent-editors').onclick=e=>{const button=e.target.closest('[data-remove-agent]');if(button){button.closest('.custom-agent-editor').remove();$('add-custom-agent').disabled=false;}};
 $('task-options').onclick=()=>{$('task-budget-input').value=state.budget;$('options-dialog').showModal();};
 $('save-task-options').onclick=e=>{const budget=Number($('task-budget-input').value);if(!Number.isFinite(budget)||budget<=0||budget>100){e.preventDefault();toast('سقف باید بین ۰٫۰۱ و ۱۰۰ دلار باشد.');return;}state.budget=budget;$('budget-label').textContent='سقف '+money(budget,2);};
 $('attach-file').onclick=()=>$('file-input').click();$('file-input').onchange=e=>readFiles(e.target.files).catch(reportError);$('attachment-list').onclick=e=>{const b=e.target.closest('[data-remove-file]');if(b){state.attachments.splice(Number(b.dataset.removeFile),1);renderAttachments();}};
 $('chat-scroll').onscroll=()=>{const el=$('chat-scroll');$('scroll-bottom').hidden=el.scrollHeight-el.scrollTop-el.clientHeight<200;};$('scroll-bottom').onclick=()=>$('chat-scroll').scrollTo({top:$('chat-scroll').scrollHeight,behavior:'smooth'});
 $('messages').onclick=async e=>{const b=e.target.closest('button');if(!b)return;const runId=b.dataset.copy||b.dataset.export||b.dataset.remember||b.dataset.inspect||b.dataset.accept;const run=state.chat?.runs.find(r=>r.run_id===runId);if(!run)return;try{if(b.dataset.copy){await navigator.clipboard.writeText(outputText(run));toast('پاسخ کپی شد.');}if(b.dataset.export)download(outputText(run),'flux-response.md');if(b.dataset.remember)openMemory(null,outputText(run).slice(0,12000),run.objective.slice(0,100));if(b.dataset.inspect){toggleAgents(true);renderAgents(run);}if(b.dataset.accept){await post(`/runs/${run.run_id}/accept`,{});await refreshChat();toast('پذیرش شما برای این نسخه ثبت شد.');}}catch(err){reportError(err);}};
 $('add-memory').onclick=()=>openMemory();$('memory-search').oninput=renderMemories;$('memory-form').onsubmit=saveMemory;
 $('memory-grid').onclick=e=>{const edit=e.target.closest('[data-edit-memory]'),del=e.target.closest('[data-delete-memory]');if(e.target.closest('#empty-add-memory'))openMemory();if(edit)openMemory(state.memories.find(m=>m.id===edit.dataset.editMemory));if(del)confirmAction('حذف یادداشت از حافظه؟','این یادداشت در درخواست‌های جدید استفاده نمی‌شود. متن ثبت‌شده در اجراهای قبلی برای حفظ تاریخچه باقی می‌ماند.',async()=>{await api('/memories/'+del.dataset.deleteMemory,{method:'DELETE'});await loadMemories();toast('یادداشت حذف شد.');});};
 $('daily-budget-form').onsubmit=async e=>{e.preventDefault();try{state.prefs.daily_budget=Number($('daily-budget-input').value);state.prefs=await api('/preferences',{method:'PUT',body:JSON.stringify(state.prefs)});await loadUsage();toast('سقف روزانه ذخیره شد.');}catch(err){reportError(err);}};
 $('export-usage').onclick=()=>{if(state.usage)download(JSON.stringify(state.usage,null,2),'flux-usage-'+state.usage.day+'.json','application/json');};

 // Project Events
 $('project-tabs-list').onclick = e => {
   const closeBtn = e.target.closest('[data-close-tab]');
   if(closeBtn){
     closeProjectTab(closeBtn.dataset.closeTab, e);
     return;
   }
   const tab = e.target.closest('[data-tab-id]');
   if(tab){
     selectProjectTab(tab.dataset.tabId);
   }
 };
 $('add-project-tab-btn').onclick = () => openProjectDialog();
 $('overview-add-project').onclick = () => openProjectDialog();
 $('projects-search').oninput = renderProjectsOverview;

 $('projects-grid').onclick = e => {
   const openProj = e.target.closest('[data-open-proj]');
   const expBtn = e.target.closest('[data-open-explorer]');
   const editBtn = e.target.closest('[data-edit-proj]');
   const delBtn = e.target.closest('[data-delete-proj]');
   if(e.target.closest('#empty-add-project')) openProjectDialog();
   if(openProj){
     const proj = state.projects.find(p => p.id === openProj.dataset.openProj);
     if(proj) openProjectInTab(proj);
   }
   if(expBtn) openExplorer(expBtn.dataset.openExplorer);
   if(editBtn){
     const proj = state.projects.find(p => p.id === editBtn.dataset.editProj);
     if(proj) openProjectDialog(proj);
   }
   if(delBtn){
     const id = delBtn.dataset.deleteProj;
     confirmAction('حذف این پروژه؟', 'تسک‌ها و تنظیمات پروژه حذف خواهند شد اما فایل‌های پوشه دست‌نخورده باقی می‌مانند.', async () => {
       await api('/projects/' + id, {method: 'DELETE'});
       closeProjectTab(id);
       await loadProjects();
       toast('پروژه حذف شد.');
     });
   }
 };

 $('proj-back-btn').onclick = () => selectProjectTab('all');
 $('proj-open-folder').onclick = () => {
   const proj = state.projects.find(p => p.id === state.currentProjectId);
   if(proj) openExplorer(proj.path);
 };
 $('proj-copy-path').onclick = async () => {
   const proj = state.projects.find(p => p.id === state.currentProjectId);
   if(proj){
     await navigator.clipboard.writeText(proj.path);
     toast('مسیر پوشه کپی شد.');
   }
 };
 $('toggle-folder-files').onclick = () => {
   $('folder-files-panel').hidden = !$('folder-files-panel').hidden;
 };
 $('proj-edit-btn').onclick = () => {
   const proj = state.projects.find(p => p.id === state.currentProjectId);
   if(proj) openProjectDialog(proj);
 };
 $('proj-delete-btn').onclick = () => {
   const id = state.currentProjectId;
   if(!id) return;
   confirmAction('حذف این پروژه؟', 'تسک‌ها و اطلاعات پروژه حذف می‌شوند اما فایل‌های پوشه در سیستم شما باقی می‌مانند.', async () => {
     await api('/projects/' + id, {method: 'DELETE'});
     closeProjectTab(id);
     await loadProjects();
     toast('پروژه حذف شد.');
   });
 };

 $('add-project-task-btn').onclick = () => openTaskDialog();
 $('project-tasks-grid').onclick = async e => {
   if(e.target.closest('#empty-add-task')) openTaskDialog();
   const runBtn = e.target.closest('[data-run-ptask]');
   const chatBtn = e.target.closest('[data-view-chat-run]');
   const editBtn = e.target.closest('[data-edit-ptask]');
   const delBtn = e.target.closest('[data-delete-ptask]');

   if(runBtn) runProjectTask(runBtn.dataset.runPtask);
   if(chatBtn) selectChat(chatBtn.dataset.viewChatRun);
   if(editBtn){
     const task = await api(`/projects/${state.currentProjectId}/tasks/${editBtn.dataset.editPtask}`);
     openTaskDialog(task);
   }
   if(delBtn){
     const id = delBtn.dataset.deletePtask;
     confirmAction('حذف این تسک؟', 'این تسک از لیست کارهای پروژه پاک خواهد شد.', async () => {
       await api(`/projects/${state.currentProjectId}/tasks/${id}`, {method: 'DELETE'});
       await loadProjectDetail(state.currentProjectId);
       toast('تسک حذف شد.');
     });
   }
 };

 $('proj-path-input').oninput = e => {
   clearTimeout(pathValidateTimer);
   pathValidateTimer = setTimeout(() => validateProjectPath(e.target.value), 400);
 };
 $('project-form').onsubmit = saveProject;
 $('project-task-form').onsubmit = saveTask;

 $('composer-project-chip').onclick = openProjectPicker;
 $('project-picker-list').onclick = e => {
   const item = e.target.closest('[data-select-proj]');
   if(item) setChatProject(item.dataset.selectProj);
 };

 // Windows Installer Dialog & PWA
 $('install-app-btn').onclick = () => $('install-dialog').showModal();
 $('btn-pwa-install').onclick = async () => {
   if(state.deferredPrompt){
     state.deferredPrompt.prompt();
     const { outcome } = await state.deferredPrompt.userChoice;
     if(outcome === 'accepted') toast('برنامه روی سیستم شما نصب شد!');
     state.deferredPrompt = null;
   } else {
     toast('برای نصب دسکتاپ، فایل Install-Flux.bat در پوشهٔ برنامه را اجرا کنید.');
   }
 };

 window.addEventListener('beforeinstallprompt', e => {
   e.preventDefault();
   state.deferredPrompt = e;
 });

 document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
 document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
 document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();newChat();}if(e.key==='Escape'){mobileClose();toggleAgents(false);}});
}

async function init(){
  hydrateIcons();
  applyTheme(localStorage.getItem('flux-theme')||'dark');
  setupEvents();
  renderAgents();
  try{
    const results = await Promise.allSettled([
      api('/preferences'),
      api('/models/status'),
      loadHistory(),
      loadMemories(),
      loadUsage(),
      loadProjects(),
      api('/settings/agents')
    ]);
    if(results[6].status==='fulfilled')state.agentSettings=results[6].value;
    if(results[0].status==='fulfilled'){
      state.prefs=results[0].value;
      state.budget=state.prefs.default_budget;
      applyTheme(state.prefs.theme);
      $('budget-label').textContent='سقف '+money(state.budget,2);
    }
    if(results[1].status==='fulfilled'){
      state.models=results[1].value;
      setWorkflow(state.workflow);
      $('mode-badge').innerHTML='<i class="dot"></i>'+'حالت آزمایشی';
    }
    const isDesktop = new URLSearchParams(location.search).has('desktop') || window.matchMedia('(display-mode: standalone)').matches;
    if(isDesktop){
      const instBtn = $('install-app-btn');
      if(instBtn) instBtn.style.display = 'none';
    }
    const last = localStorage.getItem('flux-chat');
    if(last&&state.history.some(c=>c.id===last)){
      await selectChat(last);
    } else if(state.history.length){
      await selectChat(state.history[0].id);
    }
  }catch(e){reportError(e);}
  autoSize();
}
init();
