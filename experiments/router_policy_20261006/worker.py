"""Restricted pure-function evaluator. Receives no files, credentials or network API."""
import ast, copy, json, sys

data=json.load(sys.stdin)
tree=ast.parse(data['code'])
safe=dict(len=len,range=range,sorted=sorted,list=list,dict=dict,set=set,tuple=tuple,
          min=min,max=max,sum=sum,abs=abs,int=int,float=float,str=str,bool=bool,
          enumerate=enumerate,zip=zip,all=all,any=any,reversed=reversed)
if not tree.body or any(not isinstance(x,ast.FunctionDef) for x in tree.body):
    raise ValueError('Only function definitions are permitted')
if not any(x.name=='solve' for x in tree.body):raise ValueError('solve missing')
for node in ast.walk(tree):
    if isinstance(node,(ast.Import,ast.ImportFrom,ast.ClassDef,ast.Global,ast.Nonlocal,ast.With,ast.AsyncFunctionDef)):
        raise ValueError('Unsupported code construct')
    if isinstance(node,ast.Name) and node.id.startswith('_'):raise ValueError('Private names forbidden')
    if isinstance(node,ast.Attribute) and node.attr not in {'append','get','items','keys','values','sort','pop','copy','extend','add','discard','remove','update','count','index','setdefault'}:
        raise ValueError('Unsupported attribute')
    if isinstance(node,ast.FunctionDef) and (node.decorator_list or node.name.startswith('_')):
        raise ValueError('Unsupported function')
scope={'__builtins__':safe}
exec(compile(tree,'<candidate>','exec'),scope)
results=[]
for case in data['cases']:
    argument=copy.deepcopy(case)
    value=scope['solve'](argument)
    results.append({'value':value,'mutated':argument!=case})
print(json.dumps(results))
