"""Durable contract, scheduler, evidence gates and exact-version human acceptance.

This service never executes arbitrary model-suggested tools. Dispatch is to a fresh
read-only official CLI session; pytest is a separate explicitly authorized action.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import time
import threading
import uuid
from flux.core.budget import SharedBudget
from flux.core.contracts import Contract, Review, Evidence, TRANSITIONS
from flux.knowledge.retrieval import digest
from flux.storage.workspace import clean_text, now


def uid(prefix):return prefix+'_'+uuid.uuid4().hex


class CoreService:
    def __init__(self, repo, workspace):
        self.repo,self.conn,self.workspace=repo,repo.conn,workspace
        self._transactions=threading.local()
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS core_tasks (
            id TEXT PRIMARY KEY, root_id TEXT NOT NULL, parent_id TEXT,
            project_id TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL,
            contract TEXT NOT NULL, contract_hash TEXT NOT NULL, state TEXT NOT NULL,
            artifact TEXT, artifact_hash TEXT, manifest TEXT NOT NULL DEFAULT '{}',
            review TEXT, review_revision INTEGER NOT NULL DEFAULT 0,
            generations INTEGER NOT NULL DEFAULT 0, repair_methods TEXT NOT NULL DEFAULT '[]',
            checkpoint TEXT NOT NULL DEFAULT 'generation', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS core_roots (
            id TEXT PRIMARY KEY, calls INTEGER NOT NULL DEFAULT 0,
            active_seconds REAL NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS core_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS core_operations (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, request_hash TEXT NOT NULL,
            phase TEXT NOT NULL, state TEXT NOT NULL, lease_until REAL,
            turn_id TEXT, chat_id TEXT, provider TEXT, started REAL,
            reservation_id TEXT, usage TEXT, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS core_evidence (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, artifact_hash TEXT NOT NULL,
            evidence_type TEXT NOT NULL, content TEXT NOT NULL, content_hash TEXT NOT NULL,
            outcome TEXT NOT NULL, source_ref TEXT NOT NULL, origin TEXT NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS core_acceptances (
            task_id TEXT PRIMARY KEY, artifact_hash TEXT NOT NULL, contract_hash TEXT NOT NULL,
            review_revision INTEGER NOT NULL, actor TEXT NOT NULL, accepted_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS core_outbox (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL,
            payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
        ''')
        self.conn.commit()
        with self.conn:
            columns={r[1] for r in self.conn.execute('PRAGMA table_info(core_operations)')}
            if 'source_manifest' not in columns:self.conn.execute("ALTER TABLE core_operations ADD COLUMN source_manifest TEXT NOT NULL DEFAULT '{}'")
            if 'accounted_seconds' not in columns:self.conn.execute('ALTER TABLE core_operations ADD COLUMN accounted_seconds REAL NOT NULL DEFAULT 0')
            if 'response' not in columns:self.conn.execute('ALTER TABLE core_operations ADD COLUMN response TEXT')
            if 'output_limit' not in columns:self.conn.execute('ALTER TABLE core_operations ADD COLUMN output_limit INTEGER NOT NULL DEFAULT 0')
            if 'model' not in columns:self.conn.execute("ALTER TABLE core_operations ADD COLUMN model TEXT NOT NULL DEFAULT ''")
        self.budget=SharedBudget(self.conn)
        with self.atomic():
            self.budget.account('company:local',None,100_000_000)

    @contextmanager
    def atomic(self):
        with self.repo._lock:
            depth=getattr(self._transactions,'depth',0)
            savepoint='core_'+uuid.uuid4().hex
            self.conn.execute('SAVEPOINT '+savepoint if depth else 'BEGIN IMMEDIATE')
            self._transactions.depth=depth+1
            try:
                yield
            except BaseException:
                if depth:
                    self.conn.execute('ROLLBACK TO '+savepoint);self.conn.execute('RELEASE '+savepoint)
                else:self.conn.rollback()
                raise
            else:
                if depth:self.conn.execute('RELEASE '+savepoint)
                else:self.conn.commit()
            finally:self._transactions.depth=depth

    def event(self, task_id, kind, payload):
        self.conn.execute('INSERT INTO core_events (task_id,kind,payload,created_at) VALUES (?,?,?,?)',(task_id,kind,json.dumps(payload,ensure_ascii=False),now()))

    def task(self, ident):
        with self.repo._lock:return self._task(ident)

    def _task(self, ident):
        row=self.conn.execute('SELECT * FROM core_tasks WHERE id=?',(ident,)).fetchone()
        if not row:raise KeyError(ident)
        item=dict(row)
        for key in ('contract','manifest','review','repair_methods'):
            item[key]=json.loads(item[key]) if item[key] else None
        item['operations']=[dict(r) for r in self.conn.execute('SELECT * FROM core_operations WHERE task_id=? ORDER BY created_at',(ident,))]
        item['evidence']=[dict(r) for r in self.conn.execute('SELECT * FROM core_evidence WHERE task_id=?',(ident,))]
        acceptance=self.conn.execute('SELECT * FROM core_acceptances WHERE task_id=?',(ident,)).fetchone()
        item['acceptance']=dict(acceptance) if acceptance else None
        item['root_counters']=dict(self.conn.execute('SELECT * FROM core_roots WHERE id=?',(item['root_id'],)).fetchone())
        item['budget']=self.budget.ancestors('task:'+ident)
        return item

    def tasks(self):
        return [self.task(r[0]) for r in self.conn.execute('SELECT id FROM core_tasks ORDER BY created_at DESC LIMIT 100')]

    def transition(self, ident, target, reason):
        current=self.conn.execute('SELECT state,checkpoint,artifact_hash FROM core_tasks WHERE id=?',(ident,)).fetchone()
        if not current:raise KeyError(ident)
        if target not in TRANSITIONS[current['state']]:raise ValueError(f'Invalid transition {current["state"]} -> {target}')
        if current['state']=='READY' and target=='REVIEWING' and (current['checkpoint']!='review' or not current['artifact_hash']):
            raise ValueError('A review checkpoint and artifact are required.')
        self.conn.execute('UPDATE core_tasks SET state=?,updated_at=? WHERE id=?',(target,now(),ident))
        self.event(ident,'state',{'from':current['state'],'to':target,'reason':reason})

    def register(self, contract):
        contract=Contract.model_validate(contract)
        project=self.workspace.get_project(contract.project_id)
        if not project or project['archived']:raise ValueError('Active registered project required.')
        if not Path(project['path']).is_dir():raise ValueError('Project folder is unavailable.')
        root_path=Path(project['path']).resolve()
        for relative in contract.allowed_paths:
            path=(root_path/relative).resolve()
            if not path.is_relative_to(root_path) or not path.is_file() or path.stat().st_size>300_000:raise ValueError('Only explicit existing project files under 300 KB may be bound.')
        clean_text(contract.model_dump_json(),60000)
        payload=contract.model_dump(mode='json');hash_=digest(payload)
        ident=uid('head')
        with self.atomic():
            prior=self.conn.execute('SELECT id,contract_hash FROM core_tasks WHERE request_key=?',(contract.request_key,)).fetchone()
            if prior:
                if prior['contract_hash']!=hash_:raise ValueError('Request key payload conflict.')
                ident=prior['id']
            else:
                parent=self.task(contract.parent_task_id) if contract.parent_task_id else None
                if parent:
                    if parent['parent_id'] or parent['state'] not in {'READY','NEEDS_INFO'}:raise ValueError('Parent cannot be decomposed now.')
                    root=parent['id'];root_contract=Contract.model_validate(parent['contract'])
                    if root_contract.project_id!=contract.project_id or root_contract.department_id!=contract.department_id:raise ValueError('Cross-project/department child denied.')
                    if root_contract.limits.max_depth<1:raise ValueError('Depth cap reached.')
                    count=self.conn.execute('SELECT COUNT(*) FROM core_tasks WHERE parent_id=?',(root,)).fetchone()[0]
                    if count>=root_contract.limits.max_children:raise ValueError('Child count cap reached.')
                    if not set(contract.allowed_tools)<=set(root_contract.allowed_tools) or not set(contract.allowed_paths)<=set(root_contract.allowed_paths):raise ValueError('Child authority cannot exceed parent.')
                    if contract.billing!=root_contract.billing or contract.execution_provider!=root_contract.execution_provider or contract.budget_cap_micros>root_contract.budget_cap_micros:raise ValueError('Child billing/provider/budget exceeds parent.')
                    if any(getattr(contract.limits,k)>v for k,v in root_contract.limits.model_dump().items()):raise ValueError('Child limits exceed parent.')
                    parent_criteria={c.criterion_id:c for c in root_contract.acceptance_criteria}
                    if any(c.criterion_id not in parent_criteria or c!=parent_criteria[c.criterion_id] for c in contract.acceptance_criteria):raise ValueError('Child criteria must match immutable parent criteria.')
                else:root=ident
                for dependency in contract.dependencies:
                    dep=self.task(dependency)
                    if dep['root_id']!=root or dep['parent_id']!=contract.parent_task_id:raise ValueError('Dependency must be an existing sibling in the same root.')
                self.conn.execute('INSERT INTO core_tasks (id,root_id,parent_id,project_id,request_key,contract,contract_hash,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,\'REGISTERED\',?,?)',
                                  (ident,root,contract.parent_task_id,contract.project_id,contract.request_key,contract.model_dump_json(),hash_,now(),now()))
                if not parent:self.conn.execute('INSERT INTO core_roots(id) VALUES (?)',(root,))
                department='department:'+contract.department_id
                self.budget.account(department,'company:local',100_000_000)
                project_account='project:'+contract.project_id
                existing=self.conn.execute('SELECT parent_id FROM core_budget_accounts WHERE id=?',(project_account,)).fetchone()
                if existing and existing[0]!=department:raise ValueError('Project already belongs to another department.')
                self.budget.account(project_account,department,100_000_000)
                parent_budget='task:'+contract.parent_task_id if parent else project_account
                self.budget.account('task:'+ident,parent_budget,contract.budget_cap_micros,contract.review_reserve_micros)
                self.event(ident,'registered',{'contract_hash':hash_,'policy_revision':contract.policy_revision,'actor':'local-user'})
                self.transition(ident,'READY','Validated frozen contract; the local user request authorizes execution.')
        return self.task(ident)

    def manifest(self, task):
        project=self.workspace.get_project(task['project_id'])
        if not project or project['archived']:raise ValueError('Project is not active.')
        root=Path(project['path']).resolve();result={}
        for relative in task['contract']['allowed_paths']:
            path=(root/relative).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size>300_000:
                raise ValueError('Artifact source path must be an explicit project file under 300 KB.')
            result[relative]=digest(path.read_bytes().hex())
        return result

    def fresh(self, task):
        if task['manifest']!=self.manifest(task):raise ValueError('Source revision changed; generate and review a new artifact.')

    def decision(self, ident):
        task=self.task(ident);state=task['state'];contract=Contract.model_validate(task['contract'])
        root=Contract.model_validate(self.task(task['root_id'])['contract'])
        counters=task['root_counters']
        action={'READY':'GENERATE','REVIEWING':'REVIEW','ACCEPT_CANDIDATE':'WAIT_HUMAN_ACCEPTANCE','NEEDS_REVISION':'REPAIR'}.get(state,'WAIT')
        reason=state
        if state=='READY':
            if task['checkpoint']=='review':action='REVIEW'
            elif task['generations']>=contract.limits.max_generation_attempts:action='ESCALATE';reason='generation limit'
            children=[self.task(r[0]) for r in self.conn.execute('SELECT id FROM core_tasks WHERE parent_id=?',(ident,))]
            owned={c['criterion_id'] for child in children for c in child['contract']['acceptance_criteria']}
            if children and not {c.criterion_id for c in contract.acceptance_criteria if c.required}<=owned:action='WAIT';reason='plan leaves required criteria unowned'
            dependencies=[self.task(d) for d in contract.dependencies]+children
            for dep in dependencies:
                if dep['state'] not in {'ACCEPT_CANDIDATE','ACCEPTED'} or not dep['artifact_hash']:action='WAIT';reason='dependency artifact/criteria gate'
                else:
                    try:self.fresh(dep)
                    except ValueError:action='WAIT';reason='dependency source revision changed'
        if action in {'GENERATE','REVIEW'}:
            if counters['calls']>=root.limits.max_calls:action='ESCALATE';reason='root call limit'
            elif counters['active_seconds']>=root.limits.max_active_seconds:action='ESCALATE';reason='root time limit'
        return {'task_id':ident,'action':action,'reason':reason,'state':state,'model_proposal_authority':False,'counters':counters}

    def claim(self, ident, operation_key, phase='generation', provider='codex', model='', amount_micros=0,output_limit=0):
        if provider not in {'codex','claude','gemini','gapcode','gapgpt'}:raise ValueError('Unsupported execution provider.')
        request={'task':ident,'phase':phase,'provider':provider,'model':model,'amount':amount_micros,'output_limit':output_limit}
        with self.atomic():
            prior=self.conn.execute('SELECT * FROM core_operations WHERE id=?',(operation_key,)).fetchone()
            if prior:
                if prior['request_hash']!=digest(request):raise ValueError('Operation key payload conflict.')
                return dict(prior)
            task=self.task(ident);contract=Contract.model_validate(task['contract']);root=Contract.model_validate(self.task(task['root_id'])['contract'])
            if provider!='gapgpt' and (provider!=contract.execution_provider or provider!=root.execution_provider):raise ValueError('Execution provider must match the frozen contract account.')
            expected='GENERATE' if phase=='generation' else 'REVIEW'
            decision=self.decision(ident)
            if decision['action']!=expected:raise ValueError('Dispatch denied: '+decision['reason'])
            if phase=='review':self.fresh(task)
            manifest=self.manifest(task)
            active=self.conn.execute("SELECT COUNT(*) FROM core_operations WHERE state IN ('dispatching','running')").fetchone()[0]
            root_active=self.conn.execute("SELECT COUNT(*) FROM core_operations o JOIN core_tasks t ON t.id=o.task_id WHERE t.root_id=? AND o.state IN ('dispatching','running')",(task['root_id'],)).fetchone()[0]
            if active>=2 or root_active>=root.limits.max_concurrency:raise ValueError('Concurrency capacity unavailable.')
            reservation=None
            if provider=='gapgpt':
                if contract.billing!='api' or amount_micros<=0:raise ValueError('API contract and priced reservation required.')
                reservation='api:'+operation_key
                admission=self.budget.reserve(reservation,'task:'+ident,amount_micros,'api:'+operation_key,review=phase=='review')
                if admission!='active':raise ValueError(admission)
            elif contract.billing!='subscription' or amount_micros!=0:raise ValueError('CLI dispatch uses subscription billing, not a fictitious CLI dollar cap.')
            if phase=='generation':
                self.transition(ident,'RUNNING','Generation admitted.')
                self.conn.execute('UPDATE core_tasks SET generations=generations+1 WHERE id=?',(ident,))
            elif task['state']=='READY':self.transition(ident,'REVIEWING','Resume review checkpoint.')
            self.conn.execute('UPDATE core_roots SET calls=calls+1 WHERE id=?',(task['root_id'],))
            remaining=root.limits.max_active_seconds-task['root_counters']['active_seconds']
            self.conn.execute('INSERT INTO core_operations (id,task_id,request_hash,phase,state,lease_until,provider,started,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                              (operation_key,ident,digest(request),phase,'dispatching',time.time()+min(remaining,contract.limits.max_active_seconds),provider,time.time(),now()))
            self.conn.execute('UPDATE core_operations SET source_manifest=? WHERE id=?',(json.dumps(manifest),operation_key))
            self.conn.execute('UPDATE core_operations SET model=?,output_limit=? WHERE id=?',(model,output_limit,operation_key))
            if reservation:self.conn.execute('UPDATE core_operations SET reservation_id=? WHERE id=?',(reservation,operation_key))
            self.event(ident,'dispatch_intent',request)
        return dict(self.conn.execute('SELECT * FROM core_operations WHERE id=?',(operation_key,)).fetchone())

    def bind(self, operation_key, chat_id, turn_id):
        with self.atomic():
            row=self.conn.execute('SELECT * FROM core_operations WHERE id=?',(operation_key,)).fetchone()
            if not row or row['state']!='dispatching':raise ValueError('Dispatch intent is not active.')
            self.conn.execute("UPDATE core_operations SET state='running',chat_id=?,turn_id=? WHERE id=?",(chat_id,turn_id,operation_key))
            self.event(row['task_id'],'dispatched',{'operation_key':operation_key,'turn_id':turn_id})

    def operation_failure(self, operation_key, reason, known_no_effect=False):
        with self.atomic():
            row=self.conn.execute('SELECT * FROM core_operations WHERE id=?',(operation_key,)).fetchone()
            if not row or row['state'] not in {'dispatching','running'}:return
            self.account_time(row)
            self.conn.execute("UPDATE core_operations SET state=? WHERE id=?",('failed' if known_no_effect else 'unknown',operation_key))
            task=self.task(row['task_id'])
            if task['state']=='RUNNING':self.transition(task['id'],'FAILED' if known_no_effect else 'RECOVERING',reason)
            elif task['state']=='REVIEWING':self.transition(task['id'],'ESCALATED',reason)
            self.event(task['id'],'operation_failed',{'operation_key':operation_key,'known_no_effect':known_no_effect,'reason':reason})

    def finish_api(self, operation_key, content, usage, cost_micros):
        with self.atomic():
            operation=self.conn.execute('SELECT * FROM core_operations WHERE id=?',(operation_key,)).fetchone()
            if not operation or operation['provider']!='gapgpt' or operation['state']!='dispatching':raise ValueError('API operation is not awaiting a receipt.')
            self.budget.settle(operation['reservation_id'],cost_micros)
            self.account_time(operation)
            self.conn.execute("UPDATE core_operations SET state='received',response=?,usage=? WHERE id=?",(content,json.dumps(usage),operation_key))
        return self.apply_api_receipt(operation_key)

    def apply_api_receipt(self, operation_key):
        # Effect and receipt completion commit together. Nested artifact/review
        # transactions use savepoints, so a crash cannot apply only half a gate.
        with self.atomic():return self._apply_api_receipt(operation_key)

    def _apply_api_receipt(self, operation_key):
        operation=dict(self.conn.execute('SELECT * FROM core_operations WHERE id=?',(operation_key,)).fetchone())
        if operation['state']!='received':return self.task(operation['task_id'])
        task=self.task(operation['task_id'])
        try:
            if json.loads(operation['source_manifest'])!=self.manifest(task):raise ValueError('Bound source changed during API execution.')
            from flux.engine.json_parser import parse_llm_json
            result=parse_llm_json(operation['response'])
            if operation['phase']=='generation':
                if not isinstance(result,dict) or not isinstance(result.get('content'),str):raise ValueError('Worker must return a JSON content string.')
                self.artifact(task['id'],result['content'],executor='api:'+operation_key)
            else:self.review(task['id'],result,reviewer='api:'+operation_key)
        except (ValueError,KeyError) as exc:
            with self.atomic():
                task=self.task(task['id'])
                if task['state'] in {'RUNNING','RECOVERING'}:self.transition(task['id'],'FAILED',str(exc)[:500])
                elif task['state']=='REVIEWING':self.transition(task['id'],'ESCALATED',str(exc)[:500])
        with self.atomic():self.conn.execute("UPDATE core_operations SET state='completed' WHERE id=?",(operation_key,))
        return self.task(task['id'])

    def account_time(self, operation):
        elapsed=max(0,min(time.time(),operation['lease_until'])-operation['started'])
        delta=max(0,elapsed-operation['accounted_seconds'])
        root=self.conn.execute('SELECT root_id FROM core_tasks WHERE id=?',(operation['task_id'],)).fetchone()[0]
        self.conn.execute('UPDATE core_roots SET active_seconds=active_seconds+? WHERE id=?',(delta,root))
        self.conn.execute('UPDATE core_operations SET accounted_seconds=? WHERE id=?',(max(elapsed,operation['accounted_seconds']),operation['id']))

    def artifact(self, ident, content, executor='local-user'):
        content=clean_text(content,60000)
        if not content:raise ValueError('Empty artifact.')
        with self.atomic():
            task=self.task(ident)
            if task['state'] not in {'RUNNING','RECOVERING'}:raise ValueError('Task is not awaiting an artifact.')
            manifest=self.manifest(task);hash_=digest({'content':content,'manifest':manifest,'contract_hash':task['contract_hash']})
            self.conn.execute("UPDATE core_tasks SET artifact=?,artifact_hash=?,manifest=?,review=NULL,checkpoint='review',updated_at=? WHERE id=?",(content,hash_,json.dumps(manifest),now(),ident))
            self.transition(ident,'REVIEWING','Actual artifact received; completion is not acceptance.')
            self.event(ident,'artifact',{'artifact_hash':hash_,'executor':executor,'manifest':manifest})
            self._evidence(ident,Evidence(artifact_hash=hash_,evidence_type='source_document',content=content,outcome='observed',source_ref='artifact:'+hash_),executor)
        return self.task(ident)

    def _evidence(self, ident, evidence, origin):
        task=self.task(ident)
        if evidence.artifact_hash!=task['artifact_hash']:raise ValueError('Evidence is for a different artifact.')
        clean_text(evidence.content,60000)
        evidence_id=uid('ev')
        self.conn.execute('INSERT INTO core_evidence VALUES (?,?,?,?,?,?,?,?,?,?)',(evidence_id,ident,evidence.artifact_hash,evidence.evidence_type.value,evidence.content,digest(evidence.content),evidence.outcome,evidence.source_ref,origin,now()))
        self.event(ident,'evidence',{'id':evidence_id,'artifact_hash':evidence.artifact_hash,'origin':origin,'type':evidence.evidence_type.value})
        return evidence_id

    def add_evidence(self, ident, evidence, origin='local-user'):
        evidence=Evidence.model_validate(evidence)
        with self.atomic():
            task=self.task(ident)
            if task['state']!='REVIEWING':raise ValueError('Evidence can only be added during review.')
            self.fresh(task)
            ident_ev=self._evidence(ident,evidence,origin)
        return ident_ev

    def review(self, ident, review, reviewer='local-user'):
        review=Review.model_validate(review)
        with self.atomic():
            task=self.task(ident);self.fresh(task)
            if task['state']!='REVIEWING':raise ValueError('Task is not in review.')
            if any(op['phase']=='review' and op['state'] in {'dispatching','running'} for op in task['operations']):raise ValueError('Independent reviewer is still running.')
            if review.artifact_hash!=task['artifact_hash'] or review.contract_hash!=task['contract_hash'] or review.policy_revision!=task['contract']['policy_revision']:
                raise ValueError('Review version mismatch.')
            criteria={c['criterion_id']:c for c in task['contract']['acceptance_criteria']}
            if {r.criterion_id for r in review.criterion_results}!=set(criteria):raise ValueError('Every exact criterion ID must be reviewed once.')
            evidence={e['id']:e for e in task['evidence']};issues=list(review.blocking_issues);results=[]
            for result in review.criterion_results:
                row=result.model_dump();criterion=criteria[result.criterion_id]
                refs=[evidence.get(ref) for ref in result.evidence_refs]
                valid=bool(refs) and all(e and e['artifact_hash']==task['artifact_hash'] and e['evidence_type']==criterion['evidence_type'] and e['outcome'] not in {'failed','not_run'} for e in refs)
                if criterion['evidence_type']=='test_execution':
                    valid=valid and all(e['outcome']=='passed' and e['origin'] in {'flux-pytest','local-user'} for e in refs if e)
                if result.status=='PASS' and (not valid or result.reason_code!='VERIFIED'):
                    row.update(status='UNKNOWN',reason_code='MISSING',explanation='PASS lacks valid evidence of the required type for this version.')
                if criterion['required'] and row['status']!='PASS':issues.append(result.criterion_id+': '+row['explanation'])
                results.append(row)
            record={**review.model_dump(mode='json'),'criterion_results':results,'blocking_issues':issues,'reviewer':reviewer}
            self.conn.execute('UPDATE core_tasks SET review=?,review_revision=review_revision+1,updated_at=? WHERE id=?',(json.dumps(record,ensure_ascii=False),now(),ident))
            target='ACCEPT_CANDIDATE' if not issues else 'NEEDS_REVISION' if review.repair_method else 'ESCALATED'
            self.transition(ident,target,'Deterministic criterion/evidence gate.')
            self.event(ident,'review',record)
        return self.task(ident)

    def retry(self, ident, method):
        method=clean_text(method,2000)
        if not method:raise ValueError('Changed repair method is required.')
        with self.atomic():
            task=self.task(ident)
            if task['state']!='NEEDS_REVISION':raise ValueError('Task is not eligible for repair.')
            contract=Contract.model_validate(task['contract']);methods=task['repair_methods']
            if digest(method) in methods:raise ValueError('Same repair method already attempted.')
            if task['generations']>=contract.limits.max_generation_attempts:
                self.transition(ident,'ESCALATED','Quality attempt cap reached.')
            else:
                methods.append(digest(method))
                self.conn.execute("UPDATE core_tasks SET checkpoint='generation',repair_methods=?,review=NULL WHERE id=?",(json.dumps(methods),ident))
                self.event(ident,'repair_method',{'method':method})
                self.transition(ident,'READY','New repair method authorized by local user; counters preserved.')
        return self.task(ident)

    def accept(self, ident, artifact_hash, review_revision):
        with self.atomic():
            task=self.task(ident)
            if task['state']=='ACCEPTED':
                if task['acceptance']['artifact_hash']!=artifact_hash or task['acceptance']['review_revision']!=review_revision:raise ValueError('Acceptance version conflict.')
                return task
            self.fresh(task)
            if task['state']!='ACCEPT_CANDIDATE' or task['artifact_hash']!=artifact_hash or task['review_revision']!=review_revision:raise ValueError('Accept the exact current reviewed candidate.')
            if not task['review'] or task['review']['blocking_issues']:raise ValueError('Blocking review issues.')
            # Recheck evidence at the final gate; no acceptance by changing a label.
            evidence={e['id']:e for e in task['evidence']}
            for result in task['review']['criterion_results']:
                criterion=next(c for c in task['contract']['acceptance_criteria'] if c['criterion_id']==result['criterion_id'])
                if criterion['required'] and (result['status']!='PASS' or not result['evidence_refs'] or any(ref not in evidence or evidence[ref]['artifact_hash']!=artifact_hash for ref in result['evidence_refs'])):raise ValueError('Acceptance evidence missing.')
            self.conn.execute('INSERT INTO core_acceptances VALUES (?,?,?,?,?,?)',(ident,artifact_hash,task['contract_hash'],review_revision,'local-user',now()))
            self.transition(ident,'ACCEPTED','Human accepted this exact artifact and review revision.')
            self.conn.execute('INSERT INTO core_outbox VALUES (?,?,?,?,0)',(uid('out'),ident,'memory_proposal',json.dumps({'artifact_hash':artifact_hash,'project_id':task['project_id']})))
        self.deliver_memory_proposals()
        return self.task(ident)

    def deliver_memory_proposals(self):
        # No network inside a transaction. Proposal has stable provenance/idempotency.
        rows=self.conn.execute("SELECT * FROM core_outbox WHERE delivered=0 AND kind='memory_proposal'").fetchall()
        for row in rows:
            task=self.task(row['task_id']);source='acceptance:'+task['id']+':'+task['artifact_hash']
            exists=any(source in m['provenance'] for m in self.workspace.memories(project_id=task['project_id']))
            if not exists:
                try:
                    self.workspace.save_memory('پیشنهاد حافظه: '+task['contract']['objective'][:90],
                        'Accepted artifact '+task['artifact_hash']+'\n'+task['artifact'][:11000],project_id=task['project_id'],status='proposed',provenance=[source],emission_key=source)
                except ValueError:
                    continue  # Active project or revoked scope: outbox remains pending.
            with self.atomic():self.conn.execute('UPDATE core_outbox SET delivered=1 WHERE id=?',(row['id'],))

    def sync(self, runtime, ident):
        task=self.task(ident)
        for operation in task['operations']:
            if operation['provider']=='gapgpt' and operation['state']=='received':
                self.apply_api_receipt(operation['id']);continue
            if operation['state']!='running' or not operation['turn_id']:continue
            turn=runtime.turn(operation['turn_id'])
            if turn['state'] in {'queued','running'}:
                if time.time()>operation['lease_until']:
                    # Runtime owns cancellation; status observation cannot safely
                    # start another operation while its child process still runs.
                    self.operation_failure(operation['id'],'Lease expired; reconcile and cancel owned process before resuming.')
                continue
            with self.atomic():
                current=self.conn.execute('SELECT state FROM core_operations WHERE id=?',(operation['id'],)).fetchone()[0]
                if current!='running':continue
                state='completed' if turn['state']=='completed' else 'unknown' if turn['state']=='interrupted' else 'failed'
                billing=turn['usage'].get('billing') or ('gapcode-wallet' if operation['provider']=='gapcode' else 'google-account' if operation['provider']=='gemini' else 'subscription')
                self.conn.execute('UPDATE core_operations SET state=?,usage=? WHERE id=?',(state,json.dumps({'billing':billing,'provider_usage':turn['usage'],'actual_cost_usd':None}),operation['id']))
                self.account_time(operation)
                self.event(ident,'operation_terminal',{'id':operation['id'],'state':state,'turn_state':turn['state']})
            task=self.task(ident)
            if task['state'] in {'CANCELLED','FAILED','ACCEPTED'}:continue
            if turn['state']!='completed':
                with self.atomic():
                    if task['state']=='RUNNING':self.transition(ident,'RECOVERING' if state=='unknown' else 'FAILED',turn['error'] or turn['state'])
                    elif task['state']=='REVIEWING':self.transition(ident,'ESCALATED','Reviewer did not complete.')
                continue
            if operation['phase']=='generation':
                try:
                    if json.loads(operation['source_manifest'])!=self.manifest(task):raise ValueError('Bound source changed during generation.')
                    self.artifact(ident,turn['text'],executor='cli:'+operation['chat_id'])
                except ValueError as exc:
                    with self.atomic():
                        if self.task(ident)['state'] in {'RUNNING','RECOVERING'}:self.transition(ident,'FAILED',str(exc)[:500])
            else:
                try:
                    from flux.engine.json_parser import parse_llm_json
                    self.review(ident,parse_llm_json(turn['text']),reviewer='cli:'+operation['chat_id'])
                except (ValueError,KeyError) as exc:
                    with self.atomic():
                        if self.task(ident)['state']=='REVIEWING':self.transition(ident,'ESCALATED','Invalid reviewer result: '+str(exc)[:500])
        return self.task(ident)

    def recover(self):
        with self.atomic():
            # A crash between receipt persistence and gate application is surfaced
            # for reconciliation too; the successful turn itself is retained.
            for row in self.conn.execute("SELECT o.id FROM core_operations o JOIN core_tasks t ON o.task_id=t.id WHERE o.state='completed' AND ((o.phase='generation' AND t.state='RUNNING') OR (o.phase='review' AND t.state='REVIEWING'))").fetchall():
                self.conn.execute("UPDATE core_operations SET state='running' WHERE id=?",(row[0],))
            for operation in self.conn.execute("SELECT * FROM core_operations WHERE state IN ('dispatching','running')").fetchall():
                if operation['reservation_id']:self.budget.settle(operation['reservation_id'],None)
                self.account_time(operation)
                self.conn.execute("UPDATE core_operations SET state='unknown' WHERE id=?",(operation['id'],))
                task=self.task(operation['task_id'])
                if task['state']=='RUNNING':self.transition(task['id'],'RECOVERING','Restart: unknown operation is not replayed.')
                elif task['state']=='REVIEWING':self.transition(task['id'],'WAITING_APPROVAL','Restart: reconcile reviewer before resume.')
        self.deliver_memory_proposals()

    def reconcile(self, ident, operation_key, outcome):
        if outcome not in {'no_effect','completed'}:raise ValueError('Reconcile with known no-effect or a persisted completed turn.')
        with self.atomic():
            task=self.task(ident);operation=self.conn.execute('SELECT * FROM core_operations WHERE id=? AND task_id=?',(operation_key,ident)).fetchone()
            if not operation or operation['state']!='unknown':raise ValueError('No unknown operation to reconcile.')
            self.account_time(operation)
            if operation['turn_id']:
                turn=self.conn.execute('SELECT state FROM local_turns WHERE id=?',(operation['turn_id'],)).fetchone()
                if turn and turn[0] in {'queued','running'}:raise ValueError('Owned process may still be active; cancel it first.')
                if outcome=='completed' and (not turn or turn[0]!='completed'):raise ValueError('Persisted successful turn required.')
            elif outcome=='completed' and not (operation['provider']=='gapgpt' and operation['response']):raise ValueError('No receipt for completed execution.')
            target_operation='received' if outcome=='completed' and operation['provider']=='gapgpt' else 'running' if outcome=='completed' else 'reconciled_no_effect'
            self.conn.execute('UPDATE core_operations SET state=? WHERE id=?',(target_operation,operation_key))
            if outcome=='no_effect' and operation['reservation_id']:self.budget.settle(operation['reservation_id'],0)
            if outcome=='no_effect':
                target='READY'
                if task['state'] not in {'RECOVERING','WAITING_APPROVAL'}:raise ValueError('Task is not recovering.')
                self.transition(ident,target,'Human reconciled no effect; counters preserved.')
            elif task['state']=='WAITING_APPROVAL':
                self.transition(ident,'READY','Human reconciled completed reviewer receipt.')
                self.transition(ident,'REVIEWING','Resume the same review checkpoint.')
            self.event(ident,'reconciled',{'operation':operation_key,'outcome':outcome,'actor':'local-user'})
        return self.task(ident)

    def cancel(self, ident):
        with self.atomic():
            self.transition(ident,'CANCELLED','Local user cancellation; artifacts and unknown usage retained.')
        return self.task(ident)
