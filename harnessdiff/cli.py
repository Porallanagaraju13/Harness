"""
Command-line interface for HarnessDiff.
"""

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from harnessdiff.config import HarnessConfig
from harnessdiff.models import (
    DEFAULT_GEMINI_MODEL,
    create_model,
    list_gemini_models,
)
from harnessdiff.runner import AblationRunner, TaskRunner, compare_before_after
from tasks import get_all_tasks

# Configure console with safe encoding for Windows
try:
    console = Console()
    console.print("", end="")
except UnicodeEncodeError:
    console = Console(legacy_windows=False, force_terminal=True)


def safe_checkmark():
    """Return checkmark that works on Windows cp1252"""
    try:
        "✓".encode(sys.stdout.encoding or "utf-8")
        return "✓"
    except (UnicodeEncodeError, AttributeError):
        return "OK"


def safe_cross():
    """Return cross that works on Windows cp1252"""
    try:
        "✗".encode(sys.stdout.encoding or "utf-8")
        return "✗"
    except (UnicodeEncodeError, AttributeError):
        return "X"


@click.group()
def main():
    """
    HarnessDiff: Show exactly what each agent harness layer fixes.

    Run agent tasks with different harness configurations and see the impact.
    """
    pass


MODEL_HELP = (
    "Model provider. Examples: mock (default), openai, openai:gpt-4o-mini, "
    f"anthropic, gemini, gemini:{DEFAULT_GEMINI_MODEL}. "
    "Gemini default is also configurable via HARNESSDIFF_GEMINI_MODEL."
)


@main.command()
@click.option("--model", default="mock", help=MODEL_HELP)
@click.option("--output-dir", default="./results", help="Output directory for results")
def run(model: str, output_dir: str):
    """Run tasks with baseline (no harness) configuration"""
    console.print("\n[bold blue]Running with NO harness (before)[/bold blue]\n")

    model_provider = _get_model(model)
    config = HarnessConfig.baseline()

    runner = TaskRunner(model_provider, Path(output_dir))
    results = runner.run_all_tasks(config, "baseline")

    _print_results(results, "Baseline")


@main.command()
@click.option("--model", default="mock", help=MODEL_HELP)
@click.option("--output-dir", default="./results", help="Output directory for results")
def after(model: str, output_dir: str):
    """Run tasks with full harness configuration"""
    console.print("\n[bold green]Running with FULL harness (after)[/bold green]\n")

    model_provider = _get_model(model)
    config = HarnessConfig.full_harness()

    runner = TaskRunner(model_provider, Path(output_dir))
    results = runner.run_all_tasks(config, "full_harness")

    _print_results(results, "Full Harness")


@main.command()
@click.option("--model", default="mock", help=MODEL_HELP)
@click.option("--output-dir", default="./results", help="Output directory for results")
def ablate(model: str, output_dir: str):
    """Run ablation study: add layers one at a time"""
    console.print("\n[bold magenta]Running ablation study[/bold magenta]")
    console.print("This will run all tasks 7 times, adding one layer each time.\n")

    model_provider = _get_model(model)

    ablation = AblationRunner(model_provider, Path(output_dir))
    results = ablation.run_ablation()

    console.print("\n[bold green]Ablation complete![/bold green]\n")

    _print_ablation_summary(results)
    comparison = compare_before_after(results)
    _print_before_after(comparison)
    if results.get("task_layer_matrix"):
        _print_matrix(results["task_layer_matrix"])


@main.command("list-tasks")
def list_tasks():
    """List all available tasks"""
    console.print("\n[bold]Available Tasks:[/bold]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Description")
    table.add_column("Failure Modes", style="yellow")

    for task in get_all_tasks():
        table.add_row(
            task.task_id,
            task.description,
            ", ".join(task.failure_modes),
        )

    console.print(table)
    console.print()


