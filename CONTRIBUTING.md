# Contributing to HarnessDiff

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone <repo-url>
cd harnessdiff

# Install in development mode
pip install -e .

# Install dev dependencies
pip install pytest pytest-cov black mypy

# Run tests
pytest
```

## Project Structure

```
harnessdiff/
├── agent_loop.py      # Core agent loop
├── models.py          # Model providers
├── config.py          # Configuration
├── layers/            # Harness layers (6 total)
├── runner.py          # Task runner + ablation
└── cli.py             # Command-line interface

tasks/
├── basic_tasks.py     # Task definitions
└── __init__.py        # Task registry

tests/
├── test_agent_loop.py
├── test_layers.py
├── test_models.py
├── test_tasks.py
└── test_integration.py

web/                   # Next.js dashboard
```

## Adding a New Task

1. Define task class in `tasks/basic_tasks.py`:

```python
class MyTask(Task):
    @property
    def task_id(self) -> str:
        return "my_task"
    
    @property
    def description(self) -> str:
        return "Short description"
    
    @property
    def prompt(self) -> str:
        return "Instruction for the agent"
    
    @property
    def failure_modes(self) -> List[str]:
        return ["verification", "retry", "permissions"]
    
    def setup(self, work_dir: Path) -> Dict[str, Any]:
        """Setup environment and return tools"""
        context = {"work_dir": work_dir}
        # ... define tools ...
        return context
    
    def verify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify task completion"""
        return {
            "success": True/False,
            "evidence": "What was checked",
            "details": {}
        }
```

2. Register in `tasks/__init__.py`:

```python
from tasks.basic_tasks import MyTask

def get_all_tasks() -> List[Task]:
    return [
        # ... existing tasks ...
        MyTask(),
    ]
```

3. Add tests in `tests/test_tasks.py`

## Adding a New Layer

1. Create `harnessdiff/layers/my_layer.py`:

```python
class MyLayer:
    def __init__(self, config: HarnessConfig):
        self.config = config
    
    def wrap_tools(self, tools: Dict[str, Callable]) -> Dict[str, Callable]:
        """Wrap tools with layer logic"""
        wrapped = {}
        for name, fn in tools.items():
            wrapped[name] = self._wrap(fn)
        return wrapped
    
    def _wrap(self, tool_fn: Callable) -> Callable:
        def wrapper(**kwargs):
            # Pre-execution logic
            result = tool_fn(**kwargs)
            # Post-execution logic
            return result
        return wrapper
```

2. Add config flag in `harnessdiff/config.py`
3. Integrate in `agent_loop.py` `_apply_layers()`
4. Add tests in `tests/test_layers.py`

## Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_layers.py

# With coverage
pytest --cov=harnessdiff --cov-report=html

# Verbose
pytest -xvs
```

## Code Style

- Use **black** for formatting: `black harnessdiff/ tasks/ tests/`
- Use **type hints** where practical
- Add **docstrings** to public functions
- Keep functions focused and testable

## Pull Request Guidelines

1. **Fork and branch**: Create a feature branch from `main`
2. **Tests**: Add tests for new features
3. **Pass CI**: Ensure `pytest` passes
4. **Documentation**: Update README if adding user-facing features
5. **Commit messages**: Use clear, descriptive commits

## Reporting Issues

Please include:
- Python version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

## Questions?

Open an issue or discussion on GitHub.

---

Thank you for contributing to HarnessDiff!
