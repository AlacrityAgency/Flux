"""Restricted execution for fixtures; not a complete hostile-code OS sandbox."""
import ast
import copy
import json
import sys
from pathlib import Path

SKILL = Path('C:/Users/xio/.codex/skills/flux-v1')
sys.path.insert(0, str(SKILL/'scripts'))
import compact_worker as W

def main():
    job=json.loads(sys.stdin.read());code=job['code']
    if not isinstance(code,str) or len(code)>20000:raise ValueError('invalid program size')
    tree=ast.parse(code);W.check(tree)
    safe={k:getattr(W.builtins,k) for k in W.ALLOWED if hasattr(W.builtins,k)}
    def limited_import(name,globals=None,locals=None,fromlist=(),level=0):
        if name.split('.')[0] not in W.MODULES or level:raise ValueError('disallowed import')
        return W.builtins.__import__(name,globals,locals,fromlist,level)
    safe['__import__']=limited_import
    scope={'__builtins__':safe,'__name__':'solution'}
    exec(compile(tree,'<candidate>','exec'),scope)
    fn=scope.get('solve')
    if not callable(fn):raise ValueError('missing solve')
    failures=[];executed=0
    for i,case in enumerate(job['cases']):
        f=copy.deepcopy(case['facts']);before=copy.deepcopy(f)
        try:
            answer=fn(f);executed+=1
            equal=json.dumps(answer,sort_keys=True,separators=(',',':'))==json.dumps(case['expected'],sort_keys=True,separators=(',',':'))
            if not equal:failures.append({'case':i,'reason':'wrong answer'})
            if f!=before:failures.append({'case':i,'reason':'input mutation'})
            if job.get('require_checker'):
                checker=scope.get('check')
                if not callable(checker) or checker(answer,copy.deepcopy(before)) is not True:failures.append({'case':i,'reason':'checker did not pass'})
        except Exception as exc:failures.append({'case':i,'reason':type(exc).__name__})
    print(json.dumps({'pass':not failures,'executed':executed,'failures':failures}))

if __name__=='__main__':
    try:main()
    except Exception as exc:print(json.dumps({'pass':False,'executed':0,'failures':[{'reason':type(exc).__name__+': '+str(exc)[:160]}]}))
