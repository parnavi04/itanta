# CODEBASE_DESCRIPTION.md
# Complete source directory description for any agent picking up this project.
#
# Purpose: Any AI agent, developer, or team member reading this file
# should understand the ENTIRE codebase well enough to continue building
# without needing to read every source file first.
#
# Last updated: auto-generated at scaffold time
# ─────────────────────────────────────────────────────────────────────────────

---

## 1. What this project is

The **Itanta Agentic AI Framework** is a multi-agent pipeline that accepts a
natural-language software project specification and autonomously produces a
working, tested, Dockerized Python codebase.

It orchestrates 7 specialized AI agents through a LangGraph state machine.
Agents hand off work via a single shared Pydantic state object.
Human approvals happen at 3 checkpoints using LangGraph's `interrupt()` primitive.
TDD is enforced by graph topology — the QA node is a prerequisite of the Coder node.

---

## 2. The one rule above all others

**All agents share one state object: `FrameworkState` (orchestrator/state.py).**

Every agent receives the full state, does one job, returns the updated state.
No agent calls another agent. No agent stores private state outside this object.
If you add a new field, add it to `FrameworkState` and document it here.

---

## 3. Full file listing with purpose

```
itanta_framework/
│
├── main.py
│     Entrypoint. Loads config, builds the LangGraph pipeline, runs it.
│     Handles GraphInterrupt (human checkpoints) via a resume loop.
│     CLI built with Typer — supports --spec, --resume, --tier, --no-checkpoints.
│
├── config.yaml
│     ALL tuneable parameters. max_retries, checkpoint toggles, guardrails.
│     Change behaviour here — never in source code. Satisfies NFR-03.
│
├── requirements.txt
│     All dependencies. Includes both framework deps and generated project deps
│     (FastAPI, SQLAlchemy, etc.) so the dev environment can run outputs too.
│
├── .env.example
│     Template for API keys. Copy to .env. Never commit .env.
│     Keys: GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY.
│
├── orchestrator/
│   │
│   ├── state.py  ◄─ READ THIS FIRST
│   │     Defines FrameworkState — the contract between ALL agents.
│   │     Contains all sub-models: StructuredSpec, ArchitectureDoc, Task,
│   │     ValidationResult, ActivityLogEntry, SecurityFinding, WorkflowSummary.
│   │     Pydantic v2. All fields have ownership comments.
│   │     Config: use_enum_values=True for SQLite serialization.
│   │
│   ├── graph.py  ◄─ READ THIS SECOND
│   │     LangGraph StateGraph definition.
│   │     14 nodes + 3 conditional routing functions.
│   │     Node execution order:
│   │       intake → checkpoint_1 → architect → planner → checkpoint_2 →
│   │       loop: qa → coder → checkpoint_3 → validator →
│   │         PASS: advance_task → (qa again or security)
│   │         FAIL: recovery → (qa retry, advance_task rollback, or END)
│   │       → security → docker → summarise → END
│   │     build_graph(checkpointer) → compiled graph
│   │     get_compiled_graph() → graph with SqliteSaver checkpointer
│   │
│   └── checkpointer.py  [stub — SqliteSaver from langgraph handles this]
│         LangGraph's SqliteSaver persists state after every node to
│         ./itanta_checkpoints.db. Resume by run_id restores from this file.
│
├── agents/
│   │   One file per agent. Each agent = one Python function.
│   │   Pattern: run_<name>(state: FrameworkState) -> FrameworkState
│   │
│   ├── intake_agent.py
│   │     Agent 1. LLM: Groq Llama 3.1 70B (free).
│   │     Two-pass: (1) detect ambiguities → generate questions, (2) spec generation.
│   │     Calls cli/interface.py to ask user clarifying questions.
│   │     Writes: state.clarification_qa, state.spec_doc
│   │     Key function: run_intake(state) → state
│   │
│   ├── architect_agent.py
│   │     Agent 2. LLM: Groq Llama 3.1 70B (free).
│   │     Single-pass JSON generation with strict schema.
│   │     Reads: state.spec_doc
│   │     Writes: state.architecture (ArchitectureDoc)
│   │     Key function: run_architect(state) → state
│   │
│   ├── planner_agent.py
│   │     Agent 3. LLM: Groq Llama 3.1 70B (free).
│   │     Chain-of-thought task decomposition.
│   │     Reads: state.architecture, state.spec_doc
│   │     Writes: state.task_list (list of Task objects)
│   │     Key function: run_planner(state) → state
│   │
│   ├── qa_agent.py
│   │     Agent 4. LLM: Gemini 1.5 Flash (free, separate provider).
│   │     CRITICAL: Writes FAILING tests before code exists.
│   │     Calls _verify_tests_fail() to confirm tests fail after writing.
│   │     Activity log timestamp here MUST precede coder timestamp.
│   │     Reads: state.task_list[current], architecture context
│   │     Writes: state.task_list[current].test_file_path (file on disk)
│   │     Key function: run_qa(state) → state
│   │
│   ├── coder_agent.py
│   │     Agent 5. LLM: DeepSeek Coder V2 via OpenRouter (low cost).
│   │     Fallback: Gemini 1.5 Pro (free, 2 RPM).
│   │     Uses context_builder.py for selective file injection.
│   │     On retries: error_history is appended to prompt.
│   │     Calls diff_presenter.py to show changes before applying.
│   │     Reads: test file, scoped context files
│   │     Writes: state.task_list[current].generated_files (files on disk)
│   │     Key function: run_coder(state) → state
│   │
│   ├── recovery_agent.py
│   │     Agent 6. LLM: Groq Llama 3.1 8B (free, fast).
│   │     Classifies failure type. Enriches retry prompt.
│   │     Writes DECISION:RETRY / DECISION:ROLLBACK / DECISION:ESCALATE
│   │     into error_history — graph router reads this.
│   │     On ROLLBACK: calls file_manager.restore_checkpoint().
│   │     Hard limit: if retry_count >= max_retries → always ESCALATE.
│   │     Key function: run_recovery(state) → state
│   │
│   └── security_agent.py
│         Agent 7. LLM: Groq Llama 3.1 8B (free).
│         Extended feature (FR-14). Runs after all tasks complete.
│         Scans generated .py files for OWASP Top 10 patterns.
│         Does NOT block pipeline — reports only.
│         Writes: state.security_findings
│         Key function: run_security(state) → state
│
├── validators/
│   │   Deterministic tools — no LLM, no cost, no hallucination.
│   │   Used by orchestrator/graph.py node_validator().
│   │
│   ├── test_runner.py
│   │     Runs pytest via subprocess. Parses stdout into TestRunResult.
│   │     Captures tracebacks for failing tests.
│   │     Returns: TestRunResult(passed, tests_total, tests_passed, test_failures)
│   │
│   ├── linter.py
│   │     Runs ruff on src/ directory. Returns LintResult(passed, errors).
│   │     Ruff is 10-100× faster than flake8, replaces isort + pycodestyle.
│   │
│   └── type_checker.py
│         Runs mypy on src/ directory. Returns TypeCheckResult(passed, errors).
│         --ignore-missing-imports to avoid failing on missing stubs.
│
├── tools/
│   │   Shared utilities used by multiple agents.
│   │
│   ├── llm_router.py  ◄─ ALL LLM CALLS GO HERE
│   │     Single interface to all LLM providers.
│   │     Singleton: import router from this module.
│   │     AGENT_MODEL_MAP: maps agent name → (provider, model, fallback_provider, fallback_model)
│   │     router.call(agent, system_prompt, user_prompt, ...) → LLMResponse
│   │     router.parse_json_response(response) → dict (strips markdown fences)
│   │     Auto-fallback on RateLimitError or LLMProviderError.
│   │     Providers: GroqProvider, GeminiProvider, OpenRouterProvider
│   │
│   ├── file_manager.py  ◄─ ALL FILE WRITES GO HERE
│   │     Enforces NFR-05: no writes outside project root.
│   │     set_allowed_root(path) — called once at startup from main.py.
│   │     safe_write_file(path, content) — creates dirs, checks safety.
│   │     safe_read_file(path) — returns "" if not found.
│   │     safe_delete_file(path) — checks safety before deleting.
│   │     snapshot_directory(source, checkpoint_name) — for rollback.
│   │     restore_checkpoint(checkpoint_name, output_dir) — restores snapshot.
│   │
│   ├── context_builder.py
│   │     Selective file injection for Coder agent.
│   │     Problem: passing full repo to every LLM call is expensive and slow.
│   │     Solution: score files by keyword overlap with current task.
│   │     build_task_context(output_dir, task) → formatted string (max 8000 chars)
│   │     Always includes: model files, db files, __init__ files (score boost).
│   │
│   ├── diff_presenter.py
│   │     Shows code diffs to user before applying (FR-09).
│   │     compute_and_present_diff(output_dir, new_files, auto_approve) → approved files
│   │     Uses Python difflib for unified diffs. Displays via Rich Syntax panel.
│   │     Supports: approve / reject / partial (file-by-file) decisions.
│   │     On reject with comment: writes .itanta_rejection_comment.txt for Coder.
│   │
│   └── docker_generator.py
│         Generates Dockerfile + docker-compose.yml (extended feature).
│         Selects template based on architecture.database_choice (postgres vs mongo).
│         generate_docker_compose(state) → state with docker_compose_path set.
│
├── models/
│   │   Pydantic schemas for data contracts. Most live in orchestrator/state.py.
│   │   This directory holds schemas that are only needed at report time.
│   │
│   └── report.py
│         build_summary(state) → WorkflowSummary
│         Aggregates: task counts, file counts, test pass rates, API call totals.
│         Also calls dump_activity_log() to write JSON log to output directory.
│
├── config/
│   └── loader.py
│         get_config() → Config (cached via @lru_cache)
│         Reads config.yaml + .env.
│         Config model: max_retries, rollback_on_max_retries, target_tier,
│           output_base_dir, checkpoints (3 booleans), guardrails (thresholds).
│
├── utils/
│   ├── logger.py
│   │     log_action(state_dict, agent, action, detail, api_calls_made)
│   │     log_api_call(state_dict, agent, model, tokens)
│   │     dump_activity_log(state_dict, output_path) → JSON file
│   │     EVERY significant action in EVERY agent MUST call log_action().
│   │     Judges verify TDD ordering via activity log timestamps.
│   │
│   └── exceptions.py
│         ItantaBaseError, AgentError, LLMProviderError, RateLimitError,
│         SafetyViolationError, CheckpointError, ValidationError
│
├── cli/
│   └── interface.py
│         All terminal I/O goes here. Never use print() in agents.
│         show_banner() — startup display
│         get_project_spec() — multi-line input
│         ask_clarification_questions(questions) → list[str]
│         present_checkpoint(title, content, instructions) → bool (approved?)
│         present_plan_checkpoint(tasks) → bool (approved?)
│         present_diff(task, instructions) → bool (approved?)
│         present_summary(WorkflowSummary) — final output display
│         All display via Rich (tables, syntax panels, prompts).
│
├── tests/
│   ├── unit/
│   │   └── test_state.py
│   │         Tests for FrameworkState schema, Task model, safety constraints.
│   │         Run: pytest tests/unit/ -v
│   │
│   └── integration/
│       └── test_tier1_pipeline.py
│             Smoke test: verifies graph builds, state schema valid, logger works.
│             Uses mocked LLM responses — no real API calls needed.
│             Run: pytest tests/integration/ -v
│
├── docs/
│   └── AGENT_CONTRACTS.md
│         Exact input/output contract table for every agent.
│         LLM assignments, prompt strategies, satisfies FR-XX references.
│
└── generated_projects/
      All framework output is written here.
      Each run creates: <project_slug>_<timestamp>_<run_id>/
      Contents: src/, tests/, Dockerfile, docker-compose.yml,
                itanta_activity_log.json
```

