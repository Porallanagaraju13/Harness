# HarnessDiff - Quick Start

## What You Have

A complete, working agent harness laboratory that demonstrates what each harness layer fixes. Built from scratch, grounded in "Understanding Harness Engineering" by @techNmak.

## Installation (Windows PowerShell)

```powershell
# 1. Install Python package
pip install -e .

# 2. Install web dashboard dependencies (optional)
cd web
npm install
cd ..
```

## Run the Lab

```powershell
# Run full ablation study (adds layers one at a time)
harnessdiff ablate

# Output: results/ablation_results.json
```

This runs all 5 tasks 7 times (baseline + 6 layers), measuring:
- Real success rate (verified end state)
- False claims (agent says done but verification fails)
- Unsafe actions (blocked by permissions)
- Duplicate side effects (prevented by idempotency)

## View Results

### Console Output
The ablation command prints a table showing layer-by-layer impact.

### Web Dashboard

```powershell
cd web
npm run build
npm start
# Open http://localhost:3000
```

Shows:
- Ablation chart (success rate per configuration)
- Before/after comparison cards
- Task detail viewer with verification evidence

## Run Tests

```powershell
pytest
```

**24 tests, all passing** ✅

## Quick Commands

```powershell
# List available tasks
harnessdiff list-tasks

# Run baseline (no harness)
harnessdiff run --model mock

# Run with full harness
harnessdiff after --model mock

# Full ablation study
harnessdiff ablate --model mock --output-dir results
```

## Optional: Use Real LLMs

```powershell
# OpenAI
$env:OPENAI_API_KEY = "sk-..."
harnessdiff ablate --model openai

# Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
harnessdiff ablate --model anthropic
```

Default is `--model mock` (deterministic, offline, no API key needed).

## Project Structure

```
harnessdiff/
├── harnessdiff/           # Core Python package
│   ├── agent_loop.py      # Main loop
│   ├── models.py          # Mock + LLM providers
│   ├── config.py          # Harness configuration
│   ├── runner.py          # Task execution
│   ├── cli.py             # Command-line interface
│   └── layers/            # 6 harness layers
├── tasks/                 # 5 tasks with verifiers
├── tests/                 # 24 tests (all passing)
├── web/                   # Next.js dashboard
├── results/               # Generated results
├── README.md              # Full documentation
├── FINAL_REPORT.md        # Implementation report
└── QUICKSTART.md          # This file
```

## The 6 Harness Layers

Each can be independently enabled/disabled:

1. **Tool Design** - Remove overlapping tools, improve descriptions
2. **Context Management** - Select relevant history, compact when needed
3. **Sandbox** - Isolate execution in temp directory (no Docker)
4. **Permissions** - Block dangerous operations, audit log
5. **Retry Logic** - Retry failures, track idempotency
6. **Verification** - Independent end-state checks

## The 5 Tasks

| Task | What It Tests |
|------|---------------|
| `file_creation` | Verification failure (claims done without checking) |
| `flaky_tool` | Retry logic (gives up vs. persists) |
| `dangerous_delete` | Permission blocking (protects important data) |
| `overlapping_tools` | Tool selection (5 similar tools, picks wrong one) |
| `duplicate_side_effect` | Idempotency (retry creates duplicate) |

## Extending

See `CONTRIBUTING.md` for:
- Adding new tasks
- Adding harness layers
- Adding model providers

## Documentation

- **README.md** - Full documentation with architecture
- **FINAL_REPORT.md** - Implementation report with results
- **CONTRIBUTING.md** - Extension guide
- **LICENSE** - MIT

## Support

- Run `harnessdiff --help` for CLI options
- Check `tests/` for usage examples
- See handbook chapters cited in code comments

---

**Built from scratch. No external dependencies. Fully offline-capable.**

Based on "Understanding Harness Engineering" by @techNmak.
