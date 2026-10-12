"""Fresh fixtures. Evaluator-only oracles never enter candidate prompts/workspaces."""
import itertools
import random
from decimal import Decimal, ROUND_HALF_UP

SEED = 121020260731

def build():
    rng = random.Random(SEED)
    tasks = []
    for i, size in enumerate([2, 5, 9, 13], 1):
        facts = {'lines': [{'qty': rng.randint(1, 9), 'unit_cents': rng.randint(1, 6800),
                 'discount_percent': rng.choice(['0', '12.5', '17.75', '50', '33.333'])} for _ in range(size)],
                 'shipping': rng.randint(0, 900), 'tax_percent': rng.choice(['8.875', '19.25', '7.5'])}
        if i == 1:
            facts = {'lines': [{'qty': 1, 'unit_cents': 105, 'discount_percent': '50'},
                              {'qty': 3, 'unit_cents': 17, 'discount_percent': '50'}], 'shipping': 3, 'tax_percent': '50'}
        tasks.append({'id': f'I{i}', 'family': 'invoice', 'track': 'reasoning', 'facts': facts,
          'task': 'Calculate integer cents. Round each qty*unit_cents*(1-discount_percent/100) HALF UP to cents; sum subtotal. Round tax_percent percent of subtotal HALF UP to cents. Shipping is untaxed. Decimal strings are exact. Return exactly subtotal_cents, tax_cents, total_cents.'})
    for i, n in enumerate([5, 6, 7, 8], 1):
        tasks.append({'id': f'C{i}', 'family': 'count', 'track': 'reasoning',
          'facts': {'alphabet': [0, 1, 3, 5], 'length': n, 'modulus': [7, 11, 13, 17][i-1],
                    'residue': i, 'sum_min': n+1, 'sum_max': 3*n, 'target_digit': 3, 'target_count': 2},
          'task': 'Enumerate length-digit strings over alphabet; leading zero is allowed. ALL constraints: adjacent digits differ; numeric value modulo modulus is residue; sum_min <= digit sum <= sum_max; exactly target_count copies of target_digit. Return exactly count and digit_sum_total, the sum of digit sums of valid strings.'})
    for i, n in enumerate([4, 5, 6, 7], 1):
        jobs = [{'id': f'K{j}', 'duration': rng.randint(1, 7), 'release': rng.randint(0, 9),
                 'due': rng.randint(7, 31), 'weight': rng.randint(1, 6),
                 'predecessors': [f'K{k}' for k in range(j) if rng.random() < .2]} for j in range(n)]
        tasks.append({'id': f'S{i}', 'family': 'schedule', 'track': 'reasoning', 'facts': {'jobs': jobs},
          'task': 'One machine at time 0, all jobs exactly once, nonpreemptive. Each job starts as early as possible after release, previous job completion and all predecessors; no discretionary idle. Reject orders with later predecessors. Minimize weighted tardiness sum(weight*max(0,completion-due)); ties minimize final completion, then lexicographic id sequence. Return exactly order, starts aligned to order, finish, weighted_tardiness.'})
    descriptions = {
      'access': 'Fix solve(facts): return {"allowed": bool}. Access requires active actor, resource tenant equal actor tenant, AND actor is owner OR actor role admin. A tenant admin has no cross-tenant exception. Missing/unknown role gives no admin right.',
      'intervals': 'Fix solve(facts): normalize intervals into sorted nonoverlapping half-open intervals. Ignore empty intervals, reject reversed endpoints with {"error":"reversed"}. Merge overlap but never merge mere adjacency. Return {"intervals": [[start,end],...]}. Input may be unsorted/duplicated and have negative endpoints.',
      'replay': 'Fix solve(facts): ledger events credit/debit positive integer amount with event id. First occurrence of an id takes effect; exact duplicates ignored; same id with different kind/amount rejects entire batch with {"error":"conflict"}. Balance starts at initial. Debit may overdraw (negative balance allowed). Return {"balance": int,"applied": int} counting unique events. No input mutation.',
      'rounding': 'Fix solve(facts): amount_cents nonnegative integer and percent exact decimal string [0,100]. Discounted amount = amount_cents*(1-percent/100), rounded HALF UP to integer cents, never binary-float/bankers rounding. Return {"cents": int}.',
      'migration': 'Fix solve(facts): validate entire rows before converting. Duplicate id rejects batch with {"error":"duplicate"}. Missing name rejects with {"error":"missing_name"} (duplicate check has precedence). Otherwise return {"rows": rows sorted by id, each exactly id and display_name preserving name string}. Do not mutate input.',
      'version': 'Fix solve(facts): select payload according to version. v1 reads title, v2 reads display_name (ignore title even if present); missing required field -> {"error":"missing"}; unknown version -> {"error":"version"}. Return {"label": field value} for valid input, including empty string. Do not guess across versions.'
    }
    buggy = {
      'access': 'def solve(facts):\n    a,r=facts["actor"],facts["resource"]\n    return {"allowed":a.get("role")=="admin" or a["id"]==r["owner"]}\n',
      'intervals': 'def solve(facts):\n    out=[]\n    for a,b in sorted(facts["intervals"]):\n        if out and a<=out[-1][1]: out[-1][1]=max(b,out[-1][1])\n        else: out.append([a,b])\n    return {"intervals":out}\n',
      'replay': 'def solve(facts):\n    b=facts["initial"]\n    for e in facts["events"]: b+=e["amount"] if e["kind"]=="credit" else -e["amount"]\n    return {"balance":b,"applied":len(facts["events"])}\n',
      'rounding': 'def solve(facts):\n    return {"cents":round(facts["amount_cents"]*(1-float(facts["percent"])/100))}\n',
      'migration': 'def solve(facts):\n    return {"rows":[{"id":r["id"],"display_name":r.get("name","")} for r in facts["rows"]]}\n',
      'version': 'def solve(facts):\n    p=facts["payload"]\n    return {"label":p.get("title",p.get("display_name",""))}\n'
    }
    for i, family in enumerate(descriptions, 1):
        public = cases(family, hidden=False)
        tasks.append({'id': f'E{i}', 'family': family, 'track': 'engineering', 'task': descriptions[family],
          'facts': public[0], 'public_cases': public, 'buggy_code': buggy[family]})
    return tasks