---

## 4. Data flow cheat sheet

```
raw_spec (str)
  → IntakeAgent     → clarification_qa (list) + spec_doc (StructuredSpec)
  → ArchitectAgent  → architecture (ArchitectureDoc)
  → PlannerAgent    → task_list (list[Task])
  
  [loop per task]
  → QAAgent         → task.test_file_path (file written to disk)
  → CoderAgent      → task.generated_files (files written to disk)
  → Validator       → task.validation_result (ValidationResult)
    PASS            → advance current_task_index, snapshot checkpoint
    FAIL            → RecoveryAgent → enriched error_history
      RETRY         → back to QAAgent
      ROLLBACK      → restore snapshot, skip task
      ESCALATE      → END (human must intervene)
  [end loop]
  
  → SecurityAgent   → security_findings (list[SecurityFinding])
  → DockerGenerator → docker_compose_path (str)
  → SummaryBuilder  → summary (WorkflowSummary) + activity_log.json
```

---

## 5. LLM cost map

| Agent           | Provider      | Model                  | Cost        |
|-----------------|---------------|------------------------|-------------|
| Intake          | Groq          | Llama 3.1 70B          | Free        |
| Architect       | Groq          | Llama 3.1 70B          | Free        |
| Planner         | Groq          | Llama 3.1 70B          | Free        |
| QA              | Gemini        | Gemini 1.5 Flash       | Free        |
| Coder           | OpenRouter    | DeepSeek Coder V2      | ~$0.001/1K  |
| Coder fallback  | Gemini        | Gemini 1.5 Pro         | Free (slow) |
| Recovery        | Groq          | Llama 3.1 8B           | Free        |
| Security        | Groq          | Llama 3.1 8B           | Free        |
| Validator       | Local         | pytest + ruff + mypy   | Free (OSS)  |

