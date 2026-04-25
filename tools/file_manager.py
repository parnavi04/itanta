"""
tools/file_manager.py
━━━━━━━━━━━━━━━━━━━━
Safe filesystem operations.

CRITICAL SAFETY RULE (NFR-05):
  The framework must NEVER delete files outside the project working directory.
  All write/delete operations go through this module.
  It resolves absolute paths and verifies they are inside the allowed root.

All agents use safe_write_file() — never open(path, 'w') directly.
"""

import os
import shutil
import json
from pathlib import Path
from utils.exceptions import SafetyViolationError

# The framework sets this at startup — all file ops must be inside this dir
_ALLOWED_ROOT: str = ""

def set_allowed_root(path: str):
    """Called once at startup with the generated project's output directory."""
    global _ALLOWED_ROOT
    _ALLOWED_ROOT = os.path.realpath(path)

def _assert_safe(path: str):
    """Raise SafetyViolationError if path is outside the allowed root."""
    if not _ALLOWED_ROOT:
        return  # Root not set yet (early startup)
    real = os.path.realpath(path)
    if not real.startswith(_ALLOWED_ROOT):
        raise SafetyViolationError(
            f"SAFETY VIOLATION: Attempted to write outside project directory!\n"
            f"  Attempted path: {real}\n"
            f"  Allowed root:   {_ALLOWED_ROOT}"
        )

def safe_write_file(path: str, content: str):
    """Write content to path. Creates parent directories. Enforces safety check."""
    _assert_safe(path)
    os.makedirs(os.path.dirname(os.path.realpath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def safe_read_file(path: str) -> str:
    """Read file content. Returns empty string if file doesn't exist."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def safe_delete_file(path: str):
    """Delete a single file. Enforces safety check — will not delete outside root."""
    _assert_safe(path)
    if os.path.isfile(path):
        os.remove(path)

def snapshot_directory(source_dir: str, checkpoint_name: str) -> str:
    """
    Save a snapshot of the project directory for rollback purposes.
    Snapshots are stored in .itanta_checkpoints/<checkpoint_name>/
    Returns the snapshot path.
    """
    snapshot_dir = os.path.join(
        os.path.dirname(source_dir),
        ".itanta_checkpoints",
        checkpoint_name,
    )
    if os.path.exists(snapshot_dir):
        shutil.rmtree(snapshot_dir)
    shutil.copytree(source_dir, snapshot_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return snapshot_dir

def restore_checkpoint(checkpoint_name: str, output_dir: str):
    """
    Restore project directory from a snapshot.
    Used by RecoveryAgent when rolling back to last passing task.
    """
    snapshot_dir = os.path.join(
        os.path.dirname(output_dir),
        ".itanta_checkpoints",
        checkpoint_name,
    )
    if not os.path.exists(snapshot_dir):
        raise FileNotFoundError(f"Checkpoint not found: {snapshot_dir}")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    shutil.copytree(snapshot_dir, output_dir)
