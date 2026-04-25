"""
fix_structure.py
Moves all flat files into the correct folder structure.
Run from: C:\\Users\\Lenovo\\OneDrive\\Desktop\\Itanta
Run with: python fix_structure.py
"""

import os
import shutil

# Map: filename → destination folder
MOVES = {
    # orchestrator/
    "state.py":             "orchestrator/state.py",
    "graph.py":             "orchestrator/graph.py",

    # agents/
    "intake_agent.py":      "agents/intake_agent.py",
    "architect_agent.py":   "agents/architect_agent.py",
    "planner_agent.py":     "agents/planner_agent.py",
    "qa_agent.py":          "agents/qa_agent.py",
    "coder_agent.py":       "agents/coder_agent.py",
    "recovery_agent.py":    "agents/recovery_agent.py",
    "security_agent.py":    "agents/security_agent.py",

    # tools/
    "llm_router.py":        "tools/llm_router.py",
    "file_manager.py":      "tools/file_manager.py",
    "context_builder.py":   "tools/context_builder.py",
    "diff_presenter.py":    "tools/diff_presenter.py",
    "docker_generator.py":  "tools/docker_generator.py",

    # validators/
    "test_runner.py":       "validators/test_runner.py",
    "linter.py":            "validators/linter.py",
    "type_checker.py":      "validators/type_checker.py",

    # utils/
    "logger.py":            "utils/logger.py",
    "exceptions.py":        "utils/exceptions.py",

    # config/
    "loader.py":            "config/loader.py",

    # cli/
    "interface.py":         "cli/interface.py",

    # models/
    "report.py":            "models/report.py",

    # docs/
    "AGENT_CONTRACTS.md":   "docs/AGENT_CONTRACTS.md",
}

print("Creating folders...")
folders = [
    "orchestrator", "agents", "tools", "validators",
    "utils", "config", "cli", "models", "docs",
    "generated_projects",
]
for folder in folders:
    os.makedirs(folder, exist_ok=True)
    # Add __init__.py to every Python package folder
    if folder not in ("docs", "generated_projects"):
        init = os.path.join(folder, "__init__.py")
        if not os.path.exists(init):
            open(init, "w").close()
    print(f"  created: {folder}/")

print("\nMoving files...")
errors = []
for src, dst in MOVES.items():
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        print(f"  moved: {src} → {dst}")
    else:
        errors.append(f"  MISSING: {src}")

if errors:
    print("\nWarning — these files were not found (already moved or missing):")
    for e in errors:
        print(e)

# Fix conftest.py
with open("conftest.py", "w") as f:
    f.write("import sys, os\nsys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))\n")
print("\nFixed: conftest.py")

# Fix pytest.ini
with open("pytest.ini", "w") as f:
    f.write("[pytest]\npythonpath = .\n")
print("Fixed: pytest.ini")

print("\nDone! Now run: pytest tests/ -v")
