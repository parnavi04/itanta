"""
agents/intake_agent.py
━━━━━━━━━━━━━━━━━━━━━
Agent 1 — Intake Agent

RESPONSIBILITY:
  Accepts raw natural-language project spec.
  Identifies underspecified aspects.
  Asks user targeted clarifying questions (max 5).
  Produces a locked StructuredSpec that all downstream agents rely on.

SATISFIES: FR-01, FR-02

INPUT STATE FIELDS USED:
  state.raw_spec

OUTPUT STATE FIELDS WRITTEN:
  state.clarification_qa   (list of Q&A pairs)
  state.spec_doc           (StructuredSpec)

LLM: Groq Llama 3.1 70B — free tier
"""

import json
from orchestrator.state import FrameworkState, ClarificationQA, StructuredSpec, AcceptanceCriteria
from tools.llm_router import router
from utils.logger import log_action
from utils.exceptions import AgentError
from cli.interface import ask_clarification_questions

# ── System prompt ────────────────────────────────────────────────────────────
# This persona is injected as the system message on every Intake call.

INTAKE_SYSTEM_PROMPT = """You are a senior software requirements analyst.
Your job is to receive a rough project description and produce two things:

1. A list of clarifying questions (maximum 5) that, if answered, would
   eliminate the most critical ambiguities. Ask only what is genuinely needed.
   Do NOT ask questions with obvious answers. Do NOT ask for nice-to-haves.

2. After questions are answered, a structured specification document.

Always respond in valid JSON only. No preamble. No markdown fences.
"""

AMBIGUITY_DETECTION_PROMPT = """Analyse this project specification and identify ambiguities.

PROJECT SPEC:
{raw_spec}

Respond with JSON matching this exact schema:
{{
  "ambiguities": ["list of underspecified aspects as short phrases"],
  "questions": [
    {{
      "question": "Clear, specific question text",
      "why_needed": "One sentence: what design decision this unlocks"
    }}
  ]
}}

Maximum 5 questions. Focus only on questions that change the architecture or scope.
"""

SPEC_GENERATION_PROMPT = """Generate a structured project specification.

ORIGINAL SPEC:
{raw_spec}

USER'S ANSWERS TO CLARIFYING QUESTIONS:
{qa_pairs}

Respond with JSON matching this exact schema:
{{
  "project_name": "snake_case_name",
  "project_summary": "2-3 sentence description of what will be built",
  "acceptance_criteria": [
    {{"description": "verifiable criterion", "is_testable": true}}
  ],
  "proposed_architecture_notes": "key architectural decisions inferred from the spec",
  "known_constraints": ["list of constraints mentioned or implied"],
  "tech_stack_hints": ["any tech explicitly mentioned by user"],
  "target_tier": 1
}}

target_tier must be 1-5 based on complexity:
  1 = simple CRUD, 2 = business logic, 3 = external API integration,
  4 = auth/RBAC system, 5 = complex DB operations
"""


# ── Agent function ────────────────────────────────────────────────────────────

def run_intake(state: FrameworkState) -> FrameworkState:
    """
    Main entry point for the Intake agent.
    Called by orchestrator/graph.py node_intake().

    Step 1: Detect ambiguities in raw_spec
    Step 2: Generate clarifying questions
    Step 3: Present questions to user and collect answers
    Step 4: Generate structured StructuredSpec from spec + answers
    Step 5: Write results back to state
    """
    log_action(state.model_dump(), agent="IntakeAgent", action="Analysing raw spec for ambiguities")

    if not state.raw_spec or len(state.raw_spec.strip()) < 10:
        raise AgentError("IntakeAgent", "raw_spec is empty or too short to analyse")

    # ── Step 1+2: Detect ambiguities and generate questions ──────────────────

    prompt = AMBIGUITY_DETECTION_PROMPT.format(raw_spec=state.raw_spec)
    response = router.call(
        agent="IntakeAgent",
        system_prompt=INTAKE_SYSTEM_PROMPT,
        user_prompt=prompt,
        json_mode=True,
        state=state.model_dump(),
    )

    try:
        analysis = router.parse_json_response(response)
        questions = [q["question"] for q in analysis.get("questions", [])]
    except Exception as e:
        raise AgentError("IntakeAgent", f"Failed to parse ambiguity analysis: {e}")

    log_action(
        state.model_dump(),
        agent="IntakeAgent",
        action=f"Identified {len(questions)} clarifying questions",
        detail=json.dumps(questions),
    )

    # ── Step 3: Collect answers from user ───────────────────────────────────
    # This calls the CLI interface to present questions and collect answers interactively.

    answers = ask_clarification_questions(questions)

    # Build Q&A pairs for state
    qa_pairs = [
        ClarificationQA(question=q, answer=a, answered=True)
        for q, a in zip(questions, answers)
    ]

    # ── Step 4: Generate structured spec ────────────────────────────────────

    qa_text = "\n".join([f"Q: {qa.question}\nA: {qa.answer}" for qa in qa_pairs])
    spec_prompt = SPEC_GENERATION_PROMPT.format(
        raw_spec=state.raw_spec,
        qa_pairs=qa_text,
    )

    spec_response = router.call(
        agent="IntakeAgent",
        system_prompt=INTAKE_SYSTEM_PROMPT,
        user_prompt=spec_prompt,
        json_mode=True,
        state=state.model_dump(),
    )

    try:
        spec_data = router.parse_json_response(spec_response)
    except Exception as e:
        raise AgentError("IntakeAgent", f"Failed to parse spec generation response: {e}")

    # Build typed StructuredSpec
    spec_doc = StructuredSpec(
        project_name=spec_data.get("project_name", "unnamed_project"),
        project_summary=spec_data.get("project_summary", ""),
        acceptance_criteria=[
            AcceptanceCriteria(**ac) for ac in spec_data.get("acceptance_criteria", [])
        ],
        proposed_architecture_notes=spec_data.get("proposed_architecture_notes", ""),
        known_constraints=spec_data.get("known_constraints", []),
        tech_stack_hints=spec_data.get("tech_stack_hints", []),
        target_tier=spec_data.get("target_tier", 1),
    )

    log_action(
        state.model_dump(),
        agent="IntakeAgent",
        action=f"Produced structured spec for: {spec_doc.project_name} (Tier {spec_doc.target_tier})",
    )

    # ── Step 5: Write back to state ──────────────────────────────────────────

    updated = state.model_copy(update={
        "clarification_qa": qa_pairs,
        "spec_doc": spec_doc,
    })

    return updated
