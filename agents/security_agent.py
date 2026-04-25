"""
agents/security_agent.py
━━━━━━━━━━━━━━━━━━━━━━━
Agent 7 — Security Auditor (Extended Feature FR-14)

RESPONSIBILITY:
  Runs after all tasks complete.
  Scans generated codebase for: injection vulnerabilities, auth flaws, logic errors.
  Produces SecurityFinding list. Does NOT block the pipeline — reports only.

LLM: Groq Llama 3.1 8B (free, fast for pattern scanning)
"""

import os
import json
from orchestrator.state import FrameworkState, SecurityFinding
from tools.llm_router import router
from tools.file_manager import safe_read_file
from utils.logger import log_action

SECURITY_SYSTEM = """You are a security code reviewer specialising in Python web APIs.
Scan code for OWASP Top 10 vulnerabilities. Be specific about file and line.
Respond in valid JSON only."""

SECURITY_PROMPT = """Security audit this Python web API code.

FILES TO AUDIT:
{code_samples}

Respond with JSON:
{{
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "category": "injection|auth|logic|exposure|other",
      "file_path": "relative/path.py",
      "line_number": null,
      "description": "what the vulnerability is",
      "recommendation": "how to fix it"
    }}
  ]
}}

Focus on: SQL injection, hardcoded secrets, missing auth checks, insecure direct object references.
"""


def run_security(state: FrameworkState) -> FrameworkState:
    """Audits the generated codebase for security issues."""
    if not state.output_directory or not os.path.exists(state.output_directory):
        return state  # Nothing to audit

    # Collect source files (skip tests, skip __pycache__)
    code_samples = {}
    for root, _, files in os.walk(state.output_directory):
        if "__pycache__" in root or "tests" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                rel = os.path.relpath(path, state.output_directory)
                content = safe_read_file(path)
                if content:
                    code_samples[rel] = content[:3000]  # Truncate large files

    if not code_samples:
        return state

    prompt = SECURITY_PROMPT.format(
        code_samples=json.dumps(code_samples, indent=2)
    )

    response = router.call(
        agent="SecurityAgent",
        system_prompt=SECURITY_SYSTEM,
        user_prompt=prompt,
        json_mode=True,
        state=state.model_dump(),
    )

    data = router.parse_json_response(response)
    findings = [SecurityFinding(**f) for f in data.get("findings", [])]

    log_action(
        state.model_dump(),
        agent="SecurityAgent",
        action=f"Security audit complete: {len(findings)} findings",
        detail=json.dumps([f.model_dump() for f in findings[:3]]),
    )

    return state.model_copy(update={"security_findings": findings})
