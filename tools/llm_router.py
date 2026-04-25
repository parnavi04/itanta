"""
tools/llm_router.py
━━━━━━━━━━━━━━━━━━
Single interface to all LLM providers.

ALL agents call this — never call a provider SDK directly.

Provider assignments (cost-optimised):
  GROQ     → Llama 3.1 70B (Intake, Architect, Planner)
  GROQ     → Llama 3.1 8B  (Recovery, Security)
  GEMINI   → Gemini 1.5 Flash (QA Agent)
  OPENROUTER → DeepSeek Coder V2 (Coder Agent — only paid model)
  GEMINI   → Gemini 1.5 Pro (Coder fallback — free but 2 RPM)

Adding a new provider: subclass BaseLLMProvider and register in PROVIDER_MAP.
"""

from __future__ import annotations
import os
import json
import time
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

from utils.logger import log_api_call
from utils.exceptions import LLMProviderError, RateLimitError


# ─────────────────────────────────────────────
# Response model
# ─────────────────────────────────────────────

class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0


# ─────────────────────────────────────────────
# Base provider
# ─────────────────────────────────────────────

class BaseLLMProvider(ABC):
    """All providers implement this interface."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Send a completion request. Raise LLMProviderError on failure."""
        pass


# ─────────────────────────────────────────────
# Groq provider  (free tier — primary for reasoning agents)
# ─────────────────────────────────────────────

class GroqProvider(BaseLLMProvider):
    """
    Groq API — extremely fast inference on LPU hardware.
    Free tier: 30 req/min, 14,400 req/day.
    Used for: Intake, Architect, Planner, Recovery, Security agents.
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        from groq import Groq
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = model

    def complete(self, system_prompt, user_prompt, temperature=0.2, max_tokens=4096, json_mode=False) -> LLMResponse:
        start = time.time()
        try:
            kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            latency = (time.time() - start) * 1000

            return LLMResponse(
                content=response.choices[0].message.content,
                model=self.model,
                provider="groq",
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                latency_ms=latency,
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise RateLimitError(f"Groq rate limit hit: {e}")
            raise LLMProviderError(f"Groq error: {e}")


# ─────────────────────────────────────────────
# Gemini provider  (free tier — QA agent + fallback)
# ─────────────────────────────────────────────

class GeminiProvider(BaseLLMProvider):
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
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
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
            raise LLMProviderError(f"Gemini error: {e}")


# ─────────────────────────────────────────────
# OpenRouter provider  (DeepSeek Coder — only paid model)
# ─────────────────────────────────────────────

class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter — unified API for 100+ models.
    Primary model: deepseek/deepseek-coder-v2:free  (or paid variant)
    Cost: ~$0.001/1K tokens — only used for the Coder agent.
    Fallback: if DeepSeek unavailable, swap model to gemini-pro in config.
    """

    def __init__(self, model: str = "deepseek/deepseek-coder-v2-instruct"):
        import httpx
        self.api_key = os.environ["OPENROUTER_API_KEY"]
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.http = httpx.Client(timeout=120.0)

    def complete(self, system_prompt, user_prompt, temperature=0.2, max_tokens=4096, json_mode=False) -> LLMResponse:
        start = time.time()
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/itanta-hackathon",
                "Content-Type": "application/json",
            }
            response = self.http.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            latency = (time.time() - start) * 1000

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=self.model,
                provider="openrouter",
                input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                output_tokens=data.get("usage", {}).get("completion_tokens", 0),
                latency_ms=latency,
            )
        except Exception as e:
            if "429" in str(e):
                raise RateLimitError(f"OpenRouter rate limit: {e}")
            raise LLMProviderError(f"OpenRouter error: {e}")


# ─────────────────────────────────────────────
# Router — the single public interface
# ─────────────────────────────────────────────

class LLMRouter:
    """
    The ONLY class agents should use to call LLMs.

    Usage:
        router = LLMRouter()
        response = router.call(
            agent="IntakeAgent",
            system_prompt="...",
            user_prompt="...",
            json_mode=True
        )
        text = response.content
    """

    # Maps agent name → (provider_class, model_name, fallback_provider_class, fallback_model)
    AGENT_MODEL_MAP: dict[str, tuple] = {
        "IntakeAgent":     (GroqProvider,       "llama-3.3-70b-versatile",           None, None),
        "ArchitectAgent":  (GroqProvider,       "llama-3.3-70b-versatile",           None, None),
        "PlannerAgent":    (GroqProvider,       "llama-3.3-70b-versatile",           None, None),
        "QAAgent":         (GeminiProvider,     "gemini-1.5-flash",                  GroqProvider, "llama-3.3-70b-versatile"),
        "CoderAgent":      (OpenRouterProvider, "deepseek/deepseek-coder-v2-instruct", GeminiProvider, "gemini-1.5-flash"),
        "RecoveryAgent":   (GroqProvider,       "llama-3.1-8b-instant",              None, None),
        "SecurityAgent":   (GroqProvider,       "llama-3.1-8b-instant",              None, None),
    }

    def __init__(self):
        self._provider_cache: dict[str, BaseLLMProvider] = {}
        self._total_api_calls = 0

    def _get_provider(self, provider_class, model: str) -> BaseLLMProvider:
        """Cache provider instances — don't reinstantiate on every call."""
        key = f"{provider_class.__name__}:{model}"
        if key not in self._provider_cache:
            self._provider_cache[key] = provider_class(model=model)
        return self._provider_cache[key]

    def call(
        self,
        agent: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        json_mode: bool = False,
        state: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Route an LLM call to the correct provider for this agent.
        Automatically falls back to the secondary provider on rate limit or error.

        Args:
            agent:         Agent name (must match AGENT_MODEL_MAP key)
            system_prompt: System/persona instructions
            user_prompt:   The actual task prompt
            temperature:   0.0 = deterministic, 1.0 = creative. Default 0.2 for agents.
            max_tokens:    Max response length
            json_mode:     Ask provider to return valid JSON only
            state:         Current framework state (for activity logging)
        """
        if agent not in self.AGENT_MODEL_MAP:
            raise ValueError(f"Unknown agent '{agent}'. Add it to LLMRouter.AGENT_MODEL_MAP.")

        primary_cls, primary_model, fallback_cls, fallback_model = self.AGENT_MODEL_MAP[agent]

        # Try primary provider
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
                raise LLMProviderError(f"All providers failed. Last error: {e3}")

    def parse_json_response(self, response: LLMResponse) -> dict:
        """
        Safely parse JSON from an LLM response.
        Strips markdown fences if the model wrapped the JSON in ```json blocks.
        """
        text = response.content.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"LLM returned invalid JSON: {e}\nRaw response: {text[:500]}")

    @property
    def total_api_calls(self) -> int:
        return self._total_api_calls


# Singleton — import and use this everywhere
router = LLMRouter()
