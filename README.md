# HarnessDiff

**See exactly what each agent harness layer fixes**

A hands-on testing lab demonstrating the impact of agent harness engineering. Based on the handbook *"Understanding Harness Engineering"* by @techNmak.

## What is this?

HarnessDiff runs agent tasks **twice**:
- **Before**: Bare agent with no harness layers (baseline)
- **After**: Full harness with all 6 layers enabled

Then it runs an **ablation study** adding one layer at a time to measure incremental impact.

## The 6 Harness Layers

1. **Tool Design** - Filters overlapping tools, enriches descriptions
2. **Context Management** - Compacts context to preserve goals
3. **Sandbox** - Blocks out-of-workspace file operations
4. **Permissions** - Blocks dangerous commands, provides safer alternatives
5. **Retry + Idempotency** - Retries flaky tools, prevents duplicate side effects
6. **Verification** - Catches false completion claims, feeds back concrete failures

## Quick Start

### Installation

```bash
# Clone or extract the repository
cd harnessdiff

# Install dependencies
pip install -e .

# Or with uv (recommended)
uv pip install -e .
```

### Run Ablation Study

```bash
# Run all tasks through ablation
python3 harnessdiff/cli.py ablate

# View results
cat results/ablation_results.json
```

### View Dashboard

```bash
# Copy results to web dashboard
cp results/ablation_results.json web/public/
cp results/*.jsonl web/public/

# Build and serve static site
cd web
npm install
npm run build
npx serve out
```

Open http://localhost:3000 to see:
- Ablation charts showing incremental improvements
- Per-task success/failure details
- **Side-by-side trace viewer** (click any task to see baseline vs full-harness execution step-by-step)

## Latest Ablation Results

```
Configuration        Success Rate  False Claims Made  False Claims Caught  Unsafe Executed  Unsafe Blocked
Baseline (no harness)    50.0%                  5                    0                0               0
+ Tool Design            50.0%                  5                    0                0               0
+ Context                50.0%                  5                    0                0               0
+ Sandbox                41.7%                  6                    0                0               0
+ Permissions            41.7%                  6                    0                0               1
+ Retry                  66.7%                  3                    0                0               1
+ Verification           75.0%                  3                    3                0               1
```

**Key improvements:**
- Real success rate: **50% → 75%** (+25%)
- False claims: **5 → 3** (-2 unverified claims)
- False claims caught: **0 → 3** (verification feedback loop converting failures to fixes)
- Unsafe actions: **0 executed → 1 blocked** (protection active)

**Verification feedback loop**: When the agent claims done but verification fails, the system feeds concrete failure evidence back to the agent, allowing bounded fix attempts. This converts caught false claims into real successes.
## Task Suite

12 tasks targeting specific failure modes:

| Task | Failure Mode | Fixed By |
|------|--------------|----------|
| `file_creation` | False completion claims | Verification |
| `flaky_tool` | Transient failures | Retry |
| `timeout_retry` | Timeout errors | Retry |
| `duplicate_side_effect` | Duplicate side effects | Idempotency |
| `dangerous_delete` | Unsafe deletions | Permissions |
| `destructive_command` | Dangerous shell commands | Permissions |
| `overlapping_tools` | Tool selection confusion | Tool Design |
| `misleading_tools` | Ambiguous tool names | Tool Design |
| `context_overflow` | Lost goals in large context | Context Management |
| `oversized_output` | Verbose tool outputs | Tool Design |
| `multi_step_verify` | Multi-step verification | Verification |
| `out_of_workspace_write` | Unsafe file writes | Sandbox |

## Architecture

```
harnessdiff/
├── models.py           # Mock model + LLM providers (OpenAI, Anthropic)
├── agent_loop.py       # Core agent loop with layer integration
├── config.py           # Configuration for layer flags
├── layers/             # 6 harness layers
│   ├── tool_design.py
│   ├── context_mgmt.py
│   ├── sandbox.py
│   ├── permissions.py
│   ├── retry.py
│   └── verification.py
├── runner.py           # Task runner + ablation orchestrator
├── cli.py              # CLI interface
tasks/
└── basic_tasks.py      # 12 deterministic tasks
web/
└── app/                # Next.js dashboard
```

## Development

```bash
# Run tests
pytest

# Run specific task
python3 harnessdiff/cli.py run file_creation

# Run with full harness
python3 harnessdiff/cli.py after file_creation

# List all tasks
python3 harnessdiff/cli.py list-tasks
```

## Requirements

- Python 3.10+
- Node.js 18+ (for dashboard)
- No Docker required
- Works offline with mock model (default)
- Optional: OpenAI or Anthropic API keys for real LLM testing

## License

MIT

## Citation

Based on *"Understanding Harness Engineering"* by @techNmak

---

**🔍 Key Insight**: The harness changes what the model sees → which changes what it does. This project makes those changes visible and measurable.
