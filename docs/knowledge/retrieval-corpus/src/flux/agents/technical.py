"""Technical Agent profile (GPT-5.6 Sol)."""

import json
from typing import Dict, List
from flux.contracts.head import SubtaskSpec
from flux.contracts.task import TaskInput

TECHNICAL_MODEL_ID = "gpt-5.6-sol"

TECHNICAL_SYSTEM_PROMPT = """You are Technical Agent (GPT-5.6 Sol).
Responsibilities:
- Design technical solutions, review architecture, evaluate technical risk.
- Perform high-level technical reviews of integrated outputs.

CRITICAL CONSTRAINTS:
- Output ONLY valid JSON matching this Envelope schema:
{
  "agent": "sol",
  "model_id": "gpt-5.6-sol",
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


def build_technical_prompt(task: TaskInput, subtask: SubtaskSpec) -> List[Dict[str, str]]:
    content = {
        "task_objective": task.objective,
        "subtask_id": subtask.subtask_id,
        "subtask_objective": subtask.objective,
        "acceptance_criteria": subtask.acceptance_criteria,
    }
    return [
        {"role": "system", "content": TECHNICAL_SYSTEM_PROMPT},
        {"role": "user", "content": f"Execute the technical review/design for this subtask:\n{json.dumps(content, ensure_ascii=False, indent=2)}"}
    ]
