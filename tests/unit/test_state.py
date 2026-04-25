import pytest
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
