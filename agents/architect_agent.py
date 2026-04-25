"""
agents/architect_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━
Agent 2 — Architect Agent

RESPONSIBILITY:
  Reads the locked StructuredSpec.
  Produces a complete ArchitectureDoc before any code is written.
  Determines: directory layout, data models, API contracts, DB choice, auth strategy.

SATISFIES: FR-04

INPUT:  state.spec_doc
OUTPUT: state.architecture
LLM:    Groq Llama 3.1 70B — free tier
"""

from orchestrator.state import FrameworkState, ArchitectureDoc, DataModel, APIEndpoint
from tools.llm_router import router
from utils.logger import log_action
from utils.exceptions import AgentError

ARCHITECT_SYSTEM = """You are a senior software architect specialising in Python REST APIs.
Design clean, minimal, production-ready system architectures.
Always respond in valid JSON only. No markdown. No preamble."""

ARCHITECT_PROMPT = """Design a complete system architecture for this project.

PROJECT SPEC:
{spec_json}

Respond with JSON matching this schema exactly:
{{
  "directory_tree": {{
    "src": {{
      "models": {{}},
      "routes": {{}},
      "services": {{}},
      "db": {{}}
    }},
    "tests": {{}}
  }},
  "data_models": [
    {{
      "name": "ModelName",
      "fields": {{"field_name": "type"}},
      "relationships": [],
      "table_name": "table_name"
    }}
  ],
  "api_endpoints": [
    {{
      "method": "GET",
      "path": "/api/v1/resource",
      "description": "what it does",
      "request_body": null,
      "response_schema": {{}},
      "auth_required": false,
      "status_codes": [200]
    }}
  ],
  "database_choice": "postgresql",
  "framework_choice": "fastapi",
  "auth_strategy": "none",
  "external_apis": [],
  "notes": "any important design decisions"
}}
"""


def run_architect(state: FrameworkState) -> FrameworkState:
    """Designs the full system architecture from the structured spec."""
    if not state.spec_doc:
        raise AgentError("ArchitectAgent", "spec_doc is missing — IntakeAgent must run first")

    import json
    prompt = ARCHITECT_PROMPT.format(spec_json=json.dumps(state.spec_doc.model_dump(), indent=2))

    response = router.call(
        agent="ArchitectAgent",
        system_prompt=ARCHITECT_SYSTEM,
        user_prompt=prompt,
        json_mode=True,
        state=state.model_dump(),
    )

    data = router.parse_json_response(response)

    architecture = ArchitectureDoc(
        directory_tree=data.get("directory_tree", {}),
        data_models=[
            DataModel(**{
                **m,
                "relationships": [
                    r if isinstance(r, str)
                    else r.get("model", str(r))
                    for r in m.get("relationships", [])
                ]
            })
            for m in data.get("data_models", [])
        ],
        api_endpoints=[APIEndpoint(**e) for e in data.get("api_endpoints", [])],
        database_choice=data.get("database_choice", "postgresql"),
        framework_choice=data.get("framework_choice", "fastapi"),
        auth_strategy=data.get("auth_strategy", "none"),
        external_apis=data.get("external_apis", []),
        notes=data.get("notes", ""),
    )

    log_action(
        state.model_dump(),
        agent="ArchitectAgent",
        action=f"Architecture designed: {len(architecture.api_endpoints)} endpoints, {len(architecture.data_models)} models",
    )

    return state.model_copy(update={"architecture": architecture})
