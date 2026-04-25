"""
agents/recovery_agent.py
━━━━━━━━━━━━━━━━━━━━━━━
Agent 6 — Recovery Agent

RESPONSIBILITY:
  Triggered after Validator reports a failure.
  Classifies the failure type.
  Decides: RETRY (with enriched context) | ROLLBACK | ESCALATE to human.
  Writes its decision as "DECISION:RETRY" / "DECISION:ROLLBACK" into error_history
  so the graph router (route_after_recovery) can read it.

SATISFIES: FR-15, FR-17
INPUT:  state.task_list[current].validation_result + error_history
OUTPUT: state.task_list[current].error_history (appended), state.retry_count
LLM:    Groq Llama 3.1 8B — free tier (fast, lightweight reasoning)
"""

import json
from orchestrator.state import FrameworkState, TaskStatus
from tools.llm_router import router
from tools.file_manager import restore_checkpoint
from utils.logger import log_action
from utils.exceptions import AgentError
from config.loader import get_config

RECOVERY_SYSTEM = """You are a debugging specialist analysing test failures in generated code.
Classify the failure and produce a targeted fix strategy.
Be concise. Respond in JSON only."""

RECOVERY_PROMPT = """Analyse this test failure and decide how to fix it.

TASK:
{task_title}

VALIDATION FAILURE:
{validation_result}

RETRY COUNT: {retry_count} / {max_retries}

ERROR HISTORY (previous attempts):
{error_history}

Respond with JSON:
{{
  "failure_type": "test_assertion|syntax_error|import_error|type_error|logic_error",
  "root_cause": "one sentence describing the actual problem",
  "fix_strategy": "specific instruction for the Coder agent on what to fix",
  "decision": "RETRY|ROLLBACK|ESCALATE",
  "decision_reason": "why you chose this decision"
}}

Decision rules:
- RETRY if retry_count < max_retries and the error is fixable with more context
- ROLLBACK if the task is blocked by a dependency or architectural issue
- ESCALATE if max_retries reached or the failure requires human architectural decisions
"""


def run_recovery(state: FrameworkState) -> FrameworkState:
    """
    Analyses failure, enriches the context, and decides the next step.
    Writes DECISION:RETRY / DECISION:ROLLBACK / DECISION:ESCALATE to error_history.
    """
    cfg = get_config()
    current_task = state.task_list[state.current_task_index]
    validation_result = current_task.validation_result or {}

    log_action(
        state.model_dump(),
        agent="RecoveryAgent",
        action=f"Analysing failure for task {current_task.id} (attempt {state.retry_count + 1}/{cfg.max_retries})",
    )

    # Hard limit check — don't even call LLM if at max retries
    if state.retry_count >= cfg.max_retries:
        log_action(
            state.model_dump(),
            agent="RecoveryAgent",
            action=f"Max retries ({cfg.max_retries}) reached — escalating to human",
        )
        updated_tasks = list(state.task_list)
        updated_task = current_task.model_copy(update={
            "error_history": current_task.error_history + [
                f"DECISION:ESCALATE — max retries reached after {state.retry_count} attempts"
            ],
            "status": TaskStatus.FAILED,
        })
        updated_tasks[state.current_task_index] = updated_task
        return state.model_copy(update={"task_list": updated_tasks})

    # Summarise validation errors for the prompt
    error_summary = _format_validation_errors(validation_result)
    error_history_str = "\n".join(current_task.error_history[-3:]) if current_task.error_history else "None"

    prompt = RECOVERY_PROMPT.format(
        task_title=current_task.title,
        validation_result=error_summary,
        retry_count=state.retry_count,
        max_retries=cfg.max_retries,
        error_history=error_history_str,
    )

    response = router.call(
        agent="RecoveryAgent",
        system_prompt=RECOVERY_SYSTEM,
        user_prompt=prompt,
        json_mode=True,
        state=state.model_dump(),
    )

    analysis = router.parse_json_response(response)
    decision = analysis.get("decision", "ESCALATE").upper()
    fix_strategy = analysis.get("fix_strategy", "")
    root_cause = analysis.get("root_cause", "Unknown")

    log_action(
        state.model_dump(),
        agent="RecoveryAgent",
        action=f"Decision: {decision} | Root cause: {root_cause}",
        detail=fix_strategy,
    )

    # Build enriched error entry that Coder agent will read on next retry
    enriched_error = (
        f"DECISION:{decision}\n"
        f"ROOT CAUSE: {root_cause}\n"
        f"FIX STRATEGY: {fix_strategy}\n"
        f"ERRORS:\n{error_summary}"
    )

    updated_tasks = list(state.task_list)
    updated_task = current_task.model_copy(update={
        "error_history": current_task.error_history + [enriched_error],
        "retry_count": current_task.retry_count + 1,
    })
    updated_tasks[state.current_task_index] = updated_task

    new_retry_count = state.retry_count + 1 if decision == "RETRY" else state.retry_count

    # Handle rollback — restore filesystem to last checkpoint
    if decision == "ROLLBACK" and state.last_checkpoint:
        log_action(
            state.model_dump(),
            agent="RecoveryAgent",
            action=f"Rolling back to checkpoint: {state.last_checkpoint}",
        )
        restore_checkpoint(state.last_checkpoint, state.output_directory)

    return state.model_copy(update={
        "task_list": updated_tasks,
        "retry_count": new_retry_count,
    })


def _format_validation_errors(validation_result: dict) -> str:
    """Format validation errors into a compact string for the recovery prompt."""
    parts = []
    if validation_result.get("test_failures"):
        parts.append("TEST FAILURES:\n" + "\n".join(validation_result["test_failures"][:3]))
    if validation_result.get("lint_errors"):
        parts.append("LINT ERRORS:\n" + "\n".join(validation_result["lint_errors"][:5]))
    if validation_result.get("type_errors"):
        parts.append("TYPE ERRORS:\n" + "\n".join(validation_result["type_errors"][:5]))
    return "\n\n".join(parts) if parts else "No detailed error information available"
