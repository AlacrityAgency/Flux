"""Package portable runtime source, smoke-test demo and tests, preserve frozen code."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
V5=HERE.parent/'request_memory_v5_20261002'
DEST=V5/'flux-memory-v5-runtime.zip'
manifest=json.loads((V5/'runs/final/frozen-manifest.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(HERE.parent/path)==value for path,value in manifest['sha256'].items())
files=list(V5.glob('*.py'))+[V5/'README.fa.md',V5/'REPORT.fa.md',V5/'requirements.txt',V5/'demo-job.json']
with zipfile.ZipFile(DEST,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:archive.write(path,path.name)
    archive.write(V5/'runs/final/holdout-results.json','offline-results.json')
    archive.write(V5/'runs/final/frozen-manifest.json','experiment-frozen-manifest.json')
    archive.write(HERE/'verification.json','visual-and-provenance-verification.json')
    hashes={p.name:sha(p) for p in files}
    archive.writestr('runtime-sha256.json',json.dumps(hashes,indent=2))
portable=HERE/'portable-smoke'
portable.mkdir(exist_ok=True)
with zipfile.ZipFile(DEST) as archive:archive.extractall(portable)
tests=subprocess.run([sys.executable,'-X','utf8','-m','pytest','test_v5.py','-q'],cwd=portable,
                     capture_output=True,text=True,encoding='utf-8',timeout=90)
assert tests.returncode==0,tests.stdout+tests.stderr
demo=subprocess.run([sys.executable,'-X','utf8','cli.py','demo-job.json'],cwd=portable,
                    capture_output=True,text=True,encoding='utf-8',timeout=30)
assert demo.returncode==0,demo.stderr
job=json.loads(demo.stdout)
assert job['mode']=='prepare_only' and job['actual_model_calls']==0 and job['pack']['status']=='ready'
assert all(sha(portable/name)==value for name,value in hashes.items())
assert all(sha(HERE.parent/path)==value for path,value in manifest['sha256'].items())
result={'zip':str(DEST),'zip_sha256':sha(DEST),'bytes':DEST.stat().st_size,'runtime_files':len(files),
        'portable_tests':tests.stdout.strip(),'portable_demo':'ready, zero model calls',
        'frozen_code_unchanged':True,'source_hashes_match':True,'actual_model_calls':0}
(HERE/'package-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
