"""Local Laya probabilities are advisory; deterministic evidence gates acceptance."""
import hashlib, json, os, threading, time
from pathlib import Path
os.environ.update(USE_TF='0',USE_FLAX='0',LAYA_CUDA_AMP='fp16')
import laya, torch

HERE = Path(__file__).resolve().parent
REVISION = '7b928d828b7b0e022f929d9bd2e44165aa270148'
MODEL_KEYS = ['luna','sol','astra']

FRONT = {
 'model':{'type':'choice','instructions':'Choose the least expensive model likely to solve this task correctly. Prefer Luna for straightforward extraction, arithmetic and short Python; Sol for difficult combinatorial optimization or delicate reasoning; Astra only when Sol is unlikely to succeed.',
   'criteria':{'luna':'gpt-6-luna, cheapest','sol':'gpt-6.1-sol, middle cost','astra':'gpt-6-astra, most expensive'}},
 'effort':{'type':'choice','instructions':'Choose reasoning effort needed for correct execution. Code and exact combinatorics usually need at least medium.',
   'criteria':{'low':'Low effort for simple tasks','medium':'Medium effort for moderate reasoning','high':'High effort for demanding problems'}},
 'verify':{'type':'choice','instructions':'Choose verification depth based on consequences and reasoning difficulty.',
   'criteria':{'light':'Shape and consistency for low risk','medium':'Smoke tests for medium risk','full':'Exact or property checks for high risk'}}}
END = {'action':{'type':'choice','instructions':'Decide next action. Accept a completed candidate that passed deterministic local checks. Escalate a failed candidate to the next stronger model. Stop when retries are exhausted. Confidence alone does not establish correctness.',
    'criteria':{'accept':'Successful completion and passed checks','escalate':'Failed checks; remaining attempts available','stop':'Failed checks and attempts exhausted'}}}

class Decisions:
    def __init__(self):
        start = time.perf_counter()
        self.agent = laya.load(str(HERE/'checkpoint'),subfolder='multilingual',device='cuda',backend='eager')
        torch.cuda.synchronize()
        self.load_s = time.perf_counter()-start
        self.lock = threading.Lock()

    def predict(self, state, questions, label):
        path = HERE/'laya_receipts'/(label+'.json')
        fingerprint = hashlib.sha256(json.dumps([state,questions],sort_keys=True).encode()).hexdigest()
        if path.exists():
            r=json.loads(path.read_text(encoding='utf-8'));assert r['fingerprint']==fingerprint;return r
        with self.lock:
            torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
            out = self.agent.predict_long(state,questions,lang='en',batch_size=1)
            torch.cuda.synchronize()
            r={'label':label,'fingerprint':fingerprint,'state':state,'questions':questions,
                'output':out,'latency_s':time.perf_counter()-start,
                'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                'checkpoint_revision':REVISION,'calibrated_for_routing':False,
                'local_state_tokens':len(self.agent.tok.encode(json.dumps(state,ensure_ascii=False))),
                'billable_provider_tokens':0,'paid_api_usd':0}
            path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'laya':label,'latency_s':r['latency_s'],'choices':{k:v.get('choice') for k,v in out.get('answers',{}).items()},'usage':out.get('usage')},ensure_ascii=False),flush=True)
        return r

    def front(self,task,label):
        return self.predict({'task':task['prompt'],'family':task['family'],'risk_floor':task['risk_floor']},FRONT,label)

    def end(self,task,receipt,check,attempt,label):
        # Public request and computed pass/fail only. No gold values, no audit code, no reference answer.
        return self.predict({'task':task['prompt'],'provider_completed':receipt['completed'],
            'candidate':receipt['text'],'local_check':check,'attempt':attempt,'remaining_attempts':2-attempt},END,label)

def answers(receipt):
    o=receipt['output']
    return o.get('answers',o)

def final_action(choice,passed,attempt):
    if not passed: return 'escalate' if attempt<2 else 'stop'
    if choice=='escalate' and attempt<2: return 'escalate'
    # Laya stop cannot discard a verified result, nor accept an unverified one.
    return 'accept'
