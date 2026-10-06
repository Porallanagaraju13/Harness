#!/usr/bin/env python3
"""Quick test to verify harness layers have impact"""

from harnessdiff.models import MockModel
from harnessdiff.config import HarnessConfig
from harnessdiff.runner import TaskRunner
from pathlib import Path
from tasks import get_all_tasks

# Run baseline
print("Testing baseline vs full harness...")
model = MockModel()
runner = TaskRunner(model, Path("test_results"))

baseline_config = HarnessConfig.baseline()
baseline_results = runner.run_all_tasks(baseline_config, "test_baseline")

full_config = HarnessConfig.full_harness()
full_results = runner.run_all_tasks(full_config, "test_full")

# Compare
baseline_success = sum(1 for t in baseline_results if t["real_success"])
full_success = sum(1 for t in full_results if t["real_success"])

baseline_false = sum(1 for t in baseline_results if t["false_claim_made"])
full_false_made = sum(1 for t in full_results if t["false_claim_made"])
full_false_caught = sum(1 for t in full_results if t["false_claim_caught"])

print(f"\nBaseline: {baseline_success}/{len(baseline_results)} success, {baseline_false} false claims")
print(f"Full harness: {full_success}/{len(full_results)} success, {full_false_made} false claims made, {full_false_caught} caught")

assert full_success >= baseline_success, f"Full harness should not be worse: {full_success} vs {baseline_success}"
assert full_false_caught > 0, "Verification layer should catch false claims"
print("\n✓ Harness shows measurable impact")
