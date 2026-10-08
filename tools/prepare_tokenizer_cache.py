"""Download only the public o200k BPE asset into the explicit build allowlist."""
import os
from pathlib import Path
import tiktoken
root=Path(__file__).resolve().parents[1]/'src/flux/knowledge/tokenizer-cache'
root.mkdir(parents=True,exist_ok=True)
os.environ['TIKTOKEN_CACHE_DIR']=str(root)
assert tiktoken.get_encoding('o200k_base').encode('Flux حافظه')
print('Public tokenizer assets prepared:',len(list(root.iterdir())))
