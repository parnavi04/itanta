"""
fix_generated_project.py
Patches the generated src/main.py to use SQLite instead of PostgreSQL.
Run this from INSIDE the generated project folder.

Usage:
  cd generated_projects\build_a_rest_api_for_a_simple_ledger_sys_...
  python fix_generated_project.py
"""

import os

# Verify we're in the right place
if not os.path.exists("src/main.py"):
    print("ERROR: src/main.py not found.")
    print("Make sure you CD into the generated project folder first.")
    print("Example: cd generated_projects\\build_a_rest_api_for_a_simple_ledger_sys_...")
    exit(1)

content = open("src/main.py", encoding="utf-8").read()
original = content

# Fix 1: Switch PostgreSQL URL to SQLite
for pg_url in [
    "postgresql://user:password@localhost/db",
    "postgresql://user:password@localhost/dbname",
    "postgresql://user:password@localhost/ledger",
]:
    content = content.replace(
        f'SQLALCHEMY_DATABASE_URL = "{pg_url}"',
        'SQLALCHEMY_DATABASE_URL = "sqlite:///./ledger.db"'
    )

# Fix 2: Add check_same_thread for SQLite
content = content.replace(
    "engine = create_engine(SQLALCHEMY_DATABASE_URL)",
    'engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})'
)

# Fix 3: Remove create_all at module level (it crashes on import)
content = content.replace(
    "Base.metadata.create_all(bind=engine)",
    "# DB tables created on app startup (see lifespan below)"
)

# Fix 4: Add lifespan to create tables safely on startup
if "lifespan" not in content:
    content = content.replace(
        "app = FastAPI()",
        (
            "from contextlib import asynccontextmanager\n\n"
            "@asynccontextmanager\n"
            "async def lifespan(app):\n"
            "    Base.metadata.create_all(bind=engine)\n"
            "    yield\n\n"
            "app = FastAPI(lifespan=lifespan)"
        )
    )

if content == original:
    print("WARNING: No changes made — the patterns may already be fixed or different.")
    print("Check src/main.py manually for the database URL line.")
else:
    open("src/main.py", "w", encoding="utf-8").write(content)
    print("Fixed: src/main.py")
    print("  - PostgreSQL -> SQLite")
    print("  - create_all moved to lifespan startup")
    print("  - SQLite thread safety added")

# Fix 5: Also patch any route files that import from src.main
for route_file in ["src/routes/users.py", "src/routes/login.py", "src/routes/ledger_entries.py"]:
    if os.path.exists(route_file):
        rc = open(route_file, encoding="utf-8").read()
        # Remove trailing junk like `"` and `}` that the LLM sometimes appends
        rc = rc.rstrip().rstrip('}"').rstrip()
        open(route_file, "w", encoding="utf-8").write(rc + "\n")
        print(f"Cleaned: {route_file}")

print("\nNow run:")
print("  uvicorn src.main:app --reload")
print("\nThen open: http://127.0.0.1:8000/docs")
