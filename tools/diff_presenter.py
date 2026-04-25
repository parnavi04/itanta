"""
tools/diff_presenter.py
━━━━━━━━━━━━━━━━━━━━━━
Presents code diffs to the user before applying them to the filesystem.
Satisfies FR-09: generated code changes presented before being applied.

Two modes:
  - Interactive: user sees diff in terminal, types approve/reject
  - Auto-approve: controlled by config (checkpoints.require_diff_approval = false)
"""

import os
import difflib
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich.prompt import Prompt
from tools.file_manager import safe_read_file

console = Console()


def compute_and_present_diff(
    output_directory: str,
    new_files: dict[str, str],
    auto_approve: bool = False,
) -> dict[str, str]:
    """
    For each file in new_files:
      - If file exists: compute unified diff against current content
      - If file is new: show as full addition
    Display all diffs to the user via Rich terminal.
    Return the dict of files the user approved (may exclude rejected files).

    Args:
        output_directory: Root directory of the generated project
        new_files:         {relative_path: new_content} from Coder agent
        auto_approve:      If True, skip interactive prompt

    Returns:
        Dict of approved {relative_path: content}
    """
    if not new_files:
        return {}

    console.print(f"\n[bold cyan]📋 Code Changes — {len(new_files)} file(s)[/bold cyan]\n")

    all_diffs: list[tuple[str, str, str]] = []  # (rel_path, diff_text, new_content)

    for rel_path, new_content in new_files.items():
        abs_path = os.path.join(output_directory, rel_path)
        existing_content = safe_read_file(abs_path)

        if existing_content:
            # Compute unified diff
            diff_lines = list(difflib.unified_diff(
                existing_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
                lineterm="",
            ))
            diff_text = "".join(diff_lines)
            label = "MODIFIED"
        else:
            # New file — show full content as addition
            diff_text = "".join(f"+{line}\n" for line in new_content.splitlines())
            label = "NEW FILE"

        all_diffs.append((rel_path, diff_text, new_content))

        # Display in terminal using Rich
        console.print(Panel(
            Syntax(diff_text or "(no changes)", "diff", theme="monokai", line_numbers=False),
            title=f"[{'green' if label == 'NEW FILE' else 'yellow'}]{label}: {rel_path}[/]",
            border_style="dim",
        ))

    if auto_approve:
        console.print("[dim]Auto-approving (require_diff_approval=false in config)[/dim]\n")
        return new_files

    # Interactive approval
    console.print(f"\n[bold]Files to be written:[/bold] {', '.join(new_files.keys())}")
    choice = Prompt.ask(
        "\n[bold green]Approve these changes?[/bold green]",
        choices=["approve", "reject", "partial"],
        default="approve",
    )

    if choice == "approve":
        console.print("[green]✓ Changes approved[/green]\n")
        return new_files

    elif choice == "reject":
        comment = Prompt.ask("Optional: leave a comment for the Coder agent (or press Enter)")
        console.print("[red]✗ Changes rejected[/red]\n")
        # Return empty dict — Coder agent will not write anything
        # The comment is returned via a side channel if provided
        if comment:
            # Store comment in a temporary file the Coder agent will read on retry
            _write_rejection_comment(output_directory, comment)
        return {}

    else:  # partial
        approved = {}
        for rel_path, diff_text, new_content in all_diffs:
            keep = Prompt.ask(f"  Keep [cyan]{rel_path}[/cyan]?", choices=["y", "n"], default="y")
            if keep == "y":
                approved[rel_path] = new_content
        return approved


def _write_rejection_comment(output_directory: str, comment: str):
    """Write human rejection comment to a temp file the Coder agent reads on retry."""
    comment_path = os.path.join(output_directory, ".itanta_rejection_comment.txt")
    with open(comment_path, "w") as f:
        f.write(comment)
