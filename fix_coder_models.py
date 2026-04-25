"""
fix_coder_models.py
Fixes the Coder agent model names and fallback chain.
- Updates Gemini fallback to gemini-1.5-flash (more available than pro)
- Adds Groq llama as secondary fallback if both fail
Run: python fix_coder_models.py
"""

# ── Fix 1: Update model names in llm_router.py ───────────────────────────────
content = open("tools/llm_router.py", encoding="utf-8").read()

# Fix gemini-1.5-pro fallback → gemini-1.5-flash (higher quota, more reliable)
content = content.replace(
    '"CoderAgent":      (OpenRouterProvider, "deepseek/deepseek-coder-v2-instruct", GeminiProvider, "gemini-1.5-pro")',
    '"CoderAgent":      (OpenRouterProvider, "deepseek/deepseek-coder-v2-instruct", GeminiProvider, "gemini-1.5-flash")'
)

# Also fix any other gemini-1.5-pro references
content = content.replace("gemini-1.5-pro", "gemini-1.5-flash")

open("tools/llm_router.py", "w", encoding="utf-8").write(content)
print("Fixed: tools/llm_router.py — Gemini fallback updated to gemini-1.5-flash")

# ── Fix 2: Make CoderAgent fall back to Groq if OpenRouter also fails ────────
content = open("tools/llm_router.py", encoding="utf-8").read()

old_call = '''        # Try primary provider
        try:
            provider = self._get_provider(primary_cls, primary_model)
            response = provider.complete(system_prompt, user_prompt, temperature, max_tokens, json_mode)
            self._total_api_calls += 1

            if state:
                log_api_call(state, agent=agent, model=primary_model, tokens=response.output_tokens)

            return response

        except RateLimitError as e:
            # Rate limited on primary — try fallback if available
            if fallback_cls:
                print(f"[LLMRouter] Rate limit on {primary_model}, falling back to {fallback_model}")
                time.sleep(2)  # Brief pause before fallback
                provider = self._get_provider(fallback_cls, fallback_model)
                response = provider.complete(system_prompt, user_prompt, temperature, max_tokens, json_mode)
                self._total_api_calls += 1
                return response
            raise

        except LLMProviderError:
            # Provider error — try fallback if available
            if fallback_cls:
                print(f"[LLMRouter] Provider error, falling back to {fallback_model}")
                provider = self._get_provider(fallback_cls, fallback_model)
                return provider.complete(system_prompt, user_prompt, temperature, max_tokens, json_mode)
            raise'''

new_call = '''        # Try primary provider
        try:
            provider = self._get_provider(primary_cls, primary_model)
            response = provider.complete(system_prompt, user_prompt, temperature, max_tokens, json_mode)
            self._total_api_calls += 1

            if state:
                log_api_call(state, agent=agent, model=primary_model, tokens=response.output_tokens)

            return response

        except (RateLimitError, LLMProviderError) as e:
            print(f"[LLMRouter] Primary failed ({primary_model}): {type(e).__name__}")

            # Try declared fallback
            if fallback_cls:
                try:
                    print(f"[LLMRouter] Trying fallback: {fallback_model}")
                    time.sleep(1)
                    provider = self._get_provider(fallback_cls, fallback_model)
                    response = provider.complete(system_prompt, user_prompt, temperature, max_tokens, json_mode)
                    self._total_api_calls += 1
                    return response
                except (RateLimitError, LLMProviderError) as e2:
                    print(f"[LLMRouter] Fallback also failed ({fallback_model}): {type(e2).__name__}")

            # Last resort: Groq llama-3.3-70b for any agent
            print(f"[LLMRouter] Last resort: groq llama-3.3-70b-versatile")
            try:
                last_resort = self._get_provider(GroqProvider, "llama-3.3-70b-versatile")
                response = last_resort.complete(system_prompt, user_prompt, temperature, max_tokens, json_mode)
                self._total_api_calls += 1
                return response
            except Exception as e3:
                raise LLMProviderError(f"All providers failed. Last error: {e3}")'''

if old_call in content:
    content = content.replace(old_call, new_call)
    open("tools/llm_router.py", "w", encoding="utf-8").write(content)
    print("Fixed: tools/llm_router.py — added Groq last-resort fallback")
else:
    print("Warning: fallback pattern not found — manual check needed")
    print("But the gemini model name fix was applied — try running anyway")

print("\nDone. Now run: python main.py")
