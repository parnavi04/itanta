"""utils/exceptions.py — All custom exceptions for the framework."""

class ItantaBaseError(Exception):
    """Base for all framework errors."""
    pass

class AgentError(ItantaBaseError):
    """Raised by an agent when it cannot complete its task."""
    def __init__(self, agent: str, message: str):
        super().__init__(f"[{agent}] {message}")
        self.agent = agent

class LLMProviderError(ItantaBaseError):
    """LLM API call failed and no fallback succeeded."""
    pass

class RateLimitError(LLMProviderError):
    """LLM provider rate limit hit."""
    pass

class SafetyViolationError(ItantaBaseError):
    """Attempted file operation outside the allowed project directory (NFR-05)."""
    pass

class CheckpointError(ItantaBaseError):
    """Failed to save or restore a checkpoint."""
    pass

class ValidationError(ItantaBaseError):
    """Generated code failed validation and max retries exceeded."""
    pass
