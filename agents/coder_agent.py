"""
agents/coder_agent.py
━━━━━━━━━━━━━━━━━━━━
Agent 5 — Coder Agent

RESPONSIBILITY:
  Reads the failing test file for the current task.
  Generates Python code that makes those tests pass.
  Presents a diff to the user before applying (FR-09).
  Writes approved files to the filesystem via file_manager (safe writes only).

SATISFIES: FR-08, FR-09
INPUT:  state.task_list[current].test_file_path + context files
OUTPUT: state.task_list[current].generated_files (list of written file paths)
LLM:    DeepSeek Coder V2 via OpenRouter (~$0.001/1K tokens)
        Fallback: Gemini 1.5 Pro (free, 2 RPM)
"""

import os
import json
from orchestrator.state import FrameworkState
from tools.llm_router import router
from tools.file_manager import safe_write_file, safe_read_file
from tools.context_builder import build_task_context
from tools.diff_presenter import compute_and_present_diff
from utils.logger import log_action
from utils.exceptions import AgentError

CODER_SYSTEM = """You are an expert Python backend developer.
You write clean, minimal, well-typed FastAPI/Flask code.
You are given failing pytest tests. Your job: write code that makes exactly those tests pass.
Do not write more than what is needed to pass the tests.
Follow PEP8. Add type hints. Add docstrings for public functions.
Respond with a JSON object mapping file_path → file_content (full file, not a diff).
No explanations outside the JSON."""

CODER_PROMPT = """Write Python code to make these failing tests pass.

TASK:
{task_title}
{task_description}

FAILING TESTS (file: {test_file_path}):
{test_code}

ARCHITECTURE CONTEXT:
{arch_context}

EXISTING PROJECT FILES CONTENT:
{existing_context}

CODING STANDARDS FROM CONFIG:
- Python 3.11+
- Type hints required on all function signatures
- Pydantic v2 for request/response models
- SQLAlchemy 2.0 for DB operations
- pytest-compatible test structure
- No hardcoded secrets

Respond with JSON:
{{
  "files": {{
    "src/routes/example.py": "full file content here",
    "src/models/example.py": "full file content here"
  }},
  "explanation": "one sentence: what you implemented"
}}
"""


def _parse_coder_response(content: str) -> dict:
    """
    Parse the coder LLM response which may contain triple-quoted Python code.
    Standard JSON parsers fail on this — we extract files manually.
    Strategy: ask the LLM for a simpler format and parse it robustly.
    """
    import json
    import re

    # Try standard JSON first (sometimes it works)
    try:
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)
    except Exception:
        pass

    # Extract files using regex: look for "filename": followed by content
    files = {}
    # Pattern: "path/to/file.py": "content" or """content"""
    # We split on file path markers instead
    lines = content.split("\n")
    current_file = None
    current_lines = []
    in_file = False

    for line in lines:
        # Detect file path keys like "src/main.py":
        match = re.match(r'\s*["\']((?:src|tests?)/[\w/._-]+\.py)["\'\s]*:', line)
        if match:
            if current_file and current_lines:
                files[current_file] = "\n".join(current_lines)
            current_file = match.group(1)
            current_lines = []
            in_file = True
            continue
        if in_file and current_file:
            # Stop collecting if we hit the explanation key
            if '"explanation"' in line or "\'explanation\'" in line:
                if current_file and current_lines:
                    files[current_file] = "\n".join(current_lines)
                current_file = None
                current_lines = []
                in_file = False
                continue
            # Strip leading triple-quotes, trailing triple-quotes, escaped newlines
            cleaned = line.replace('\\\\', '\\').replace(\'\\n\', \'\\n\')
            cleaned = cleaned.strip(\'"\'\').strip(\'"""\'\')
            if cleaned not in ('"""', "\'\'\'", '",', '"'):
                current_lines.append(cleaned)

    if current_file and current_lines:
        files[current_file] = "\n".join(current_lines)

    if files:
        return {"files": files, "explanation": "parsed from response"}

    # Last resort: treat entire response as a single main.py file
    # Extract anything that looks like Python code
    code_match = re.search(r'```python\n(.*?)```', content, re.DOTALL)
    if code_match:
        return {"files": {"src/main.py": code_match.group(1)}, "explanation": "extracted from code block"}

    # Give up gracefully — return empty so the recovery agent handles it
    return {"files": {}, "explanation": "could not parse response"}


def run_coder(state: FrameworkState) -> FrameworkState:
    """
    Generates code for the current task.
    Reads failing tests → generates implementation → presents diff → writes files.
    """
    current_task = state.task_list[state.current_task_index]

    if not current_task.test_file_path:
        raise AgentError("CoderAgent", f"No test file for task {current_task.id} — QAAgent must run first")

    # Read the test file content
    test_code = safe_read_file(current_task.test_file_path)
    if not test_code:
        raise AgentError("CoderAgent", f"Test file is empty: {current_task.test_file_path}")

    # Build scoped context — only relevant existing files, not the whole repo
    arch_context = _get_arch_context(state, current_task)
    existing_context = build_task_context(state.output_directory, current_task)

    # Enrich prompt with error history if this is a retry
    task_description = current_task.description
    if current_task.error_history:
        last_error = current_task.error_history[-1]
        task_description += f"\n\nPREVIOUS ATTEMPT FAILED WITH:\n{last_error}\nFix this specific issue."

    prompt = CODER_PROMPT.format(
        task_title=current_task.title,
        task_description=task_description,
        test_file_path=current_task.test_file_path,
        test_code=test_code,
        arch_context=arch_context,
        existing_context=existing_context,
    )

    log_action(
        state.model_dump(),
        agent="CoderAgent",
        action=f"Generating code for task {current_task.id} (retry #{current_task.retry_count})",
    )

    response = router.call(
        agent="CoderAgent",
        system_prompt=CODER_SYSTEM,
        user_prompt=prompt,
        temperature=0.1,  # Low temperature for deterministic code
        max_tokens=6000,
        json_mode=False,  # json_mode breaks when code contains triple-quotes
        state=state.model_dump(),
    )

    data = _parse_coder_response(response.content)
    files_to_write: dict[str, str] = data.get("files", {})

    if not files_to_write:
        raise AgentError("CoderAgent", "LLM returned no files to write")

    # Compute and present diff to user (FR-09)
    # compute_and_present_diff shows what WILL change before applying
    approved_files = compute_and_present_diff(
        output_directory=state.output_directory,
        new_files=files_to_write,
    )

    # Write only approved files to filesystem (via safe_write_file which enforces NFR-05)
    written_paths = []
    for rel_path, content in approved_files.items():
        abs_path = os.path.join(state.output_directory, rel_path)
        safe_write_file(abs_path, content)
        written_paths.append(abs_path)
        log_action(
            state.model_dump(),
            agent="CoderAgent",
            action=f"File written: {rel_path}",
        )

    # Update task with generated file paths
    updated_tasks = list(state.task_list)
    updated_task = current_task.model_copy(update={"generated_files": written_paths})
    updated_tasks[state.current_task_index] = updated_task

    return state.model_copy(update={"task_list": updated_tasks})


def _get_arch_context(state: FrameworkState, task) -> str:
    """Return a compact JSON string of architecture relevant to this task."""
    if not state.architecture:
        return "{}"
    task_words = set((task.title + " " + task.description).lower().split())
    return json.dumps({
        "database": state.architecture.database_choice,
        "framework": state.architecture.framework_choice,
        "auth": state.architecture.auth_strategy,
        "relevant_models": [
            m.model_dump() for m in state.architecture.data_models
            if any(w in m.name.lower() for w in task_words)
        ],
    })
