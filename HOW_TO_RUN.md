# HOW TO RUN — Itanta Agentic AI Framework
# Complete setup guide from unzip to first successful run.
# Verified on: Python 3.11+, Windows / macOS / Linux
# ─────────────────────────────────────────────────────────────────────────────

---

## STEP 0 — What you need before starting

| Requirement        | Where to get it                            | Cost  |
|--------------------|--------------------------------------------|-------|
| Python 3.11+       | https://python.org/downloads               | Free  |
| Groq API key       | https://console.groq.com → API Keys        | Free  |
| Gemini API key     | https://aistudio.google.com/app/apikey     | Free  |
| OpenRouter API key | https://openrouter.ai/keys                 | Free* |

*OpenRouter account is free. You only pay when the Coder agent calls DeepSeek (~₹0.08 for a
full Tier 1 run). Add $1 credit — it lasts the entire hackathon.

---

## STEP 1 — Unzip and enter the folder

```bash
unzip itanta_framework.zip
cd itanta_framework
```

Your folder should look like this:
```
itanta_framework/
├── main.py
├── config.yaml
├── requirements.txt
├── .env.example
├── agents/
├── orchestrator/
├── tools/
├── validators/
├── utils/
├── cli/
├── config/
├── models/
├── tests/
└── docs/
```

---

## STEP 2 — Create a virtual environment (strongly recommended)

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` at the start of your terminal prompt.

---

## STEP 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs everything: LangGraph, Groq SDK, Gemini SDK, Pydantic, pytest, ruff, mypy,
Rich, Typer, Docker SDK, and all generated project dependencies.

Expected output: lots of "Successfully installed..." messages. Takes 1-2 minutes.

**If you see errors on Windows** about `psycopg2-binary`, run:
```bash
pip install -r requirements.txt --ignore-requires-python
```
PostgreSQL driver issues on Windows don't affect the framework itself — only the
generated project's DB connection.

---

## STEP 4 — Set up your API keys

```bash
# Copy the template
cp .env.example .env
```

Now open `.env` in any text editor and fill in your three keys:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxx
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxx
```

**How to get each key:**

**Groq (free):**
1. Go to https://console.groq.com
2. Sign up (GitHub login works)
3. Click "API Keys" in sidebar → "Create API Key"
4. Copy the key starting with `gsk_`

**Gemini (free):**
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key starting with `AIzaSy`

**OpenRouter (low cost):**
1. Go to https://openrouter.ai
2. Sign up → go to Keys page
3. Create a key
4. Add $1 credit (Settings → Credits) — lasts entire hackathon
5. Copy the key starting with `sk-or-`

---

## STEP 5 — Verify setup (run the test suite)

Before running the full framework, confirm everything is wired correctly:

```bash
pytest tests/ -v
```

**Expected output:**
```
tests/integration/test_tier1_pipeline.py::test_state_schema_is_valid    PASSED
tests/integration/test_tier1_pipeline.py::test_graph_builds_without_error PASSED
tests/integration/test_tier1_pipeline.py::test_graph_has_all_expected_nodes PASSED
tests/integration/test_tier1_pipeline.py::test_activity_log_appends_correctly PASSED
tests/unit/test_state.py::TestFrameworkState::test_default_state_is_valid PASSED
tests/unit/test_state.py::TestFrameworkState::test_state_serialises_to_dict PASSED
tests/unit/test_state.py::TestFrameworkState::test_state_round_trips PASSED
tests/unit/test_state.py::TestFrameworkState::test_model_copy_does_not_mutate PASSED
tests/unit/test_state.py::TestTask::test_task_default_status_is_pending PASSED
tests/unit/test_state.py::TestTask::test_task_retry_count_starts_at_zero PASSED
tests/unit/test_state.py::TestTask::test_task_error_history_appends PASSED
tests/unit/test_state.py::TestSafetyConstraint::test_safe_write_blocks_path_traversal PASSED
tests/unit/test_state.py::TestSafetyConstraint::test_safe_write_allows_project_paths PASSED

13 passed in 1.11s
```

