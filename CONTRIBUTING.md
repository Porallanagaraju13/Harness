# Contributing to HarnessDiff

Thank you for your interest in contributing to HarnessDiff!

## Development Setup

1. Clone the repository
2. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run tests:
   ```bash
   pytest
   ```

## Project Structure

- `harnessdiff/` - Core agent loop and harness layers
- `tasks/` - Task definitions with deterministic checks
- `web/` - Dashboard for visualizing results
- `tests/` - Test suite

## Adding Components

### Adding a Task

1. Create a new task class in `tasks/`
2. Implement `setup()`, `verify()`, and `description` property
3. Add failure injections if relevant
4. Register in `tasks/__init__.py`

### Adding a Harness Layer

1. Create a new layer class in `harnessdiff/layers/`
2. Implement the layer interface (wrap model or tools)
3. Add configuration in `harnessdiff/config.py`
4. Add tests in `tests/test_layers.py`

### Adding a Model Provider

1. Implement the `ModelProvider` interface in `harnessdiff/models.py`
2. Add API key handling in environment variables
3. Document usage in README

## Code Style

- Use type hints where practical
- Follow PEP 8 conventions
- Write tests for new functionality
- Keep cross-platform compatibility (Windows + Linux)

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass
5. Submit a pull request with a clear description

## Questions?

Open an issue for questions or discussions about features and architecture.
