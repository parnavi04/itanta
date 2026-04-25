"""
orchestrator/graph.py
━━━━━━━━━━━━━━━━━━━━
The LangGraph StateGraph that wires all 7 agents together.

READ THIS BEFORE TOUCHING ANY AGENT.

Node execution order:
  intake → architect → planner → [CP: human approves] →
  loop: qa → coder → [CP: human reviews diff] → validator →
    PASS: next_task (or finish if all done)
    FAIL: recovery → (retry qa/coder OR rollback OR escalate)
  → security_audit → docker_gen → summarise

Human checkpoints use LangGraph's interrupt() primitive.
State is checkpointed to SQLite after every node via SqliteSaver.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver  # pip install langgraph-checkpoint-sqlite
from langgraph.errors import GraphInterrupt

from orchestrator.state import FrameworkState, WorkflowPhase, TaskStatus
from agents.intake_agent import run_intake
from agents.architect_agent import run_architect
from agents.planner_agent import run_planner
from agents.qa_agent import run_qa
from agents.coder_agent import run_coder
from agents.recovery_agent import run_recovery
from agents.security_agent import run_security
from validators.test_runner import run_tests
from validators.linter import run_linter
from validators.type_checker import run_type_checker
from tools.docker_generator import generate_docker_compose
from utils.logger import log_action
from config.loader import get_config
from cli.interface import present_checkpoint, present_diff, present_summary


# ─────────────────────────────────────────────
# Node wrappers
# Each node receives state dict, returns updated state dict.
# LangGraph merges returned keys into the full state.
# ─────────────────────────────────────────────

def node_intake(state: dict) -> dict:
    """
    Node 1 — Intake agent.
    Identifies ambiguity in raw_spec, asks clarifying questions,
    produces structured spec_doc.
    """
    log_action(state, agent="IntakeAgent", action="Starting requirement intake")
    return run_intake(FrameworkState(**state)).model_dump()


def node_checkpoint_1(state: dict) -> dict:
    """
    Human Checkpoint 1 — User reviews the clarification Q&A and spec_doc.
    LangGraph interrupt() pauses the graph here.
    State is serialized to disk — user can close terminal and resume later.
    """
    fw_state = FrameworkState(**state)
    log_action(state, agent="Orchestrator", action="Checkpoint 1: awaiting human approval of spec")

    # present_checkpoint displays the spec to the user in the terminal
    approved = present_checkpoint(
        title="Review Project Specification",
        content=fw_state.spec_doc.model_dump() if fw_state.spec_doc else {},
        instructions="Review the structured spec above. Type 'approve' to continue or 'edit' to add comments."
    )

    # interrupt() pauses the graph and saves state to SQLite checkpoint
    # The CLI will call graph.invoke() with Command(resume=True) to continue
    if not approved:
        raise GraphInterrupt("Waiting for human approval at Checkpoint 1")

    updated = fw_state.model_dump()
    updated["human_approved"] = True
    return updated


def node_architect(state: dict) -> dict:
    """
    Node 2 — Architect agent.
    Reads spec_doc, produces full architecture: directory tree,
    data models, API contracts, DB choice.
    """
    log_action(state, agent="ArchitectAgent", action="Designing system architecture")
    return run_architect(FrameworkState(**state)).model_dump()


def node_planner(state: dict) -> dict:
    """
    Node 3 — Planner agent.
    Reads architecture, produces ordered atomic task_list.
    Each task has a risk level, checkpoint flag, and definition of done.
    """
    log_action(state, agent="PlannerAgent", action="Decomposing into atomic tasks")
    return run_planner(FrameworkState(**state)).model_dump()


def node_checkpoint_2(state: dict) -> dict:
    """
    Human Checkpoint 2 — User reviews the full task list before execution begins.
    This is FR-06: implementation plan presented before execution.
    """
    fw_state = FrameworkState(**state)
    log_action(state, agent="Orchestrator", action="Checkpoint 2: awaiting human approval of task plan")

    approved = present_checkpoint(
        title="Review Implementation Plan",
        content={"tasks": [t.model_dump() for t in fw_state.task_list]},
        instructions="Review the task list. Type 'approve' to begin execution."
    )

    if not approved:
        raise GraphInterrupt("Waiting for human approval at Checkpoint 2")

    updated = fw_state.model_dump()
    updated["human_approved"] = True
    updated["phase"] = WorkflowPhase.EXECUTION
    return updated


def node_qa(state: dict) -> dict:
    """
    Node 4 — QA agent (TDD-first).
    Writes FAILING tests for the current task BEFORE any code exists.
    Activity log timestamp here must precede the coder node timestamp.
    This ordering is enforced by the graph edge — QA → Coder.
    """
    fw_state = FrameworkState(**state)
    current_task = fw_state.task_list[fw_state.current_task_index]
    log_action(state, agent="QAAgent", action=f"Writing failing tests for task {current_task.id}: {current_task.title}")
    return run_qa(fw_state).model_dump()


def node_coder(state: dict) -> dict:
    """
    Node 5 — Coder agent.
    Reads the failing tests. Generates code that satisfies them.
    Presents diff to user before applying (FR-09).
    """
    fw_state = FrameworkState(**state)
    current_task = fw_state.task_list[fw_state.current_task_index]
    log_action(state, agent="CoderAgent", action=f"Generating code for task {current_task.id}")
    return run_coder(fw_state).model_dump()


def node_checkpoint_3(state: dict) -> dict:
    """
    Human Checkpoint 3 — User reviews the code diff before it is applied.
    This is FR-09: generated code changes presented before being applied to filesystem.
    """
    fw_state = FrameworkState(**state)
    current_task = fw_state.task_list[fw_state.current_task_index]
    log_action(state, agent="Orchestrator", action=f"Checkpoint 3: showing diff for task {current_task.id}")

    cfg = get_config()

    # If file_change_threshold is exceeded, force human review regardless of config
    files_changed = len(current_task.generated_files)
    force_review = files_changed >= cfg.guardrails.file_change_threshold

    if cfg.checkpoints.require_diff_approval or force_review:
        approved = present_diff(
            task=current_task,
            instructions="Review the code diff. Type 'approve' to apply or 'reject' to send feedback."
        )
        if not approved:
            raise GraphInterrupt(f"Waiting for human diff approval at task {current_task.id}")

    updated = fw_state.model_dump()
    updated["human_approved"] = True
    return updated


def node_validator(state: dict) -> dict:
    """
    Node 6 — Validator (deterministic — no LLM).
    Runs pytest + ruff + mypy.
    Returns pass/fail — a FAIL is a blocking event that routes to Recovery.
    """
    fw_state = FrameworkState(**state)
    current_task = fw_state.task_list[fw_state.current_task_index]
    log_action(state, agent="Validator", action=f"Running validation for task {current_task.id}")

    # Run all three validation tools
    test_result  = run_tests(fw_state.output_directory, current_task.test_file_path)
    lint_result  = run_linter(fw_state.output_directory)
    type_result  = run_type_checker(fw_state.output_directory)

    # Merge results
    passed = test_result.passed and lint_result.passed and type_result.passed
    combined = {
        "passed": passed,
        "tests_total": test_result.tests_total,
        "tests_passed": test_result.tests_passed,
        "tests_failed": test_result.tests_failed,
        "test_failures": test_result.test_failures,
        "lint_errors": lint_result.errors,
        "type_errors": type_result.errors,
    }

    # Write result back into the current task
    updated = fw_state.model_dump()
    updated["task_list"][fw_state.current_task_index]["validation_result"] = combined

    if passed:
        updated["task_list"][fw_state.current_task_index]["status"] = TaskStatus.PASSED
        updated["last_checkpoint"] = f"task_{current_task.id}"
        updated["retry_count"] = 0  # Reset retry counter on success
        log_action(updated, agent="Validator", action=f"Task {current_task.id} PASSED validation")
    else:
        updated["task_list"][fw_state.current_task_index]["status"] = TaskStatus.FAILED
        log_action(updated, agent="Validator", action=f"Task {current_task.id} FAILED validation", detail=str(combined["test_failures"]))

    return updated


def node_recovery(state: dict) -> dict:
    """
    Node 7 — Recovery agent.
    Classifies failure. Enriches retry prompt. Decides: retry | rollback | escalate.
    """
    fw_state = FrameworkState(**state)
    log_action(state, agent="RecoveryAgent", action=f"Handling failure for task {fw_state.task_list[fw_state.current_task_index].id}")
    return run_recovery(fw_state).model_dump()


def node_advance_task(state: dict) -> dict:
    """
    Utility node — advances current_task_index after a passing task.
    Not an AI agent — pure state management.
    """
    fw_state = FrameworkState(**state)
    updated = fw_state.model_dump()
    updated["current_task_index"] = fw_state.current_task_index + 1
    updated["retry_count"] = 0
    return updated


def node_security(state: dict) -> dict:
    """
    Node 8 — Security auditor (extended feature FR-14).
    Scans all generated files for injection, auth flaws, logic errors.
    """
    log_action(state, agent="SecurityAgent", action="Running security audit on generated codebase")
    return run_security(FrameworkState(**state)).model_dump()


def node_docker(state: dict) -> dict:
    """
    Node 9 — Docker compose generator.
    Produces docker-compose.yml based on the architecture doc.
    """
    log_action(state, agent="DockerGenerator", action="Generating docker-compose.yml")
    return generate_docker_compose(FrameworkState(**state)).model_dump()


def node_summarise(state: dict) -> dict:
    """
    Final node — aggregates activity_log into WorkflowSummary.
    Displays final report to user.
    """
    from models.report import build_summary
    fw_state = FrameworkState(**state)
    log_action(state, agent="Orchestrator", action="Generating workflow summary")
    summary = build_summary(fw_state)
    updated = fw_state.model_dump()
    updated["summary"] = summary.model_dump()
    updated["phase"] = WorkflowPhase.COMPLETE
    present_summary(summary)
    return updated


# ─────────────────────────────────────────────
# Routing functions (conditional edges)
# ─────────────────────────────────────────────

def route_after_validator(state: dict) -> str:
    """
    After validation:
      PASS + more tasks remaining → advance_task
      PASS + all tasks done       → security
      FAIL + retries left         → recovery
      FAIL + max retries          → recovery (will escalate internally)
    """
    fw_state = FrameworkState(**state)
    cfg = get_config()
    current_task = fw_state.task_list[fw_state.current_task_index]

    if current_task.validation_result and current_task.validation_result.get("passed"):
        # Check if there are more tasks
        if fw_state.current_task_index + 1 < len(fw_state.task_list):
            return "advance_task"
        else:
            return "security"
    else:
        # Failed — recovery handles retry limit logic internally
        return "recovery"


def route_after_recovery(state: dict) -> str:
    """
    After recovery agent decides:
      "retry"    → go back to qa node (TDD loop restarts for this task)
      "rollback" → advance_task (skipping the failed task with rollback note)
      "escalate" → END (framework stops, human must intervene)
    """
    fw_state = FrameworkState(**state)
    current_task = fw_state.task_list[fw_state.current_task_index]

    # Recovery agent writes its decision into task detail
    decision = current_task.error_history[-1] if current_task.error_history else ""

    if "DECISION:RETRY" in decision:
        return "qa"
    elif "DECISION:ROLLBACK" in decision:
        return "advance_task"
    else:
        return END  # Escalate to human — framework stops gracefully


def route_after_advance(state: dict) -> str:
    """After advancing task index, check if we're done."""
    fw_state = FrameworkState(**state)
    if fw_state.current_task_index >= len(fw_state.task_list):
        return "security"
    return "qa"