Estimated full hackathon API spend: **< $0.20 (~₹17)**

---

## 6. Where to make common changes

| What you want to change             | Where to change it                          |
|-------------------------------------|---------------------------------------------|
| Add a new agent                     | agents/<name>.py + graph.py (new node+edge) |
| Change which LLM an agent uses      | tools/llm_router.py AGENT_MODEL_MAP         |
| Change retry limit                  | config.yaml max_retries                     |
| Disable a human checkpoint          | config.yaml checkpoints.*                   |
| Add a new state field               | orchestrator/state.py FrameworkState        |
| Change output directory             | config.yaml output_base_dir                 |
| Add a new failure recovery strategy | agents/recovery_agent.py run_recovery()     |
| Change the Dockerfile template      | tools/docker_generator.py templates         |
| Add a new supported DB              | tools/docker_generator.py + architect prompt|

---

## 7. What is NOT implemented yet (for next agent to build)

These items are scaffolded/stubbed but need full implementation:

- [ ] `orchestrator/checkpointer.py` — currently uses LangGraph's built-in SqliteSaver.
      No custom code needed unless adding Redis-backed checkpointing for multi-user.

- [ ] `cli/interface.py` present_checkpoint — currently shows full JSON.
      Should be improved to show human-readable summaries, not raw JSON.

- [ ] `agents/coder_agent.py` — `_write_rejection_comment` in diff_presenter
      needs to be READ back in coder_agent on retry (currently commented logic).

- [ ] `tests/unit/` — Only state tests exist. Need unit tests for every agent
      using mocked LLM responses. One test file per agent.

- [ ] `tests/integration/` — Tier 1 smoke test is structural only.
      Need a full end-to-end test that runs the Ledger CRUD tier with mocked LLMs.

- [ ] `models/spec.py`, `models/architecture.py`, `models/task.py` — currently
      all models live in orchestrator/state.py. Can be split for cleanliness.
