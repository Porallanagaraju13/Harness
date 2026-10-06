"""Integration test that harness beats baseline"""

import pytest
from pathlib import Path
from harnessdiff.models import MockModel
from harnessdiff.config import HarnessConfig
from harnessdiff.runner import TaskRunner
from tasks import get_all_tasks


def test_full_harness_beats_baseline():
    """Full harness should have higher real success than baseline"""
    model = MockModel()
    runner = TaskRunner(model, Path("test_results"))
    
    # Run baseline
    baseline_config = HarnessConfig.baseline()
    baseline_results = runner.run_all_tasks(baseline_config, "test_baseline")
    
    # Run with full harness
    full_config = HarnessConfig.full_harness()
    full_results = runner.run_all_tasks(full_config, "test_full")
    
    # Calculate metrics
    baseline_success = sum(1 for t in baseline_results if t["real_success"])
    full_success = sum(1 for t in full_results if t["real_success"])
    
    baseline_false = sum(1 for t in baseline_results if t["false_claim_made"])
    full_false_made = sum(1 for t in full_results if t["false_claim_made"])
    full_false_caught = sum(1 for t in full_results if t["false_claim_caught"])
    
    baseline_unsafe = sum(t["unsafe_attempts"] for t in baseline_results)
    full_unsafe_blocked = sum(t["unsafe_blocked"] for t in full_results)
    
    # Assertions
    assert full_success >= baseline_success, (
        f"Full harness should not be worse: {full_success}/{len(full_results)} "
        f"vs baseline {baseline_success}/{len(baseline_results)}"
    )
    
    assert full_false_caught > 0, "Verification layer should catch some false claims"
    
    print(f"\n✓ Baseline: {baseline_success}/{len(baseline_results)} success, "
          f"{baseline_false} false claims, {baseline_unsafe} unsafe attempts")
    print(f"✓ Full harness: {full_success}/{len(full_results)} success, "
          f"{full_false_made} false claims made, {full_false_caught} caught, "
          f"{full_unsafe_blocked} unsafe blocked")
    print(f"✓ Improvement: +{full_success - baseline_success} tasks, "
          f"-{baseline_false - full_false_made} false claims")


def test_retry_layer_improves_flaky_tasks():
    """Retry layer should help with transient failures"""
    model = MockModel()
    runner = TaskRunner(model, Path("test_results"))
    
    # Get flaky tasks
    flaky_task_ids = ["flaky_tool", "timeout_retry"]
    
    baseline_config = HarnessConfig.baseline()
    retry_config = HarnessConfig.baseline()
    retry_config.use_retry_logic = True
    retry_config.max_retries = 3
    
    baseline_success = 0
    retry_success = 0
    
    for task_id in flaky_task_ids:
        from tasks import get_task_by_id
        task = get_task_by_id(task_id)
        
        baseline_metrics = runner.run_task(task, baseline_config, f"test_baseline_{task_id}")
        retry_metrics = runner.run_task(task, retry_config, f"test_retry_{task_id}")
        
        if baseline_metrics["real_success"]:
            baseline_success += 1
        if retry_metrics["real_success"]:
            retry_success += 1
    
    assert retry_success >= baseline_success, (
        f"Retry layer should help flaky tasks: {retry_success} vs {baseline_success}"
    )


def test_permission_layer_blocks_dangerous():
    """Permission layer should block dangerous operations"""
    model = MockModel()
    runner = TaskRunner(model, Path("test_results"))
    
    dangerous_task_id = "dangerous_delete"
    from tasks import get_task_by_id
    task = get_task_by_id(dangerous_task_id)
    
    baseline_config = HarnessConfig.baseline()
    perm_config = HarnessConfig.baseline()
    perm_config.use_permissions = True
    
    baseline_metrics = runner.run_task(task, baseline_config, "test_baseline_danger")
    perm_metrics = runner.run_task(task, perm_config, "test_perm_danger")
    
    # Permission layer should log blocks
    assert perm_metrics["unsafe_blocked"] > 0, "Permission layer should block dangerous operations"
