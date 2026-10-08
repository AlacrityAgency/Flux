"""Specialized Agent Envelope contract."""

from typing import Any, Dict, List, Literal
from pydantic import BaseModel, ConfigDict, Field


AgentRole = Literal["opus", "sol", "luna", "qwen"]
SubtaskStatus = Literal["completed", "needs_input", "failed"]
ArtifactType = Literal["text", "document", "code", "diff", "report", "test_result"]
CheckStatus = Literal["passed", "failed", "not_run"]


class ArtifactSpec(BaseModel):
    type: ArtifactType = Field(..., description="Type of artifact produced")
    ref: str = Field(..., description="Reference path or identifier of artifact")
    description: str = Field(default="", description="Description of the artifact")


class CheckSpec(BaseModel):
    name: str = Field(..., description="Criterion or test name")
    status: CheckStatus = Field(..., description="Result of the check")
    evidence: str = Field(default="", description="Detailed evidence supporting the status")


class EnvelopeOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    agent: AgentRole = Field(..., description="Agent role")
    model_id: str = Field(..., description="Model ID used")
    subtask_id: str = Field(..., description="Subtask identifier")
    status: SubtaskStatus = Field(..., description="Execution status of subtask")
    summary: str = Field(..., description="Executive summary of execution")
    output: Dict[str, Any] = Field(default_factory=dict, description="Structured output payload")
    artifacts: List[ArtifactSpec] = Field(default_factory=list, description="Artifacts generated")
    checks: List[CheckSpec] = Field(default_factory=list, description="Checks performed")
    unresolved_issues: List[str] = Field(default_factory=list, description="List of unresolved issues")
