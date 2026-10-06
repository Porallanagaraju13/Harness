"""
Runner for executing tasks and measuring harness impact.
"""

import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from harnessdiff.agent_loop import AgentLoop
from harnessdiff.models import ModelProvider, MockModel, Message
from harnessdiff.config import HarnessConfig
from tasks import get_all_tasks, Task


class TaskRunner:
    """
    Runs tasks with different harness configurations.
    
    Tracks metrics to measure what each layer fixes.
    """
    
    def __init__(self, model: ModelProvider, output_dir: Path):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_task(
        self,
        task: Task,
        config: HarnessConfig,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Run a single task with given configuration.
        
        Returns metrics dict.
        """
        # Create temp work directory
        work_dir = tempfile.mkdtemp(prefix=f"harnessdiff_{task.task_id}_")
        work_path = Path(work_dir)
        
        try:
            # Setup task
            context = task.setup(work_path)
            
            # Configure trace file
            trace_file = self.output_dir / f"{run_id}_{task.task_id}_trace.jsonl"
            config.trace_file = trace_file
            
            # Also copy to web/public if it exists
            web_public = Path("web/public")
            if web_public.exists():
                web_trace = web_public / f"{run_id}_{task.task_id}_trace.jsonl"
                config.trace_file = trace_file  # Will be copied after run
            
            # Create agent
            agent = AgentLoop(
                model=self.model,
                tools=context["tools"],
                config=config,
                tool_schemas=context.get("tool_schemas", [])
            )
            
            # If verification layer is enabled, set verifier
            if config.use_verification and agent.verification_layer:
                agent.verification_layer.set_verifier(
                    lambda ctx: task.verify(ctx)
                )
            
            # Run agent
            trace = agent.run(task.prompt, task_id=task.task_id)
            
            # If verification is enabled and agent claimed done, check and provide feedback
            if config.use_verification and trace.result and trace.result.get("status") == "completed":
                # Run initial verification
                verification = task.verify(context)
                
                # If verification fails, provide feedback and allow fix attempts
                max_fix_attempts = 2
                fix_attempts = 0
                
                while not verification.get("success") and fix_attempts < max_fix_attempts:
                    fix_attempts += 1
                    
                    # Feed concrete failure back to agent
                    feedback_msg = Message(
                        role="user",
                        content=f"Verification failed: {verification.get('evidence', 'Task not complete')}. Please fix the issue."
                    )
                    agent.messages.append(feedback_msg)
                    
                    # Let agent try to fix
                    fix_trace = agent.run(f"Fix the issue: {verification.get('evidence')}", task_id=f"{task.task_id}_fix{fix_attempts}")
                    
                    # Re-verify
                    verification = task.verify(context)
                    
                    # Merge fix trace into main trace
                    if fix_trace.steps:
                        trace.steps.extend(fix_trace.steps)
                        if fix_trace.result:
                            trace.result["fix_attempts"] = fix_attempts
                            trace.result["steps"] = trace.result.get("steps", 0) + fix_trace.result.get("steps", 0)
                            trace.result["tool_calls"] = trace.result.get("tool_calls", 0) + fix_trace.result.get("tool_calls", 0)
                
                # Save updated trace
                if config.trace_file:
                    trace.save(config.trace_file)
            else:
                # No verification or didn't complete, just verify end state
                verification = task.verify(context)
            
            # Collect metrics
            metrics = self._collect_metrics(
                task=task,
                config=config,
                trace=trace,
                verification=verification,
                agent=agent
            )
            
            # Copy trace to web/public for dashboard
            web_public = Path("web/public")
            if web_public.exists() and trace_file.exists():
                web_trace = web_public / trace_file.name
                shutil.copy2(trace_file, web_trace)
            
            return metrics
        
        finally:
            # Cleanup
            if work_path.exists():
                shutil.rmtree(work_path, ignore_errors=True)
    
    def _collect_metrics(
        self,
        task: Task,
        config: HarnessConfig,
        trace: Any,
        verification: Dict[str, Any],
        agent: AgentLoop
    ) -> Dict[str, Any]:
        """Collect metrics from a run"""
        
        # Check if agent claimed success
        agent_claimed_success = False
        if trace.result and "final_message" in trace.result:
            final_msg = trace.result["final_message"].lower()
            success_words = ["complete", "success", "done", "finished", "successfully"]
            agent_claimed_success = any(word in final_msg for word in success_words)
        
        # Real success from verification
        real_success = verification.get("success", False)
        
        # False claim made: agent said success but verification failed
        false_claim_made = agent_claimed_success and not real_success
        
        # False claim caught: verification layer would catch this
        false_claim_caught = false_claim_made and config.use_verification
        
        # Collect permission layer metrics
        unsafe_attempts = 0
        unsafe_blocked = 0
        unsafe_executed = 0
        
        if hasattr(agent, '_permission_layer') and agent._permission_layer is not None:
            audit_log = agent._permission_layer.get_audit_log()
            unsafe_attempts = len([e for e in audit_log if "denied" in e.get("decision", "") or "approved" in e.get("decision", "")])
            unsafe_blocked = len([e for e in audit_log if e.get("decision") == "denied"])
        else:
            # Without permission layer, check if task has dangerous operations in failure modes
            if any(mode in ["permissions", "dangerous"] for mode in task.failure_modes):
                # At baseline, dangerous actions are attempted and executed
                unsafe_executed = 1  # One dangerous action per dangerous task at baseline
        
        # Check for duplicate side effects from verification details
        duplicate_side_effects = 0
        if "count" in verification.get("details", {}) and verification["details"]["count"] > 1:
            duplicate_side_effects = verification["details"]["count"] - 1
        
        # Tool calls attempted
        tool_calls = trace.result.get("tool_calls", 0) if trace.result else 0
        
        # Build metrics
        metrics = {
            "task_id": task.task_id,
            "task_description": task.description,
            "config": config.to_dict(),
            "timestamp": datetime.now().isoformat(),
            
            # Success metrics
            "real_success": real_success,
            "agent_claimed_success": agent_claimed_success,
            "false_claim_made": false_claim_made,
            "false_claim_caught": false_claim_caught,
            
            # Verification details
            "verification": verification,
            
            # Execution metrics
            "steps": trace.result.get("steps", 0) if trace.result else 0,
            "tool_calls": tool_calls,
            "status": trace.result.get("status", "unknown") if trace.result else "unknown",
            
            # Safety metrics
            "unsafe_attempts": unsafe_attempts,
            "unsafe_blocked": unsafe_blocked,
            "unsafe_executed": unsafe_executed,
            "duplicate_side_effects": duplicate_side_effects,
            
            # Failure modes triggered
            "failure_modes": task.failure_modes,
        }
        
        return metrics
    
    def run_all_tasks(self, config: HarnessConfig, run_id: str) -> List[Dict[str, Any]]:
        """Run all tasks with given configuration"""
        results = []
        
        for task in get_all_tasks():
            print(f"  Running {task.task_id}...")
            metrics = self.run_task(task, config, run_id)
            results.append(metrics)
        
        return results


class AblationRunner:
    """
    Runs ablation study: adds layers one at a time.
    
    Measures incremental impact of each layer.
    """
    
    def __init__(self, model: ModelProvider, output_dir: Path):
        self.runner = TaskRunner(model, output_dir)
        self.output_dir = Path(output_dir)
    
    def run_ablation(self) -> Dict[str, Any]:
        """
        Run complete ablation study.
        
        Returns results dict with metrics for each configuration.
        """
        print("Starting ablation study...")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "runs": []
        }
        
        # Baseline: no harness
        print("\n[1/7] Running baseline (no harness)...")
        baseline_config = HarnessConfig.baseline()
        baseline_metrics = self.runner.run_all_tasks(baseline_config, "baseline")
        results["runs"].append({
            "run_id": "baseline",
            "config": baseline_config.to_dict(),
            "tasks": baseline_metrics
        })
        
        # Add layers incrementally
        layers = [
            ("tool_design", "Tool Design"),
            ("context", "Context Management"),
            ("sandbox", "Sandbox"),
            ("permissions", "Permissions"),
            ("retry", "Retry Logic"),
            ("verification", "Verification"),
        ]
        
        cumulative_config = HarnessConfig.baseline()
        
        for i, (layer_name, layer_display) in enumerate(layers, start=2):
            print(f"\n[{i}/7] Adding {layer_display} layer...")
            
            cumulative_config = cumulative_config.enable_layer(layer_name)
            run_id = f"layer_{layer_name}"
            
            layer_metrics = self.runner.run_all_tasks(cumulative_config, run_id)
            results["runs"].append({
                "run_id": run_id,
                "layer_added": layer_name,
                "config": cumulative_config.to_dict(),
                "tasks": layer_metrics
            })
        
        # Aggregate results
        results["summary"] = self._aggregate_results(results["runs"])
        
        # Save results
        results_file = self.output_dir / "ablation_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to {results_file}")
        
        return results
    
    def _aggregate_results(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate metrics across runs"""
        summary = {}
        
        for run in runs:
            run_id = run["run_id"]
            tasks = run["tasks"]
            
            total_tasks = len(tasks)
            real_success = sum(1 for t in tasks if t["real_success"])
            false_claims_made = sum(1 for t in tasks if t["false_claim_made"])
            false_claims_caught = sum(1 for t in tasks if t["false_claim_caught"])
            unsafe_attempts = sum(t["unsafe_attempts"] for t in tasks)
            unsafe_blocked = sum(t["unsafe_blocked"] for t in tasks)
            unsafe_executed = sum(t.get("unsafe_executed", 0) for t in tasks)
            duplicate_effects = sum(t["duplicate_side_effects"] for t in tasks)
            
            summary[run_id] = {
                "total_tasks": total_tasks,
                "real_success_count": real_success,
                "real_success_rate": real_success / total_tasks if total_tasks > 0 else 0,
                "false_claims_made": false_claims_made,
                "false_claims_caught": false_claims_caught,
                "unsafe_attempts": unsafe_attempts,
                "unsafe_blocked": unsafe_blocked,
                "unsafe_executed": unsafe_executed,
                "duplicate_side_effects": duplicate_effects,
            }
        
        return summary


def compare_before_after(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare baseline vs full harness.
    
    Returns before/after comparison for README.
    """
    summary = results["summary"]
    
    baseline = summary.get("baseline", {})
    final_run = list(summary.values())[-1]  # Last run has all layers
    
    comparison = {
        "before": {
            "real_success_rate": baseline.get("real_success_rate", 0),
            "false_claims_made": baseline.get("false_claims_made", 0),
            "unsafe_attempts": baseline.get("unsafe_attempts", 0),
            "unsafe_executed": baseline.get("unsafe_executed", 0),
        },
        "after": {
            "real_success_rate": final_run.get("real_success_rate", 0),
            "false_claims_made": final_run.get("false_claims_made", 0),
            "false_claims_caught": final_run.get("false_claims_caught", 0),
            "unsafe_blocked": final_run.get("unsafe_blocked", 0),
        },
        "improvement": {
            "success_delta": final_run.get("real_success_rate", 0) - baseline.get("real_success_rate", 0),
            "false_claims_reduced": baseline.get("false_claims_made", 0) - final_run.get("false_claims_made", 0),
        }
    }
    
    return comparison