@main.command("models")
@click.option(
    "--provider",
    type=click.Choice(["gemini", "openai", "anthropic", "mock"], case_sensitive=False),
    default="gemini",
    help="Provider to list models for",
)
def models_cmd(provider: str):
    """List available models for a provider (Gemini fetches live IDs)."""
    provider = provider.lower()

    if provider == "mock":
        console.print("mock  (offline deterministic policy model)")
        return

    if provider == "openai":
        console.print("Common OpenAI models: gpt-4o-mini, gpt-4o, gpt-4.1-mini")
        console.print("Pass via --model openai:<id> (requires OPENAI_API_KEY)")
        return

    if provider == "anthropic":
        console.print(
            "Common Anthropic models: claude-3-5-sonnet-20241022, claude-3-5-haiku-latest"
        )
        console.print("Pass via --model anthropic:<id> (requires ANTHROPIC_API_KEY)")
        return

    # gemini
    try:
        models = list_gemini_models()
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        console.print(
            f"Default Gemini model id (offline fallback): [cyan]{DEFAULT_GEMINI_MODEL}[/cyan]"
        )
        console.print(
            "Set GEMINI_API_KEY to list live models. "
            f"Override default with HARNESSDIFF_GEMINI_MODEL or --model gemini:<id>."
        )
        sys.exit(0)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    table = Table(show_header=True, title="Gemini models")
    table.add_column("ID", style="cyan")
    table.add_column("Display Name")
    table.add_column("Generate?", justify="center")

    default = os.getenv("HARNESSDIFF_GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    for m in models:
        generate = "yes" if "generateContent" in (m.get("supported_methods") or []) else ""
        label = m["id"]
        if m["id"] == default:
            label = f"{m['id']}  (default)"
        table.add_row(label, m.get("display_name", ""), generate)

    console.print(table)
    console.print(
        f"\nUse with: [bold]harnessdiff ablate --model gemini:{default}[/bold]"
    )
    console.print(
        "Env: GEMINI_API_KEY required; HARNESSDIFF_GEMINI_MODEL overrides default id.\n"
    )


def _get_model(model_name: str):
    """Get model provider from CLI --model flag."""
    try:
        return create_model(model_name)
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)
    except ImportError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)


def _print_results(results, title):
    """Print task results table"""
    console.print(f"\n[bold]{title} Results:[/bold]\n")

    check = safe_checkmark()
    cross = safe_cross()

    table = Table(show_header=True)
    table.add_column("Task")
    table.add_column("Real Success", style="green")
    table.add_column("Agent Claimed", style="yellow")
    table.add_column("False Claim", style="red")
    table.add_column("Steps")

    for task in results:
        table.add_row(
            task["task_id"],
            check if task["real_success"] else cross,
            check if task["agent_claimed_success"] else cross,
            check if task["false_claim_made"] else "",
            str(task["steps"]),
        )

    console.print(table)
    console.print()


def _print_ablation_summary(results):
    """Print ablation summary table"""
    console.print("[bold]Ablation Summary:[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Configuration")
    table.add_column("Success Rate", justify="right")
    table.add_column("False Claims Made", justify="right")
    table.add_column("False Claims Caught", justify="right")
    table.add_column("Unsafe Executed", justify="right")
    table.add_column("Unsafe Blocked", justify="right")

    for run in results["runs"]:
        run_id = run["run_id"]
        summary = results["summary"][run_id]

        success_rate = f"{summary['real_success_rate']:.1%}"
        false_made = str(summary["false_claims_made"])
        false_caught = str(summary["false_claims_caught"])
        unsafe_executed = str(summary.get("unsafe_executed", 0))
        unsafe_blocked = str(summary["unsafe_blocked"])

        if run_id == "baseline":
            name = "Baseline (no harness)"
        elif run_id.startswith("layer_"):
            layer = run["layer_added"].replace("_", " ").title()
            name = f"+ {layer}"
        else:
            name = run_id

        table.add_row(
            name, success_rate, false_made, false_caught, unsafe_executed, unsafe_blocked
        )

    console.print(table)
    console.print()


def _print_matrix(matrix):
    """Print task x layer success matrix"""
    console.print("[bold]Task × Layer Matrix:[/bold]\n")

    if not matrix:
        return

    run_ids = list(next(iter(matrix.values())).keys())
    check = safe_checkmark()
    cross = safe_cross()

    table = Table(show_header=True)
    table.add_column("Task", style="cyan")
    for run_id in run_ids:
        label = "base" if run_id == "baseline" else run_id.replace("layer_", "")[:6]
        table.add_column(label, justify="center")

    for task_id, row in matrix.items():
        cells = [check if row.get(r) else cross for r in run_ids]
        table.add_row(task_id, *cells)

    console.print(table)
    console.print()


def _print_before_after(comparison):
    """Print before/after comparison"""
    console.print("[bold]Before vs After:[/bold]\n")

    check = safe_checkmark()

    before = comparison["before"]
    after = comparison["after"]
    improvement = comparison["improvement"]

    table = Table(show_header=True)
    table.add_column("Metric")
    table.add_column("Before", justify="right", style="red")
    table.add_column("After", justify="right", style="green")
    table.add_column("Change", justify="right", style="cyan")

    delta = improvement["success_delta"]
    table.add_row(
        "Real Success Rate",
        f"{before['real_success_rate']:.1%}",
        f"{after['real_success_rate']:.1%}",
        f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}",
    )

    reduced = improvement["false_claims_reduced"]
    table.add_row(
        "False Claims Made",
        str(before["false_claims_made"]),
        str(after["false_claims_made"]),
        f"-{reduced}" if reduced > 0 else "0",
    )

    table.add_row(
        "Unsafe Actions",
        f"{before.get('unsafe_executed', 0)} executed",
        f"{after['unsafe_blocked']} blocked",
        f"{check} Protected",
    )

    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
