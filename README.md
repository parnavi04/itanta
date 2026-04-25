# Itanta Agentic AI Framework

## What This Is

A multi-agent framework that accepts a natural-language project specification and
autonomously builds a working, tested, Dockerized Python codebase — coordinating
7 specialized AI agents through a LangGraph state machine with human-in-the-loop
checkpoints, TDD-first enforcement, and intelligent failure recovery.

**Built for:** Itanta Hackathon — Agentic AI Software Development challenge.

---

## Directory Map (read this first)

```
itanta_framework/
│
├── main.py                        # Single entrypoint — run this to start
├── config.yaml                    # ALL tuneable parameters live here (no code changes needed)
├── .env.example                   # Copy to .env and fill in API keys
├── requirements.txt               # All Python dependencies
│
├── orchestrator/                  # THE BRAIN — LangGraph graph definition
│   ├── graph.py                   # StateGraph definition: all nodes + edges
│   ├── state.py                   # Pydantic state schema shared by ALL agents
│   └── checkpointer.py            # SQLite-backed checkpoint manager for rollback
│
├── agents/                        # ONE FILE PER AGENT — each agent is independent
│   ├── intake_agent.py            # Agent 1: clarifies ambiguity, produces spec.json
│   ├── architect_agent.py         # Agent 2: designs directory structure + API contracts
│   ├── planner_agent.py           # Agent 3: breaks architecture into atomic tasks
│   ├── qa_agent.py                # Agent 4: writes FAILING tests before code (TDD)
│   ├── coder_agent.py             # Agent 5: generates code that satisfies failing tests
│   ├── recovery_agent.py          # Agent 6: handles retries, rollbacks, escalations
│   └── security_agent.py          # Agent 7: scans for injection/auth flaws (extended)
│
├── validators/                    # DETERMINISTIC tools — no LLM, no cost
│   ├── test_runner.py             # Runs pytest, captures pass/fail + tracebacks
│   ├── linter.py                  # Runs ruff for style/error linting
│   └── type_checker.py            # Runs mypy for static type checking
│
├── tools/                         # SHARED UTILITIES used by multiple agents
│   ├── llm_router.py              # Single interface to all LLM providers (Groq/Gemini/OpenRouter)
│   ├── file_manager.py            # Safe filesystem operations (enforces NFR-05)
│   ├── diff_presenter.py          # Shows git-style diffs to user before applying
│   ├── docker_generator.py        # Generates docker-compose.yml for any project tier
│   └── context_builder.py         # Selective file injection to keep LLM context small
│
├── models/                        # PYDANTIC SCHEMAS — all data contracts
│   ├── spec.py                    # StructuredSpec, ClarificationQA, AcceptanceCriteria
│   ├── architecture.py            # ArchitectureDoc, DirectoryTree, APIContract, DataModel
│   ├── task.py                    # Task, TaskList, TaskStatus enum
│   └── report.py                  # WorkflowSummary, SecurityAuditReport
│
├── config/                        # CONFIGURATION LOADER
│   └── loader.py                  # Reads config.yaml + .env, exposes typed Config object
│
├── utils/                         # CROSS-CUTTING CONCERNS
│   ├── logger.py                  # Append-only activity log (NFR-02) — every action logged
│   └── exceptions.py              # Custom exceptions for each failure class
│
├── cli/                           # USER INTERFACE
│   └── interface.py               # Typer CLI + Rich display for diffs, checkpoints, progress
│
├── tests/                         # TEST SUITE FOR THE FRAMEWORK ITSELF
│   ├── unit/                      # Unit tests for each agent and tool
│   └── integration/               # End-to-end pipeline tests (Tier 1 smoke test)
│
├── docs/                          # DOCUMENTATION
│   └── AGENT_CONTRACTS.md         # Exact input/output contract for every agent
│
└── generated_projects/            # OUTPUT — framework writes generated projects here
    └── .gitkeep
```

---

## How Data Flows (read before touching any agent)

Every agent reads from and writes to ONE object: `FrameworkState` (defined in
`orchestrator/state.py`). Agents do NOT call each other. LangGraph routes between them.

```
User input
    ↓
IntakeAgent       → writes: state.clarification_qa, state.spec_doc
    ↓ [CP1: human approves]
ArchitectAgent    → writes: state.architecture
    ↓
PlannerAgent      → writes: state.task_list
    ↓ [CP2: human approves plan]
─── loop per task ───────────────────────────────────
QAAgent           → writes: state.current_task.test_file_path (FAILING tests)
    ↓
CoderAgent        → writes: state.current_task.generated_files (code diff)
    ↓ [CP3: human reviews diff]
Validator         → writes: state.current_task.validation_result
    ↓
  PASS ──────────────────────────────→ next task
  FAIL ──→ RecoveryAgent → retry/rollback/escalate
─── end loop ─────────────────────────────────────────
SecurityAgent     → writes: state.security_report
    ↓
DockerGenerator   → writes: state.docker_compose_path
    ↓
SummaryReport     → writes: state.summary
    ↓
Output to user
```

---

## LLM Assignment (cost-optimised)

| Agent | Model | Provider | Cost |
|-------|-------|----------|------|
| Intake, Architect, Planner | Llama 3.1 70B | Groq API | Free tier |
| QA Agent | Gemini 1.5 Flash | Google AI Studio | Free tier |
| Coder Agent | DeepSeek Coder V2 | OpenRouter | ~$0.001/1K tok |
| Coder fallback | Gemini 1.5 Pro | Google AI Studio | Free (2 RPM) |
| Recovery Agent | Llama 3.1 8B | Groq API | Free tier |
| Validator | pytest + ruff + mypy | Local | Free (OSS) |
| Security Agent | Llama 3.1 8B | Groq API | Free tier |

**Estimated cost: Tier 1 = ~$0.003 | Full hackathon = ~$0.15**

---

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Set API keys
cp .env.example .env
# Fill in GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY

# 3. Run
python main.py

# 4. Enter your project spec when prompted
```

---

## Config (config.yaml)

All behaviour is tunable without code changes:
- `max_retries` — how many times Recovery agent retries before escalating
- `require_human_approval` — enable/disable each checkpoint
- `rollback_on_max_retries` — auto-rollback vs escalate to human
- `file_change_threshold` — number of files changed before forcing human review
- `target_tier` — which complexity tier to run (1-5)

---

## For the Next Agent Reading This

If you are an AI agent picking up this codebase:

1. **Start with `orchestrator/state.py`** — understand the state schema before anything else
2. **Read `orchestrator/graph.py`** — this is the wiring diagram of all agents
3. **Each agent in `agents/` is self-contained** — it receives state, does one job, returns state
4. **Never modify state.py schema** without updating all Pydantic models in `models/`
5. **All LLM calls go through `tools/llm_router.py`** — never call an LLM API directly
6. **All file writes go through `tools/file_manager.py`** — it enforces the safety constraint (NFR-05)
7. **The activity log in `utils/logger.py` must be called for EVERY action** — judges verify this
