"""Verification Agent profile (Qwen 3.6 Thinking)."""

import json
from typing import Any, Dict, List
from flux.contracts.task import TaskInput
from flux.contracts.envelope import ArtifactSpec, CheckSpec

VERIFICATION_MODEL_ID = "gapgpt-qwen-3.6-thinking"

VERIFICATION_SYSTEM_PROMPT = """You are Verification Agent (Qwen 3.6 Thinking).
Responsibilities:
- Independently evaluate produced artifacts and checks against root acceptance criteria.
- Analyze test results and find documented defects.
- Issue decisions: ACCEPT_CANDIDATE, REVISE, ESCALATE, or REJECT.

CRITICAL RULES:
1. An un-executed test ('not_run') is NOT equivalent to passed. If any necessary check is 'not_run', you CANNOT issue ACCEPT_CANDIDATE.
2. REVISE is ONLY allowed with precise, actionable blocking issues.
3. You CANNOT modify contractor output yourself or weaken/alter acceptance criteria.
4. ACCEPT_CANDIDATE represents human acceptance candidate, not final human acceptance.
5. For every satisfied acceptance criterion, copy its exact original text into
   passed_criteria. Do not paraphrase, shorten, translate, or substitute it.

CRITICAL CONSTRAINTS:
- Output ONLY valid JSON matching this schema:
{
  "decision": "ACCEPT_CANDIDATE|REVISE|ESCALATE|REJECT",
  "blocking_issues": [
    {
      "criterion": "string",
      "evidence": "string",
      "required_change": "string"
    }
  ],
  "passed_criteria": ["string"],
  "failed_criteria": ["string"],
  "confidence": "low|medium|high"
}
"""


def build_verification_prompt(
    task: TaskInput,
    artifacts: List[ArtifactSpec],
    checks: List[CheckSpec],
    subtask_summaries: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    content = {
        "root_objective": task.objective,
        "acceptance_criteria": task.acceptance_criteria,
        "artifacts_to_verify": [a.model_dump() for a in artifacts],
        "checks_reported": [c.model_dump() for c in checks],
        "subtask_summaries": subtask_summaries
    }
    return [
        {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Verify the following execution results against acceptance criteria:\n{json.dumps(content, ensure_ascii=False, indent=2)}"}
    ]
