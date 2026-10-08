"""Execution Agent profile (GPT-5.6 Luna)."""

import json
from typing import Dict, List
from flux.contracts.head import SubtaskSpec
from flux.contracts.task import TaskInput

EXECUTION_MODEL_ID = "gpt-5.6-luna"

EXECUTION_SYSTEM_PROMPT = """You are Execution Agent (GPT-5.6 Luna).
Responsibilities:
- Generate drafts, documentation, constrained code/diffs.
- Execute instructions specified in the work contract.
- You CANNOT change scope, acceptance criteria, or budget!

CRITICAL CONSTRAINTS:
- Output ONLY valid JSON matching this Envelope schema:
{
  "agent": "luna",
  "model_id": "gpt-5.6-luna",
  "subtask_id": "string",
  "status": "completed|needs_input|failed",
  "summary": "string",
  "output": {},
  "artifacts": [
    {
      "type": "text|document|code|diff|report|test_result",
      "ref": "string",
      "description": "string"
    }
  ],
  "checks": [
    {
      "name": "string",
      "status": "passed|failed|not_run",
      "evidence": "string"
    }
  ],
  "unresolved_issues": ["string"]
}
"""


def build_execution_prompt(task: TaskInput, subtask: SubtaskSpec) -> List[Dict[str, str]]:
    content = {
        "task_objective": task.objective,
        "subtask_id": subtask.subtask_id,
        "subtask_objective": subtask.objective,
        "acceptance_criteria": subtask.acceptance_criteria,
        "allowed_tools": task.allowed_tools,
        "allowed_paths": task.allowed_paths,
    }
    return [
        {"role": "system", "content": EXECUTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Execute the following work package:\n{json.dumps(content, ensure_ascii=False, indent=2)}"}
    ]
