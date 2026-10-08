from fractions import Fraction
import pytest
import engine as E


def graph():
    return {'nodes':[{'id':'a','kind':'input','text':'2,4,7,17; target 83'},
                     {'id':'b','kind':'objective','text':'minimum coins'},
                     {'id':'c','kind':'check','text':'feasible and optimal'}], 'edges':[['a','b'],['b','c']]}


def test_omitted_coin_detected():
    g=graph(); g['nodes'][0]['text']='2,7,17; target 83'
    assert not E.graph_audit(g,'coins 2,4,7,17 target 83')[0]


def test_graph_connected():
    assert E.graph_audit(graph(),'coins 2,4,7,17 target 83')[0]
    g=graph();g['edges']=[['b','c']]
    assert not E.graph_audit(g,'coins 2,4,7,17 target 83')[0]


def test_persian_numbers():
    assert E.literals('۲ و ۴ و ۸۳') == {'2','4','83'}


def test_rounding_disagreement():
    spec=E.V6.AnswerSpec('number',6)
    assert E.V6.close(Fraction('0.123456'),Fraction('0.123457'),spec)
    assert not E.exact_agreement(Fraction('0.123456'),Fraction('0.123457'),spec)


@pytest.mark.parametrize('code', ['def check(a):\n return True', 'def check(a):\n return a == solve()'])
def test_invalid_check(code):
    assert not E.checker_audit(code)


def test_independent_check_rejects_wrong_answer():
    r=E.run('def solve():\n return 9\ndef check(a):\n return a==7',checked=True)
    assert r['status']=='ok' and r['verified'] is False


def test_exact_arithmetic():
    r=E.run('from fractions import Fraction\ndef solve():\n return Fraction(1,3)\ndef check(a):\n return a*3==1',checked=True)
    assert r['verified'] is True and E.V6.to_fraction(r['result'])==Fraction(1,3)


def test_formatter_escape_rejected():
    code='from collections import Counter\nfrom string import Formatter\ndef solve():\n f,_=Formatter().get_field("0.__init__.__globals__[__builtins__][open]",(Counter,),{})\n return str(f)'
    assert E.run(code)['status']=='error'


def test_timeout():
    assert E.run('def solve():\n while True: pass', timeout=.15)['status']=='timeout'
