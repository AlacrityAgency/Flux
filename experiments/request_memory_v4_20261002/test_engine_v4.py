from pathlib import Path
import re
import pytest
from engine_v4 import Atom, Config, Index, Record, make_spec, retrieve, run, repair, tokens, verify_answer

ENGINE = Path(__file__).with_name('engine_v4.py').read_text(encoding='utf-8')


def corpus():
    aa = [Atom('a', 'alpha01 depends_on: beta02.', 'd1', 1, 0),
          Atom('b', 'beta02 owner: team09.', 'd2', 1, 0),
          Atom('c', 'alpha01 owner: team03.', 'd1', 2, 0),
          Atom('d', 'gamma03 owner: team05.', 'd3', 1, 0),
          Atom('e', 'def load_cfg(path):\n    limit_ms = 250\n    return path', 'src.py', 1, 0),
          Atom('f', 'def other():\n    return load_cfg("x")', 'src.py', 5, 0)]
    return aa


def test_engine_has_no_dataset_specific_rules():
    for banned in ['svc', 'owner', 'depends_on', 'rare_code', 'dependency', 'approval', 'forbidden']:
        assert banned not in ENGINE.lower(), banned


def test_scope_and_revision_gate_before_indexing():
    a = Atom('x', 'alpha01 owner: team03.', 'd', 1, 0)
    leaked = Atom('x', 'alpha01 owner: LEAKED.', 'd', 1, 0)
    records = [Record(a), Record(leaked, project='sibling'), Record(leaked, revision=2, status='proposed'),
               Record(Atom('y', 'alpha01 scope: old.', 'd', 2, 0)),
               Record(Atom('y', 'alpha01 scope: old.', 'd', 2, 0), revision=2, status='deleted')]
    ix = Index(records)
    assert ix.ids == ['x']
    p = run(ix, 'r', 'alpha01 owner and scope', ['alpha01 owner', 'alpha01 scope'], Config(fill_tokens=600))
    assert 'LEAKED' not in p['rendered'] and 'old' not in p['rendered']
    assert 'alpha01 scope' in p['gaps']


def test_relation_hop_without_keywords():
    ix = Index([Record(a) for a in corpus()])
    p = run(ix, 'r', 'what does alpha01 rely on and who runs that', ['alpha01 depends_on', 'owner'], Config(fill_tokens=0))
    assert {'a', 'b'} <= set(p['ids'])
    assert {'from': 'a', 'to': 'b', 'via': 'beta02'} in p['relations']


def test_exact_budget_and_required_overflow():
    ix = Index([Record(a) for a in corpus()])
    p = run(ix, 'r', 'load_cfg limit_ms', ['load_cfg', 'limit_ms'], Config(budget=400))
    assert p['tokens'] == tokens(p['rendered']) <= 400
    with pytest.raises(ValueError):
        run(ix, 'r', 'load_cfg limit_ms', ['load_cfg', 'limit_ms'], Config(budget=60, fill_tokens=0))


def test_router_skips_self_contained_requests():
    ix = Index([Record(a) for a in corpus()])
    assert not make_spec('m', 'Count binary strings of length 18 with seven ones', ['Return the number'], ix).retrieve
    assert make_spec('k', 'who is the owner of alpha01', ['alpha01 owner'], ix).retrieve
    p = run(ix, 'm', 'Count binary strings of length 18 with seven ones', ['Return the number'])
    assert p['status'] == 'no_retrieval' and p['items'] == []


def test_verifier_and_single_repair():
    ix = Index([Record(a) for a in corpus()])
    p = run(ix, 'r', 'alpha01 owner', ['alpha01 owner'], Config(per_criterion=1, fill_tokens=0, neighbors=0))
    assert verify_answer(p, {'owner': 'team03'}, ['c'])['ok']
    assert not verify_answer(p, {'owner': 'team77'}, ['c'])['ok']
    assert not verify_answer(p, {'owner': 'team03'}, ['made-up'])['ok']
    assert verify_answer(p, {'owner': None})['ok']
    bad = verify_answer(p, {'limit_ms': '250'})
    assert not bad['ok']
    fixed = repair(ix, p, bad['problems'])
    assert verify_answer(fixed, {'limit_ms': '250'})['ok']


def test_neighbors_only_for_fragments():
    ix = Index([Record(a) for a in corpus()])
    p = run(ix, 'r', 'load_cfg', ['load_cfg'], Config(per_criterion=1, fill_tokens=0, neighbors=1))
    assert {'e', 'f'} <= set(p['ids'])
    q = run(ix, 'r', 'gamma03 owner', ['gamma03 owner'], Config(per_criterion=1, fill_tokens=0, neighbors=1))
    assert q['ids'] == ['d']
