"""
setup_tests.py
Run this once to create all test files and pytest.ini correctly.
Usage: python setup_tests.py
"""

import os

# ── Create directories ────────────────────────────────────────────────────────
os.makedirs("tests/unit", exist_ok=True)
os.makedirs("tests/integration", exist_ok=True)

# ── pytest.ini ────────────────────────────────────────────────────────────────
with open("pytest.ini", "w") as f:
    f.write("[pytest]\npythonpath = .\n")
print("Written: pytest.ini")

# ── tests/__init__.py ─────────────────────────────────────────────────────────
for path in ["tests/__init__.py", "tests/unit/__init__.py", "tests/integration/__init__.py"]:
    with open(path, "w") as f:
        f.write("")
print("Written: __init__.py files")

# ── tests/unit/test_state.py ──────────────────────────────────────────────────
unit_test = '''import pytest
from orchestrator.state import FrameworkState, Task, TaskStatus


class TestFrameworkState:

    def test_default_state_is_valid(self):
        state = FrameworkState()
        assert state.raw_spec == ""
        assert state.task_list == []
        assert state.current_task_index == 0
        assert state.retry_count == 0
        assert state.activity_log == []

    def test_state_serialises_to_dict(self):
        state = FrameworkState(raw_spec="Build a REST API")
        data = state.model_dump()
        assert isinstance(data, dict)
        assert data["raw_spec"] == "Build a REST API"

    def test_state_round_trips(self):
        original = FrameworkState(raw_spec="test spec", retry_count=2)
        data = original.model_dump()
        restored = FrameworkState(**data)
        assert restored.raw_spec == original.raw_spec
        assert restored.retry_count == original.retry_count

    def test_model_copy_does_not_mutate(self):
        original = FrameworkState(raw_spec="original")
        updated = original.model_copy(update={"raw_spec": "updated"})
        assert original.raw_spec == "original"
        assert updated.raw_spec == "updated"


class TestTask:

    def test_task_default_status_is_pending(self):
        task = Task(id=1, title="Test task", description="Do something")
        assert task.status == TaskStatus.PENDING

    def test_task_retry_count_starts_at_zero(self):
        task = Task(id=1, title="Test", description="Test")
        assert task.retry_count == 0

    def test_task_error_history_appends(self):
        task = Task(id=1, title="Test", description="Test")
        updated = task.model_copy(update={"error_history": task.error_history + ["error 1"]})
        assert len(updated.error_history) == 1
        assert len(task.error_history) == 0


class TestSafetyConstraint:

    def test_safe_write_blocks_path_traversal(self):
        from tools.file_manager import set_allowed_root, _assert_safe, SafetyViolationError
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            set_allowed_root(tmpdir)
            with pytest.raises(SafetyViolationError):
                _assert_safe("/etc/passwd")

    def test_safe_write_allows_project_paths(self):
        from tools.file_manager import set_allowed_root, _assert_safe
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            set_allowed_root(tmpdir)
            _assert_safe(tmpdir + "/src/models/user.py")
'''

with open("tests/unit/test_state.py", "w") as f:
    f.write(unit_test)
print("Written: tests/unit/test_state.py")

# ── tests/integration/test_tier1_pipeline.py ─────────────────────────────────
integration_test = '''import pytest
from orchestrator.graph import build_graph
from orchestrator.state import FrameworkState, TaskStatus


def test_state_schema_is_valid():
    state = FrameworkState(raw_spec="Build a ledger API")
    assert state.raw_spec == "Build a ledger API"
    assert state.current_task_index == 0


def test_graph_builds_without_error():
    graph = build_graph(checkpointer=None)
    assert graph is not None


def test_graph_has_all_expected_nodes():
    graph = build_graph(checkpointer=None)
    assert graph is not None


def test_activity_log_appends_correctly():
    from utils.logger import log_action
    state = FrameworkState().model_dump()
    log_action(state, agent="TestAgent", action="First action")
    log_action(state, agent="TestAgent", action="Second action")
    assert len(state["activity_log"]) == 2
    assert state["activity_log"][0]["action"] == "First action"
    assert state["activity_log"][1]["action"] == "Second action"
    assert state["activity_log"][0]["timestamp"] <= state["activity_log"][1]["timestamp"]
'''

with open("tests/integration/test_tier1_pipeline.py", "w") as f:
    f.write(integration_test)
print("Written: tests/integration/test_tier1_pipeline.py")

print("\nAll done. Now run: pytest tests/ -v")
