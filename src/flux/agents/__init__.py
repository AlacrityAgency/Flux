"""Flux agents package."""

from flux.agents.head import HEAD_MODEL_ID, build_head_prompt
from flux.agents.planning import PLANNING_MODEL_ID, build_planning_prompt
from flux.agents.technical import TECHNICAL_MODEL_ID, build_technical_prompt
from flux.agents.execution import EXECUTION_MODEL_ID, build_execution_prompt
from flux.agents.verification import VERIFICATION_MODEL_ID, build_verification_prompt

__all__ = [
    "HEAD_MODEL_ID",
    "build_head_prompt",
    "PLANNING_MODEL_ID",
    "build_planning_prompt",
    "TECHNICAL_MODEL_ID",
    "build_technical_prompt",
    "EXECUTION_MODEL_ID",
    "build_execution_prompt",
    "VERIFICATION_MODEL_ID",
    "build_verification_prompt",
]
