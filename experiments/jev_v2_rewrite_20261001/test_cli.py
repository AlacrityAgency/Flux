import json, subprocess, sys, os
from pathlib import Path

SCRIPT = Path(os.environ.get("JEV_V2_CLI_PATH",str(Path(__file__).with_name("run.py"))))

def test_real_cli_preserves_contract_and_excludes_sensitive_files(tmp_path):
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "store.py").write_text("def store_key(request):\n    key = request.key\n    return key\n",encoding="utf-8")
    (root / ".env").write_text("key = secret-value-must-not-appear",encoding="utf-8")
    task=tmp_path / "task.json"
    original={"objective":"Show the stored request key","acceptance_criteria":["Show the key assignment"],"project_id":"demo"}
    task.write_text(json.dumps(original),encoding="utf-8")
    output=tmp_path / "pack.json"
    p=subprocess.run([sys.executable,str(SCRIPT),"--root",str(root),"--project-id","demo", "--task",str(task),
                      "--budget","600","--output",str(output)],capture_output=True,text=True)
    assert p.returncode == 0,p.stderr
    result=json.loads(output.read_text(encoding="utf-8"))
    assert result["model_calls"] == 0
    assert result["context_tokens"] <= 600
    assert "secret-value-must-not-appear" not in json.dumps(result)
    assert result["assessments"][0]["criterion"] == original["acceptance_criteria"][0]
    assert json.loads(task.read_text(encoding="utf-8")) == original

def test_cli_refuses_mismatched_project_before_creating_context(tmp_path):
    task=tmp_path / "task.json"
    task.write_text(json.dumps({"project_id":"other","objective":"key","criteria":[]}),encoding="utf-8")
    output=tmp_path / "out.json"
    p=subprocess.run([sys.executable,str(SCRIPT),"--root",str(tmp_path),"--project-id","demo","--task",str(task),
                      "--output",str(output)],capture_output=True,text=True)
    assert p.returncode != 0
    assert not output.exists()
