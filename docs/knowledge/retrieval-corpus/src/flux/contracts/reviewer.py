"""Reviewer Decision schema for Verification Agent."""

from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


ReviewDecisionType = Literal["ACCEPT_CANDIDATE", "REVISE", "ESCALATE", "REJECT"]
ConfidenceLevel = Literal["low", "medium", "high"]


class BlockingIssue(BaseModel):
    criterion: str = Field(..., description="Criterion that was violated")
    evidence: str = Field(..., description="Concrete evidence of violation")
    required_change: str = Field(..., description="Actionable change needed to resolve issue")


class ReviewDecision(BaseModel):
    decision: ReviewDecisionType = Field(..., description="Reviewer decision")
    blocking_issues: List[BlockingIssue] = Field(default_factory=list, description="List of blocking issues")
    passed_criteria: List[str] = Field(default_factory=list, description="Criteria successfully passed")
    failed_criteria: List[str] = Field(default_factory=list, description="Criteria that failed")
    confidence: ConfidenceLevel = Field(default="high", description="Reviewer confidence")

    @model_validator(mode="after")
    def validate_rules(self) -> "ReviewDecision":
        # Rule: REVISE must provide at least one blocking issue
        if self.decision == "REVISE" and not self.blocking_issues:
            raise ValueError("Decision 'REVISE' requires at least one precise blocking issue.")
        # Rule: ACCEPT_CANDIDATE cannot have blocking issues or failed criteria
        if self.decision == "ACCEPT_CANDIDATE":
            if self.blocking_issues:
                raise ValueError("Decision 'ACCEPT_CANDIDATE' cannot contain blocking issues.")
            if self.failed_criteria:
                raise ValueError("Decision 'ACCEPT_CANDIDATE' cannot contain failed criteria.")
        return self
