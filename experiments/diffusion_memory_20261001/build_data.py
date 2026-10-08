"""Real allowlisted source snapshot + independently labelled synthetic scaling corpus."""
from pathlib import Path
import json
import math
import random
import re
from memory import Atom, ENC, atom_priority, dumps, sha, tokens

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def synthetic(target=1_000_000, seed=6417):
    rng=random.Random(seed);parts=[];docs=[];offset=0;i=0
    while offset<target+2000:
        subject=f'svc{i:05d}';dep=f'svc{(i*31+7)%1000:05d}'
        fields={'owner':f'team{rng.randrange(40):02d}','depends_on':dep,
                'timeout_ms':str(rng.randrange(100,20001)),
                'approval':'required' if i%3 else 'delegated',
                'scope':f'tenant{rng.randrange(20):02d}',
                'retry_limit':str(rng.randrange(1,6)),
                'forbidden':'export_secret' if i%7==0 else 'unreviewed_publish',
                'rare_code':f'EX{i:05d}x{rng.randrange(100000,999999)}'}
        header=f'Document {i} service {subject}, revision 2, active, project synthetic-flux.\n'
        events=[]
        for j in range(12):
            events.append(f'Event {i*12+j}: {subject} observed stage {j}, latency {rng.randrange(1,9000)} milliseconds, queue depth {rng.randrange(50)}, worker w{rng.randrange(90)}, trace {rng.randrange(10**8,10**9)}, request {i:05d}-{j:02d}, verified telemetry only; execution does not grant permission.\n')
        fact_lines=[f'{subject} {k}: {v}.\n' for k,v in fields.items()]
        text=header+''.join(events)+''.join(fact_lines)+'End document.\n\n'
        size=tokens(text)
        docs.append({'id':i,'subject':subject,'fields':fields,'text':text,'offset':offset,
                     'fact_start_line':1+len(events)+1,'tokens':size})
        parts.append(text);offset+=size;i+=1
    joined=''.join(parts)
    # ASCII only: no partial UTF-8 bytes. Last record is deliberately incomplete
    # and excluded from extracted atoms and evaluation; never pad/repeat text.
    raw=ENC.decode(ENC.encode(joined,disallowed_special=())[:target])
    assert tokens(raw)==target
    docs=[d for d in docs if d['offset']+d['tokens']<=target-64]
    atoms=[];chunks=[]
    for d in docs:
        block=min(99,d['offset']//10000)
        ref=f'synthetic/doc{d["id"]:05d}'
        chunks.append(Atom(ref,d['text'],ref,1,block))
        for j,(k,v) in enumerate(d['fields'].items()):
            line=f'{d["subject"]} {k}: {v}.'
            atoms.append(Atom(f'{ref}:{j}',line,ref,d['fact_start_line']+j,block,atom_priority(line)))
    # This is an independent evaluator file, never passed to compression/retrieval.
    test_rng=random.Random(seed+19);tasks=[]
    eligible=[d for d in docs if d['id']>=1000]
    selected=test_rng.sample(eligible,80)
    by_subject={d['subject']:d for d in docs}
    for j,d in enumerate(selected):
        if j%4==0:
            field='rare_code';kind='rare_detail'
        elif j%4==1:
            field='owner';kind='lookup'
        elif j%4==2:
            field='timeout_ms';kind='lookup'
        else:
            field='approval';kind='constraint'
        needle=f'{d["subject"]} {field}: {d["fields"][field]}.'
        query=f'Find the {field} of {d["subject"]}. Cite the current source.'
        if j%2:query=f'برای {d["subject"]} مقدار {field} و شاهد منبع فعلی را پیدا کن.'
        tasks.append({'id':f'S{j:03d}','kind':kind,'query':query,
                      'criteria':[f'{d["subject"]} {field}'],'needles':[needle]})
    for j,d in enumerate(selected[:32]):
        target_doc=by_subject[d['fields']['depends_on']]
        q=f'Find the dependency of {d["subject"]} and the owner of that dependency.'
        tasks.append({'id':f'H{j:03d}','kind':'two_hop','query':q,
                      'criteria':[f'{d["subject"]} depends_on','owner'],
                      'needles':[f'{d["subject"]} depends_on: {target_doc["subject"]}.',
                                 f'{target_doc["subject"]} owner: {target_doc["fields"]["owner"]}.']})
    for j,d in enumerate(selected[:24]):
        fields=['approval','scope','forbidden']
        tasks.append({'id':f'C{j:03d}','kind':'decision_evidence',
                      'query':f'For {d["subject"]}, establish approval scope and forbidden actions before deciding.',
                      'criteria':[f'{d["subject"]} {f}' for f in fields],
                      'needles':[f'{d["subject"]} {f}: {d["fields"][f]}.' for f in fields]})
    return {'name':'synthetic_1m','raw':raw,'raw_tokens':tokens(raw),'blocks':100,
            'atoms':atoms,'chunks':chunks,'tasks':tasks,'docs':len(docs),'seed':seed,
            'limits':'Semistructured generated records, exact-field oracle; not natural-language answer quality.'}


REAL_TASKS=[
 ('R01','What defaults does admit_context use for input, output reserve and window?',
  ['admit_context','input_budget','output_reserve','window'],
  ['input_budget=16000','output_reserve=4000','window=24000']),
 ('R02','How does build_pack prevent resurrection of deleted older memory revisions?',
  ['build_pack','canonical','revision'],['Canonicalize BEFORE eligibility',"row.get('revision', 1)","r.get('status', 'verified') == 'verified'"]),
 ('R03','How does SharedBudget preserve unknown costs and reserve a reviewer floor?',
  ['SharedBudget','unknown','review_floor'],["account['unknown']","account['review_floor']","status='held_unknown'"]),
 ('R04','What gates protect exact artifact acceptance in CoreService.accept?',
  ['accept','artifact_hash','review_revision'],["task['artifact_hash']!=artifact_hash","task['review_revision']!=review_revision","self.fresh(task)"]),
 ('R05','How are deleted memory revision texts purged and sessions invalidated?',
  ['delete_memory','memory_revisions','invalidate_memory_sessions'],["UPDATE memory_revisions SET content=''",'self._invalidate_memory_sessions']),
 ('R06','Which file size and explicit source count limits does SourceIndex enforce?',
  ['SourceIndex','paths','300_000'],['len(paths) > 200','path.stat().st_size > 300_000']),
 ('R07','چطور context از نیمه‌کردن معیار یا artifact اجباری جلوگیری می‌کند؟',
  ['admit_context','Mandatory context'],['No criterion/artifact was silently truncated']),
 ('R08','What are the Limits defaults for root calls, generation attempts and active seconds?',
  ['Limits','max_calls','max_generation_attempts','max_active_seconds'],
  ['max_calls: int = Field(default=32','max_generation_attempts: int = Field(default=3','max_active_seconds: int = Field(default=1200']),
 ('R09','What tokenizer and fallback are used for local evidence pack counting?',
  ['token_count','encoding','utf8'],["tiktoken.get_encoding('o200k_base')","len(text.encode('utf-8'))"]),
 ('R10','How does the head request disable automatic duplicate memory injection?',
  ['context_admitted','use_memory','admit_context'],['use_memory=False',"context_meta=admit_context(framing+'\\nUser request:\\n'+prompt)"]),
 ('R11','How does SourceIndex detect stale source content before retrieval?',
  ['SourceIndex','records','content_hash'],["UPDATE knowledge_sources SET status='stale'","==source['content_hash']"]),
 ('R12','Does Contract currently support arbitrary enterprise tenants and human owners?',
  ['Contract','tenant_id','human_owner'],["tenant_id: Literal['local']", "human_owner: Literal['local-user']"]),
]


def real_sources():
    files=[];seen=set();texts=[];atoms=[];chunks=[];offset=0
    for folder in ['src','tests','docs']:
        for p in sorted((ROOT/folder).rglob('*')):
            if not p.is_file() or p.suffix not in {'.py','.md','.js','.toml'}:continue
            if any(x in p.parts for x in ['retrieval-corpus','__pycache__']):continue
            if folder=='docs' and 'knowledge' in p.relative_to(ROOT/'docs').parts:continue
            if any(x in p.name.lower() for x in ['credential','secret','password']):continue
            content=p.read_text(encoding='utf-8');digest=sha(content)
            if digest in seen or not content.strip():continue
            seen.add(digest);ref=p.relative_to(ROOT).as_posix();size=tokens(content)
            files.append({'path':ref,'sha256':digest,'tokens':size})
            texts.append(f'\nSOURCE {ref}\n'+content)
            lines=content.splitlines();block=offset//10000
            for i in range(0,len(lines),4):
                text='\n'.join(lines[i:i+4])
                if text.strip():atoms.append(Atom(f'{ref}:{i+1}',text,ref,i+1,block,atom_priority(text)))
            for i in range(0,len(lines),42):
                text='\n'.join(lines[i:i+42])
                if text.strip():chunks.append(Atom(f'{ref}:{i+1}',text,ref,i+1,block))
            offset+=size
    raw='\n'.join(texts)
    tasks=[]
    for ident,query,criteria,needles in REAL_TASKS:
        absent=[n for n in needles if n not in raw]
        if absent:raise AssertionError(f'Stale real gold {ident}: {absent}')
        tasks.append({'id':ident,'kind':'source_evidence','query':query,'criteria':criteria,'needles':needles})
    return {'name':'flux_real','raw':raw,'raw_tokens':tokens(raw),'blocks':math.ceil(offset/10000),
            'atoms':atoms,'chunks':chunks,'tasks':tasks,'files':files,
            'limits':'Current source anchor coverage only. Test-definition retrieval is not test execution.'}


def save_corpus(corpus,out):
    out.mkdir(parents=True,exist_ok=True)
    (out/'raw.txt').write_text(corpus['raw'],encoding='utf-8')
    (out/'atoms.json').write_text(dumps([a.__dict__ for a in corpus['atoms']]),encoding='utf-8')
    (out/'chunks.json').write_text(dumps([a.__dict__ for a in corpus['chunks']]),encoding='utf-8')
    (out/'manifest.json').write_text(dumps({k:v for k,v in corpus.items() if k not in {'raw','atoms','chunks','tasks'}}),encoding='utf-8')
