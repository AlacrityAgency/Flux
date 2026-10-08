import pytest
from memory import Atom, GraphRetriever, compact, dumps, envelope, pack, tokens


def fixture_atoms():
    return [Atom(f'a{i}',f'svc{i:05d} approval: required. owner: team{i%3}.',f'doc{i}',1,i%4,1.) for i in range(80)]


def test_entire_serialized_graph_is_under_cap_and_repeated_compaction_is_monotonic():
    aa=fixture_atoms();first=compact(aa,4,5000);second=compact(aa,4,2000,first)
    assert tokens(dumps(first['payload']))==first['tokens']<=5000
    assert tokens(dumps(second['payload']))==second['tokens']<=2000
    assert {a.ident for a in second['atoms']} <= {a.ident for a in first['atoms']}


def test_extracts_exact_source_text_without_fabrication():
    aa=fixture_atoms();level=compact(aa,4,3000)
    originals={a.ident:a.text for a in aa}
    for node in level['payload']['nodes']:
        for ident,_,_,text in node['atoms']:assert originals[ident]==text


def test_query_envelope_is_counted_and_no_piece_is_truncated():
    aa=fixture_atoms();p=pack(aa,list(range(len(aa))),300)
    assert p['tokens']==tokens(p['rendered'])<=300
    original={a.ident:a.text for a in aa}
    assert all(original[x['id']]==x['text'] for x in p['items'])


def test_archive_reading_is_explicit_and_not_claimed_as_graph_storage():
    aa=fixture_atoms();level=compact(aa,4,3000);r=GraphRetriever(level,aa)
    p=r.retrieve('svc00001 approval',400,['svc00001 approval'],archive=True)
    assert p['external_atom_tokens_scanned']>0
    assert p['model_calls']==0 and p['semantic_sufficiency']=='unverified'


def test_no_gold_in_graph_schema():
    g=compact(fixture_atoms(),4,3000)['payload']
    assert 'needles' not in dumps(g) and 'criteria' not in dumps(g)


def test_low_metadata_budget_fails_explicitly():
    with pytest.raises(ValueError):compact(fixture_atoms(),4,10)
