"""Offline: answer typed-fact requests straight from v5 bindings, no model call. Verify with v5 verifier + pilot scorer."""
import sys, json
from time import perf_counter
from statistics import median
LIVE = r'D:/project/Alacrity/Flux/experiments/luna_v4_v5_live_20261002'
sys.path.insert(0, LIVE)
import run_pilot as P
from contracts import Source
from memory_v5 import Snapshot
from engine_v5 import normalize_request, retrieve
from verifier_v5 import verify

public = json.load(open(LIVE + '/public-jobs.json', encoding='utf-8'))
gold = {g['id']: g for g in json.load(open(LIVE + '/evaluation-only.json', encoding='utf-8'))}
live = {r['id'] if 'id' in r else r['request']['request_id']: r for r in json.load(open(LIVE + '/results.json', encoding='utf-8'))['rows'] if r.get('arm', 'v5') == 'v5'} if False else None
snap = Snapshot([Source(**s) for s in public['sources']], aliases=public['aliases'])

def direct(request):
    req = normalize_request(request, snap)
    pack = retrieve(snap, req, P.POLICY)
    if pack.status != 'ready' or pack.route != 'project_grounded' or not req.needs:
        return None, pack, req
    units = {u['unit_id']: u for u in pack.payload['units']}
    claims = []
    for need in req.needs:
        b = pack.payload['bindings'].get(need.need_id)
        if not b:
            return None, pack, req
        u = units[b['evidence_refs'][0]]
        claims.append({'need_id': need.need_id, 'entity_ref': b['entity'], 'field_ref': b['field'], 'namespace': b['namespace'],
                       'value': u['value'], 'value_type': b['value_type'], 'proof_kind': b['proof_kind'], 'evidence_refs': b['evidence_refs']})
    out = {'claims': claims}
    return out, pack, req

rows = []
for case in public['cases']:
    request = P.decode(case['request'])
    for _ in range(3):  # warm
        direct(request)
    t = perf_counter(); out, pack, req = direct(request); ms = (perf_counter() - t) * 1000
    if out is None:
        rows.append((case['id'], case['family'], 'model_needed', pack.route, round(ms, 3)))
        continue
    v = verify(snap, req, pack, out)
    s = P.score(out, req, gold[case['id']])
    rows.append((case['id'], case['family'], 'direct', v.status, s['passed'], s.get('display'), round(ms, 3)))
import pathlib; pathlib.Path(r"D:/project/Alacrity/Flux/experiments/request_memory_v6_20261002/fact-tier-results.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")
for r in rows: print(r)
d = [r for r in rows if r[2] == 'direct']
print('direct-answerable:', len(d), '/', len(rows), ' correct:', sum(r[4] for r in d), ' verified:', sum(r[3] == 'verified' for r in d), ' median ms:', median(r[-1] for r in d))
