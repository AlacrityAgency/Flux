"""Local Laya front/end with explicit checkpoint and separate receipt."""
import argparse,json,os,time
from pathlib import Path
os.environ.update(USE_TF='0',USE_FLAX='0',LAYA_CUDA_AMP='fp16')
FRONT={'verify':{'type':'choice','instructions':'Choose depth of independent verification based on consequences and reasoning difficulty.',
 'criteria':{'light':'Shape and consistency for low risk','medium':'Smoke or property tests for medium risk','full':'Exact reference or comprehensive independent tests for high risk'}}}
END={'action':{'type':'choice','instructions':'Accept completed candidates with passed independent checks. Escalate failed candidates if attempts remain. Stop after failed checks and exhausted attempts. Confidence does not establish correctness.',
 'criteria':{'accept':'Successful completion and passed checks','escalate':'Further stronger attempt warranted and attempts remain','stop':'Failure and no attempts remain'}}}

def guard(choice,passed,attempt):
    if not passed:return 'escalate' if attempt<2 else 'stop'
    return 'escalate' if choice=='escalate' and attempt<2 else 'accept'

def predict(agent,state,phase,receipt,device='cuda'):
    import torch
    if receipt.exists():raise FileExistsError('Local receipt exists')
    if device.startswith('cuda'):torch.cuda.synchronize()
    start=time.perf_counter();out=agent.predict_long(state,FRONT if phase=='front' else END,lang='en',batch_size=1)
    if device.startswith('cuda'):torch.cuda.synchronize()
    usage=out.get('usage',{})
    if usage.get('truncated') or usage.get('truncated_questions') or usage.get('state_tokens_dropped',0):raise ValueError('Laya dropped required input')
    result={'state':state,'phase':phase,'output':out,'latency_s':time.perf_counter()-start,
      'calibrated_for_model_success':False,'provider_billable_tokens':0}
    receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--checkpoint',type=Path,required=True);a.add_argument('--state',type=Path,required=True)
    a.add_argument('--phase',choices=['front','end'],required=True);a.add_argument('--receipt',type=Path,required=True)
    a.add_argument('--device',default='cuda');args=a.parse_args()
    import laya
    agent=laya.load(str(args.checkpoint),subfolder='multilingual',device=args.device,backend='eager')
    r=predict(agent,json.loads(args.state.read_text(encoding='utf-8')),args.phase,args.receipt,args.device)
    print(json.dumps(r['output'],ensure_ascii=False))
