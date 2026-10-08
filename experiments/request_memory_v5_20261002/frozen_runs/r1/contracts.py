"""Public typed contracts. No benchmark gold or Flux database access."""
from dataclasses import dataclass, field, asdict
import hashlib
import json
import re
import tiktoken

ENC = tiktoken.get_encoding('o200k_base')

def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256((value if isinstance(value, str) else dumps(value)).encode('utf-8')).hexdigest()

def tokens(text):
    return len(ENC.encode(text, disallowed_special=()))

def normalize(text):
    return str(text).lower().replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ')

def terms(text):
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(text))
    return re.findall(r'[^\W_]+', normalize(text).replace('_', ' '))

@dataclass(frozen=True)
class Source:
    source_id: str
    text: str
    project: str = 'experiment'
    revision: int = 1
    epoch: str = '1'
    status: str = 'verified'
    role: str = 'document'
    format: str = 'text'
    namespace: str = ''
    schema: dict = field(default_factory=dict)

@dataclass(frozen=True)
class Unit:
    unit_id: str
    source_id: str
    source_hash: str
    line_start: int
    line_end: int
    text: str
    entity: str = ''
    field: str = ''
    value: object = None
    value_type: str = ''
    proof_kind: str = 'text_excerpt'
    role: str = 'document'
    namespace: str = ''

@dataclass(frozen=True)
class Relation:
    left: str
    right: str
    kind: str

@dataclass(frozen=True)
class Need:
    need_id: str
    entity: str = ''
    field: str = ''
    namespace: str = ''
    value_type: str = ''
    proof_kind: str = 'typed_fact'
    required: bool = True
    query: str = ''
    # Optional public relation traversal: start_entity -> via_field -> target field.
    via_field: str = ''
    membership: bool = False

@dataclass(frozen=True)
class Request:
    request_id: str
    query: str
    project: str = 'experiment'
    epoch: str = '1'
    needs: tuple = ()
    task_kind: str = 'unknown'
    memory_need: str = 'auto'
    expression: str = ''
    public_tests: tuple = ()
    allow_partial: bool = False

    def __post_init__(self):
        if not self.request_id or not isinstance(self.query, str):
            raise ValueError('Request ID/query required')
        if len({n.need_id for n in self.needs}) != len(self.needs):
            raise ValueError('Duplicate need IDs')
        if self.memory_need not in ('auto','project_grounded','self_contained','uncertain'):
            raise ValueError('Unknown memory need')
        if self.task_kind not in ('unknown','factual','math','code','mixed'):
            raise ValueError('Unknown task kind')
        if self.needs and self.memory_need == 'self_contained':
            raise ValueError('Source needs cannot be self-contained')

@dataclass(frozen=True)
class Policy:
    evidence_budget: int = 3000
    prompt_budget: int = 8000
    primary_model: str = 'gpt-6-luna'
    fallback_model: str = 'gpt-6.1-sol'
    allow_escalation: bool = False
    max_calls: int = 2
    deadline_seconds: float = 180
    optional_units: int = 2
    graph_hops: int = 1
    relation_cap: int = 32

    def __post_init__(self):
        if not 0 <= self.max_calls <= 2 or self.graph_hops not in (0, 1, 2):
            raise ValueError('v5 permits at most two physical calls and two graph hops')
        if min(self.evidence_budget, self.prompt_budget, self.optional_units, self.relation_cap) < 0:
            raise ValueError('Negative budget/cap')
        if self.deadline_seconds <= 0:
            raise ValueError('Deadline must be positive')

@dataclass
class Pack:
    status: str
    payload: dict
    rendered: str
    token_count: int
    count_passes: int
    route: str
    gaps: list
    required_ids: tuple = ()
    matrix: list = field(default_factory=list)
    prepare_ms: float = 0

    def public(self):
        return asdict(self)

@dataclass
class Verification:
    status: str
    per_need: list
    problems: list
    method: str
    output_hash: str
    snapshot_hash: str
    details: dict = field(default_factory=dict)

    @property
    def blocking(self):
        return self.status in ('invalid', 'contradicted', 'partial')
