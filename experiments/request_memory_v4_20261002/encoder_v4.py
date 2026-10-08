"""Frozen multilingual-e5-small, loaded read-only from the v3 model cache.

Passages are cached on disk (index time). Queries are always computed, so the
measured request latency includes the real embedding cost.
"""
from pathlib import Path
import hashlib
import os
import sys
from time import perf_counter
import numpy as np

HERE = Path(__file__).resolve().parent
V3 = HERE.parent/'request_memory_v3_20261002'
sys.path.insert(0, str(V3/'deps'))
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
REVISION = '614241f622f53c4eeff9890bdc4f31cfecc418b3'
MODEL_PATH = V3/'model_cache/models--intfloat--multilingual-e5-small/snapshots'/REVISION


class Encoder:
    def __init__(self, cache=HERE/'embedding_cache'):
        import torch
        from transformers import AutoModel, AutoTokenizer
        start = perf_counter()
        self.torch = torch
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(MODEL_PATH), local_files_only=True, use_safetensors=True).to(self.device).eval()
        self.cache = cache
        self.cache.mkdir(exist_ok=True)
        self.load_seconds = perf_counter()-start
        self.query_calls = 0

    def _embed(self, texts, kind, batch_size=64):
        out = []
        for i in range(0, len(texts), batch_size):
            batch = [kind+': '+t for t in texts[i:i+batch_size]]
            inputs = self.tokenizer(batch, max_length=512, truncation=True, padding=True, return_tensors='pt')
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with self.torch.inference_mode():
                hidden = self.model(**inputs).last_hidden_state
                mask = inputs['attention_mask'].unsqueeze(-1)
                vec = self.torch.nn.functional.normalize((hidden*mask).sum(1)/mask.sum(1), p=2, dim=1)
            out.append(vec.float().cpu().numpy())
        return np.concatenate(out).astype(np.float32) if out else np.zeros((0, 384), np.float32)

    def encode(self, texts, kind='passage'):
        texts = list(texts)
        if kind != 'passage':
            self.query_calls += 1
            return self._embed(texts, kind)
        key = hashlib.sha256((REVISION+'\npassage\n'+'\n'.join(texts)).encode('utf-8')).hexdigest()
        p = self.cache/f'{key}.npy'
        if p.exists():
            return np.load(p)
        v = self._embed(texts, kind)
        np.save(p, v)
        return v
