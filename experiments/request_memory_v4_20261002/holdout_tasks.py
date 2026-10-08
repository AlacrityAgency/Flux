"""Fresh holdout tasks over the frozen Flux snapshot.

Written and hashed BEFORE engine_v4.py existed. These questions were never used
to design or tune v3/v4. Needles are exact source strings checked against the
frozen snapshot; they are consumed by the evaluator only.
"""
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent.parent / 'diffusion_memory_20261001' / 'snapshots' / 'flux_real' / 'sources'

REAL_HOLDOUT = [
    ('HR01', 'Which states can a run move to from VERIFYING?',
     ['VALID_TRANSITIONS', 'VERIFYING'],
     ['"VERIFYING": {"ACCEPT_CANDIDATE", "REVISE"']),
    ('HR02', 'What price does get_model_price fall back to for an unknown model?',
     ['get_model_price', 'fallback', 'unknown'],
     ['return ModelPrice(input_per_million=10.0, output_per_million=50.0)']),
    ('HR03', 'تخمین‌گر توکن برای متن مخلوط فارسی و انگلیسی از چه فرمولی استفاده می‌کند؟',
     ['estimate_tokens_from_text', 'len(text)'],
     ['return int(len(text) / 2.5) + 20']),
    ('HR04', 'What does strict_review return when the decision type is not recognized?',
     ['strict_review', 'decision'],
     ["return ReviewDecision(decision='ESCALATE',confidence='low')"]),
    ('HR05', 'What happens in BudgetLedger when a budget reservation cannot be made?',
     ['BudgetLedger', 'reserve_budget', 'BudgetExceededError'],
     ['raise BudgetExceededError(', 'Budget cap exceeded!']),
    ('HR06', 'What are the default limits for subtasks, concurrent agents and root calls in Settings?',
     ['Settings', 'max_subtasks', 'max_concurrent_agents', 'max_root_calls'],
     ['max_subtasks: int = 5', 'max_concurrent_agents: int = 2', 'max_root_calls: int = 20']),
    ('HR07', 'How many subtasks does DAGValidator allow and how does it report a cycle?',
     ['DAGValidator', 'max_subtasks', 'Cycle'],
     ['max_subtasks: int = 5) -> List[List[SubtaskSpec]]', 'Cycle detected in subtask dependency graph!']),
    ('HR08', 'What is the default max_concurrent of ConcurrencyLimiter?',
     ['ConcurrencyLimiter', 'max_concurrent'],
     ['def __init__(self, max_concurrent: int = 2):']),
    ('HR09', 'در codex_windows برچسب پنجره‌های ۳۰۰ دقیقه‌ای و ۱۰۰۸۰ دقیقه‌ای چیست؟',
     ['codex_windows', 'minutes'],
     ["label = '۵ ساعته' if minutes == 300 else 'هفتگی' if minutes == 10080"]),
    ('HR10', 'What input and output price per million does the pricing table give gpt-5.6-luna?',
     ['MODEL_PRICES', 'gpt-5.6-luna'],
     ['"gpt-5.6-luna": ModelPrice(input_per_million=0.2, output_per_million=1.2)']),
    ('HR11', 'What error message does parse_llm_json raise for an empty model response?',
     ['parse_llm_json', 'empty'],
     ['raise ValueError("پاسخ مدل خالی بود.")']),
    ('HR12', 'Which run states are terminal, with no outgoing transitions?',
     ['VALID_TRANSITIONS', 'set()'],
     ['"ACCEPT_CANDIDATE": set()', '"REJECTED": set()', '"FAILED": set()', '"CANCELLED": set()']),
]


def real_holdout_tasks():
    raw = '\n'.join(p.read_text(encoding='utf-8') for p in sorted(SNAPSHOT.rglob('*')) if p.is_file())
    tasks = []
    for ident, query, criteria, needles in REAL_HOLDOUT:
        absent = [n for n in needles if n not in raw]
        if absent:
            raise AssertionError(f'Holdout gold not in frozen snapshot {ident}: {absent}')
        tasks.append({'id': ident, 'kind': 'source_evidence', 'query': query, 'criteria': criteria, 'needles': needles})
    return tasks