If all 13 pass → you are ready. If any fail, see the Troubleshooting section at the bottom.

---

## STEP 6 — Run the framework

```bash
python main.py
```

**What you see immediately:**

```
╭──────────────────────────────────────────╮
│               ITANTA                     │
│  Itanta Agentic AI Framework             │
│  Multi-agent software development...    │
│                                          │
│  Agents: Intake → Architect → Planner   │
│          → QA → Coder → Validator       │
│          → Recovery                     │
│  Checkpoints: Human approval at Spec,   │
│               Plan, and every Code Diff  │
│  TDD: Tests written before code          │
╰──────────────────────────────────────────╯

Project Specification
Describe what you want to build. Press Enter twice when done.

>
```

---

## STEP 7 — Enter a project spec

Type your spec and press Enter twice. Start with a Tier 1 spec for your first run:

**Recommended first spec (Tier 1 — simplest, fastest):**
```
Build a REST API for a simple ledger system.
It should allow creating, reading, updating and deleting ledger entries.
Each entry has an amount, description, date, and category.
Use FastAPI and PostgreSQL.
```

Press Enter twice to submit.

---

## WHAT HAPPENS NEXT — full walkthrough

### Phase 1: Intake (30-60 seconds)

The Intake agent analyses your spec, finds ambiguities, and asks up to 5 questions.
You answer each one:

```
Clarifying Questions (4 questions)

1. Should the API require authentication, or is it open access?
   Your answer: open access for now

2. Should entries support soft delete (mark as deleted) or hard delete?
   Your answer: hard delete is fine

3. Do you need pagination on the GET all entries endpoint?
   Your answer: yes, basic pagination

4. Should amounts support negative values (for expenses)?
   Your answer: yes
```

### Checkpoint 1 — Review the spec (you approve or reject)

```
⏸  CHECKPOINT: Review Project Specification

{
  "project_name": "simple_ledger",
  "project_summary": "A CRUD REST API for ledger entries...",
  "acceptance_criteria": [...],
  "target_tier": 1
}

Approve and continue? [Y/n]:
```
Type `y` and press Enter.

### Phase 2: Architecture + Planning (30-60 seconds)

The Architect agent designs the system. The Planner agent breaks it into tasks.
Both run automatically — no input needed.

### Checkpoint 2 — Review the task plan (you approve)

```
⏸  CHECKPOINT: Implementation Plan

╭─────────────────────────────────────────────────────╮
│ #  │ Task                        │ Risk   │ CP  │   │
│ 1  │ DB schema + migrations      │ low    │ —   │   │
│ 2  │ Entry Pydantic model        │ low    │ —   │   │
│ 3  │ POST /entries endpoint      │ low    │ —   │   │
│ 4  │ GET /entries (paginated)    │ low    │ —   │   │
│ 5  │ GET /entries/{id}           │ low    │ —   │   │
│ 6  │ PUT /entries/{id}           │ medium │ —   │   │
│ 7  │ DELETE /entries/{id}        │ low    │ —   │   │
│ 8  │ Error handling + 404s       │ low    │ —   │   │
╰─────────────────────────────────────────────────────╯

Approve plan and begin execution? [Y/n]:
```
Type `y` and press Enter.

### Phase 3: TDD Execution loop (3-8 minutes, repeats per task)

For each task, the framework runs this cycle automatically:

```
[1/8] QAAgent → DB schema + migrations
      ✓ Tests written: tests/test_task_1_db_schema.py
      ✓ Tests confirmed FAILING (TDD condition met)

[1/8] CoderAgent → DB schema + migrations
      Generating code...

⏸  CODE REVIEW: Task 1 — DB schema + migrations

+ # FILE: src/db/base.py
+ from sqlalchemy import create_engine...
+ [full new file shown here]

Apply these changes? [Y/n]:
```
Type `y` for each task, or just press Enter (default is approve).

```
      ✓ Validator: 3/3 tests passed, 0 lint errors, 0 type errors
      ✓ Checkpoint saved: task_1
```

