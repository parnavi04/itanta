"""validators/linter.py — Runs ruff linter on generated code."""
import subprocess, os
from pydantic import BaseModel

class LintResult(BaseModel):
    passed: bool
    errors: list[str] = []

def run_linter(project_dir: str) -> LintResult:
    if not project_dir or not os.path.exists(project_dir):
        return LintResult(passed=True)
    result = subprocess.run(
        ["python", "-m", "ruff", "check", "src/", "--output-format=text"],
        capture_output=True, text=True, cwd=project_dir,
    )
    errors = [l for l in result.stdout.split("\n") if l.strip() and not l.startswith("Found")]
    return LintResult(passed=result.returncode == 0, errors=errors[:20])
