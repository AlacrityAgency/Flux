"""Frozen public multilingual E5 embeddings; local weights, no source upload."""
from pathlib import Path
import json
import os
import sys
import hashlib
from time import perf_counter
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'deps'))
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='90'
os.environ['HF_HUB_ETAG_TIMEOUT']='30'
MODEL='intfloat/multilingual-e5-small'


class Encoder:
    def __init__(self):
        import torch
        from transformers import AutoModel,AutoTokenizer
        from huggingface_hub import HfApi,snapshot_download
        torch.set_num_threads(4)
        stamp=HERE/'embedding-model.json'
        if stamp.exists():
            info=json.loads(stamp.read_text(encoding='utf-8')); revision=info['revision']
        else:
            revision=HfApi(token=False).model_info(MODEL).sha
        start=perf_counter()
        path=snapshot_download(MODEL,revision=revision,token=False,cache_dir=str(HERE/'model_cache'),
             allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json',
                             'special_tokens_map.json','sentencepiece.bpe.model'])
        self.device='cuda' if torch.cuda.is_available() else 'cpu'
        self.tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True)
        self.model=AutoModel.from_pretrained(path,local_files_only=True,use_safetensors=True).to(self.device).eval()
        self.torch=torch;self.revision=revision;self.encoded_tokens=0;self.truncated_inputs=0
        info={'model':MODEL,'revision':revision,'dimensions':384,'device':self.device,
              'transformers':'4.48.3','max_encoder_tokens':512,'pooling':'masked mean per overlapping window; normalized window mean',
              'local_loading_seconds':perf_counter()-start,'source_uploads':0}
        stamp.write_text(json.dumps(info,indent=2),encoding='utf-8')

    def encode(self,texts,kind='passage',batch_size=64,cache_key=None):
        cache=HERE/'embedding_cache';cache.mkdir(exist_ok=True)
        h=hashlib.sha256((self.revision+'\nwindowed-v1\n'+kind+'\n'+'\n'.join(texts)).encode('utf-8')).hexdigest()
        p=cache/f'{h}.npy'
        if p.exists():return np.load(p)
        outputs=[]
        for start in range(0,len(texts),batch_size):
            batch=[kind+': '+t for t in texts[start:start+batch_size]]
            lengths=self.tokenizer(batch,truncation=False,add_special_tokens=True)['input_ids']
            self.truncated_inputs+=sum(len(x)>512 for x in lengths) # counted overlength inputs, covered by windows
            inputs=self.tokenizer(batch,max_length=512,truncation=True,padding=True,stride=64,
                                  return_overflowing_tokens=True,return_tensors='pt')
            mapping=inputs.pop('overflow_to_sample_mapping').numpy()
            self.encoded_tokens+=int(inputs['attention_mask'].sum())
            inputs={k:v.to(self.device) for k,v in inputs.items()}
            with self.torch.inference_mode():
                hidden=self.model(**inputs).last_hidden_state
                mask=inputs['attention_mask'].unsqueeze(-1)
                mean=(hidden*mask).sum(dim=1)/mask.sum(dim=1)
                vec=self.torch.nn.functional.normalize(mean,p=2,dim=1)
            window_vectors=vec.float().cpu().numpy()
            pooled=np.stack([window_vectors[mapping==i].mean(axis=0) for i in range(len(batch))])
            pooled/=np.maximum(1e-12,np.linalg.norm(pooled,axis=1,keepdims=True))
            outputs.append(pooled)
        result=np.concatenate(outputs).astype(np.float32)
        np.save(p,result)
        return result


if __name__=='__main__':
    e=Encoder();v=e.encode(['بودجه و حافظه پروژه','Project memory and budget'],'query')
    print(json.dumps({'model':MODEL,'revision':e.revision,'shape':list(v.shape),'bilingual_cosine':float(v[0]@v[1])}))
