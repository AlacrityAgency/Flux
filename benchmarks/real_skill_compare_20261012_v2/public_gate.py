"""Project-owned SUPER scenario runner; public fixtures only, real assertions."""
import argparse
import json
from pathlib import Path
import benchmark as B

def main():
    p=argparse.ArgumentParser();p.add_argument('--task-id',required=True);p.add_argument('--project',default='.')
    a=p.parse_args();task=next(t for t in B.read(B.HERE/'tasks.json') if t['id']==a.task_id)
    code=(Path(a.project)/'solution.py').read_text(encoding='utf-8')
    result=B.program_check(task,code,hidden=False)
    print(json.dumps({'checks':[{'name':'task-contract','status':'PASS' if result['pass'] else 'FAIL',
           'executed':result['executed']}],'failures':result['failures']}))
    return 0 if result['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
