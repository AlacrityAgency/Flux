"""Head Agent output schema contract."""

from typing import List, Literal
from pydantic import BaseModel, Field, field_validator


TaskType = Literal["planning", "operations", "documentation", "technical", "review", "mixed"]
CompanyRelevance = Literal["valid", "unclear", "invalid"]
RiskLevel = Literal["low", "medium", "high"]
AssignedAgent = Literal["opus", "sol", "luna", "qwen"]
FinalReviewAgent = Literal["qwen", "sol", "fable"]


class SubtaskSpec(BaseModel):
    subtask_id: str = Field(..., description="Unique subtask identifier")
    objective: str = Field(..., description="Subtask objective")
    assigned_agent: AssignedAgent = Field(..., description="Agent assigned to execute this subtask")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Subtask acceptance criteria")
    dependencies: List[str] = Field(default_factory=list, description="List of dependent subtask_ids")
    max_output_tokens: int = Field(default=2000, description="Maximum output tokens for this subtask")


class HeadOutput(BaseModel):
    task_type: TaskType = Field(..., description="Categorized task type")
    company_relevance: CompanyRelevance = Field(..., description="Relevance to company operations")
    summary: str = Field(..., description="Analysis summary")
    ambiguities: List[str] = Field(default_factory=list, description="Identified ambiguities")
    risk_level: RiskLevel = Field(default="low", description="Assessed risk level")
    requires_human_input: bool = Field(default=False, description="Whether human clarification is needed")
    subtasks: List[SubtaskSpec] = Field(default_factory=list, description="Up to 5 decomposed subtasks")
    final_review_agent: FinalReviewAgent = Field(default="qwen", description="Agent designated for final review")
    reason: str = Field(default="", description="Reasoning behind routing and planning")

    @field_validator("subtasks")
    @classmethod
    def validate_subtasks_count(cls, v: List[SubtaskSpec]) -> List[SubtaskSpec]:
        if len(v) > 5:
            raise ValueError(f"Head Agent cannot create more than 5 subtasks. Received: {len(v)}")
        # Verify unique subtask_ids
        ids = [s.subtask_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate subtask_id found in subtasks list.")
        return v
