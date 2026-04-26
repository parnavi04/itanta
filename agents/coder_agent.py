"""
agents/coder_agent.py — Clean rewrite with working JSON parser
"""

import os
import re
import json
from orchestrator.state import FrameworkState
from tools.llm_router import router
from tools.file_manager import safe_write_file, safe_read_file
from tools.context_builder import build_task_context
from tools.diff_presenter import compute_and_present_diff
from utils.logger import log_action
from utils.exceptions import AgentError

CODER_SYSTEM = """You are an expert Python backend developer.
Write clean FastAPI/SQLAlchemy code that makes the given failing tests pass.

Respond ONLY with a JSON object in this exact format:
{
  "files": {
    "src/filename.py": "file content using \\n for newlines"
  },
  "explanation": "one sentence"
}

CRITICAL: Use \\n for newlines inside string values. Never use triple quotes inside JSON."""

CODER_PROMPT = """Write Python code to make these failing tests pass.

TASK: {task_title}
{task_description}

FAILING TESTS ({test_file_path}):
{test_code}

ARCHITECTURE:
{arch_context}

EXISTING FILES:
{existing_context}

Respond with JSON. File content must use \\n for newlines. No triple quotes."""


def _parse_coder_response(content):
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
    try:
        data = json.loads(text)
        if "files" in data:
            return data
    except Exception:
        pass

    files = {}
    path_pattern = re.compile(r'"((?:src|tests?)/[\w/.\-]+\.py)"\s*:\s*')
    matches = list(path_pattern.finditer(text))

    for i, match in enumerate(matches):
        file_path = match.group(1)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            exp_match = re.search(r'"explanation"\s*:', text[start:])
            end = start + exp_match.start() if exp_match else len(text)

        raw = text[start:end].strip().rstrip(",").strip()
        if raw.startswith('"""'):
            raw = raw[3:-3] if raw.endswith('"""') else raw[3:]
        elif raw.startswith('"'):
            try:
                raw = json.loads(raw.rstrip(","))
            except Exception:
                raw = raw.strip('"')
        files[file_path] = raw.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')

    if files:
        return {"files": files, "explanation": "parsed"}

    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", content, re.DOTALL)
    if code_blocks:
        return {"files": {"src/main.py": code_blocks[0]}, "explanation": "extracted"}

    return {"files": {}, "explanation": "parse failed"}


def run_coder(state: FrameworkState) -> FrameworkState:
    current_task = state.task_list[state.current_task_index]

    if not current_task.test_file_path:
        raise AgentError("CoderAgent", f"No test file for task {current_task.id}")

    test_code = safe_read_file(current_task.test_file_path)
    if not test_code:
        raise AgentError("CoderAgent", f"Test file empty: {current_task.test_file_path}")

    arch_context = _get_arch_context(state, current_task)
    existing_context = build_task_context(state.output_directory, current_task)

    task_description = current_task.description
    if current_task.error_history:
        task_description += f"\n\nPREVIOUS FAILURE:\n{current_task.error_history[-1]}\nFix this."

    prompt = CODER_PROMPT.format(
        task_title=current_task.title,
        task_description=task_description,
        test_file_path=current_task.test_file_path,
        test_code=test_code,
        arch_context=arch_context,
        existing_context=existing_context,
    )

    log_action(state.model_dump(), agent="CoderAgent",
               action=f"Generating code for task {current_task.id} (retry #{current_task.retry_count})")

    response = router.call(
        agent="CoderAgent",
        system_prompt=CODER_SYSTEM,
        user_prompt=prompt,
        temperature=0.1,
        max_tokens=6000,
        json_mode=False,
        state=state.model_dump(),
    )

    data = _parse_coder_response(response.content)
    files_to_write = data.get("files", {})

    if not files_to_write:
        raise AgentError("CoderAgent", "LLM returned no files to write")

    approved_files = compute_and_present_diff(
        output_directory=state.output_directory,
        new_files=files_to_write,
    )

    written_paths = []
    for rel_path, file_content in approved_files.items():
        abs_path = os.path.join(state.output_directory, rel_path)
        safe_write_file(abs_path, file_content)
        written_paths.append(abs_path)
        log_action(state.model_dump(), agent="CoderAgent", action=f"File written: {rel_path}")

    updated_tasks = list(state.task_list)
    updated_tasks[state.current_task_index] = current_task.model_copy(
        update={"generated_files": written_paths}
    )
    return state.model_copy(update={"task_list": updated_tasks})


def _get_arch_context(state, task):
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