def cases(family, hidden=True):
    rng = random.Random(SEED + list(['access','intervals','replay','rounding','migration','version']).index(family))
    if family == 'access':
        base = [{'actor': {'id': 'a','tenant':'T','role':'user','active':True}, 'resource': {'owner':'a','tenant':'T'}},
                {'actor': {'id':'a','tenant':'T','role':'admin','active':True}, 'resource': {'owner':'b','tenant':'U'}},
                {'actor': {'id':'a','tenant':'T','role':'user','active':False}, 'resource': {'owner':'a','tenant':'T'}}]
        return base + [{'actor': {'id':'a','tenant':t,'role':r,'active':act}, 'resource': {'owner':o,'tenant':'T'}}
          for t,r,act,o in itertools.product(['T','U'],['user','admin','unknown'],[False,True],['a','b'])] if hidden else base
    if family == 'intervals':
        base = [{'intervals': [[1,3],[3,5],[2,4],[8,8]]}, {'intervals': [[2,1]]}, {'intervals': []}]
        return base + [{'intervals': [[a,a+rng.randint(0,5)] for a in [rng.randint(-10,10) for _ in range(12)]]} for _ in range(20)] if hidden else base
    if family == 'replay':
        e={'id':'a','kind':'credit','amount':7}
        base = [{'initial':10,'events':[e,e]}, {'initial':0,'events':[e,dict(e,amount=8)]}, {'initial':2,'events':[]}]
        return base + [{'initial':rng.randint(-10,10),'events':sum(([{'id':str(i),'kind':rng.choice(['credit','debit']),'amount':rng.randint(1,20)}]*rng.randint(1,3) for i in range(7)),[])} for _ in range(20)] if hidden else base
    if family == 'rounding':
        base = [{'amount_cents':105,'percent':'50'}, {'amount_cents':0,'percent':'12.5'}, {'amount_cents':101,'percent':'100'}]
        return base + [{'amount_cents':n,'percent':p} for n,p in itertools.product([1,3,7,33,199,1001,123456789],['50','12.5','33.333','99.9','0'])] if hidden else base
    if family == 'migration':
        base = [{'rows':[{'id':2,'name':'B'},{'id':1,'name':'A'}]}, {'rows':[{'id':1,'name':'X'},{'id':1,'name':'Y'}]}, {'rows':[{'id':2}]}]
        extra = [{'rows':[]},{'rows':[{'id':2},{'id':2,'name':'x'}]}]
        extra += [{'rows':[{'id':i,'name':f'NAME{i}','extra':True} for i in rng.sample(range(30),12)]} for _ in range(15)]
        return base+extra if hidden else base
    base = [{'version':2,'payload':{'title':'legacy','display_name':'new'}}, {'version':3,'payload':{'title':'A'}}, {'version':1,'payload':{}}]
    return base + [{'version':v,'payload':p} for v,p in itertools.product([0,1,2,3],[{}, {'title':''}, {'display_name':''},{'title':'x','display_name':'y'},{'title':None}])] if hidden else base

