from __future__ import annotations
import os
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "false")
"""
orchestrator/state.py
━━━━━━━━━━━━━━━━━━━━
THE SINGLE SOURCE OF TRUTH for all data flowing between agents.

RULES (DO NOT BREAK):
  - Every agent receives the full FrameworkState and returns the full FrameworkState.
  - No agent modifies fields it does not own (see ownership comments below).
  - Schema changes require updating ALL Pydantic models in models/ as well.
  - State is serialized to SQLite after every node — keep all fields JSON-serializable.
"""



from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING    = "pending"
    IN_PROGRESS = "in_progress"
    PASSED     = "passed"
    FAILED     = "failed"
    SKIPPED    = "skipped"

class RiskLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"

class WorkflowPhase(str, Enum):
    INTAKE        = "intake"
    ARCHITECTURE  = "architecture"
    PLANNING      = "planning"
    EXECUTION     = "execution"
    SECURITY_AUDIT = "security_audit"
    COMPLETE      = "complete"
    FAILED        = "failed"


# ─────────────────────────────────────────────
# Sub-models (nested inside FrameworkState)
# ─────────────────────────────────────────────

class ClarificationQA(BaseModel):
    """One question-answer pair from the Intake agent's clarification round."""
    question: str
    answer: str = ""          # Empty until user responds
    answered: bool = False


class AcceptanceCriteria(BaseModel):
    """A single verifiable acceptance criterion for the project."""
    description: str
    is_testable: bool = True


class StructuredSpec(BaseModel):
    """
    OWNED BY: IntakeAgent
    Produced after user answers clarifying questions.
    All downstream agents build on this — it is the locked project definition.
    """
    project_name: str = ""
    project_summary: str = ""
    acceptance_criteria: list[AcceptanceCriteria] = []
    proposed_architecture_notes: str = ""
    known_constraints: list[str] = []
    tech_stack_hints: list[str] = []       # Any tech the user explicitly mentioned
    target_tier: int = 1                   # 1-5 complexity tier


class APIEndpoint(BaseModel):
    """Describes a single REST API endpoint in the architecture."""
    method: str                            # GET, POST, PUT, DELETE, PATCH
    path: str                              # e.g. /api/v1/books
    description: str
    request_body: Optional[dict] = None   # JSON schema dict
    response_schema: Optional[dict] = None
    auth_required: bool = False
    status_codes: list[int] = [200]


class DataModel(BaseModel):
    """Describes a database model/entity."""
    name: str                              # e.g. "Book"
    fields: dict[str, str] = {}           # field_name → type string
    relationships: list[str] = []         # e.g. ["belongs_to:User"]
    table_name: str = ""


class ArchitectureDoc(BaseModel):
    """
    OWNED BY: ArchitectAgent
    Full system design before any code is written.
    Determines everything the Planner and Coder agents will do.
    """
    directory_tree: dict[str, Any] = {}   # Nested dict representing folder structure
    data_models: list[DataModel] = []
    api_endpoints: list[APIEndpoint] = []
    database_choice: str = "postgresql"   # postgresql | mongodb | sqlite
    framework_choice: str = "fastapi"     # fastapi | flask
    auth_strategy: str = "none"           # none | jwt | oauth2
    external_apis: list[str] = []         # For Tier 3 live bridge
    notes: str = ""


class Task(BaseModel):
    """
    OWNED BY: PlannerAgent (creation) + all execution agents (status updates)
    One atomic unit of work. Must produce exactly ONE verifiable output.
    """
    id: int
    title: str
    description: str                       # Detailed "definition of done"
    risk_level: RiskLevel = RiskLevel.LOW
    requires_human_checkpoint: bool = False
    status: TaskStatus = TaskStatus.PENDING
    test_file_path: str = ""               # Written by QAAgent BEFORE code
    generated_files: list[str] = []        # Written by CoderAgent
    validation_result: Optional[dict] = None  # Written by Validator
    retry_count: int = 0
    error_history: list[str] = []         # Accumulates errors across retries
    depends_on: list[int] = []            # Task IDs this task depends on


