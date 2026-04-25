"""config/loader.py — Typed config object from config.yaml + .env"""

import os
import yaml
from functools import lru_cache
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class CheckpointConfig(BaseModel):
    require_spec_approval: bool = True
    require_plan_approval: bool = True
    require_diff_approval: bool = True

class GuardrailConfig(BaseModel):
    file_change_threshold: int = 10   # Force human review if >N files change at once
    max_file_deletions: int = 0       # Safety: never delete files (NFR-05)
    block_shell_commands: list[str] = ["rm -rf", "sudo", "format", "del /f"]

class Config(BaseModel):
    max_retries: int = 3
    rollback_on_max_retries: bool = True
    target_tier: int = 1
    output_base_dir: str = "./generated_projects"
    checkpoints: CheckpointConfig = CheckpointConfig()
    guardrails: GuardrailConfig = GuardrailConfig()

@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load and cache config. Call this anywhere."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return Config(**data)
    return Config()  # Defaults if no config file
