"""Configuration-only development probes; no held-out task or solution here."""
import sys
from concurrent.futures import ThreadPoolExecutor
from provider_v2 import invoke

def one(job):
    m,effort,minimal,label=job
    return invoke(m,effort,'Do not use tools or read files. Return only {"probe":"ok"}.',label,minimal=minimal)

if __name__=='__main__':
    jobs=[('gpt-6-luna','low',False,'dev_default_luna_1'),('gpt-6-luna','low',True,'dev_minimal_luna_1'),
          ('gpt-6-luna','low',False,'dev_default_luna_2'),('gpt-6-luna','low',True,'dev_minimal_luna_2'),
          ('gpt-6.1-sol','low',True,'dev_minimal_sol'),('gpt-6-astra','low',True,'dev_minimal_astra')]
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,jobs))
