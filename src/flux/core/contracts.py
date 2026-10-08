from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class EvidenceType(StrEnum):
    CODE='code'
    TEST_DEFINITION='test_definition'
    TEST_EXECUTION='test_execution'
    APPROVED_DECISION='approved_decision'
    POLICY='policy'
    SOURCE_DOCUMENT='source_document'
    TOOL_RESULT='tool_result'
    UI_OBSERVATION='ui_observation'


class Criterion(StrictModel):
    criterion_id: str = Field(min_length=1,max_length=80,pattern=r'^[A-Za-z0-9_.-]+$')
    text: str = Field(min_length=1,max_length=2000)
    required: bool = True
    evidence_type: EvidenceType = EvidenceType.SOURCE_DOCUMENT


class Limits(StrictModel):
    max_children: int = Field(default=5,ge=0,le=5)
    max_depth: int = Field(default=1,ge=0,le=1)
    max_generation_attempts: int = Field(default=3,ge=1,le=3)
    max_calls: int = Field(default=32,ge=1,le=32)
    max_active_seconds: int = Field(default=1200,ge=1,le=1200)
    max_concurrency: int = Field(default=2,ge=1,le=2)


class Contract(StrictModel):
    tenant_id: Literal['local'] = 'local'
    department_id: str = Field(default='technical',min_length=1,max_length=80)
    project_id: str = Field(min_length=1,max_length=100)
    human_owner: Literal['local-user'] = 'local-user'
    request_key: str = Field(min_length=1,max_length=100)
    objective: str = Field(min_length=5,max_length=12000)
    output_format: Literal['markdown','plain_text','json'] = 'markdown'
    output_notes: str = Field(default='',max_length=2000)
    scope: list[str] = Field(default_factory=list,max_length=30)
    out_of_scope: list[str] = Field(default_factory=list,max_length=30)
    acceptance_criteria: list[Criterion] = Field(min_length=1,max_length=30)
    allowed_tools: list[Literal['read_workspace','pytest']] = Field(default_factory=lambda:['read_workspace'])
    allowed_paths: list[str] = Field(default_factory=list,max_length=50)
    policy_revision: int = Field(default=1,ge=1)
    limits: Limits = Field(default_factory=Limits)
    budget_cap_micros: int = Field(default=500000,gt=0,le=100000000)
    review_reserve_micros: int = Field(default=0,ge=0)
    billing: Literal['subscription','api'] = 'subscription'
    execution_provider: Literal['codex','claude','gemini','gapcode'] = 'codex'
    parent_task_id: str | None = None
    dependencies: list[str] = Field(default_factory=list,max_length=5)
    criterion_ids: list[str] = Field(default_factory=list,max_length=30)
    data_class: Literal['public','internal'] = 'internal'

    @model_validator(mode='after')
    def coherent(self):
        ids=[c.criterion_id for c in self.acceptance_criteria]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate criterion IDs.')
        if self.review_reserve_micros>self.budget_cap_micros:raise ValueError('Review reserve exceeds budget.')
        if len(set(self.dependencies))!=len(self.dependencies):raise ValueError('Duplicate dependencies.')
        if len(set(self.criterion_ids))!=len(self.criterion_ids):raise ValueError('Duplicate owned criteria.')
        return self


class CriterionResult(StrictModel):
    criterion_id: str
    status: Literal['PASS','FAIL','UNKNOWN','NOT_APPLICABLE']
    evidence_refs: list[str] = Field(default_factory=list,max_length=30)
    reason_code: Literal['VERIFIED','NOT_RUN','MISSING','CONFLICT','DEFECT','NOT_APPLICABLE']
    explanation: str = Field(min_length=1,max_length=4000)


class Review(StrictModel):
    artifact_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    contract_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    policy_revision: int = Field(ge=1)
    criterion_results: list[CriterionResult] = Field(min_length=1,max_length=30)
    blocking_issues: list[str] = Field(default_factory=list,max_length=30)
    repair_method: str = Field(default='',max_length=2000)

    @model_validator(mode='after')
    def unique_results(self):
        ids=[r.criterion_id for r in self.criterion_results]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate criterion results.')
        return self


class Evidence(StrictModel):
    artifact_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    evidence_type: EvidenceType
    content: str = Field(min_length=1,max_length=60000)
    outcome: Literal['passed','failed','not_run','observed'] = 'observed'
    source_ref: str = Field(min_length=1,max_length=1000)


TRANSITIONS = {
    'REGISTERED': {'READY','NEEDS_INFO','FAILED','CANCELLED'},
    'NEEDS_INFO': {'READY','CANCELLED'},
    'READY': {'RUNNING','REVIEWING','WAITING_APPROVAL','BLOCKED_BUDGET','CANCELLED'},
    'RUNNING': {'REVIEWING','NEEDS_INFO','WAITING_APPROVAL','RECOVERING','FAILED','CANCELLED'},
    'REVIEWING': {'ACCEPT_CANDIDATE','NEEDS_REVISION','ESCALATED','WAITING_APPROVAL','CANCELLED'},
    'NEEDS_REVISION': {'READY','ESCALATED','BLOCKED_BUDGET','CANCELLED'},
    'WAITING_APPROVAL': {'READY','ESCALATED','CANCELLED'},
    'BLOCKED_BUDGET': {'READY','CANCELLED'},
    'ACCEPT_CANDIDATE': {'ACCEPTED','NEEDS_REVISION','ESCALATED','CANCELLED'},
    'ESCALATED': {'READY','NEEDS_INFO','FAILED','CANCELLED'},
    'RECOVERING': {'READY','REVIEWING','WAITING_APPROVAL','FAILED','CANCELLED'},
    'ACCEPTED': set(), 'FAILED': set(), 'CANCELLED': set(),
}
