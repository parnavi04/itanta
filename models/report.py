"""
models/report.py
━━━━━━━━━━━━━━━
Builds the final WorkflowSummary by aggregating the activity log.
Satisfies NFR-06: summary of tasks, files, tests, API calls.
"""

import os
from datetime import datetime
from orchestrator.state import FrameworkState, WorkflowSummary, TaskStatus
from utils.logger import dump_activity_log


def build_summary(state: FrameworkState) -> WorkflowSummary:
    """
    Aggregate the activity log and task list into a WorkflowSummary.
    Also dumps the full activity log to a JSON file in the output directory.
    """
    # Task counts
    tasks_completed = sum(1 for t in state.task_list if t.status == TaskStatus.PASSED)
    tasks_skipped   = sum(1 for t in state.task_list if t.status == TaskStatus.SKIPPED)
    tasks_failed    = sum(1 for t in state.task_list if t.status == TaskStatus.FAILED)

    # File count — all .py files generated in the output dir
    files_generated = 0
    if state.output_directory and os.path.exists(state.output_directory):
        for _, _, files in os.walk(state.output_directory):
            files_generated += sum(1 for f in files if f.endswith(".py"))

    # Test counts — from task validation results
    tests_total = tests_passed = 0
    for task in state.task_list:
        if task.validation_result:
            tests_total  += task.validation_result.get("tests_total", 0)
            tests_passed += task.validation_result.get("tests_passed", 0)

    # API call count from activity log
    total_api_calls = sum(entry.get("api_calls_made", 0) for entry in state.activity_log)

    # Retry count
    total_retries = sum(t.retry_count for t in state.task_list)

    # Duration
    try:
        start = datetime.fromisoformat(state.start_time)
        duration = (datetime.now() - start).total_seconds()
    except Exception:
        duration = 0.0

    summary = WorkflowSummary(
        tasks_completed=tasks_completed,
        tasks_skipped=tasks_skipped,
        tasks_failed=tasks_failed,
        files_generated=files_generated,
        tests_total=tests_total,
        tests_passed=tests_passed,
        total_api_calls=total_api_calls,
        total_retries=total_retries,
        duration_seconds=duration,
        output_directory=state.output_directory,
    )

    # Dump activity log to file
    if state.output_directory and os.path.exists(state.output_directory):
        log_path = os.path.join(state.output_directory, "itanta_activity_log.json")
        dump_activity_log(state.model_dump(), log_path)

    return summary
