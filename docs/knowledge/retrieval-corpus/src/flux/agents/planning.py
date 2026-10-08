"""Planning Agent profile (Claude Opus 5)."""

import json
from typing import Dict, List
from flux.contracts.head import SubtaskSpec
from flux.contracts.task import TaskInput

PLANNING_MODEL_ID = "claude-opus-5"

PLANNING_SYSTEM_PROMPT = """You are Planning Agent (Claude Opus 5).
Responsibilities:
- Transform managerial objective into a structured execution plan.
- Identify scope boundaries, dependencies, acceptance criteria, and operational/technical handoffs.
- You do NOT execute code.

CRITICAL CONSTRAINTS:
- Output ONLY valid JSON matching this Envelope schema:
{
  "agent": "opus",
  "model_id": "claude-opus-5",
  "subtask_id": "string",
  "status": "completed|needs_input|failed",
  "summary": "string",
  "output": {},
  "artifacts": [
    {
      "type": "document|report",
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


def build_planning_prompt(task: TaskInput, subtask: SubtaskSpec) -> List[Dict[str, str]]:
    content = {
        "task_objective": task.objective,
        "subtask_id": subtask.subtask_id,
        "subtask_objective": subtask.objective,
        "acceptance_criteria": subtask.acceptance_criteria,
    }
    return [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": f"Plan the following subtask:\n{json.dumps(content, ensure_ascii=False, indent=2)}"}
    ]