This repeats for all 8 tasks. You only need to press Enter at each diff.

### Phase 4: Security audit + Docker (30 seconds)

Runs automatically. No input needed.

```
SecurityAgent → Running security audit...
               ✓ 0 critical, 1 medium finding (logged)
DockerGenerator → Dockerfile + docker-compose.yml generated
```

### Final output

```
╭──────────────────────────╮
│  ✓ WORKFLOW COMPLETE     │
╰──────────────────────────╯

  Tasks completed    8
  Tasks skipped      0
  Tasks failed       0
  Files generated    12
  Tests total        24
  Tests passed       24
  Total API calls    41
  Total retries      0
  Duration           4m 23s
  Output directory   ./generated_projects/simple_ledger_20241201_143022_a1b2c3d4/

Activity log saved to: ./generated_projects/.../itanta_activity_log.json
```

---

## WHAT YOU GET IN THE OUTPUT FOLDER

```
generated_projects/simple_ledger_20241201_143022_a1b2c3d4/
│
├── src/
│   ├── main.py                  FastAPI app entry point
│   ├── db/
│   │   ├── base.py              SQLAlchemy engine + session setup
│   │   └── migrations/          Alembic migration files
│   ├── models/
│   │   └── entry.py             SQLAlchemy Entry model
│   ├── schemas/
│   │   └── entry.py             Pydantic request/response schemas
│   └── routes/
│       └── entries.py           All 5 CRUD endpoints
│
├── tests/
│   ├── test_task_1_db_schema.py
│   ├── test_task_2_entry_model.py
│   ├── test_task_3_post_entries.py
│   └── ... (one file per task)
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt             (for the generated project)
└── itanta_activity_log.json    (full audit trail with timestamps)
```

---

## HOW TO RUN THE GENERATED PROJECT

```bash
cd generated_projects/simple_ledger_.../

# Option A: Docker (recommended — zero setup)
docker compose up --build
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# Option B: Local (needs PostgreSQL running)
pip install -r requirements.txt
uvicorn src.main:app --reload
```

---

## CLI OPTIONS

```bash
# Pass spec directly (skip interactive prompt)
python main.py --spec "Build a task manager API with user auth"

# Force a specific complexity tier
python main.py --tier 2

# Skip all human approval prompts (useful for demos/CI)
python main.py --no-checkpoints

# Resume a paused run (use the run_id from the output)
python main.py --resume a1b2c3d4

# See all options
python main.py --help
```

---

## TROUBLESHOOTING

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: langgraph.checkpoint.sqlite` | Missing sub-package | `pip install langgraph-checkpoint-sqlite` |
| `AuthenticationError: Groq` | Wrong or missing API key | Check `.env` has correct `GROQ_API_KEY` |
| `RateLimitError: Groq` | Hit free tier limit (30 req/min) | Framework auto-retries. If persistent, wait 1 min |
| `ModuleNotFoundError: groq` | Dependencies not installed | `pip install -r requirements.txt` |
| `venv\Scripts\Activate.ps1 cannot be loaded` | PowerShell execution policy | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Tests fail: `ImportError` | Not running from project root | `cd itanta_framework` then `pytest tests/ -v` |
| `FileNotFoundError: .env` | Forgot to copy .env.example | `cp .env.example .env` then fill in keys |
| Coder agent slow on Tier 3+ | Gemini 1.5 Pro fallback (2 RPM) | Add credit to OpenRouter — DeepSeek is faster |
| Generated project won't start | Missing DB | Use `docker compose up` — it starts PostgreSQL too |

---

## QUICK COMMAND REFERENCE

```bash
# Full setup (one time)
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                               # Then fill in your 3 API keys

# Verify setup
pytest tests/ -v                                   # Should show 13 passed

# Run the framework
python main.py                                     # Interactive
python main.py --tier 1 --no-checkpoints          # Fast demo mode (no human prompts)

# Run the generated project
cd generated_projects/<your_project>/
docker compose up --build
```
