import pytest
from graph_memory import Atom, MemoryGraph, Record, Retriever, dumps, eligible, tokens


def samples():
    return [Atom('a', 'svc00001 depends_on: svc00002.', 'synthetic/a', 1, 0),
            Atom('b', 'svc00002 owner: team09.', 'synthetic/b', 1, 1),
            Atom('c', 'svc00001 forbidden: export_secret.', 'synthetic/a', 2, 0)]


def test_scope_and_tombstone_before_index():
    a = samples()[0]
    rows = [Record(a), Record(a, revision=2, status='deleted'), Record(a, project='other', revision=99)]
    assert eligible(rows, 'experiment') == []
    assert eligible([Record(a), Record(a, revision=2, status='proposed')], 'experiment') == [a]


def test_conflicting_same_revision_fails():
    a = samples()[0]
    with pytest.raises(ValueError):
        eligible([Record(a), Record(a, enabled=False)], 'experiment')


def test_each_edge_has_shared_provenance_and_no_duplicate_text():
    m = MemoryGraph([Record(a) for a in samples()]); g = m.compress(6000)
    assert g['payload']['mini_blocks']
    for mini in g['payload']['mini_blocks']:
        assert len(set(mini['nodes'])) == 2
        assert all(r['left'] in m.byid and r['right'] in m.byid for r in mini['relations'])
    ids = [c[0] for c in g['payload']['memories']]
    assert len(ids) == len(set(ids))
    assert g['tokens'] == tokens(dumps(g['payload'])) <= 6000


def test_expand_then_pack_dependency_bundle():
    m = MemoryGraph([Record(a) for a in samples()]); r = Retriever(m, m.compress(6000))
    p = r.retrieve('Find the dependency of svc00001 and its owner', 400, ['svc00001 depends_on', 'owner'])
    assert {'a', 'b'} <= set(p['ids'])
    assert p['semantic_sufficiency'] == 'unverified' and p['model_calls'] == 0
    assert p['tokens'] == tokens(p['rendered']) <= 400


def test_matrix_is_bounded_and_hash_changes_after_canonical_change():
    rows = [Record(a) for a in samples()]; m = MemoryGraph(rows)
    for row in m.matrix.values():
        assert all(0 <= v <= 1 for v in row[:-1]) and row[-1] > 0
    new = MemoryGraph(rows+[Record(samples()[2], revision=2, status='deleted')])
    assert new.snapshot_hash != m.snapshot_hash and 'c' not in new.byid


def test_small_budget_does_not_clip_or_claim_pass():
    m = MemoryGraph([Record(a) for a in samples()]); r = Retriever(m, m.compress(6000))
    p = r.retrieve('svc00001 dependency owner', 65)
    assert p['omitted_relation_bundle']
    assert all(x['text'] == m.byid[x['id']].text for x in p['items'])
    assert p['tokens'] <= 65 and p['semantic_sufficiency'] == 'unverified'


def test_recompression_uses_archive_not_lossy_previous_view():
    m = MemoryGraph([Record(a) for a in samples()]); small = m.compress(3000); large = m.compress(6000)
    assert small['payload']['archive_snapshot_hash'] == large['payload']['archive_snapshot_hash']
    assert {a.ident for a in small['atoms']} <= {a.ident for a in large['atoms']}


def test_too_small_graph_cap_fails_explicitly():
    m = MemoryGraph([Record(a) for a in samples()])
    with pytest.raises(ValueError): m.compress(10)
