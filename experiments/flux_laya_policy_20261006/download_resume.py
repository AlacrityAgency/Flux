"""Range-resumable public checkpoint download, verified against Hub LFS SHA256."""
import hashlib, json, shutil, time
from pathlib import Path
import requests
HERE=Path(__file__).resolve().parent
REV='7b928d828b7b0e022f929d9bd2e44165aa270148'
REPO='convaiinnovations/laya'
FILENAME='multilingual/model.safetensors'
target=HERE/'checkpoint'/FILENAME
temp=target.with_suffix('.partial')
meta=requests.get(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true',timeout=30).json()
record=next(x for x in meta['siblings'] if x['rfilename']==FILENAME)
size,expected=record['size'],record['lfs']['sha256']
if not temp.exists() and not target.exists():
    old=list((HERE/'checkpoint/.cache/huggingface/download/multilingual').glob('*.incomplete'))
    if old:shutil.copyfile(old[0],temp)
if target.exists():temp=target
else:
    while (temp.stat().st_size if temp.exists() else 0)<size:
        offset=temp.stat().st_size if temp.exists() else 0
        end=min(offset+8*1024*1024,size)-1
        for attempt in range(8):
            try:
                r=requests.get(f'https://huggingface.co/{REPO}/resolve/{REV}/{FILENAME}?chunk={offset}',
                    headers={'Range':f'bytes={offset}-{end}'},timeout=(20,45))
                assert r.status_code==206 and r.headers.get('Content-Range','').startswith(f'bytes {offset}-')
                assert len(r.content)==end-offset+1
                with temp.open('ab') as f:f.write(r.content)
                print(f'{end+1}/{size}',flush=True);break
            except Exception as e:
                print(f'retry {offset} {attempt}: {e}',flush=True)
                if attempt==7:raise
                time.sleep(1)
assert temp.stat().st_size==size
actual=hashlib.file_digest(temp.open('rb'),'sha256').hexdigest()
assert actual==expected,(actual,expected)
if temp!=target:temp.replace(target)
(HERE/'checkpoint-provenance.json').write_text(json.dumps({'revision':REV,'filename':FILENAME,'bytes':size,'sha256':actual,'hub_lfs_sha256':expected},indent=2),encoding='utf-8')
print('Verified complete checkpoint',actual,flush=True)
