from dataclasses import replace
import pytest
import corpus as C
import optimized_v2 as O

def task(text="Show the stored request key", project="alpha"):
    return {"objective":text,"project_id":project,"criteria":[{"text":text}]}

def chunk(id="src/store.py::save_key", body=None, project="alpha"):
    return C.Chunk(id,"src/store.py",body or "def save_key(request):\n    key = request.key\n    return key",project_id=project)

def test_scope_isolates_ranking_statistics_as_well_as_output():
    code=[chunk()]
    index=O.Index(code,[])
    expected=index.select(task()).content
    foreign=[C.Memory(f"other{i}","other","request key","request key "*100) for i in range(100)]
    another=O.Index(code,foreign)
    assert another.select(task()).content == expected
    assert "other" not in another.spaces
    assert all(not u.prepared for u in another.by_project["other"])

def test_revision_and_status_filter_runs_before_indexing():
    memories=[C.Memory("decision","alpha","key policy","old forbidden",revision=1),
              C.Memory("decision","alpha","key policy","current allowed",revision=3),
              C.Memory("bad","alpha","key policy","stale forbidden",status="obsolete"),
              C.Memory("superseded","alpha","key policy","superseded forbidden",superseded_by="decision")]
    index=O.Index([],memories)
    space=index.space("alpha")
    assert [u.id for u in space.units] == ["decision"]
    assert space.units[0].revision == 3
    assert "forbidden" not in space.idf

@pytest.mark.parametrize("budget",[100,150,300,600,1500,3000])
def test_exact_budget_includes_warning_and_reference_headers(budget):
    code=[chunk(f"src/store.py::save_key{i}",f"def save_key{i}(request):\n    key = request.key\n    return key") for i in range(10)]
    pack=O.Index(code,[],O.Config(budget=budget)).select(task())
    assert O.token_count(pack.content) == pack.tokens <= budget
    assert "semantic sufficiency requires verification" in pack.content

def test_absent_topic_reports_missing_without_certifying_sufficiency():
    pack=O.Index([chunk()],[]).select(task("quasar spectroscopy redshift"))
    assert not pack.order
    assert pack.assessments[0]["retrieval_status"] == "missing"
    assert pack.assessments[0]["semantic_sufficiency"] == "unverified"

def test_gold_fields_are_never_read():
    class Trap(dict):
        def __getitem__(self,key):
            if key == "needs":
                raise AssertionError("Evaluation gold leaked into retrieval")
            return super().__getitem__(key)
    t=task()
    t["criteria"]=[Trap(text=t["objective"],needs="secret evaluation anchors")]
    pack=O.Index([chunk()],[]).select(t)
    assert pack.order

def test_excerpt_preserves_guard_and_balanced_mapping():
    text='def save_key(request):\n    if request.allowed:\n        data = {\n            "key": request.key,\n            "expiry": 24,\n        }\n        return data\n    return None'
    cfg=O.Config(window=2,stride=1,neighbours=0,budget=600)
    pack=O.Index([chunk(body=text)],[],cfg).select(task("Show the key expiry mapping"))
    assert "if request.allowed:" in pack.content
    assert '"key": request.key,' in pack.content
    assert '"expiry": 24,' in pack.content
    assert "        }" in pack.content
    kept=pack.keep[pack.order[0]]
    assert all(pack.order[0].lines[i] in pack.content for i in kept)

def test_large_memory_is_not_claimed_present_after_truncation():
    memory=C.Memory("large","alpha","recorded key decision","recorded key decision "*1000)
    pack=O.Index([], [memory],O.Config(budget=300)).select(task("Respect the recorded decision about key"))
    assert not pack.order
    assert pack.gaps

def test_project_with_same_memory_id_keeps_own_revision():
    memories=[C.Memory("same","alpha","key policy","alpha key",revision=1),
              C.Memory("same","beta","key policy","beta key",revision=99)]
    index=O.Index([],memories)
    assert index.space("alpha").units[0].revision == 1
    assert index.space("beta").units[0].revision == 99

def test_empty_project_id_is_rejected():
    with pytest.raises(ValueError):
        O.Index([chunk()],[]).select(task(project=""))
