'use strict';
const $ = id => document.getElementById(id);
const state = {
  projects: [],
  overview: {running: 0, max_parallel: 3, deferred: 0, attention: {}},
  inbox: [],
  inboxFilter: 'open',
  selectedIndex: 0,
  worktrees: [],
  pipelines: [],
  wiki: {head: '', entries: []},
  wikiHistory: [],
  notifyEnabled: false,
  stream: null
};

const prioNames = {blocked: 'منتظر تأیید شما (فوری)', action: 'نیازمند اقدام', warning: 'هشدار همپوشانی / تعویق', review: 'آمادهٔ بازبینی', info: 'اطلاع'};
const stepNames = {pending: 'در انتظار', running: 'در حال اجرا', waiting: 'منتظر تأیید/ظرفیت', gating: 'اجرای تست و بیلد', passed: 'تست پاس شد ✓', failed: 'ناموفق ✗', blocked: 'مسدودشده', cancelled: 'لغوشده', interrupted: 'قطع‌شده'};

function el(tag, text = '', className = '') {
  const node = document.createElement(tag);
  if (text !== '' && text !== null && text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function faNum(n) {
  return Number(n || 0).toLocaleString('fa-IR');
}

function showError(err) {
  const box = $('global-error');
  box.textContent = err?.message || String(err);
  box.hidden = false;
}

function showNotice(msg) {
  const box = $('global-notice');
  box.textContent = msg;
  box.hidden = false;
  setTimeout(() => { box.hidden = true; }, 4200);
}

async function api(path, options = {}) {
  $('global-error').hidden = true;
  const response = await fetch(path, {
    ...options,
    headers: {'Content-Type': 'application/json', ...(options.headers || {})}
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || 'خطا در ارتباط با سرور'));
  }
  return data;
}

const DEFAULT_STEPS = [
  {
    id: 'core',
    title: 'پیاده‌سازی هسته و پاس کردن تست واحد',
    prompt: 'ماژول پایه و تست واحد آن را پیاده‌سازی کن.',
    provider: 'codex',
    depends_on: [],
    scope: ['src/'],
    gates: [{name: 'pytest', run: 'pytest -q'}]
  },
  {
    id: 'integration',
    title: 'تکمیل لایهٔ یکپارچه‌سازی بر پایهٔ گام اول',
    prompt: 'بر اساس خروجی تست‌شدهٔ گام core، لایهٔ API و تست یکپارچه‌سازی را کامل کن.',
    provider: 'codex',
    depends_on: ['core'],
    scope: ['src/', 'tests/'],
    gates: [{name: 'pytest', run: 'pytest -q'}]
  }
];

function populateProjects() {
  const selects = [$('wt-project'), $('plan-project'), $('pipe-project'), $('wiki-project')];
  for (const select of selects) {
    const prev = select.value;
    select.replaceChildren();
    if (!state.projects.length) {
      const opt = el('option', 'ابتدا از بخش پروژه‌ها یک مخزن گیت ثبت کنید');
      opt.value = '';
      select.append(opt);
      continue;
    }
    for (const proj of state.projects) {
      const opt = el('option', `${proj.name} (${proj.path})`);
      opt.value = proj.id;
      select.append(opt);
    }
    if (prev && state.projects.some(p => p.id === prev)) select.value = prev;
  }
}

function renderTelemetry() {
  const ov = state.overview;
  $('stat-running').textContent = `در حال اجرا: ${faNum(ov.running)} / ${faNum(ov.max_parallel)}`;
  $('stat-deferred').textContent = `به تعویق افتاده: ${faNum(ov.deferred)}`;
  const blocked = (ov.attention?.blocked || 0) + (ov.attention?.action || 0);
  $('stat-blocked').textContent = `نیازمند توجه فوری: ${faNum(blocked)}`;
  if (document.activeElement !== $('max-parallel-input')) {
    $('max-parallel-input').value = String(ov.max_parallel || 3);
  }
}

function openPromptFor(item) {
  if (item?.chat_id) {
    location.href = `/chat?chat_id=${encodeURIComponent(item.chat_id)}&focus=prompt`;
  }
}

function renderInbox() {
  const container = $('inbox-list');
  container.replaceChildren();
  if (!state.inbox.length) {
    container.append(el('p', 'هیچ عاملی منتظر شما نیست؛ صف توجه خالی است.', 'muted'));
    return;
  }
  if (state.selectedIndex >= state.inbox.length) state.selectedIndex = Math.max(0, state.inbox.length - 1);
  state.inbox.forEach((item, idx) => {
    const card = el('article', '', `inbox-card prio-${item.priority}${idx === state.selectedIndex ? ' selected' : ''}`);
    card.tabIndex = 0;
    card.setAttribute('role', 'option');
    card.setAttribute('aria-selected', String(idx === state.selectedIndex));
    card.onclick = () => {
      state.selectedIndex = idx;
      renderInbox();
    };

    const top = el('div', '', 'inbox-top');
    const titleWrap = el('div', '', 'card-actions');
    titleWrap.append(
      el('span', `#${faNum(idx + 1)}`, 'kv-chip'),
      el('span', prioNames[item.label] || item.label, `badge ${item.label}`),
      el('strong', item.title)
    );
    const meta = el('small', item.worktree_id || item.chat_id || item.pipeline_id || '', 'muted');
    top.append(titleWrap, meta);
    card.append(top);

    const detailParts = [];
    if (item.detail?.error) detailParts.push(item.detail.error);
    if (item.detail?.summary) detailParts.push(item.detail.summary);
    if (item.detail?.body) detailParts.push(`[${item.detail.kind || 'note'}] ${item.detail.body}`);
    if (item.detail?.hold?.reason) detailParts.push(item.detail.hold.reason);
    if (item.detail?.path) detailParts.push(`مسیر همپوشان: ${item.detail.path} (${item.detail.level || ''})`);
    if (detailParts.length) card.append(el('p', detailParts.join('\n'), 'inbox-detail'));

    const actions = el('div', '', 'card-actions');
    if (item.chat_id) {
      const jump = el('button', 'پرش به پرامپت گفتگو (o)', 'primary');
      jump.type = 'button';
      jump.onclick = e => { e.stopPropagation(); openPromptFor(item); };
      actions.append(jump);
    }
    if (item.worktree_id) {
      const diffBtn = el('button', 'فصل‌بندی تغییرات · Diff Chapters (d)');
      diffBtn.type = 'button';
      diffBtn.onclick = e => { e.stopPropagation(); openChapters(item.worktree_id).catch(showError); };
      actions.append(diffBtn);
    }
    if (item.kind === 'memory' && item.state === 'open') {
      const approveBtn = el('button', 'تأیید و ثبت در حافظهٔ گیت (a)', 'primary');
      approveBtn.type = 'button';
      approveBtn.onclick = async e => {
        e.stopPropagation();
        try {
          await api(`/api/parallel/attention/${encodeURIComponent(item.id)}/approve-memory`, {method: 'POST', body: '{}'});
          showNotice('حافظه در refs/flux/memory تأیید و ماندگار شد.');
          await refreshAll();
        } catch (err) { showError(err); }
      };
      actions.append(approveBtn);
    }
    if (item.state === 'open') {
      const resolveBtn = el('button', 'حل شد (r)');
      resolveBtn.type = 'button';
      resolveBtn.onclick = async e => {
        e.stopPropagation();
        try {
          await api(`/api/parallel/attention/${encodeURIComponent(item.id)}/resolve`, {method: 'POST', body: '{}'});
          await loadAttention();
          await loadOverview();
        } catch (err) { showError(err); }
      };
      const dismissBtn = el('button', 'نادیده');
      dismissBtn.type = 'button';
      dismissBtn.onclick = async e => {
        e.stopPropagation();
        try {
          await api(`/api/parallel/attention/${encodeURIComponent(item.id)}/resolve?dismiss=true`, {method: 'POST', body: '{}'});
          await loadAttention();
          await loadOverview();
        } catch (err) { showError(err); }
      };
      actions.append(resolveBtn, dismissBtn);
    }
    card.append(actions);

    if (item.chat_id && item.state === 'open') {
      const replyForm = el('form', '', 'quick-reply');
      const replyInput = el('input');
      replyInput.id = `quick-reply-${idx}`;
      replyInput.placeholder = 'پاسخ سریع یا دستور رفع انسداد را همین‌جا بنویسید و Enter بزنید…';
      const replyBtn = el('button', 'ارسال به عامل', 'primary');
      replyBtn.type = 'submit';
      replyForm.append(replyInput, replyBtn);
      replyForm.onclick = e => e.stopPropagation();
      replyForm.onsubmit = async e => {
        e.preventDefault();
        const prompt = replyInput.value.trim();
        if (!prompt) return;
        replyBtn.disabled = true;
        try {
          await api(`/api/local/chats/${encodeURIComponent(item.chat_id)}/turns`, {
            method: 'POST',
            body: JSON.stringify({prompt, request_key: 'attn-' + crypto.randomUUID(), use_memory: true})
          });
          replyInput.value = '';
          showNotice('پاسخ ارسال شد و عامل دوباره فعال گردید.');
          await refreshAll();
        } catch (err) { showError(err); }
        finally { replyBtn.disabled = false; }
      };
      card.append(replyForm);
    }
    container.append(card);
  });
}

function renderWorktrees() {
  const container = $('worktree-list');
  container.replaceChildren();
  if (!state.worktrees.length) {
    container.append(el('p', 'هنوز Worktree ایزوله‌ای ساخته نشده است.', 'muted'));
    return;
  }
  for (const wt of state.worktrees) {
    const card = el('article', '', 'entity-card');
    const head = el('div', '', 'inbox-top');
    head.append(el('strong', wt.name), el('span', wt.branch, 'kv-chip'));
    card.append(head, el('small', wt.path, 'muted'));

    const chips = el('div', '', 'kv-list');
    for (const [k, v] of Object.entries(wt.ports || {})) {
      chips.append(el('span', `${k}=${v}`, 'kv-chip'));
    }
    if (wt.env?.DATABASE_URL) {
      const dbLabel = wt.env.DATABASE_URL.startsWith('postgres') ? 'DB=postgres(ephemeral)' : 'DB=sqlite(isolated)';
      chips.append(el('span', dbLabel, 'kv-chip'));
    }
    card.append(chips);

    if (wt.links?.length) {
      const linkRow = el('div', '', 'card-actions');
      for (const link of wt.links) {
        const chip = el('span', `${link.name}: ${link.status}`, 'badge');
        linkRow.append(chip);
        if (link.status === 'linked') {
          const unshare = el('button', `جداسازی ${link.name}`);
          unshare.type = 'button';
          unshare.onclick = async () => {
            try {
              await api(`/api/parallel/worktrees/${encodeURIComponent(wt.id)}/unshare`, {
                method: 'POST',
                body: JSON.stringify({name: link.name})
              });
              showNotice(`لینک اشتراکی ${link.name} جدا شد.`);
              await loadWorktrees();
            } catch (err) { showError(err); }
          };
          linkRow.append(unshare);
        }
      }
      card.append(linkRow);
    }

    const actions = el('div', '', 'card-actions');
    const chatBtn = el('button', 'گفتگوی جدید در این محیط', 'primary');
    chatBtn.type = 'button';
    chatBtn.onclick = async () => {
      try {
        const chat = await api(`/api/parallel/worktrees/${encodeURIComponent(wt.id)}/chats`, {
          method: 'POST',
          body: JSON.stringify({provider: 'codex', access: 'work'})
        });
        location.href = `/chat?chat_id=${encodeURIComponent(chat.id)}&focus=prompt`;
      } catch (err) { showError(err); }
    };

    const diffBtn = el('button', 'فصل‌بندی تغییرات (Diff Chapters)');
    diffBtn.type = 'button';
    diffBtn.onclick = () => openChapters(wt.id).catch(showError);

    const overlapBtn = el('button', 'بررسی همپوشانی');
    overlapBtn.type = 'button';
    overlapBtn.onclick = () => openOverlaps(wt.id, wt.name).catch(showError);

    const commitBtn = el('button', 'ثبت Commit');
    commitBtn.type = 'button';
    commitBtn.onclick = async () => {
      try {
        const res = await api(`/api/parallel/worktrees/${encodeURIComponent(wt.id)}/commit`, {
          method: 'POST',
          body: JSON.stringify({message: `flux(${wt.name}): checkpoint`})
        });
        showNotice(res.commit ? `کامیت ثبت شد: ${res.commit.slice(0, 10)}` : 'تغییری برای کامیت وجود نداشت.');
      } catch (err) { showError(err); }
    };

    const rmBtn = el('button', 'حذف Worktree');
    rmBtn.type = 'button';
    rmBtn.onclick = async () => {
      try {
        await api(`/api/parallel/worktrees/${encodeURIComponent(wt.id)}`, {method: 'DELETE'});
        showNotice(`محیط ${wt.name} پاک‌سازی شد.`);
        await refreshAll();
      } catch (err) { showError(err); }
    };

    actions.append(chatBtn, diffBtn, overlapBtn, commitBtn, rmBtn);
    card.append(actions);
    container.append(card);
  }
}

function renderPipelines() {
  const container = $('pipeline-list');
  container.replaceChildren();
  if (!state.pipelines.length) {
    container.append(el('p', 'هنوز پایپلاینی ثبت نشده است.', 'muted'));
    return;
  }
  for (const pipe of state.pipelines) {
    const card = el('article', '', 'entity-card');
    const top = el('div', '', 'inbox-top');
    top.append(
      el('strong', `${pipe.name} (${pipe.id})`),
      el('span', pipe.state, `badge ${pipe.state}`)
    );
    card.append(top);
    if (pipe.error) card.append(el('p', pipe.error, 'inbox-detail'));

    const tiersWrap = el('div', '', 'dag-tiers');
    const byId = new Map((pipe.steps || []).map(s => [s.id, s]));
    (pipe.tiers || []).forEach((tierIds, idx) => {
      const col = el('div', '', 'dag-tier');
      col.append(el('small', `سطح وابستگی ${faNum(idx)}`, 'muted'));
      for (const sid of tierIds) {
        const step = byId.get(sid);
        if (!step) continue;
        const box = el('div', '', 'dag-step');
        const stHead = el('div', '', 'inbox-top');
        stHead.append(el('strong', step.title || step.id), el('span', stepNames[step.state] || step.state, `badge ${step.state}`));
        box.append(stHead);
        if (step.depends_on?.length) {
          box.append(el('small', `پس از پاس شدن: ${step.depends_on.join(', ')}`, 'muted'));
        }
        for (const gate of (step.gate_results || [])) {
          const g = el('details');
          g.append(el('summary', `${gate.passed ? '✓' : '✗'} ${gate.name} (${gate.seconds}s)`));
          if (gate.output) g.append(el('pre', gate.output, 'diff-box'));
          box.append(g);
        }
        if (step.error) box.append(el('small', step.error, 'inbox-detail'));
        const stActions = el('div', '', 'card-actions');
        if (step.chat_id) {
          const openBtn = el('button', 'گفتگو');
          openBtn.type = 'button';
          openBtn.onclick = () => { location.href = `/chat?chat_id=${encodeURIComponent(step.chat_id)}&focus=prompt`; };
          stActions.append(openBtn);
        }
        if (step.worktree_id) {
          const chBtn = el('button', 'Diff Chapters');
          chBtn.type = 'button';
          chBtn.onclick = () => openChapters(step.worktree_id).catch(showError);
          stActions.append(chBtn);
        }
        if (stActions.childNodes.length) box.append(stActions);
        col.append(box);
      }
      tiersWrap.append(col);
    });
    card.append(tiersWrap);

    const actions = el('div', '', 'card-actions');
    if (pipe.state === 'draft') {
      const b = el('button', 'شروع پایپلاین', 'primary');
      b.type = 'button';
      b.onclick = () => api(`/api/parallel/pipelines/${encodeURIComponent(pipe.id)}/start`, {method: 'POST', body: '{}'}).then(refreshAll).catch(showError);
      actions.append(b);
    }
    if (pipe.state === 'paused') {
      const b = el('button', 'ادامهٔ گام‌های قطع‌شده', 'primary');
      b.type = 'button';
      b.onclick = () => api(`/api/parallel/pipelines/${encodeURIComponent(pipe.id)}/resume`, {method: 'POST', body: '{}'}).then(refreshAll).catch(showError);
      actions.append(b);
    }
    if (pipe.state === 'running') {
      const b = el('button', 'توقف پایپلاین');
      b.type = 'button';
      b.onclick = () => api(`/api/parallel/pipelines/${encodeURIComponent(pipe.id)}/cancel`, {method: 'POST', body: '{}'}).then(refreshAll).catch(showError);
      actions.append(b);
    }
    card.append(actions);
    container.append(card);
  }
}

function renderWiki() {
  const container = $('wiki-entries');
  const histBox = $('wiki-history');
  container.replaceChildren();
  histBox.replaceChildren();
  const projectId = $('wiki-project').value;
  $('wiki-head-info').textContent = state.wiki.head
    ? `مرجع گیت refs/flux/memory روی کامیت ${state.wiki.head.slice(0, 12)}`
    : 'هنوز هیچ رکوردی در refs/flux/memory این مخزن ثبت نشده است.';

  if (!state.wiki.entries?.length) {
    container.append(el('p', 'حافظهٔ گیت برای این پروژه خالی است.', 'muted'));
  }
  for (const entry of (state.wiki.entries || [])) {
    const card = el('article', '', 'entity-card');
    const top = el('div', '', 'inbox-top');
    const left = el('div', '', 'card-actions');
    if (entry.pinned) left.append(el('span', '★ سنجاق‌شده', 'badge review'));
    left.append(el('span', entry.kind, 'kv-chip'), el('strong', entry.title));
    top.append(left, el('span', entry.status, `badge ${entry.status}`));
    card.append(top, el('p', entry.body, 'inbox-detail'));

    const actions = el('div', '', 'card-actions');
    if (entry.status !== 'verified') {
      const verifyBtn = el('button', 'تأیید', 'primary');
      verifyBtn.type = 'button';
      verifyBtn.onclick = () => api(`/api/parallel/projects/${encodeURIComponent(projectId)}/wiki/${encodeURIComponent(entry.id)}`, {
        method: 'PATCH', body: JSON.stringify({status: 'verified'})
      }).then(loadWiki).catch(showError);
      actions.append(verifyBtn);
    }
    if (entry.status !== 'retired') {
      const retireBtn = el('button', 'بازنشسته');
      retireBtn.type = 'button';
      retireBtn.onclick = () => api(`/api/parallel/projects/${encodeURIComponent(projectId)}/wiki/${encodeURIComponent(entry.id)}`, {
        method: 'PATCH', body: JSON.stringify({status: 'retired'})
      }).then(loadWiki).catch(showError);
      actions.append(retireBtn);
    }
    const delBtn = el('button', 'حذف');
    delBtn.type = 'button';
    delBtn.onclick = () => api(`/api/parallel/projects/${encodeURIComponent(projectId)}/wiki/${encodeURIComponent(entry.id)}`, {
      method: 'DELETE'
    }).then(loadWiki).catch(showError);
    actions.append(delBtn);
    card.append(actions);
    container.append(card);
  }

  for (const h of state.wikiHistory) {
    histBox.append(el('p', `${h.commit.slice(0, 10)} · ${h.time} · ${h.message}`, 'muted'));
  }
}

async function openChapters(worktreeId) {
  const data = await api(`/api/parallel/worktrees/${encodeURIComponent(worktreeId)}/chapters?patch=true`);
  $('chapters-summary').textContent = `${faNum(data.files)} فایل تغییر یافته · +${faNum(data.added)} / -${faNum(data.removed)} خط نسبت به ${data.base.slice(0, 10)}`;
  const toc = $('chapters-toc');
  const body = $('chapters-body');
  toc.replaceChildren();
  body.replaceChildren();
  if (!data.chapters.length) {
    body.append(el('p', 'هیچ تغییری نسبت به شاخهٔ مبنا ثبت نشده است.', 'muted'));
  }
  data.chapters.forEach((ch, index) => {
    const id = `chapter-sec-${index}`;
    const jump = el('button', `${faNum(index + 1)}. ${ch.title} (+${ch.added}/-${ch.removed})`);
    jump.type = 'button';
    jump.onclick = () => document.getElementById(id)?.scrollIntoView({behavior: 'smooth'});
    toc.append(jump);

    const card = el('section', '', 'chapter-card');
    card.id = id;
    const head = el('div', '', 'inbox-top');
    head.append(
      el('strong', `${faNum(index + 1)}. ${ch.title}`),
      el('span', `ریسک: ${ch.risk} · +${ch.added} / -${ch.removed}`, `badge ${ch.risk === 'high' ? 'blocked' : ch.risk === 'medium' ? 'warning' : 'review'}`)
    );
    card.append(head);

    const filesWrap = el('div', '', 'kv-list');
    for (const f of ch.files) {
      filesWrap.append(el('span', `${f.path} (+${f.added}/-${f.removed})`, 'kv-chip'));
    }
    card.append(filesWrap);

    if (ch.patch) {
      const box = el('div', '', 'diff-box');
      for (const line of ch.patch.split('\n')) {
        const cls = line.startsWith('@@') ? 'diff-line diff-hunk'
          : (line.startsWith('+') && !line.startsWith('+++')) ? 'diff-line diff-add'
          : (line.startsWith('-') && !line.startsWith('---')) ? 'diff-line diff-del'
          : 'diff-line';
        box.append(el('div', line, cls));
      }
      card.append(box);
    }
    body.append(card);
  });
  $('chapters-dialog').showModal();
}

async function openOverlaps(worktreeId, name) {
  const items = await api(`/api/parallel/worktrees/${encodeURIComponent(worktreeId)}/overlaps?all=true`);
  $('overlaps-title').textContent = `بررسی همپوشانی کد برای «${name}»`;
  const body = $('overlaps-body');
  body.replaceChildren();
  if (!items.length) {
    body.append(el('p', 'هیچ تداخل فایل، تابع یا دامنه با سایر Worktreeهای فعال دیده نشد.', 'muted'));
  }
  for (const f of items) {
    const card = el('div', '', 'entity-card');
    card.append(
      el('strong', `[${f.level}] ${f.path} ↔ ${f.other_name}`),
      el('p', (f.symbols?.length ? `توابع/کلاس‌های مشترک: ${f.symbols.join(', ')}` : 'همپوشانی فایل یا دامنه'), 'muted')
    );
    body.append(card);
  }
  $('overlaps-dialog').showModal();
}

async function loadProjects() {
  state.projects = await api('/projects');
  populateProjects();
}
async function loadOverview() {
  state.overview = await api('/api/parallel/overview');
  renderTelemetry();
}
async function loadAttention() {
  const data = await api(`/api/parallel/attention?state=${state.inboxFilter}`);
  state.inbox = data.items || [];
  renderInbox();
}
async function loadWorktrees() {
  state.worktrees = await api('/api/parallel/worktrees');
  renderWorktrees();
}
async function loadPipelines() {
  state.pipelines = await api('/api/parallel/pipelines');
  renderPipelines();
}
async function loadWiki() {
  const projectId = $('wiki-project').value;
  if (!projectId) {
    state.wiki = {head: '', entries: []};
    state.wikiHistory = [];
    renderWiki();
    return;
  }
  try {
    state.wiki = await api(`/api/parallel/projects/${encodeURIComponent(projectId)}/wiki`);
    state.wikiHistory = await api(`/api/parallel/projects/${encodeURIComponent(projectId)}/wiki-history`);
  } catch (_) {
    state.wiki = {head: '', entries: []};
    state.wikiHistory = [];
  }
  renderWiki();
}

async function refreshAll() {
  await Promise.all([loadOverview(), loadAttention(), loadWorktrees(), loadPipelines()]);
  await loadWiki();
}

function connectStream() {
  if (state.stream) state.stream.close();
  const es = new EventSource('/api/parallel/events/stream');
  state.stream = es;
  es.onopen = () => {
    $('stat-stream').textContent = 'جریان زنده: متصل';
    $('stat-stream').className = 'pill ok';
  };
  es.onerror = () => {
    $('stat-stream').textContent = 'جریان زنده: قطع / تلاش مجدد…';
    $('stat-stream').className = 'pill';
  };
  const onEvent = ev => {
    try {
      const payload = JSON.parse(ev.data || '{}');
      if (payload.kind === 'attention.raised' && state.notifyEnabled && 'Notification' in window && Notification.permission === 'granted') {
        const item = payload.payload || {};
        if ((item.priority ?? 9) <= 1) {
          const n = new Notification('Flux · نیاز به توجه شما', {body: item.title || ''});
          n.onclick = () => { window.focus(); openPromptFor(item); };
        }
      }
    } catch (_) {}
    refreshAll().catch(() => {});
  };
  for (const name of ['attention.raised', 'attention.resolved', 'turn.state', 'turn.deferred', 'worktree.created', 'worktree.removed', 'pipeline.step', 'pipeline.state', 'memory.changed', 'overlap.scan']) {
    es.addEventListener(name, onEvent);
  }
}

// Tabs
for (const btn of document.querySelectorAll('[role="tab"]')) {
  btn.onclick = () => {
    for (const other of document.querySelectorAll('[role="tab"]')) {
      const active = other === btn;
      other.setAttribute('aria-selected', String(active));
      $(other.getAttribute('aria-controls')).hidden = !active;
    }
  };
}

// Filters & Header buttons
$('filter-open').onclick = () => {
  state.inboxFilter = 'open';
  $('filter-open').classList.add('active');
  $('filter-all').classList.remove('active');
  loadAttention().catch(showError);
};
$('filter-all').onclick = () => {
  state.inboxFilter = 'all';
  $('filter-all').classList.add('active');
  $('filter-open').classList.remove('active');
  loadAttention().catch(showError);
};
$('refresh-all-btn').onclick = () => refreshAll().catch(showError);
$('scan-overlaps-btn').onclick = async () => {
  try {
    const res = await api('/api/parallel/overlaps/scan', {method: 'POST', body: '{}'});
    showNotice(`پایش انجام شد؛ ${faNum(res.length)} همپوشانی شناسایی گردید.`);
    await refreshAll();
  } catch (err) { showError(err); }
};
$('max-parallel-input').onchange = async () => {
  try {
    const val = Math.max(1, Math.min(16, Number($('max-parallel-input').value) || 3));
    await api('/api/parallel/settings', {method: 'PUT', body: JSON.stringify({max_parallel: val})});
    await loadOverview();
  } catch (err) { showError(err); }
};
$('notify-toggle-btn').onclick = async () => {
  if (!('Notification' in window)) {
    showError('مرورگر شما از Web Notification پشتیبانی نمی‌کند.');
    return;
  }
  const perm = await Notification.requestPermission();
  state.notifyEnabled = perm === 'granted';
  $('notify-toggle-btn').textContent = state.notifyEnabled ? 'اعلان مرورگر: روشن ✓' : 'اعلان مرورگر: رد شد';
};

// Forms
$('worktree-form').onsubmit = async e => {
  e.preventDefault();
  try {
    const scope = $('wt-scope').value.split(',').map(s => s.trim()).filter(Boolean);
    const wt = await api('/api/parallel/worktrees', {
      method: 'POST',
      body: JSON.stringify({
        project_id: $('wt-project').value,
        name: $('wt-name').value.trim(),
        base: $('wt-base').value.trim() || 'HEAD',
        scope
      })
    });
    $('wt-name').value = '';
    showNotice(`محیط ایزولهٔ «${wt.name}» با پورت‌های اختصاصی آماده شد.`);
    await refreshAll();
  } catch (err) { showError(err); }
};

$('plan-form').onsubmit = async e => {
  e.preventDefault();
  const objective = $('plan-objective').value.trim();
  if (!objective) return;
  const btn = $('plan-form').querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = 'در حال تحلیل و طراحی گراف با ارکستراتور…';
  try {
    const res = await api('/api/parallel/pipelines/plan', {
      method: 'POST',
      body: JSON.stringify({
        project_id: $('plan-project').value,
        objective,
        provider: $('plan-provider').value
      })
    });
    $('pipe-project').value = res.spec.project_id;
    $('pipe-name').value = res.spec.name;
    $('pipe-steps').value = JSON.stringify(res.spec.steps, null, 2);
    showNotice('گراف وابستگی پیشنهاد شد؛ گام‌ها را بازبینی و ثبت کنید.');
  } catch (err) { showError(err); }
  finally {
    btn.disabled = false;
    btn.textContent = 'شکستن به گام‌های DAG (پیش‌نمایش)';
  }
};

$('pipeline-form').onsubmit = async e => {
  e.preventDefault();
  try {
    const steps = JSON.parse($('pipe-steps').value);
    const start = $('pipe-autostart').checked;
    await api(`/api/parallel/pipelines?start=${start}`, {
      method: 'POST',
      body: JSON.stringify({
        project_id: $('pipe-project').value,
        name: $('pipe-name').value.trim(),
        steps
      })
    });
    showNotice(start ? 'پایپلاین ثبت و اجرا آغاز شد.' : 'پایپلاین در حالت پیش‌نویس ثبت شد.');
    await refreshAll();
  } catch (err) { showError(err); }
};

$('wiki-project').onchange = () => loadWiki().catch(showError);
$('wiki-form').onsubmit = async e => {
  e.preventDefault();
  const projectId = $('wiki-project').value;
  if (!projectId) return;
  try {
    await api(`/api/parallel/projects/${encodeURIComponent(projectId)}/wiki`, {
      method: 'POST',
      body: JSON.stringify({
        title: $('wiki-title').value.trim(),
        body: $('wiki-body').value.trim(),
        kind: $('wiki-kind').value,
        pinned: $('wiki-pinned').checked,
        status: 'verified'
      })
    });
    $('wiki-title').value = '';
    $('wiki-body').value = '';
    $('wiki-pinned').checked = false;
    showNotice('نکته در مرجع گیت refs/flux/memory ثبت شد.');
    await loadWiki();
  } catch (err) { showError(err); }
};

$('close-chapters').onclick = () => $('chapters-dialog').close();
$('close-overlaps').onclick = () => $('overlaps-dialog').close();

// Keyboard shortcuts for instant unblocking
document.addEventListener('keydown', e => {
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || document.querySelector('dialog[open]')) return;
  if (!state.inbox.length) return;
  if (e.key === 'j' || e.key === 'ArrowDown') {
    e.preventDefault();
    state.selectedIndex = (state.selectedIndex + 1) % state.inbox.length;
    renderInbox();
  } else if (e.key === 'k' || e.key === 'ArrowUp') {
    e.preventDefault();
    state.selectedIndex = (state.selectedIndex - 1 + state.inbox.length) % state.inbox.length;
    renderInbox();
  } else if (e.key >= '1' && e.key <= '9') {
    const idx = Number(e.key) - 1;
    if (idx < state.inbox.length) {
      e.preventDefault();
      state.selectedIndex = idx;
      renderInbox();
    }
  } else if (e.key === 'Enter') {
    const input = $(`quick-reply-${state.selectedIndex}`);
    if (input) { e.preventDefault(); input.focus(); }
    else if (state.inbox[state.selectedIndex]?.chat_id) { e.preventDefault(); openPromptFor(state.inbox[state.selectedIndex]); }
  } else if (e.key === 'o') {
    const item = state.inbox[state.selectedIndex];
    if (item?.chat_id) { e.preventDefault(); openPromptFor(item); }
  } else if (e.key === 'd') {
    const item = state.inbox[state.selectedIndex];
    if (item?.worktree_id) { e.preventDefault(); openChapters(item.worktree_id).catch(showError); }
  } else if (e.key === 'a') {
    const item = state.inbox[state.selectedIndex];
    if (item?.kind === 'memory' && item.state === 'open') {
      e.preventDefault();
      api(`/api/parallel/attention/${encodeURIComponent(item.id)}/approve-memory`, {method: 'POST', body: '{}'}).then(refreshAll).catch(showError);
    }
  } else if (e.key === 'r') {
    const item = state.inbox[state.selectedIndex];
    if (item?.state === 'open') {
      e.preventDefault();
      api(`/api/parallel/attention/${encodeURIComponent(item.id)}/resolve`, {method: 'POST', body: '{}'}).then(refreshAll).catch(showError);
    }
  }
});

(async () => {
  $('pipe-steps').value = JSON.stringify(DEFAULT_STEPS, null, 2);
  try {
    await loadProjects();
    await refreshAll();
  } catch (err) {
    showError(err);
  }
  connectStream();
})();

