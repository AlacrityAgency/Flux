import copy
import pytest
from completed_graph import CompletedMemoryGraph, CompletedRetriever
from graph_memory import Atom, Record, dumps, sha, tokens


def memory():
    return CompletedMemoryGraph([Record(Atom('a','svc00001 depends_on: svc00002.','synthetic/a',1,0)),
                                Record(Atom('b','svc00002 owner: team09.','synthetic/b',1,1))])


def test_missing_static_bridge_is_recalled_as_budgeted_mini_block():
    m=memory(); level=m.compress(6000); level=copy.deepcopy(level)
    level['payload']['mini_blocks']=[]
    r=CompletedRetriever(m,level)
    p=r.retrieve('svc00001 dependency owner',400)
    assert {'a','b'}<=set(p['ids']) and p['archive_relation_fallback']
    assert p['shared_mini_blocks']==[['depends_on','svc00001','a','b']]
    assert tokens(p['rendered'])==p['tokens']<=400
    assert not r.active_links # Query-local view does not mutate shared graph.


def test_same_text_new_revision_changes_snapshot_and_rejects_old_graph():
    m=memory(); old=m.compress(6000)
    newer=CompletedMemoryGraph([Record(a,revision=2) for a in m.atoms])
    assert newer.snapshot_hash != m.snapshot_hash
    with pytest.raises(ValueError): CompletedRetriever(newer,old)


def test_graph_only_never_reconstructs_missing_text_from_archive():
    m=memory(); g=m.compress(6000); g=copy.deepcopy(g)
    g['atoms']=[a for a in g['atoms'] if a.ident!='b']
    g['payload']['memories']=[a for a in g['payload']['memories'] if a[0]!='b']
    for n in g['payload']['nodes']: n['refs']=[x for x in n['refs'] if x!='b']
    r=CompletedRetriever(m,g); p=r.retrieve('svc00001 dependency owner',400,mode='graph_only')
    assert 'b' not in p['ids'] and not p['archive_relation_fallback']


def test_relation_metadata_is_inside_budget_even_when_bundle_does_not_fit():
    m=memory(); r=CompletedRetriever(m,m.compress(6000))
    p=r.retrieve('svc00001 dependency owner',75)
    assert p['tokens']==tokens(p['rendered'])<=75
    assert not p['shared_mini_blocks'] and p['semantic_sufficiency']=='unverified'
