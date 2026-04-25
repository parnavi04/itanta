"""
main.py
━━━━━━
Itanta Agentic AI Framework — Single Entrypoint

Run this file to start the framework:
    python main.py

What happens:
  1. Loads config.yaml + .env
  2. Shows CLI banner, prompts for project spec
  3. Builds a unique output directory for this run
  4. Sets up file safety root (NFR-05)
  5. Compiles the LangGraph pipeline
  6. Runs the pipeline — all agents execute in order
  7. On interrupt() (human checkpoint), pauses and waits for user input
  8. On completion, writes summary + activity log

Resume an interrupted run:
    python main.py --resume <run_id>
"""

import os
import uuid
import typer
from datetime import datetime
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from orchestrator.graph import get_compiled_graph
from orchestrator.state import FrameworkState
from tools.file_manager import set_allowed_root
from config.loader import get_config
from cli.interface import show_banner, get_project_spec, console
from utils.logger import dump_activity_log


app = typer.Typer(
    name="itanta",
    help="Agentic AI Software Development Framework",
    add_completion=False,
)


@app.command()
def run(
    spec: str = typer.Option(None, "--spec", "-s", help="Project spec (or omit to enter interactively)"),
    resume: str = typer.Option(None, "--resume", "-r", help="Resume a paused run by run_id"),
    tier: int = typer.Option(None, "--tier", "-t", help="Force complexity tier 1-5"),
    no_checkpoints: bool = typer.Option(False, "--no-checkpoints", help="Skip all human approvals (CI mode)"),
):
    """
    Start the Itanta Agentic AI Framework.
    Accepts a project spec and autonomously builds a working codebase.
    """
    show_banner()
    cfg = get_config()

    # ── Override config from CLI flags ──────────────────────────────────────
    if no_checkpoints:
        cfg.checkpoints.require_spec_approval = False
        cfg.checkpoints.require_plan_approval = False
        cfg.checkpoints.require_diff_approval = False
        console.print("[yellow]⚠ All human checkpoints disabled (--no-checkpoints)[/yellow]\n")

    if tier:
        cfg.target_tier = tier

    # ── Build/load graph ────────────────────────────────────────────────────
    graph = get_compiled_graph()

    # ── Resume path ─────────────────────────────────────────────────────────
    if resume:
        console.print(f"[cyan]Resuming run: {resume}[/cyan]\n")
        thread_config = {"configurable": {"thread_id": resume}}
        _run_with_checkpoints(graph, None, thread_config, is_resume=True)
        return

    # ── New run ─────────────────────────────────────────────────────────────
    # Get project specification
    raw_spec = spec if spec else get_project_spec()
    if not raw_spec.strip():
        console.print("[red]Error: Project specification cannot be empty.[/red]")
        raise typer.Exit(1)

    # Generate unique run ID and output directory
    run_id = str(uuid.uuid4())[:8]
    project_slug = _slugify(raw_spec[:40])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.abspath(cfg.output_base_dir),
        f"{project_slug}_{timestamp}_{run_id}",
    )
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "tests"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "src"), exist_ok=True)

    # Set safety root — all file writes must be inside this directory (NFR-05)
    set_allowed_root(output_dir)
    console.print(f"[dim]Output directory: {output_dir}[/dim]")
    console.print(f"[dim]Run ID: {run_id}[/dim]\n")

    # Build initial state
    initial_state = FrameworkState(
        raw_spec=raw_spec,
        run_id=run_id,
        output_directory=output_dir,
    ).model_dump()

    thread_config = {"configurable": {"thread_id": run_id}}
    _run_with_checkpoints(graph, initial_state, thread_config, is_resume=False)


def _run_with_checkpoints(graph, initial_state, thread_config, is_resume: bool):
    """
    Execute the LangGraph pipeline, handling human-in-the-loop interrupts.

    LangGraph interrupt() pauses the graph and surfaces a GraphInterrupt.
    We catch it, let the CLI handle the human interaction,
    then call graph.invoke(Command(resume=True)) to continue from the checkpoint.
    """
    max_interrupt_loops = 50  # Safety valve — prevents infinite loops
    loops = 0

    # First invocation (or resume)
    if is_resume:
        result = graph.invoke(Command(resume=True), config=thread_config)
    else:
        result = graph.invoke(initial_state, config=thread_config)

    # Handle potential interrupted state (checkpoint already hit)
    while loops < max_interrupt_loops:
        loops += 1

        # Check if graph hit an interrupt (human checkpoint)
        snapshot = graph.get_state(thread_config)
        if snapshot.next:
            # Graph is paused at a checkpoint — resume after human interaction
            console.print(f"\n[dim]Resuming after checkpoint (next node: {snapshot.next})[/dim]")
            result = graph.invoke(Command(resume=True), config=thread_config)
        else:
            # Graph completed normally
            break

    # Final state
    if result:
        final_state = FrameworkState(**result)
        if final_state.summary:
            console.print("\n[bold green]✓ Framework run complete.[/bold green]")
        else:
            console.print("\n[yellow]Run ended without summary — check activity log for details.[/yellow]")

        # Always dump activity log on exit
        if final_state.output_directory and os.path.exists(final_state.output_directory):
            log_path = os.path.join(final_state.output_directory, "itanta_activity_log.json")
            dump_activity_log(result, log_path)
            console.print(f"[dim]Activity log: {log_path}[/dim]")


def _slugify(text: str) -> str:
    """Convert text to a safe directory name slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:40].strip("_") or "project"


if __name__ == "__main__":
    app()
