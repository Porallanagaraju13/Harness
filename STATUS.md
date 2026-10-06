# HarnessDiff Status Report

## Current State

### ✅ What's Working

1. **Infrastructure Complete**
   - Core agent loop with JSONL traces ✓
   - 6 harness layers (tool design, context, sandbox, permissions, retry, verification) ✓
   - 11 tasks with real verification ✓
   - CLI (`harnessdiff run/after/ablate/list-tasks`) ✓
   - Metrics collection and aggregation ✓
   - 24 passing tests ✓

2. **Task Suite Expanded to 11 Tasks**
   - file_creation
   - flaky_tool
   - dangerous_delete
   - overlapping_tools
   - duplicate_side_effect
   - timeout_retry
   - oversized_output
   - misleading_tools
   - destructive_command
   - multi_step_verify
   - context_overflow

3. **Metrics Tracking**
   - Real success vs agent claims
   - False claims made vs caught (separated)
   - Unsafe attempts vs blocked
   - Duplicate side effects

### ⚠️ Known Issues

1. **Mock Model Behavior**
   - The mock model calls tools but doesn't consistently exhibit the right failure modes
   - Some tasks succeed when they should fail (e.g., dangerous operations complete)
   - The model needs better logic to reliably fail without harness and succeed with it

2. **Layer Impact**
   - Adding layers currently makes results WORSE instead of better
   - Tool design layer removes necessary tools
   - Layers add overhead without fixing the targeted problems
   - Need to ensure each layer genuinely improves behavior through real code paths

3. **Permission Layer**
   - Not blocking dangerous operations (showing 0 blocked everywhere)
   - Audit log not being populated correctly
   - Need to ensure dangerous tools actually attempt risky operations

### 📊 Actual Run Results (Current)

From latest `harnessdiff run`:

| Task | Real Success | Agent Claimed | False Claim |
|------|--------------|---------------|-------------|
| file_creation | ✓ | ✓ | |
| flaky_tool | ✗ | ✓ | ✓ |
| dangerous_delete | ✓ | ✓ | |
| overlapping_tools | ✗ | ✓ | ✓ |
| duplicate_side_effect | ✗ | ✗ | |
| timeout_retry | ✗ | ✓ | ✓ |
| oversized_output | ✓ | ✓ | |
| misleading_tools | ✗ | ✓ | ✓ |
| destructive_command | ✓ | ✓ | |
| multi_step_verify | ✗ | ✓ | ✓ |
| context_overflow | ✓ | ✓ | |

**Baseline**: 5/11 success (45%), 5 false claims  
**Full Harness**: 4/11 success (36%), 6 false claims made, 6 caught

**Problem**: Full harness is WORSE than baseline, not better.

## Installation & Commands (Windows PowerShell)

### Install
```powershell
pip install -e .
```

### Run Tasks
```powershell
# Baseline (no harness)
harnessdiff run --output-dir results

# Full harness
harnessdiff after --output-dir results

# Full ablation (7 runs)
harnessdiff ablate --output-dir results

# List tasks
harnessdiff list-tasks
```

### Run Tests
```powershell
pytest
# Currently: 24/24 passing
```

### Web Dashboard
```powershell
cd web
npm install
npm run build

# Serve static export
npx serve out
# Or open web/out/index.html directly
```

## What Needs to Be Fixed

### Priority 1: Make Harness Actually Help

1. **Fix Mock Model**
   - Ensure it reliably attempts dangerous operations (so permissions can block them)
   - Ensure it gives up on first retry failure (so retry layer helps)
   - Ensure it picks wrong overlapping tool (so tool design helps)
   - Currently too smart in some areas, too dumb in others

2. **Fix Layer Logic**
   - Tool design: Should IMPROVE tool selection, not break it
   - Retry: Should catch transient failures and succeed
   - Permissions: Should block dangerous operations (show non-zero blocked count)
   - Verification: Should catch false claims and trigger fixes

3. **Verification Integration**
   - When verification catches a false claim, agent should retry with fix
   - Currently just marks it as "caught" but doesn't improve the outcome

### Priority 2: Dashboard Updates

1. **Static Export Instructions**
   - Update README/QUICKSTART with correct `npx serve out` command
   - Remove references to `npm start` for static exports

2. **Side-by-Side Trace Viewer**
   - Not yet implemented
   - Would show baseline vs harnessed run for same task
   - Highlight where bare agent went wrong
   - Label which layer caught it

### Priority 3: Tests

Add integration tests that assert:
```python
def test_harness_beats_baseline():
    baseline_success = run_baseline()
    full_success = run_full_harness()
    assert full_success > baseline_success

def test_layers_improve_metrics():
    baseline = run_baseline()
    with_retry = run_with_retry_layer()
    assert with_retry["retry_success"] > baseline["retry_success"]
```

## Root Cause Analysis

The core issue is that the **mock model and harness layers need to be co-designed**:

1. Mock model must exhibit specific failures
2. Each layer must detect and fix its target failure
3. Layers must not interfere with each other

Currently:
- Mock model isn't reliably broken in the right ways
- Layers add complexity without targeted fixes
- No integration between verification layer catching issues and retry logic

## Recommended Next Steps

1. **Simplify mock model** to have 3 clear modes:
   - `dangerous_mode`: Always attempts risky operations
   - `flaky_mode`: Fails first N attempts, succeeds after
   - `wrong_tool_mode`: Picks wrong tool from overlaps

2. **Fix tool design layer** to only remove duplicates, not break existing tools

3. **Wire verification layer** to trigger retry when it catches false claim

4. **Add focused integration test** for each layer showing it helps its target failure mode

5. **Document remaining gaps** clearly in README

## File Locations

- Core: `harnessdiff/` (agent_loop.py, models.py, config.py, runner.py, cli.py)
- Layers: `harnessdiff/layers/` (6 files)
- Tasks: `tasks/basic_tasks.py` (11 tasks)
- Tests: `tests/` (24 tests, all passing)
- Web: `web/` (Next.js dashboard)
- Results: `results/ablation_results.json`

## Git Status

```
On branch main
3 commits ahead of origin/main
Working tree has uncommitted test file
```

Latest commit: "Fix mock model and expand task suite to 11 tasks"

---

**Bottom line**: The infrastructure is solid, but the mock model and layer integration need debugging to show the harness actually helps. The current results show the opposite due to implementation bugs, not conceptual issues with the approach.
