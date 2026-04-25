# AGENT_CONTRACTS.md
# Exact input/output contract for every agent in the Itanta framework.
# Read this before modifying any agent.

---

## Contract rules (ALL agents must follow)

1. Every agent function signature: `run_<name>(state: FrameworkState) -> FrameworkState`
2. Use `state.model_copy(update={...})` — never mutate state in place
3. Call `log_action()` at the START and END of every agent function
4. All LLM calls go through `router.call(agent="AgentName", ...)` — never call SDK directly
5. All file writes go through `safe_write_file()` — never use `open()` directly
6. Return the full state even if your agent only changed one field

---

## Agent 1 — IntakeAgent

| Field          | Value                                      |
|----------------|--------------------------------------------|
| File           | `agents/intake_agent.py`                   |
| Entry point    | `run_intake(state) -> state`               |
| LLM            | Groq Llama 3.1 70B (free)                 |
| Reads          | `state.raw_spec`                           |
| Writes         | `state.clarification_qa`, `state.spec_doc` |
| Human I/O      | Presents questions, collects answers       |
| Satisfies      | FR-01, FR-02                               |

**Prompt strategy:** Two-pass — first call detects ambiguities and generates questions,
second call (after user answers) generates the structured spec.

---

## Agent 2 — ArchitectAgent

| Field          | Value                                        |
|----------------|----------------------------------------------|
| File           | `agents/architect_agent.py`                  |
| Entry point    | `run_architect(state) -> state`              |
| LLM            | Groq Llama 3.1 70B (free)                   |
| Reads          | `state.spec_doc`                             |
| Writes         | `state.architecture`                         |
| Human I/O      | None (runs autonomously)                     |
| Satisfies      | FR-04                                        |

**Prompt strategy:** Single-pass with few-shot schema enforcement.
Outputs directory tree, data models, API contracts, DB choice.

---

## Agent 3 — PlannerAgent

| Field          | Value                                        |
|----------------|----------------------------------------------|
| File           | `agents/planner_agent.py`                    |
| Entry point    | `run_planner(state) -> state`                |
| LLM            | Groq Llama 3.1 70B (free)                   |
| Reads          | `state.architecture`, `state.spec_doc`       |
| Writes         | `state.task_list`                            |
| Human I/O      | None (plan shown at Checkpoint 2)            |
| Satisfies      | FR-05                                        |

**Prompt strategy:** Chain-of-thought decomposition. Instructs LLM to list
all features first, then break each into the smallest independent unit.

---

## Agent 4 — QAAgent (TDD-First)

| Field          | Value                                               |
|----------------|-----------------------------------------------------|
| File           | `agents/qa_agent.py`                                |
| Entry point    | `run_qa(state) -> state`                            |
| LLM            | Gemini 1.5 Flash (free, separate provider)          |
| Reads          | `state.task_list[current]`, architecture context    |
| Writes         | `state.task_list[current].test_file_path`           |
| Human I/O      | None                                                |
| Satisfies      | FR-11                                               |

**Critical invariant:** Tests MUST fail when first run (no production code exists yet).
Agent verifies this via `_verify_tests_fail()` after writing the file.
Activity log timestamp here must be EARLIER than the Coder agent's timestamp.
This ordering is enforced by LangGraph edge: `qa → coder`.

---

## Agent 5 — CoderAgent

| Field          | Value                                                     |
|----------------|-----------------------------------------------------------|
| File           | `agents/coder_agent.py`                                   |
| Entry point    | `run_coder(state) -> state`                               |
| LLM            | DeepSeek Coder V2 via OpenRouter (low cost)               |
|                | Fallback: Gemini 1.5 Pro (free, 2 RPM)                   |
| Reads          | `state.task_list[current].test_file_path`, context files  |
| Writes         | `state.task_list[current].generated_files`                |
| Human I/O      | Presents diff at Checkpoint 3                             |
| Satisfies      | FR-08, FR-09                                              |

**Context strategy:** Uses `context_builder.py` to inject only task-relevant files.
On retries, `task.error_history` is appended to the prompt with specific fix instructions.
Temperature: 0.1 (lower than other agents — deterministic code generation).

---

## Agent 6 — RecoveryAgent

| Field          | Value                                               |
|----------------|-----------------------------------------------------|
| File           | `agents/recovery_agent.py`                          |
| Entry point    | `run_recovery(state) -> state`                      |
| LLM            | Groq Llama 3.1 8B (free, fast)                     |
| Reads          | `state.task_list[current].validation_result`        |
| Writes         | `state.task_list[current].error_history` (appended) |
|                | `state.retry_count`                                 |
| Human I/O      | None (escalation produces human-readable report)    |
| Satisfies      | FR-15, FR-17                                        |

**Decision protocol:**
- `DECISION:RETRY` → graph routes back to QA node. Error + fix strategy appended to task.
- `DECISION:ROLLBACK` → filesystem restored to `state.last_checkpoint` snapshot.
- `DECISION:ESCALATE` → graph reaches END. Framework stops with clear error report.

---

## Agent 7 — SecurityAgent (Extended)

| Field          | Value                                       |
|----------------|---------------------------------------------|
| File           | `agents/security_agent.py`                  |
| Entry point    | `run_security(state) -> state`              |
| LLM            | Groq Llama 3.1 8B (free, fast)             |
| Reads          | All `.py` files in `state.output_directory` |
| Writes         | `state.security_findings`                   |
| Human I/O      | None (findings included in summary report)  |
| Satisfies      | FR-14 (extended feature)                    |

**Scope:** OWASP Top 10 patterns. Truncates files to 3000 chars each.
Does NOT block the pipeline — reports findings only.

---

## Validator (deterministic — no LLM)

| Field          | Value                                          |
|----------------|------------------------------------------------|
| Files          | `validators/test_runner.py`, `linter.py`, `type_checker.py` |
| Called by      | `orchestrator/graph.py` node_validator()       |
| Tools          | pytest + ruff + mypy (all free, open source)   |
| Output         | `ValidationResult` (pass/fail + tracebacks)    |
| Satisfies      | FR-12                                          |

**Design choice:** Deterministic tools chosen over LLM for binary pass/fail.
No hallucination risk. Zero API cost. Runs after every code generation.
