'use strict';
// This panel shares the existing project and memory API with the legacy UI.
const workspaceData={projects:[],memories:[],tab:'projects',projectEdit:null,memoryEdit:null,pendingDelete:null,loading:0};
const workspaceNormalize=value=>String(value||'').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/\u200c/g,' ').toLocaleLowerCase();
function workspaceError(error,id='workspace-error'){const node=$(id);node.textContent=error.message||String(error);node.hidden=false;}
function workspaceNotice(message){$('workspace-notice').textContent=message;$('workspace-notice').hidden=false;}
function workspaceAction(label,action,className=''){const button=textNode('button',label,className);button.type='button';button.onclick=()=>Promise.resolve().then(action).catch(error=>workspaceError(error));return button;}
function workspaceTab(tab){
 workspaceData.tab=tab;$('workspace-search').value='';
 for(const key of ['projects','memories']){const selected=tab===key;$(key+'-tab').setAttribute('aria-selected',String(selected));$(key+'-tab').tabIndex=selected?0:-1;$(key+'-panel').hidden=!selected;}
 $('workspace-search').placeholder=tab==='projects'?'جستجو در پروژه‌ها…':'جستجو در حافظه…';renderWorkspace();
}
function renderWorkspace(){
 const query=workspaceNormalize($('workspace-search').value.trim());
 const projects=workspaceData.projects.filter(p=>(!p.archived||$('include-archived-projects').checked)&&workspaceNormalize(p.name+' '+p.path+' '+p.description).includes(query));
 $('project-list').replaceChildren();
 for(const project of projects){
  const card=textNode('article','','workspace-card');card.dataset.projectId=project.id;
  const heading=textNode('div','','workspace-card-heading');heading.append(textNode('h3',project.name),textNode('span',project.archived?'بایگانی‌شده':'فعال','workspace-badge'));
  const path=textNode('p',project.path,'workspace-path');path.dir='ltr';card.append(heading,path);
  if(project.description)card.append(textNode('p',project.description,'workspace-card-content'));
  const actions=textNode('div','','workspace-actions');
  if(!project.archived){const use=workspaceAction('گفتگوی تازه در این پروژه',()=>chooseWorkspaceProject(project),'primary');use.disabled=!!active()||state.busy;if(use.disabled)use.title='پس از پایان اجرای جاری، پروژه را انتخاب کن.';actions.append(use);}
  actions.append(workspaceAction('ویرایش پروژه',()=>editWorkspaceProject(project)),workspaceAction(project.archived?'بازگرداندن پروژه':'بایگانی پروژه',()=>archiveWorkspaceProject(project)));
  card.append(actions);$('project-list').append(card);
 }
 if(!projects.length)$('project-list').append(textNode('p',query?'پروژه‌ای پیدا نشد.':'هنوز پروژه‌ای ثبت نشده است.','muted'));
 const scope=$('memory-filter-project').value;const memories=workspaceData.memories.filter(m=>(scope==='all'||m.project_id===scope)&&workspaceNormalize(m.title+' '+m.content).includes(query));$('memory-list').replaceChildren();
 for(const memory of memories){
  const card=textNode('article','','workspace-card');card.dataset.memoryId=memory.id;
  const heading=textNode('div','','workspace-card-heading');heading.append(textNode('h3',memory.title),textNode('span',memory.enabled?'فعال':'غیرفعال','workspace-badge'));
  card.append(textNode('small',(workspaceData.projects.find(p=>p.id===memory.project_id)?.name|| (memory.project_id==='*'?'مشترک با اجازهٔ شما':'بدون پروژه'))+' · '+({verified:'تأییدشده',proposed:'پیشنهاد',stale:'قدیمی'}[memory.status]||memory.status),'muted'));card.append(heading,textNode('p',memory.content,'workspace-card-content'),textNode('p','نسخهٔ '+Number(memory.revision).toLocaleString('fa-IR'),'muted'));
  const actions=textNode('div','','workspace-actions');actions.append(workspaceAction('ویرایش یادداشت',()=>editWorkspaceMemory(memory)),workspaceAction('حذف یادداشت',()=>confirmWorkspaceMemoryDelete(memory)));card.append(actions);$('memory-list').append(card);
 }
 if(!memories.length)$('memory-list').append(textNode('p',query?'یادداشتی پیدا نشد.':'هنوز یادداشتی ثبت نشده است.','muted'));
}
async function loadWorkspace(){
 const generation=++workspaceData.loading;$('workspace-refresh').disabled=true;$('workspace-error').hidden=true;
 const results=await Promise.allSettled([api('/projects?archived=true'),api('/memories')]);
 if(generation!==workspaceData.loading)return;
 for(const [index,result] of results.entries()){if(result.status==='fulfilled')workspaceData[index?'memories':'projects']=result.value;else workspaceError(result.reason);}
 refreshMemoryScopes();renderWorkspace();$('workspace-refresh').disabled=false;
}
async function workspaceFolder(path){const folder=await api('/filesystem/validate-path?path='+encodeURIComponent(path));if(!folder.exists||!folder.is_dir)throw new Error('پوشهٔ پروژه پیدا نشد. مسیر یک پوشهٔ موجود را وارد کن.');return folder;}
async function chooseWorkspaceProject(project){
 if(active()||state.busy)throw new Error('برای انتخاب پروژه، ابتدا اجرای جاری را تمام یا متوقف کن.');
 await workspaceFolder(project.path);
 // A running turn might have started while the folder request was pending.
 if(active()||state.busy)throw new Error('اجرای جاری هنوز تمام نشده است.');
 const draft=$('prompt').value;newChat();state.cwd=project.path;state.projectId=project.id;
 if($('provider').value==='notebooklm'){$('provider').value='codex';$('provider').dispatchEvent(new Event('change'));}
 $('prompt').value=draft;resizePrompt();renderChat();$('project-memory-dialog').close();$('prompt').focus();
}
function editWorkspaceProject(project=null){workspaceData.projectEdit=project?.id||null;$('project-editor-title').textContent=project?'ویرایش پروژه':'پروژهٔ جدید';$('project-name').value=project?.name||'';$('project-path').value=project?.path||state.cwd;$('project-description').value=project?.description||'';$('project-edit-error').hidden=true;$('project-editor').showModal();$('project-name').focus();}
async function saveWorkspaceProject(event){
 event.preventDefault();const button=event.submitter;button.disabled=true;$('project-edit-error').hidden=true;
 try{const payload={name:$('project-name').value.trim(),path:$('project-path').value.trim(),description:$('project-description').value.trim()};if(!payload.name)throw new Error('نام پروژه را وارد کن.');await workspaceFolder(payload.path);await api('/projects'+(workspaceData.projectEdit?'/'+encodeURIComponent(workspaceData.projectEdit):''),{method:workspaceData.projectEdit?'PATCH':'POST',body:JSON.stringify(payload)});$('project-editor').close();await loadWorkspace();workspaceNotice('پروژه ذخیره شد.');}catch(error){workspaceError(error,'project-edit-error');}finally{button.disabled=false;}
}
async function archiveWorkspaceProject(project){await api('/projects/'+encodeURIComponent(project.id),{method:'PATCH',body:JSON.stringify({archived:!project.archived})});await loadWorkspace();workspaceNotice(project.archived?'پروژه بازگردانده شد.':'پروژه بایگانی شد؛ از نمایش پروژه‌های بایگانی‌شده می‌توانی آن را بازگردانی.');}
function editWorkspaceMemory(memory=null){workspaceData.memoryEdit=memory?.id||null;$('memory-editor-title').textContent=memory?'ویرایش یادداشت':'یادداشت جدید';$('memory-title').value=memory?.title||'';$('memory-content').value=memory?.content||'';$('memory-enabled').checked=memory?!!memory.enabled:true;refreshMemoryScopes();$('memory-project').value=memory?.project_id??state.chat?.project_id??state.projectId??'';$('memory-status').value=memory?.status||'verified';workspaceData.memoryRevision=memory?.revision||null;$('memory-edit-error').hidden=true;$('memory-editor').showModal();$('memory-title').focus();}
async function saveWorkspaceMemory(event){
 event.preventDefault();const button=event.submitter;button.disabled=true;$('memory-edit-error').hidden=true;
 try{const payload={title:$('memory-title').value.trim(),content:$('memory-content').value.trim(),enabled:$('memory-enabled').checked,project_id:$('memory-project').value,status:$('memory-status').value,expected_revision:workspaceData.memoryRevision};if(!payload.title||!payload.content)throw new Error('عنوان و متن یادداشت را وارد کن.');await api('/memories'+(workspaceData.memoryEdit?'/'+encodeURIComponent(workspaceData.memoryEdit):''),{method:workspaceData.memoryEdit?'PUT':'POST',body:JSON.stringify(payload)});$('memory-editor').close();await loadWorkspace();workspaceNotice('یادداشت در حافظهٔ محلی ذخیره شد.');}catch(error){workspaceError(error,'memory-edit-error');}finally{button.disabled=false;}
}
function confirmWorkspaceMemoryDelete(memory){workspaceData.pendingDelete=memory.id;$('workspace-confirm-message').textContent='یادداشت «'+memory.title+'» حذف شود؟ در درخواست‌های بعدی بازیابی نمی‌شود. نشست دستیار بازسازی می‌شود. متن قابل مشاهدهٔ گفتگوهای قبلی باقی می‌ماند.';$('workspace-confirm-error').hidden=true;$('workspace-confirm').showModal();}
async function deleteWorkspaceMemory(event){event.preventDefault();const button=event.submitter;button.disabled=true;try{await api('/memories/'+encodeURIComponent(workspaceData.pendingDelete),{method:'DELETE'});workspaceData.pendingDelete=null;$('workspace-confirm').close();await loadWorkspace();workspaceNotice('یادداشت حذف شد.');}catch(error){workspaceError(error,'workspace-confirm-error');}finally{button.disabled=false;}}
$('project-memory-button').onclick=()=>{closeSidebar();$('workspace-notice').hidden=true;$('project-memory-dialog').showModal();loadWorkspace().catch(error=>workspaceError(error));};
$('workspace-refresh').onclick=()=>loadWorkspace().catch(error=>workspaceError(error));$('workspace-search').oninput=renderWorkspace;$('include-archived-projects').onchange=renderWorkspace;
for(const key of ['projects','memories']){$(key+'-tab').onclick=()=>workspaceTab(key);$(key+'-tab').onkeydown=event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'projects':event.key==='End'?'memories':workspaceData.tab==='projects'?'memories':'projects';workspaceTab(next);$(next+'-tab').focus();}};}
$('add-project').onclick=()=>editWorkspaceProject();$('project-form').onsubmit=saveWorkspaceProject;$('add-memory').onclick=()=>editWorkspaceMemory();$('memory-form').onsubmit=saveWorkspaceMemory;$('workspace-confirm-form').onsubmit=deleteWorkspaceMemory;
// local.js installs data-close handlers before this script loads; these dialogs
// are already present in the HTML and use the same native dialog behavior.

function refreshMemoryScopes(){
 for(const id of ['memory-project','memory-filter-project']){
  const node=$(id),old=node.value;node.replaceChildren();
  const options=id==='memory-filter-project'?[['all','همهٔ یادداشت‌ها'],['','بدون پروژه'],['*','مشترک با اجازهٔ شما']]:[['','بدون پروژه'],['*','مشترک با اجازهٔ شما']];
  for(const p of workspaceData.projects)options.push([p.id,p.name+(p.archived?' (بایگانی)':'')]);
  for(const [value,label] of options){const option=textNode('option',label);option.value=value;node.append(option);}
  if(options.some(o=>o[0]===old))node.value=old;
 }
}
$('memory-filter-project').onchange=renderWorkspace;
