"""
fix_coder_json.py
Fixes two issues:
1. LLM returns code with triple-quotes inside JSON (breaks all JSON parsers)
   Solution: Tell the Coder agent NOT to use json_mode, parse the response differently
2. Gemini SDK deprecated — update to google.genai
Run: python fix_coder_json.py
"""

import re

# ── Fix 1: Coder agent — disable json_mode, use code-block parsing instead ──
print("Fixing agents/coder_agent.py ...")
content = open("agents/coder_agent.py", encoding="utf-8").read()

# Change the router.call to NOT use json_mode (code with quotes breaks JSON mode)
content = content.replace(
    "        json_mode=True,\n        state=state.model_dump(),\n    )\n\n    data = router.parse_json_response(response)",
    "        json_mode=False,  # json_mode breaks when code contains triple-quotes\n        state=state.model_dump(),\n    )\n\n    data = _parse_coder_response(response.content)"
)

# Add the custom parser function before run_coder
custom_parser = '''
def _parse_coder_response(content: str) -> dict:
    """
    Parse the coder LLM response which may contain triple-quoted Python code.
    Standard JSON parsers fail on this — we extract files manually.
    Strategy: ask the LLM for a simpler format and parse it robustly.
    """
    import json
    import re

    # Try standard JSON first (sometimes it works)
    try:
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\\n")
            text = "\\n".join(lines[1:-1])
        return json.loads(text)
    except Exception:
        pass

    # Extract files using regex: look for "filename": followed by content
    files = {}
    # Pattern: "path/to/file.py": "content" or """content"""
    # We split on file path markers instead
    lines = content.split("\\n")
    current_file = None
    current_lines = []
    in_file = False

    for line in lines:
        # Detect file path keys like "src/main.py":
        match = re.match(r\'\\s*["\\']((?:src|tests?)/[\\w/._-]+\\.py)["\\'\\s]*:\', line)
        if match:
            if current_file and current_lines:
                files[current_file] = "\\n".join(current_lines)
            current_file = match.group(1)
            current_lines = []
            in_file = True
            continue
        if in_file and current_file:
            # Stop collecting if we hit the explanation key
            if \'"explanation"\' in line or "\\'explanation\\'" in line:
                if current_file and current_lines:
                    files[current_file] = "\\n".join(current_lines)
                current_file = None
                current_lines = []
                in_file = False
                continue
            # Strip leading triple-quotes, trailing triple-quotes, escaped newlines
            cleaned = line.replace(\'\\\\\\\\\', \'\\\\\').replace(\\'\\\\n\\', \\'\\\\n\\')
            cleaned = cleaned.strip(\\'"\\'\\').strip(\\'"""\\'\\')
            if cleaned not in (\'"""\', "\\'\\'\\'", \'",\', \'"\'):
                current_lines.append(cleaned)

    if current_file and current_lines:
        files[current_file] = "\\n".join(current_lines)

    if files:
        return {"files": files, "explanation": "parsed from response"}

    # Last resort: treat entire response as a single main.py file
    # Extract anything that looks like Python code
    code_match = re.search(r\'```python\\n(.*?)```\', content, re.DOTALL)
    if code_match:
        return {"files": {"src/main.py": code_match.group(1)}, "explanation": "extracted from code block"}

    # Give up gracefully — return empty so the recovery agent handles it
    return {"files": {}, "explanation": "could not parse response"}

'''

# Insert before run_coder function
content = content.replace(
    "\ndef run_coder(state: FrameworkState) -> FrameworkState:",
    custom_parser + "\ndef run_coder(state: FrameworkState) -> FrameworkState:"
)

open("agents/coder_agent.py", "w", encoding="utf-8").write(content)
print("  Fixed: json_mode disabled, custom parser added")

# ── Fix 2: Update Gemini SDK from google.generativeai to google.genai ────────
print("Fixing tools/llm_router.py ...")
content = open("tools/llm_router.py", encoding="utf-8").read()

old_gemini = '''class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini via google-generativeai SDK.
    Flash: free 15 req/min, 1M tok/day  → primary for QA agent
    Pro:   free 2 req/min               → fallback for Coder agent
    """

    def __init__(self, model: str = "gemini-1.5-flash"):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.model_name = model
        self.genai = genai

    def complete(self, system_prompt, user_prompt, temperature=0.2, max_tokens=4096, json_mode=False) -> LLMResponse:
        start = time.time()
        try:
            generation_config = {"temperature": temperature, "max_output_tokens": max_tokens}
            if json_mode:
                generation_config["response_mime_type"] = "application/json"

            model = self.genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )
            response = model.generate_content(user_prompt)
            latency = (time.time() - start) * 1000

            return LLMResponse(
                content=response.text,
                model=self.model_name,
                provider="gemini",
                latency_ms=latency,
            )
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Gemini rate limit hit: {e}")
            raise LLMProviderError(f"Gemini error: {e}")'''

new_gemini = '''class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini via google-genai SDK (updated from deprecated google.generativeai).
    Flash: free 15 req/min, 1M tok/day  → primary for QA agent
    """

    def __init__(self, model: str = "gemini-1.5-flash"):
        try:
            from google import genai
            self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            self.sdk = "new"
        except ImportError:
            import google.generativeai as genai_old
            genai_old.configure(api_key=os.environ["GEMINI_API_KEY"])
            self.genai_old = genai_old
            self.sdk = "old"
        self.model_name = model

    def complete(self, system_prompt, user_prompt, temperature=0.2, max_tokens=4096, json_mode=False) -> LLMResponse:
        start = time.time()
        try:
            if self.sdk == "new":
                from google.genai import types
                full_prompt = f"{system_prompt}\\n\\n{user_prompt}"
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=config,
                )
                text = response.text
            else:
                generation_config = {"temperature": temperature, "max_output_tokens": max_tokens}
                model = self.genai_old.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_prompt,
                    generation_config=generation_config,
                )
                response = model.generate_content(user_prompt)
                text = response.text

            latency = (time.time() - start) * 1000
            return LLMResponse(
                content=text,
                model=self.model_name,
                provider="gemini",
                latency_ms=latency,
            )
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower() or "429" in str(e):
                raise RateLimitError(f"Gemini rate limit hit: {e}")
            raise LLMProviderError(f"Gemini error: {e}")'''

if old_gemini in content:
    content = content.replace(old_gemini, new_gemini)
    print("  Fixed: GeminiProvider updated to google.genai SDK")
else:
    # Try to patch just the import line
    content = content.replace(
        "        import google.generativeai as genai\n        genai.configure(api_key=os.environ[\"GEMINI_API_KEY\"])\n        self.model_name = model\n        self.genai = genai",
        "        try:\n            from google import genai as genai_new\n            genai_new.configure(api_key=os.environ[\"GEMINI_API_KEY\"])\n            self.genai = genai_new\n        except Exception:\n            import google.generativeai as genai_old\n            genai_old.configure(api_key=os.environ[\"GEMINI_API_KEY\"])\n            self.genai = genai_old\n        self.model_name = model"
    )
    print("  Applied partial Gemini fix")

open("tools/llm_router.py", "w", encoding="utf-8").write(content)

# ── Fix 3: Install updated Gemini SDK ────────────────────────────────────────
print("\nInstalling updated google-genai SDK...")
import subprocess
result = subprocess.run(
    ["pip", "install", "google-genai", "--quiet"],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("  Installed: google-genai")
else:
    print("  Warning: could not auto-install. Run: pip install google-genai")

print("\nAll fixes applied. Now run: python main.py")
