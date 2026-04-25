"""
agents/planner_agent.py
━━━━━━━━━━━━━━━━━━━━━━
Agent 3 — Planner Agent

RESPONSIBILITY:
  Reads ArchitectureDoc.
  Produces an ordered list of atomic tasks.
  Each task = one independently testable unit of work.

SATISFIES: FR-05
INPUT:  state.architecture
OUTPUT: state.task_list
LLM:    Groq Llama 3.1 70B
"""

import json
from orchestrator.state import FrameworkState, Task, RiskLevel
from tools.llm_router import router
from utils.logger import log_action
from utils.exceptions import AgentError

PLANNER_SYSTEM = """You are a senior technical lead decomposing a software project into tasks.
Each task must be atomic: it produces exactly one independently verifiable unit of output.
Order tasks by dependency — a task must not depend on code not yet written.
Respond in valid JSON only."""

PLANNER_PROMPT = """Break down this architecture into ordered atomic implementation tasks.

ARCHITECTURE:
{arch_json}

PROJECT SPEC:
{spec_json}

Respond with JSON:
{{
  "tasks": [
    {{
      "id": 1,
      "title": "Short title",
      "description": "Exact definition of done — what this task produces",
      "risk_level": "low|medium|high",
      "requires_human_checkpoint": false,
      "depends_on": []
    }}
  ]
}}

Rules:
- One task per API endpoint minimum
- DB schema setup must be task 1
- Auth tasks must come after models
- Maximum 20 tasks for Tier 1-2, 35 for Tier 3-5
"""


def run_planner(state: FrameworkState) -> FrameworkState:
    """Converts architecture into an ordered atomic task list."""
    if not state.architecture:
        raise AgentError("PlannerAgent", "architecture is missing")

    prompt = PLANNER_PROMPT.format(
        arch_json=json.dumps(state.architecture.model_dump(), indent=2),
        spec_json=json.dumps(state.spec_doc.model_dump(), indent=2) if state.spec_doc else "{}",
    )

    response = router.call(
        agent="PlannerAgent",
        system_prompt=PLANNER_SYSTEM,
        user_prompt=prompt,
        json_mode=True,
        state=state.model_dump(),
    )

    data = router.parse_json_response(response)
    tasks = [
        Task(
            id=t["id"],
            title=t["title"],
            description=t["description"],
            risk_level=RiskLevel(t.get("risk_level", "low")),
            requires_human_checkpoint=t.get("requires_human_checkpoint", False),
            depends_on=t.get("depends_on", []),
        )
        for t in data.get("tasks", [])
    ]

    log_action(
        state.model_dump(),
        agent="PlannerAgent",
        action=f"Created {len(tasks)} atomic tasks",
    )

    return state.model_copy(update={"task_list": tasks})
