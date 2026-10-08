"""Default: prepare only. --live explicitly opts into account-backed generation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from contracts import Source, Need, Request, Policy, dumps
from memory_v5 import Snapshot
from engine_v5 import normalize_request, retrieve, prompt_for
from controller_v5 import Controller, Ledger
from provider_v5 import CodexProvider

HERE = Path(__file__).resolve().parent

def load_job(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    sources = [Source(**s) for s in data['sources']]
    raw = dict(data['request'])
    raw['needs'] = tuple(Need(**n) for n in raw.get('needs', []))
    raw['public_tests'] = tuple(raw.get('public_tests', []))
    request = Request(**raw)
    snapshot = Snapshot(sources, request.project, request.epoch, data.get('aliases'))
    return snapshot, normalize_request(request, snapshot), Policy(**data.get('policy', {}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', help='JSON result, optional')
    args = parser.parse_args()
    snapshot, request, policy = load_job(args.job)
    if args.live:
        ledger = Ledger(str(HERE / 'runs-ledger.sqlite'))
        try:
            result = Controller(snapshot, CodexProvider(HERE / 'model_runs'), ledger).run(request, policy)
        finally:
            ledger.close()
    else:
        pack = retrieve(snapshot, request, policy)
        admission = prompt_for(request, pack, policy)
        result = {'mode': 'prepare_only', 'actual_model_calls': 0, 'request': asdict(request),
                  'snapshot_units': len(snapshot.units), 'pack': pack.public(),
                  'prompt_admission': {k: v for k, v in admission.items() if k != 'prompt'}}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    print(rendered)

if __name__ == '__main__':
    main()
