"""Restricted one-shot evaluation of benchmark solve; no tools, filesystem or network."""
import ast
import builtins
import copy
import json
import sys


def main():
    job=json.loads(sys.stdin.read());tree=ast.parse(job['code'])
    denied={'eval','exec','open','compile','input','globals','locals','getattr','setattr','delattr','vars','dir','breakpoint','help','__import__'}
    modules={'heapq','bisect','collections','math','itertools','functools'}
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module]
            if any(name not in modules for name in names):raise ValueError('Disallowed import')
        if isinstance(node,ast.Attribute) and node.attr.startswith('_'):raise ValueError('Private attribute forbidden')
        if isinstance(node,ast.Name) and (node.id in denied or node.id.startswith('__')):raise ValueError('Disallowed builtin/name')
        if isinstance(node,(ast.ClassDef,ast.Global,ast.Nonlocal)):raise ValueError('Unsupported construct')
    allowed=['len','range','enumerate','zip','min','max','sum','sorted','reversed','list','dict','set','tuple','int','float','str','bool','abs','any','all','map','filter','isinstance','Exception','ValueError','KeyError']
    safe={k:getattr(builtins,k) for k in allowed}
    def limited_import(name,globals=None,locals=None,fromlist=(),level=0):
        if name not in modules or level:raise ValueError('Disallowed module')
        return builtins.__import__(name,globals,locals,fromlist,level)
    safe['__import__']=limited_import;scope={'__builtins__':safe}
    exec(compile(tree,'<benchmark>','exec'),scope)
    fn=scope.get('solve');passed=[];errors=[]
    for case in job['tests']:
        arg=copy.deepcopy(case['input']);before=copy.deepcopy(arg)
        try:
            answer=fn(arg);passed.append(answer==case['expected'] and arg==before);errors.append(None)
        except Exception as e:passed.append(False);errors.append(type(e).__name__+': '+str(e))
    print(json.dumps({'passed':passed,'errors':errors}))


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'passed':[False],'errors':[type(e).__name__+': '+str(e)]}))
