"""
tools/context_builder.py
━━━━━━━━━━━━━━━━━━━━━━━
Selective file injection for the Coder agent.

PROBLEM: By Task 15 in a Tier 4 project, the repo has 30+ files.
Passing ALL files to every LLM call wastes tokens, costs money, and degrades quality.

SOLUTION: Build a scoped context — only inject files that are relevant to the current task.
Relevance is determined by keyword matching between the task description and file contents.

USED BY: agents/coder_agent.py
"""

import os
from orchestrator.state import Task
from tools.file_manager import safe_read_file

# Maximum characters of existing code to inject per LLM call
# ~8000 chars ≈ ~2000 tokens — keeps context manageable
MAX_CONTEXT_CHARS = 8000


def build_task_context(output_directory: str, task: Task) -> str:
    """
    Build a scoped context string for the Coder agent.

    Strategy:
      1. Extract keywords from the task title + description
      2. Walk the project directory
      3. Score each file by keyword overlap with task
      4. Include the top N files up to MAX_CONTEXT_CHARS

    Returns a formatted string ready to inject into the Coder prompt.
    """
    if not output_directory or not os.path.exists(output_directory):
        return "No existing project files."

    # Keywords from task (skip common words)
    stop_words = {"the", "a", "an", "for", "to", "of", "in", "is", "be", "that", "with", "and", "or"}
    task_text = (task.title + " " + task.description).lower()
    keywords = {w for w in task_text.split() if len(w) > 3 and w not in stop_words}

    # Score all Python files in the project
    scored_files: list[tuple[int, str, str]] = []
    for root, dirs, files in os.walk(output_directory):
        # Skip irrelevant directories
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules", ".venv"}]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, output_directory)

            # Skip the test file for this task (Coder shouldn't see its own failing tests as "existing code")
            if task.test_file_path and os.path.basename(abs_path) in task.test_file_path:
                continue

            content = safe_read_file(abs_path)
            if not content:
                continue

            # Score = number of keyword matches in file path + content
            score = sum(1 for kw in keywords if kw in rel_path.lower() or kw in content.lower())

            # Always include core files (models, db setup, config)
            if any(core in rel_path for core in ["model", "db", "config", "base", "__init__"]):
                score += 5

            scored_files.append((score, rel_path, content))

    # Sort by score descending, then build context up to char limit
    scored_files.sort(key=lambda x: x[0], reverse=True)

    context_parts = []
    total_chars = 0

    for score, rel_path, content in scored_files:
        if score == 0:
            continue  # Skip completely irrelevant files
        # Truncate very large files
        content_chunk = content if len(content) <= 2000 else content[:2000] + "\n# [TRUNCATED]"
        entry = f"# FILE: {rel_path}\n{content_chunk}\n"

        if total_chars + len(entry) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(entry)
        total_chars += len(entry)

    if not context_parts:
        return "No relevant existing files found."

    return f"# EXISTING PROJECT FILES ({len(context_parts)} most relevant)\n\n" + "\n".join(context_parts)
