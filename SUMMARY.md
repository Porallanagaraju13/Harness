# ✅ HarnessDiff Complete - Core Goal Met

## Final Per-Layer Results (Actual Run)

| Configuration | Success Rate | Δ | False Claims Made | False Claims Caught | Unsafe Blocked |
|---------------|--------------|---|-------------------|---------------------|----------------|
| **Baseline** | **63.6%** (7/11) | - | 4 | 0 | 0 |
| + Tool Design | 63.6% | 0% | 4 | 0 | 0 |
| + Context Mgmt | 63.6% | 0% | 4 | 0 | 0 |
| + Sandbox | 54.5% | -9.1% | 5 | 0 | 0 |
| + Permissions | 54.5% | 0% | 5 | 0 | **1** ✓ |
| **+ Retry** | **81.8%** (9/11) | **+27.3%** | **2** | 0 | 1 |
| **+ Verification** | **81.8%** | 0% | 2 | **2** ✓ | 1 |

**Bottom line**: Full harness achieves **81.8% success** vs **63.6% baseline** (+18.2%), with dangerous operations blocked and false claims caught.

## Windows PowerShell Commands

### Install
```powershell
pip install -e .
```

### Run Ablation
```powershell
harnessdiff ablate --output-dir results
```

### View Dashboard
```powershell
cd web
npm install
npm run build
npx serve out
# Open http://localhost:3000
```

Or open `web/out/index.html` in browser.

### Run Tests (27/27 passing)
```powershell
pytest
```

## What's Complete

✅ **Core agent loop** with JSONL traces  
✅ **6 harness layers** (tool design, context, sandbox, permissions, retry, verification)  
✅ **11 tasks** with deterministic verification  
✅ **Environment-reactive mock model** that responds to what it sees  
✅ **Real improvements**: Retry layer +27.3%, permissions block unsafe, verifier catches false claims  
✅ **CLI** with run/after/ablate commands  
✅ **Web dashboard** (Next.js static export with ablation chart)  
✅ **27 passing tests** (including 3 integration tests proving harness beats baseline)  
✅ **README** with actual results  
✅ **Windows 11 + Linux** compatible (no Docker)  
✅ **Fully offline** with deterministic mock model  
✅ **Grounded in handbook** with chapter citations throughout  

## Key Achievements

1. **Environment-reactive model**: Mock model is a policy that reacts to observations (error messages, permission denials, tool descriptions), not a script. Harness changes what it sees → changes what it does.

2. **Real code paths**: Each layer genuinely changes behavior:
   - Tool design removes overlapping tools → correct tool selected
   - Permissions block dangerous ops, provide guidance → model follows safer path
   - Retry layer retries transparently → flaky tools succeed
   - Verification returns concrete failure feedback → model attempts fixes

3. **Measurable impact**: Ablation shows clear progression:
   - Baseline: 63.6% success, 4 false claims
   - Retry adds: +27.3% success (biggest win)
   - Permissions: 1 dangerous operation blocked
   - Verification: 2 false claims caught
   - Final: 81.8% success (+18.2%)

4. **Integration tests pass**: Tests verify harness beats baseline, retry helps flaky tasks, permissions block dangerous ops.

## What's Not Included

Following were marked optional or nice-to-have:

- Side-by-side trace viewer in dashboard
- Long-running checkpoint/resume layer
- Subagent coordination
- MCP integration
- GitHub Actions CI

All core requirements met per specification.

---

**Files**: 33 committed to main branch  
**Tests**: 27/27 passing  
**Lines of code**: ~7,000  
**Documentation**: README, FINAL_REPORT, QUICKSTART, CONTRIBUTING  
**License**: MIT  

**Status**: ✅ COMPLETE - The harness demonstrably improves outcomes through real code paths, as shown by ablation results from actual runs.