def oracle(task, f=None):
    f = task['facts'] if f is None else f
    family = task['family']
    if family in ['invoice', 'rounding']:
        half = lambda x: int(x.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        if family == 'rounding': return {'cents':half(Decimal(f['amount_cents'])*(1-Decimal(f['percent'])/100))}
        subtotal = sum(half(Decimal(x['qty'])*Decimal(x['unit_cents'])*(1-Decimal(x['discount_percent'])/100)) for x in f['lines'])
        tax = half(Decimal(subtotal)*Decimal(f['tax_percent'])/100)
        return {'subtotal_cents':subtotal,'tax_cents':tax,'total_cents':subtotal+tax+f['shipping']}
    if family == 'count':
        good=[]
        for ds in itertools.product(f['alphabet'],repeat=f['length']):
            if any(a==b for a,b in zip(ds,ds[1:])) or ds.count(f['target_digit']) != f['target_count']: continue
            if f['sum_min']<=sum(ds)<=f['sum_max'] and int(''.join(map(str,ds)))%f['modulus']==f['residue']:good.append(sum(ds))
        return {'count':len(good),'digit_sum_total':sum(good)}
    if family == 'schedule':
        jobs={j['id']:j for j in f['jobs']};best=None
        for order in itertools.permutations(sorted(jobs)):
            seen=set();clock=penalty=0;starts=[]
            for jid in order:
                j=jobs[jid]
                if not set(j['predecessors'])<=seen:break
                clock=max(clock,j['release']);starts.append(clock);clock+=j['duration']
                penalty+=j['weight']*max(0,clock-j['due']);seen.add(jid)
            else:
                key=(penalty,clock,order)
                if best is None or key<best[0]:best=(key,starts)
        k,s=best;return {'order':list(k[2]),'starts':s,'finish':k[1],'weighted_tardiness':k[0]}
    if family == 'access':
        a,r=f['actor'],f['resource'];return {'allowed':bool(a['active'] and a['tenant']==r['tenant'] and (a['id']==r['owner'] or a.get('role')=='admin'))}
    if family == 'intervals':
        if any(a>b for a,b in f['intervals']):return {'error':'reversed'}
        # Independent boundary partition and component reconstruction, no candidate code.
        segments=sorted(set((a,b) for a,b in f['intervals'] if a<b));out=[]
        for a,b in segments:
            if out and a<out[-1][1]:out[-1][1]=max(out[-1][1],b)
            else:out.append([a,b])
        return {'intervals':out}
    if family == 'replay':
        groups={}
        for e in f['events']:
            signature=(e['kind'],e['amount'])
            if e['id'] in groups and groups[e['id']]!=signature:return {'error':'conflict'}
            groups[e['id']]=signature
        return {'balance':f['initial']+sum(amount*(1 if kind=='credit' else -1) for kind,amount in groups.values()),'applied':len(groups)}
    if family == 'migration':
        rows=f['rows']
        if len({r['id'] for r in rows})!=len(rows):return {'error':'duplicate'}
        if any('name' not in r for r in rows):return {'error':'missing_name'}
        return {'rows':[{'id':r['id'],'display_name':r['name']} for r in sorted(rows,key=lambda r:r['id'])]}
    if family == 'version':
        if f['version'] not in [1,2]:return {'error':'version'}
        key='title' if f['version']==1 else 'display_name'
        return {'label':f['payload'][key]} if key in f['payload'] else {'error':'missing'}
    raise ValueError(family)