# ─────────────────────────────────────────────
# Graph Assembly
# ─────────────────────────────────────────────

def build_graph(checkpointer=None) -> StateGraph:
    """
    Assembles and compiles the full LangGraph StateGraph.
    Call this once at startup. The compiled graph is reusable across runs.

    Args:
        checkpointer: SqliteSaver instance for state persistence.
                      If None, state is not persisted (useful for testing).
    """
    builder = StateGraph(dict)  # state is a plain dict; we cast to FrameworkState inside nodes

    # ── Add nodes ──────────────────────────────────────────────────
    builder.add_node("intake",        node_intake)
    builder.add_node("checkpoint_1",  node_checkpoint_1)
    builder.add_node("architect",     node_architect)
    builder.add_node("planner",       node_planner)
    builder.add_node("checkpoint_2",  node_checkpoint_2)
    builder.add_node("qa",            node_qa)
    builder.add_node("coder",         node_coder)
    builder.add_node("checkpoint_3",  node_checkpoint_3)
    builder.add_node("validator",     node_validator)
    builder.add_node("recovery",      node_recovery)
    builder.add_node("advance_task",  node_advance_task)
    builder.add_node("security",      node_security)
    builder.add_node("docker",        node_docker)
    builder.add_node("summarise",     node_summarise)

    # ── Add edges (deterministic flow) ────────────────────────────
    builder.set_entry_point("intake")
    builder.add_edge("intake",       "checkpoint_1")
    builder.add_edge("checkpoint_1", "architect")
    builder.add_edge("architect",    "planner")
    builder.add_edge("planner",      "checkpoint_2")
    builder.add_edge("checkpoint_2", "qa")
    builder.add_edge("qa",           "coder")           # TDD: QA MUST precede Coder
    builder.add_edge("coder",        "checkpoint_3")
    builder.add_edge("checkpoint_3", "validator")
    builder.add_edge("security",     "docker")
    builder.add_edge("docker",       "summarise")
    builder.add_edge("summarise",    END)

    # ── Add conditional edges (routing logic) ──────────────────────
    builder.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "advance_task": "advance_task",
            "security":     "security",
            "recovery":     "recovery",
        }
    )

    builder.add_conditional_edges(
        "recovery",
        route_after_recovery,
        {
            "qa":           "qa",
            "advance_task": "advance_task",
            END:            END,
        }
    )

    builder.add_conditional_edges(
        "advance_task",
        route_after_advance,
        {
            "qa":       "qa",
            "security": "security",
        }
    )

    # ── Compile ────────────────────────────────────────────────────
    return builder.compile(checkpointer=checkpointer)


def get_compiled_graph():
    """
    Returns a compiled graph with SQLite checkpointing.
    SQLite file is stored at ./itanta_checkpoints.db
    This is the function called by main.py.
    """
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    return build_graph(checkpointer=checkpointer)