# Changelog

All notable changes to HarnessDiff will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-06

### Added
- Initial production release
- 12 deterministic tasks testing specific harness failure modes
- 6 harness layers with incremental ablation study
- Environment-reactive mock model for offline-capable testing
- Real LLM provider support (Gemini, OpenAI, and Anthropic)
- First-class Gemini provider (default model `gemini-3.8-flash`, `GEMINI_API_KEY`, `HARNESSDIFF_GEMINI_MODEL`)
- `harnessdiff models --provider gemini` to list live model ids
- Task x layer success matrix showing which layer fixes which task
- Side-by-side trace viewer in dashboard
- Complete CLI for running tasks, ablations, and before/after comparisons
- Cross-platform support (Linux, macOS, Windows)
- Comprehensive test suite with pytest
- Next.js static dashboard with charts and trace viewer

### Features
- **Tool Design Layer**: Filters overlapping tools and improves descriptions
- **Context Management Layer**: Preserves goals during context compaction
- **Sandbox Layer**: Blocks out-of-workspace file operations
- **Permissions Layer**: Blocks dangerous operations with safer alternatives
- **Retry + Idempotency Layer**: Handles transient failures and prevents duplicates
- **Verification Layer**: Independent verification with feedback loop

### Metrics
- Baseline success rate: 50.0%
- Full harness success rate: 83.3% (+33.3% improvement)
- False claims reduced from 5 to 2
- Unsafe operations: 2 executed at baseline → 1 blocked with harness

## Links
- Repository: https://github.com/Porallanagaraju13/Harness
- Demo: https://harnessdiff.vercel.app
