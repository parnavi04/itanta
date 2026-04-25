import pytest
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
