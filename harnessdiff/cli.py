"""
Command-line interface for HarnessDiff.
"""

import os
import sys
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table

from harnessdiff.models import MockModel, OpenAIModel, AnthropicModel
from harnessdiff.config import HarnessConfig
from harnessdiff.runner import TaskRunner, AblationRunner, compare_before_after
from tasks import get_all_tasks

console = Console()


@click.group()
def main():
    """
    HarnessDiff: Show exactly what each agent harness layer fixes.
    
    Run agent tasks with different harness configurations and see the impact.
    """
    pass


@main.command()
@click.option("--model", default="mock", help="Model to use: mock, openai, anthropic")
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
@click.option("--model", default="mock", help="Model to use: mock, openai, anthropic")
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
@click.option("--model", default="mock", help="Model to use: mock, openai, anthropic")
@click.option("--output-dir", default="./results", help="Output directory for results")
def ablate(model: str, output_dir: str):
    """Run ablation study: add layers one at a time"""
    console.print("\n[bold magenta]Running ablation study[/bold magenta]")
    console.print("This will run all tasks 7 times, adding one layer each time.\n")
    
    model_provider = _get_model(model)
    
    ablation = AblationRunner(model_provider, Path(output_dir))
    results = ablation.run_ablation()
    
    console.print("\n[bold green]Ablation complete![/bold green]\n")
    
    # Print summary
    _print_ablation_summary(results)
    
    # Print before/after comparison
    comparison = compare_before_after(results)
    _print_before_after(comparison)


@main.command()
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
            ", ".join(task.failure_modes)
        )
    
    console.print(table)
    console.print()


def _get_model(model_name: str):
    """Get model provider"""
    if model_name == "mock":
        return MockModel()
    elif model_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
            sys.exit(1)
        return OpenAIModel(api_key=api_key)
    elif model_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
            sys.exit(1)
        return AnthropicModel(api_key=api_key)
    else:
        console.print(f"[red]Error: Unknown model: {model_name}[/red]")
        sys.exit(1)


def _print_results(results, title):
    """Print task results table"""
    console.print(f"\n[bold]{title} Results:[/bold]\n")
    
    table = Table(show_header=True)
    table.add_column("Task")
    table.add_column("Real Success", style="green")
    table.add_column("Agent Claimed", style="yellow")
    table.add_column("False Claim", style="red")
    table.add_column("Steps")
    
    for task in results:
        table.add_row(
            task["task_id"],
            "✓" if task["real_success"] else "✗",
            "✓" if task["agent_claimed_success"] else "✗",
            "✓" if task["false_claim_made"] else "",
            str(task["steps"])
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
    table.add_column("Unsafe Blocked", justify="right")
    
    for run in results["runs"]:
        run_id = run["run_id"]
        summary = results["summary"][run_id]
        
        success_rate = f"{summary['real_success_rate']:.1%}"
        false_made = str(summary['false_claims_made'])
        false_caught = str(summary['false_claims_caught'])
        unsafe_blocked = str(summary['unsafe_blocked'])
        
        # Format run name
        if run_id == "baseline":
            name = "Baseline (no harness)"
        elif run_id.startswith("layer_"):
            layer = run["layer_added"].replace("_", " ").title()
            name = f"+ {layer}"
        else:
            name = run_id
        
        table.add_row(name, success_rate, false_made, false_caught, unsafe_blocked)
    
    console.print(table)
    console.print()


def _print_before_after(comparison):
    """Print before/after comparison"""
    console.print("[bold]Before vs After:[/bold]\n")
    
    before = comparison["before"]
    after = comparison["after"]
    improvement = comparison["improvement"]
    
    table = Table(show_header=True)
    table.add_column("Metric")
    table.add_column("Before", justify="right", style="red")
    table.add_column("After", justify="right", style="green")
    table.add_column("Change", justify="right", style="cyan")
    
    table.add_row(
        "Real Success Rate",
        f"{before['real_success_rate']:.1%}",
        f"{after['real_success_rate']:.1%}",
        f"+{improvement['success_delta']:.1%}" if improvement['success_delta'] > 0 else f"{improvement['success_delta']:.1%}"
    )
    
    table.add_row(
        "False Claims Made",
        str(before['false_claims_made']),
        str(after['false_claims_made']),
        f"-{improvement['false_claims_reduced']}" if improvement['false_claims_reduced'] > 0 else "0"
    )
    
    table.add_row(
        "Unsafe Actions",
        f"{before['unsafe_attempts']} attempted",
        f"{after['unsafe_blocked']} blocked",
        "✓ Protected"
    )
    
    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
