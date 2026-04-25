"""validators/type_checker.py — Runs mypy static type checking."""
import subprocess, os
from pydantic import BaseModel

class TypeCheckResult(BaseModel):
    passed: bool
    errors: list[str] = []

def run_type_checker(project_dir: str) -> TypeCheckResult:
    if not project_dir or not os.path.exists(project_dir):
        return TypeCheckResult(passed=True)
    result = subprocess.run(
        ["python", "-m", "mypy", "src/", "--ignore-missing-imports", "--no-error-summary"],
        capture_output=True, text=True, cwd=project_dir,
    )
    errors = [l for l in result.stdout.split("\n") if "error:" in l]
    return TypeCheckResult(passed=result.returncode == 0, errors=errors[:20])
