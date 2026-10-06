"""Tests for tasks"""

import tempfile
from pathlib import Path

from tasks import (
    DangerousDeleteTask,
    DuplicateSideEffectTask,
    FileCreationTask,
    FlakyToolTask,
    OverlappingToolsTask,
    get_all_tasks,
)


def test_file_creation_task():
    """Test file creation task setup and verification"""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = FileCreationTask()
        work_dir = Path(tmpdir)

        # Setup
        context = task.setup(work_dir)
        assert "tools" in context
        assert "write_file" in context["tools"]

        # Execute
        context["tools"]["write_file"]("output.txt", "Hello World")

        # Verify
        result = task.verify(context)
        assert result["success"]


def test_file_creation_task_failure():
    """Test file creation task fails without file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = FileCreationTask()
        work_dir = Path(tmpdir)

        context = task.setup(work_dir)

        # Don't create file
        result = task.verify(context)
        assert not result["success"]


def test_flaky_tool_task():
    """Test flaky tool task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = FlakyToolTask()
        work_dir = Path(tmpdir)

        context = task.setup(work_dir)

        # Should fail first 2 times
        try:
            context["tools"]["fetch_data"]()
            assert False, "Should have failed"
        except Exception:
            pass

        try:
            context["tools"]["fetch_data"]()
            assert False, "Should have failed"
        except Exception:
            pass

        # Should succeed third time
        result = context["tools"]["fetch_data"]()
        assert "Data successfully fetched" in result

        # Verify
        verification = task.verify(context)
        assert verification["success"]


def test_dangerous_delete_task():
    """Test dangerous delete task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = DangerousDeleteTask()
        work_dir = Path(tmpdir)

        context = task.setup(work_dir)

        # Important file should exist
        assert context["important_file"].exists()

        # Verify protection
        result = task.verify(context)
        assert result["success"]


def test_overlapping_tools_task():
    """Test overlapping tools task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = OverlappingToolsTask()
        work_dir = Path(tmpdir)

        context = task.setup(work_dir)

        # Multiple tools available
        assert len(context["tools"]) > 1

        # Use correct tool
        result = context["tools"]["search"](query="project plan")
        assert "Found" in result

        # Verify
        verification = task.verify(context)
        assert verification["success"]


def test_duplicate_side_effect_task():
    """Test duplicate side effect task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = DuplicateSideEffectTask()
        work_dir = Path(tmpdir)

        context = task.setup(work_dir)

        # First call should fail
        try:
            context["tools"]["create_user"](name="John Doe")
            assert False, "Should have failed"
        except Exception:
            pass

        # Second call should succeed
        result = context["tools"]["create_user"](name="John Doe")
        assert "User created" in result

        # Verify only one record
        verification = task.verify(context)
        assert verification["success"]


def test_get_all_tasks():
    """Test get_all_tasks returns tasks"""
    tasks = get_all_tasks()
    assert len(tasks) > 0

    for task in tasks:
        assert hasattr(task, "task_id")
        assert hasattr(task, "description")
        assert hasattr(task, "prompt")
