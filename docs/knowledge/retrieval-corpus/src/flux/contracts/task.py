"""Task input contract and pre-API validation."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


from flux.contracts.agents import AgentSettings

PriorityType = Literal["P0", "P1", "P2", "P3"]
DataClassType = Literal["public", "internal", "client_confidential", "secret"]


class TaskInput(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    root_id: str = Field(..., description="Root task identifier")
    project_id: str = Field(..., description="Project identifier")
    human_owner: str = Field(..., description="Human owner responsible for task")
    objective: str = Field(..., description="Goal of the task")
    scope: List[str] = Field(default_factory=list, description="In-scope elements")
    out_of_scope: List[str] = Field(default_factory=list, description="Out-of-scope elements")
    acceptance_criteria: List[str] = Field(..., description="List of acceptance criteria")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies on other task IDs")
    allowed_tools: List[str] = Field(default_factory=list, description="List of allowed tools")
    allowed_paths: List[str] = Field(default_factory=list, description="List of allowed filesystem paths")
    artifact_refs: List[str] = Field(default_factory=list, description="References to existing artifacts")
    budget_cap_usd: float = Field(..., allow_inf_nan=False, description="Budget cap in USD (must be > 0)")
    agent_settings: AgentSettings = Field(default_factory=AgentSettings)
    context: list[dict] = Field(default_factory=list, max_length=12)
    workflow: Literal["low", "medium", "high", "auto", "team"] = "low"
    max_attempts: int = Field(default=3, description="Maximum attempts for subtasks")
    priority: PriorityType = Field(default="P1", description="Priority level")
    data_class: DataClassType = Field(default="internal", description="Data classification level")

    @field_validator("task_id", "root_id", "project_id", "human_owner")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty.")
        return v.strip()

    @field_validator("objective")
    @classmethod
    def validate_objective(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field 'objective' must not be empty.")
        if len(v.strip()) < 5:
            raise ValueError("Field 'objective' is too brief or vague.")
        return v.strip()

    @field_validator("acceptance_criteria")
    @classmethod
    def validate_acceptance_criteria(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise ValueError("Field 'acceptance_criteria' must contain at least one criterion.")
        cleaned = [c.strip() for c in v if c and c.strip()]
        if not cleaned:
            raise ValueError("Field 'acceptance_criteria' must not contain only empty strings.")
        return cleaned

    @field_validator("budget_cap_usd")
    @classmethod
    def validate_budget_cap(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Field 'budget_cap_usd' must be strictly positive.")
        return v

    @field_validator("max_attempts")
    @classmethod
    def validate_max_attempts(cls, v: int) -> int:
        if v < 1 or v > 3:
            raise ValueError("Field 'max_attempts' must be between 1 and 3.")
        return v

    @field_validator("data_class")
    @classmethod
    def validate_data_class(cls, v: DataClassType) -> DataClassType:
        if v == "secret":
            raise ValueError("Execution with data_class='secret' is strictly prohibited.")
        return v


def validate_task_pre_api(task: TaskInput) -> tuple[bool, Optional[str]]:
    """Strict deterministic pre-API validation of task."""
    try:
        # Pydantic validation handles most checks; additional domain checks here:
        if task.data_class == "secret":
            return False, "data_class 'secret' is not permitted"
        if task.budget_cap_usd <= 0:
            return False, "budget_cap_usd must be > 0"
        if not task.acceptance_criteria:
            return False, "acceptance_criteria must not be empty"
        return True, None
    except Exception as e:
        return False, str(e)
