/* Real conversation list for the organisation workspace sidebar: open, rename, archive, restore, delete. */
(()=>{
'use strict';
const API='/api/local/chats';
const WORKSPACE='/design-v2/03-10-workspace.html';
const NEW_CHAT=WORKSPACE+'?screen=9';
const $=(s,r=document)=>r.querySelector(s);
const params=new URLSearchParams(location.search);
const currentId=()=>new URLSearchParams(location.search).get('chat')||'';
let chats=[],archived=[],showArchived=false;

async function call(path,options){
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options&&options.headers)}});
  let data=null;try{data=await response.json()}catch(_){}
  if(!response.ok)throw new Error((data&&typeof data.detail==='string'&&data.detail)||'انجام نشد.');
  return data;
}

/* ---------- small native-looking dialogs (confirm / prompt / notice) ---------- */
function ask({title,message='',input,confirmLabel='تأیید',danger=false,cancel=true}){
  return new Promise(resolve=>{
    const d=document.createElement('dialog');d.className='fx-dialog';
    const h=document.createElement('h2');h.textContent=title;d.appendChild(h);
    if(message){const p=document.createElement('p');p.textContent=message;d.appendChild(p)}
    let field=null;
    if(input!==undefined){field=document.createElement('input');field.type='text';field.maxLength=160;field.value=input;field.setAttribute('aria-label',title);d.appendChild(field)}
    const row=document.createElement('div');row.className='fx-dialog-actions';
    const ok=document.createElement('button');ok.type='button';ok.textContent=confirmLabel;ok.className=danger?'fx-danger':'primary';
    if(cancel){const no=document.createElement('button');no.type='button';no.textContent='انصراف';no.onclick=()=>d.close('cancel');row.appendChild(no)}
    row.appendChild(ok);d.appendChild(row);
    ok.onclick=()=>{if(field&&!field.value.trim()){field.focus();return}d.close('ok')};
    if(field)field.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();ok.click()}});
    d.addEventListener('close',()=>{const result=d.returnValue==='ok'?(field?field.value.trim():true):null;d.remove();resolve(result)});
    document.body.appendChild(d);d.showModal();(field||ok).focus();if(field)field.select();
  });
}

/* ---------- actions ---------- */
async function refresh(){
  try{[chats,archived]=await Promise.all([call(API),call(API+'?archived=only')])}catch(_){chats=[];archived=[]}
  render();
  window.dispatchEvent(new CustomEvent('flux:chats-changed',{detail:{chats,archived}}));
}
async function rename(chat){
  const title=await ask({title:'تغییر نام گفتگو',input:chat.title,confirmLabel:'ذخیره'});
  if(!title||title===chat.title)return;
  try{await call(API+'/'+chat.id,{method:'PATCH',body:JSON.stringify({title})});await refresh()}catch(e){await ask({title:'تغییر نام نشد',message:e.message,confirmLabel:'متوجه شدم',cancel:false})}
}
async function setArchived(chat,value){
  try{await call(API+'/'+chat.id,{method:'PATCH',body:JSON.stringify({archived:value})});await refresh();if(value&&currentId()===chat.id)location.href=NEW_CHAT}
  catch(e){await ask({title:value?'بایگانی نشد':'بازگردانی نشد',message:e.message,confirmLabel:'متوجه شدم',cancel:false})}
}
async function remove(chat){
  const yes=await ask({title:'حذف گفتگو',message:'«'+chat.title+'» با همهٔ پیام‌هایش برای همیشه حذف می‌شود. اگر فقط نمی‌خواهی در فهرست ببینی، بایگانی کن.',confirmLabel:'حذف',danger:true});
  if(!yes)return;
  try{await call(API+'/'+chat.id,{method:'DELETE'});await refresh();if(currentId()===chat.id)location.href=NEW_CHAT}
  catch(e){await ask({title:'حذف نشد',message:e.message,confirmLabel:'متوجه شدم',cancel:false})}
}
const menuFor=(chat,isArchived)=>[
  {label:'باز کردن',run:()=>{location.href=NEW_CHAT+'&chat='+encodeURIComponent(chat.id)}},
  {label:'تغییر نام…',key:'F2',run:()=>rename(chat)},
  isArchived?{label:'بازگردانی از بایگانی',run:()=>setArchived(chat,false)}:{label:'بایگانی',run:()=>setArchived(chat,true)},
  '-',
  {label:'حذف…',key:'Del',run:()=>remove(chat)}
];

/* ---------- rendering ---------- */
const icon=id=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('class','ic');const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#i-'+id);s.appendChild(u);return s};
function row(chat,isArchived){
  const wrap=document.createElement('div');wrap.className='chat-row'+(isArchived?' archived':'');
  const a=document.createElement('a');a.href=NEW_CHAT+'&chat='+encodeURIComponent(chat.id);a.dataset.chatId=chat.id;a.title=chat.title;
  if(chat.id===currentId())a.setAttribute('aria-current','page');
  const t=document.createElement('span');t.textContent=chat.title;a.append(icon('chat'),t);
  const more=document.createElement('button');more.type='button';more.className='chat-more';more.setAttribute('aria-label','گزینه‌های گفتگو');more.setAttribute('aria-haspopup','menu');more.textContent='⋯';
  more.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const r=more.getBoundingClientRect();window.fluxMenu&&window.fluxMenu.show(menuFor(chat,isArchived),r.left,r.bottom+2)});
  a.addEventListener('fx:menu',e=>{e.detail.items.push(...menuFor(chat,isArchived))});
  a.addEventListener('keydown',e=>{if(e.key==='Delete'){e.preventDefault();remove(chat)}else if(e.key==='F2'){e.preventDefault();rename(chat)}});
  wrap.append(a,more);return wrap;
}
function render(){
  const box=$('.recent:not(.proj-list)');if(!box)return;
  box.replaceChildren();
  const fresh=document.createElement('a');fresh.href=NEW_CHAT;fresh.className='chat-new';if(!currentId()&&location.search.includes('screen=9')&&location.pathname.endsWith('03-10-workspace.html'))fresh.setAttribute('aria-current','page');
  const s=document.createElement('span');s.textContent='گفتگوی تازه با مدل‌ها';fresh.append(icon('plus'),s);box.appendChild(fresh);
  if(!chats.length){const e=document.createElement('div');e.className='chat-empty';e.textContent='هنوز گفتگویی نیست.';box.appendChild(e)}
  for(const c of chats)box.appendChild(row(c,false));
  if(archived.length){
    const t=document.createElement('button');t.type='button';t.className='chat-archive-toggle';t.setAttribute('aria-expanded',String(showArchived));
    t.textContent=(showArchived?'پنهان کردن بایگانی':'بایگانی‌شده')+' ('+archived.length.toLocaleString('fa-IR')+')';
    t.onclick=()=>{showArchived=!showArchived;render()};box.appendChild(t);
    if(showArchived)for(const c of archived)box.appendChild(row(c,true));
  }
}

const css=document.createElement('link');css.rel='stylesheet';css.href='/static/chats-nav.css';document.head.appendChild(css);
window.fluxChats={ask,rename,remove,setArchived,refresh,call};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',refresh);else refresh();
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
})();
