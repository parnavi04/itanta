"""
cli/interface.py
━━━━━━━━━━━━━━━
Terminal user interface using Typer (CLI framework) + Rich (display).

Satisfies:
  NFR-01: User can submit first spec within 5 minutes of setup
  FR-06:  Implementation plan presented to user before execution
  FR-09:  Code diff presented to user before being applied

All user-facing output goes through this module.
Agents should NEVER use print() directly — use log_action() or these functions.
"""

from __future__ import annotations
import json
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.text import Text
from rich import box
from orchestrator.state import Task, WorkflowSummary

console = Console()


# ─────────────────────────────────────────────
# Welcome banner
# ─────────────────────────────────────────────

def show_banner():
    """Display the framework intro banner at startup."""
    console.print(Panel.fit(
        "[bold cyan]Itanta Agentic AI Framework[/bold cyan]\n"
        "[dim]Multi-agent software development pipeline[/dim]\n\n"
        "[green]Agents:[/green] Intake → Architect → Planner → QA → Coder → Validator → Recovery\n"
        "[green]Checkpoints:[/green] Human approval at Spec, Plan, and every Code Diff\n"
        "[green]TDD:[/green] Tests written before code — always",
        title="[bold]ITANTA[/bold]",
        border_style="cyan",
    ))


# ─────────────────────────────────────────────
# Spec input
# ─────────────────────────────────────────────

def get_project_spec() -> str:
    """
    Prompt user for their project specification.
    Supports multi-line input (blank line to finish).
    """
    console.print("\n[bold cyan]Project Specification[/bold cyan]")
    console.print("[dim]Describe what you want to build. Be as detailed as you like.[/dim]")
    console.print("[dim]Press Enter twice when done.[/dim]\n")

    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Clarification questions (Intake agent)
# ─────────────────────────────────────────────

def ask_clarification_questions(questions: list[str]) -> list[str]:
    """
    Present the Intake agent's clarifying questions to the user.
    Collect and return answers.
    """
    if not questions:
        return []

    console.print(f"\n[bold yellow]Clarifying Questions[/bold yellow] [dim]({len(questions)} questions)[/dim]\n")
    console.print("[dim]Answer these to help the framework understand your project precisely.[/dim]\n")

    answers = []
    for i, question in enumerate(questions, 1):
        console.print(f"[bold]{i}.[/bold] {question}")
        answer = Prompt.ask("   [green]Your answer[/green]")
        answers.append(answer)
        console.print()

    return answers


# ─────────────────────────────────────────────
# Human checkpoints
# ─────────────────────────────────────────────

def present_checkpoint(title: str, content: dict, instructions: str) -> bool:
    """
    Present a checkpoint to the user — show content and ask for approval.
    Returns True if approved, False if rejected.
    """
    console.print(f"\n[bold magenta]⏸  CHECKPOINT: {title}[/bold magenta]")
    console.print(f"[dim]{instructions}[/dim]\n")

    # Pretty-print the content as a formatted JSON panel
    content_str = json.dumps(content, indent=2, default=str)
    console.print(Panel(
        Syntax(content_str, "json", theme="monokai", line_numbers=False),
        title=f"[cyan]{title}[/cyan]",
        border_style="magenta",
    ))

    approved = Confirm.ask(f"\n[bold green]Approve and continue?[/bold green]", default=True)
    return approved


def present_plan_checkpoint(tasks: list[Task]) -> bool:
    """
    Special checkpoint for the task plan — shows a table of all tasks
    with their risk levels and checkpoint flags.
    """
    console.print("\n[bold magenta]⏸  CHECKPOINT: Implementation Plan[/bold magenta]")
    console.print("[dim]Review the task list before execution begins.[/dim]\n")

    table = Table(
        title="Implementation Plan",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#",     style="dim", width=4)
    table.add_column("Task",  style="white")
    table.add_column("Risk",  width=8)
    table.add_column("Checkpoint", width=12)
    table.add_column("Depends On", style="dim", width=12)

    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}

    for task in tasks:
        risk_color = risk_colors.get(str(task.risk_level), "white")
        table.add_row(
            str(task.id),
            task.title,
            f"[{risk_color}]{task.risk_level}[/{risk_color}]",
            "✓ yes" if task.requires_human_checkpoint else "—",
            ", ".join(str(d) for d in task.depends_on) or "—",
        )

    console.print(table)
    return Confirm.ask("\n[bold green]Approve plan and begin execution?[/bold green]", default=True)


# ─────────────────────────────────────────────
# Diff display (Coder agent output)
# ─────────────────────────────────────────────

def present_diff(task: Task, instructions: str) -> bool:
    """
    Present the code diff for a task and ask for approval.
    The actual diff content is displayed by diff_presenter.py.
    This function handles the approval prompt.
    """
    console.print(f"\n[bold yellow]⏸  CODE REVIEW: Task {task.id} — {task.title}[/bold yellow]")
    console.print(f"[dim]{instructions}[/dim]\n")
    console.print(f"[dim]Files: {', '.join(task.generated_files)}[/dim]\n")

    return Confirm.ask("[bold green]Apply these changes?[/bold green]", default=True)


# ─────────────────────────────────────────────
# Progress indicators
# ─────────────────────────────────────────────

def show_task_progress(current: int, total: int, task_title: str, agent: str):
    """Display current task progress in a single-line status."""
    console.print(
        f"[dim][{current}/{total}][/dim] "
        f"[cyan]{agent}[/cyan] → "
        f"[white]{task_title}[/white]"
    )


def show_agent_thinking(agent_name: str, action: str):
    """Show a spinner while an LLM call is in progress."""
    # Used as context manager: with show_agent_thinking(...):
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]{agent_name}[/cyan] {action}..."),
        transient=True,
    )


# ─────────────────────────────────────────────
# Summary report (final output)
# ─────────────────────────────────────────────

def present_summary(summary: WorkflowSummary):
    """
    Display the final workflow summary report (NFR-06).
    Shows: tasks completed/skipped/failed, files generated,
           tests passed/failed, total API calls.
    """
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]✓ WORKFLOW COMPLETE[/bold green]",
        border_style="green",
    ))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Metric", style="dim")
    table.add_column("Value",  style="bold white")

    table.add_row("Tasks completed",    f"[green]{summary.tasks_completed}[/green]")
    table.add_row("Tasks skipped",      f"[yellow]{summary.tasks_skipped}[/yellow]")
    table.add_row("Tasks failed",       f"[red]{summary.tasks_failed}[/red]")
    table.add_row("Files generated",    str(summary.files_generated))
    table.add_row("Tests total",        str(summary.tests_total))
    table.add_row("Tests passed",       f"[green]{summary.tests_passed}[/green]")
    table.add_row("Total API calls",    str(summary.total_api_calls))
    table.add_row("Total retries",      str(summary.total_retries))
    table.add_row("Duration",           f"{summary.duration_seconds:.1f}s")
    table.add_row("Output directory",   f"[cyan]{summary.output_directory}[/cyan]")

    console.print(table)
    console.print(
        "\n[dim]Activity log saved to:[/dim] "
        f"[cyan]{summary.output_directory}/itanta_activity_log.json[/cyan]\n"
    )
