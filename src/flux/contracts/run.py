"""Run states, usage, events, and RunResult contracts."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from flux.contracts.envelope import ArtifactSpec, CheckSpec
from flux.contracts.reviewer import ReviewDecision


RunState = Literal[
    "NEW",
    "VALIDATING",
    "PLANNING",
    "QUEUED",
    "RUNNING",
    "VERIFYING",
    "ACCEPT_CANDIDATE",
    "NEEDS_INPUT",
    "REVISE",
    "ESCALATED",
    "REJECTED",
    "PAUSED_BUDGET",
    "FAILED",
    "CANCELLED"
]


class UsageInfo(BaseModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    latency_ms: int = 0
    attempt: int = 1


class RunResult(BaseModel):
    schema_version: str = "1.0.0"
    run_id: str
    task_id: str
    root_id: str
    project_id: str
    status: RunState
    summary: str
    artifacts: List[ArtifactSpec] = Field(default_factory=list)
    checks: List[CheckSpec] = Field(default_factory=list)
    decision: Optional[ReviewDecision] = None
    unresolved_issues: List[str] = Field(default_factory=list)
    spent_cost_usd: float = 0.0
    reserved_cost_usd: float = 0.0
    unknown_cost_usd: float = 0.0
    total_calls: int = 0
    human_acceptance_required: bool = True
    completed_at: Optional[datetime] = None


class RunEvent(BaseModel):
    sequence: int
    run_id: str
    from_state: Optional[RunState] = None
    to_state: RunState
    reason: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
