"""Task suite registry"""

from tasks.basic_tasks import (
    FileCreationTask,
    FlakyToolTask,
    DangerousDeleteTask,
    OverlappingToolsTask,
    DuplicateSideEffectTask,
    Task
)


def get_all_tasks() -> list:
    """Get all available tasks"""
    return [
        FileCreationTask(),
        FlakyToolTask(),
        DangerousDeleteTask(),
        OverlappingToolsTask(),
        DuplicateSideEffectTask(),
    ]


def get_task_by_id(task_id: str) -> Task:
    """Get task by ID"""
    for task in get_all_tasks():
        if task.task_id == task_id:
            return task
    raise ValueError(f"Task not found: {task_id}")


__all__ = [
    "Task",
    "FileCreationTask",
    "FlakyToolTask",
    "DangerousDeleteTask",
    "OverlappingToolsTask",
    "DuplicateSideEffectTask",
    "get_all_tasks",
    "get_task_by_id",
]