class ValidationResult(BaseModel):
    """Result from the deterministic Validator module."""
    passed: bool
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_failures: list[str] = []         # Full tracebacks
    lint_errors: list[str] = []
    type_errors: list[str] = []
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ActivityLogEntry(BaseModel):
    """
    OWNED BY: utils/logger.py — every agent writes here via the logger.
    Append-only. Never delete entries. Judges verify ordering via timestamps.
    """
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    phase: str
    agent: str
    action: str                            # Human-readable description
    detail: str = ""                       # JSON or extra context
    api_calls_made: int = 0               # LLM API calls in this action


class SecurityFinding(BaseModel):
    """One finding from the SecurityAgent."""
    severity: str                          # critical | high | medium | low
    category: str                          # injection | auth | logic | exposure
    file_path: str
    line_number: Optional[int] = None
    description: str
    recommendation: str
    resolved: bool = False


class WorkflowSummary(BaseModel):
    """OWNED BY: final step — aggregated from activity log."""
    tasks_completed: int = 0
    tasks_skipped: int = 0
    tasks_failed: int = 0
    files_generated: int = 0
    tests_total: int = 0
    tests_passed: int = 0
    total_api_calls: int = 0
    total_retries: int = 0
    duration_seconds: float = 0.0
    output_directory: str = ""


# ─────────────────────────────────────────────
# Master State Object
# ─────────────────────────────────────────────

class FrameworkState(BaseModel):
    """
    THE CONTRACT BETWEEN ALL AGENTS.

    Field ownership:
      raw_spec              → set by CLI/user input, never modified
      clarification_qa      → IntakeAgent
      spec_doc              → IntakeAgent
      architecture          → ArchitectAgent
      task_list             → PlannerAgent (creation), all agents (status updates)
      current_task_index    → orchestrator/graph.py router
      retry_count           → RecoveryAgent
      last_checkpoint       → checkpointer.py
      activity_log          → utils/logger.py (all agents call this)
      security_findings     → SecurityAgent
      docker_compose_path   → DockerGenerator (in tools/)
      summary               → final graph node
      error_message         → any agent on fatal error
      phase                 → orchestrator/graph.py

    DO NOT add agent-specific private fields here.
    If an agent needs temporary data, use task.detail or add a sub-model.
    """

    # ── Input (set once, never changed) ────────────────────────────
    raw_spec: str = ""

    # ── Phase 1: Intake ────────────────────────────────────────────
    clarification_qa: list[ClarificationQA] = []
    spec_doc: Optional[StructuredSpec] = None

    # ── Phase 2: Architecture ──────────────────────────────────────
    architecture: Optional[ArchitectureDoc] = None

    # ── Phase 3: Planning ──────────────────────────────────────────
    task_list: list[Task] = []
    current_task_index: int = 0

    # ── Phase 4: Execution (per-task loop) ─────────────────────────
    retry_count: int = 0                   # Resets to 0 after each passing task
    last_checkpoint: str = ""              # "task_N" — used for rollback target
    human_approved: bool = False           # Set to True at each checkpoint by CLI

    # ── Cross-cutting ──────────────────────────────────────────────
    activity_log: list[ActivityLogEntry] = []
    phase: WorkflowPhase = WorkflowPhase.INTAKE
    error_message: str = ""               # Set by any agent on unrecoverable error

    # ── Outputs ────────────────────────────────────────────────────
    security_findings: list[SecurityFinding] = []
    docker_compose_path: str = ""
    output_directory: str = ""
    summary: Optional[WorkflowSummary] = None

    # ── Meta ───────────────────────────────────────────────────────
    run_id: str = ""                       # UUID assigned at start of each run
    start_time: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = ConfigDict(use_enum_values=True)

    model_config = ConfigDict(use_enum_values=True)
