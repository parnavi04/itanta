"""validators/test_runner.py — Runs pytest, captures structured results."""

import subprocess
import os
from pydantic import BaseModel

class TestRunResult(BaseModel):
    passed: bool
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_failures: list[str] = []

def run_tests(project_dir: str, test_file: str = "") -> TestRunResult:
    """
    Run pytest on the project. If test_file is specified, run only that file.
    Returns structured pass/fail with full tracebacks for failures.
    """
    if not project_dir or not os.path.exists(project_dir):
        return TestRunResult(passed=False, test_failures=["Project directory not found"])

    target = test_file if test_file and os.path.exists(test_file) else os.path.join(project_dir, "tests")
    result = subprocess.run(
        ["python", "-m", "pytest", target, "-v", "--tb=short", "--json-report", "--json-report-file=-"],
        capture_output=True, text=True, cwd=project_dir,
    )

    # Parse pytest output into structured result
    failures = []
    total = passed = failed = 0

    for line in result.stdout.split("\n"):
        if " PASSED" in line:
            passed += 1; total += 1
        elif " FAILED" in line:
            failed += 1; total += 1
        elif "FAILED" in line and "::" in line:
            failures.append(line.strip())

    # Capture tracebacks from stderr/stdout
    if result.returncode != 0:
        # Extract short failure sections
        stdout = result.stdout
        if "short test summary" in stdout:
            summary_start = stdout.find("short test summary")
            failures = [stdout[summary_start:summary_start + 2000]]
        elif result.stderr:
            failures.append(result.stderr[:1000])

    return TestRunResult(
        passed=result.returncode == 0,
        tests_total=total or max(passed + failed, 1),
        tests_passed=passed,
        tests_failed=failed,
        test_failures=failures,
    )
