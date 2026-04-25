"""utils/logger.py — Append-only activity log. Every agent action must be logged here."""

import json
from datetime import datetime
from orchestrator.state import ActivityLogEntry

def log_action(state: dict, agent: str, action: str, detail: str = "", api_calls_made: int = 0):
    """
    Append a timestamped entry to state['activity_log'].
    Called by every agent for every significant action.
    Judges verify ordering via timestamps — never skip this.
    """
    entry = ActivityLogEntry(
        timestamp=datetime.now().isoformat(),
        phase=state.get("phase", "unknown"),
        agent=agent,
        action=action,
        detail=detail,
        api_calls_made=api_calls_made,
    )
    if "activity_log" not in state:
        state["activity_log"] = []
    state["activity_log"].append(entry.model_dump())

def log_api_call(state: dict, agent: str, model: str, tokens: int = 0):
    """Convenience: log an LLM API call with model and token info."""
    log_action(state, agent=agent, action=f"LLM API call → {model}", detail=f"output_tokens={tokens}", api_calls_made=1)

def dump_activity_log(state: dict, output_path: str):
    """Write the full activity log to a JSON file for submission."""
    log = state.get("activity_log", [])
    with open(output_path, "w") as f:
        json.dump(log, f, indent=2, default=str)
