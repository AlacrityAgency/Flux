import numpy as np
import pytest
from engine import Atom,Record,Request,ArchiveBuilder,Memory,optimize,pack,probe_graph,tokens,dumps


class EncoderStub:
    def encode(self,texts,kind):
        # Stub for structural unit tests only. Actual benchmark uses frozen E5 weights.
        return np.tile(np.array([[1.,0.,0.]],dtype=np.float32),(len(texts),1))


def setup():
    aa=[Atom('a','svc00001 depends_on: svc00002.','doc1',1,0),
        Atom('b','svc00002 owner: team09.','doc2',1,1),
        Atom('c','svc00001 forbidden: export_secret.','doc1',2,0),
        Atom('d','svc00003 owner: team03.','doc3',1,2)]
    m=Memory([Record(a) for a in aa],EncoderStub())
    return m,ArchiveBuilder(aa)


def test_request_notes_are_requirements_not_answer_facts():
    from engine import note_request
    n=note_request(Request('r','q',('owner',)))
    assert n[0]['status']=='requirement' and n[0]['sources']==[]


def test_scope_tombstone_filters_before_embedding():
    a=Atom('a','old private value','doc',1,0)
    b=Atom('b','active value','doc2',1,1)
    m=Memory([Record(a),Record(a,revision=2,status='deleted'),Record(a,project='other'),Record(b)],EncoderStub())
    assert list(m.byid)==['b'] and len(m.vectors)==1


def test_target_unreachable_has_no_padding():
    m,b=setup();r=b.build(Request('r','owner',('owner',)))
    assert r['status']=='target_unreachable' and r['tokens']<1000000
    assert r['tokens']==tokens(r['rendered'])
    assert all(a.text in r['rendered'] for a in m.atoms)


def test_dependency_witnesses_are_protected_and_bridge_reuses_refs():
    m,b=setup();req=Request('r','svc00001 dependency owner',('svc00001 depends_on','owner'))
    ar=b.build(req);scores,ids,protected,links=m.route(req,ar)
    assert {'a','b'}<=protected and links
    g=optimize(req,m,scores,ids,protected,links)
    assert all(x in g['ids'] for x in ['a','b'])
    assert any(t['rollback'] and t['missing_probes'] for t in g['trace'])
    p=pack(req,m,scores,g,800)
    assert {'a','b'}<=set(p['ids']) and p['tokens']==tokens(p['rendered'])<=800
    assert p['semantic_sufficiency']=='unverified'


def test_model_critic_cannot_delete_critical_source_probe():
    m,b=setup();req=Request('r','svc00001 forbidden',('svc00001 forbidden',))
    ar=b.build(req);score,ids,protected,links=m.route(req,ar)
    g=optimize(req,m,score,ids,protected,links,critic_proposal=('c',))
    assert g['trace'][0]['rollback'] and 'c' in g['ids']


def test_required_bundle_overflow_raises_without_clipping():
    m,b=setup();req=Request('r','svc00001 dependency owner',('owner',))
    ar=b.build(req);score,ids,protected,links=m.route(req,ar);g=optimize(req,m,score,ids,protected,links)
    with pytest.raises(ValueError):pack(req,m,score,g,30)


def test_closed_reasoning_request_does_not_get_unrelated_private_sources():
    m,b=setup();req=Request('r','Compute 2 plus 2',('answer',),external_evidence=False)
    ar=b.build(req);score,ids,protected,links=m.route(req,ar)
    assert ids==protected==set() and links==[]


def test_rollback_preserves_source_manifest_and_archive():
    m,b=setup();req=Request('r','svc00001 forbidden',('forbidden',))
    ar=b.build(req);before=ar['hash'];score,ids,protected,links=m.route(req,ar)
    optimize(req,m,score,ids,protected,links,critic_proposal=tuple(ids))
    assert ar['hash']==before and ar['hash']
