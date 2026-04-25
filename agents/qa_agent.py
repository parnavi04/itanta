"""
agents/qa_agent.py
━━━━━━━━━━━━━━━━━
Agent 4 — QA Agent (TDD-First)

RESPONSIBILITY:
  For each task, write FAILING pytest tests BEFORE any production code exists.
  Tests must be written to disk and confirmed failing before Coder runs.
  Activity log timestamp here MUST precede the Coder agent timestamp.

CRITICAL: If tests pass before code is written, they are useless. This agent
must verify the tests fail after writing them.

SATISFIES: FR-11
INPUT:  state.task_list[current_task_index], state.architecture, state.spec_doc
OUTPUT: state.task_list[current_task_index].test_file_path
LLM:    Gemini 1.5 Flash — free tier (separate provider to avoid Groq rate limits)
"""

import os
import json
import subprocess
from orchestrator.state import FrameworkState, TaskStatus
from tools.llm_router import router
from tools.file_manager import safe_write_file
from utils.logger import log_action
from utils.exceptions import AgentError

QA_SYSTEM = """You are a senior QA engineer writing pytest test cases using Test-Driven Development.
You write tests BEFORE the implementation exists.
Tests must be specific, meaningful, and actually verify the contract — not just import checks.
Always include: success path, at least 2 failure/edge cases, 1 boundary condition.
Respond with valid Python pytest code only. No explanations."""

QA_PROMPT = """Write failing pytest tests for this task.

TASK:
{task_json}

ARCHITECTURE CONTEXT:
{arch_context}

EXISTING PROJECT FILES (for import context):
{existing_files}

Write a complete pytest file. Requirements:
- Import from the path where the implementation WILL be (e.g., from src.routes.books import router)
- Tests must FAIL right now because the implementation doesn't exist yet
- Test function names must be descriptive: test_<what>_<condition>
- Include fixtures if needed (e.g., TestClient, DB session)
- Use pytest-style asserts, not unittest

Return ONLY the Python code. No markdown. No explanation.
"""


def run_qa(state: FrameworkState) -> FrameworkState:
    """
    Writes failing tests for the current task.
    Verifies they fail (if code exists from previous tasks that might accidentally pass them).
    Writes test file to disk.
    """
    current_task = state.task_list[state.current_task_index]

    log_action(
        state.model_dump(),
        agent="QAAgent",
        action=f"Writing TDD tests for task {current_task.id}: {current_task.title}",
    )

    # Build context: only pass architecture context relevant to this task
    arch_context = _build_arch_context(state, current_task)
    existing_files = _list_existing_files(state.output_directory)

    prompt = QA_PROMPT.format(
        task_json=json.dumps(current_task.model_dump(), indent=2),
        arch_context=arch_context,
        existing_files=existing_files,
    )

    response = router.call(
        agent="QAAgent",
        system_prompt=QA_SYSTEM,
        user_prompt=prompt,
        state=state.model_dump(),
    )

    test_code = response.content.strip()
    if test_code.startswith("```"):
        lines = test_code.split("\n")
        test_code = "\n".join(lines[1:-1])

    # Write test file to disk
    test_file_name = f"test_task_{current_task.id}_{current_task.title.lower().replace(' ', '_')[:30]}.py"
    test_file_path = os.path.join(state.output_directory, "tests", test_file_name)

    safe_write_file(test_file_path, test_code)

    log_action(
        state.model_dump(),
        agent="QAAgent",
        action=f"Test file written: {test_file_path}",
        detail=f"Tests must fail before code is generated — confirming...",
    )

    # Verify tests fail (they SHOULD fail — no implementation exists yet)
    # If they pass, the tests are bad (testing nothing or always true)
    _verify_tests_fail(test_file_path, state)

    # Update task with test file path
    updated_tasks = list(state.task_list)
    updated_task = current_task.model_copy(update={
        "test_file_path": test_file_path,
        "status": TaskStatus.IN_PROGRESS,
    })
    updated_tasks[state.current_task_index] = updated_task

    return state.model_copy(update={"task_list": updated_tasks})


def _build_arch_context(state: FrameworkState, task) -> str:
    """Extract only the architecture pieces relevant to this task."""
    if not state.architecture:
        return ""
    # Find relevant endpoints and models for this task by keyword matching
    task_words = set(task.title.lower().split() + task.description.lower().split())
    relevant_endpoints = [
        e.model_dump() for e in state.architecture.api_endpoints
        if any(word in e.path.lower() or word in e.description.lower() for word in task_words)
    ]
    relevant_models = [
        m.model_dump() for m in state.architecture.data_models
        if any(word in m.name.lower() for word in task_words)
    ]
    return json.dumps({"endpoints": relevant_endpoints, "models": relevant_models})


def _list_existing_files(output_dir: str) -> str:
    """Return a flat list of existing .py files for import context."""
    if not output_dir or not os.path.exists(output_dir):
        return "No files exist yet."
    files = []
    for root, _, filenames in os.walk(output_dir):
        for f in filenames:
            if f.endswith(".py") and "test_" not in f:
                rel = os.path.relpath(os.path.join(root, f), output_dir)
                files.append(rel)
    return "\n".join(files) if files else "No source files yet."


def _verify_tests_fail(test_file_path: str, state: FrameworkState):
    """
    Run the test file and confirm it fails.
    If it passes (green), the tests are trivially true — warn but don't block.
    """
    result = subprocess.run(
        ["python", "-m", "pytest", test_file_path, "--tb=no", "-q"],
        capture_output=True, text=True,
        cwd=state.output_directory or ".",
    )
    if result.returncode == 0:
        log_action(
            state.model_dump(),
            agent="QAAgent",
            action="WARNING: Tests passed before implementation — tests may be trivial",
            detail=result.stdout,
        )
    else:
        log_action(
            state.model_dump(),
            agent="QAAgent",
            action="CONFIRMED: Tests fail as expected (TDD condition met)",
        )
