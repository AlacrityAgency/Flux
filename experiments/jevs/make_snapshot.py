"""Freeze the Flux text files used by the experiment (the real folder is being edited by other work)."""
import hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
HERE = Path(__file__).resolve().parent
REAL = HERE.parents[1]
sys.path.insert(0, str(HERE))
import corpus as C
dst = HERE / "snapshot"
if dst.exists():
    sys.exit("snapshot already exists; delete it explicitly to re-freeze")
manifest = {}
for p in C.project_files(REAL):
    rel = p.relative_to(REAL)
    (dst / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dst / rel)
    manifest[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
(HERE / "snapshot_manifest.json").write_text(json.dumps({"taken_at": datetime.now(timezone.utc).isoformat(),
    "files": manifest}, indent=1), encoding="utf-8")
print(len(manifest), "files frozen")
