"""Syntactic contract and restricted execution; independent oracle is separate."""
import argparse,ast,json,subprocess,sys
from pathlib import Path
from call_model import normalize

def audit(data,facts):
    refs=data.get('refs')
    if not isinstance(refs,list) or not all(isinstance(x,str) for x in refs) or len(refs)!=len(set(refs)) or set(refs)!=set(facts):raise ValueError('Mandatory top-level facts reference mismatch')
    code=data.get('code');tree=ast.parse(code)
    funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    for name,args in [('solve',['facts']),('check',['answer','facts'])]:
        if name not in funcs or [a.arg for a in funcs[name].args.args]!=args:raise ValueError(name+' signature mismatch')
        used={n.id for n in ast.walk(funcs[name]) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
        if not set(args)<=used:raise ValueError(name+' arguments unused')
    check=funcs['check'];body=[n for n in check.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant))]
    if len(body)==1 and isinstance(body[0],ast.Return) and isinstance(body[0].value,ast.Constant):raise ValueError('Constant checker')
    if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='solve' for n in ast.walk(check)):raise ValueError('Checker directly calls solve')
    return code

def decode(node):
    kind=node['type'];v=node['value']
    if kind in ['fraction','decimal']:
        if v[1]!=1:raise ValueError('Integer-cent contract violated')
        return v[0]
    if kind=='mapping':return {k:decode(x) for k,x in v.items()}
    if kind=='sequence':return [decode(x) for x in v]
    if kind in ['string','bool','null']:return v
    raise ValueError('Unsupported result encoding: '+kind)

def validate(data,facts):
    try:
        code=audit(data,facts)
        p=subprocess.run([sys.executable,'-I','-S',str(Path(__file__).with_name('compact_worker.py'))],
          input=json.dumps({'code':code,'facts':facts,'checked':True}),capture_output=True,text=True,encoding='utf-8',timeout=5)
        r=json.loads(p.stdout)
        if r.get('status')!='ok' or r.get('verified') is not True:raise ValueError(str(r)[:600])
        return {'pass':True,'answer':decode(r['result']),'independent_verifier_pass':None}
    except Exception as e:return {'pass':False,'reason':type(e).__name__+': '+str(e)[:600],'independent_verifier_pass':None}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--candidate',type=Path,required=True);a.add_argument('--facts',type=Path,required=True)
    args=a.parse_args();result=validate(normalize(args.candidate.read_text(encoding='utf-8')),json.loads(args.facts.read_text(encoding='utf-8')))
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['pass'] else 1)
