"""Task suite registry"""

from tasks.basic_tasks import (
    FileCreationTask,
    FlakyToolTask,
    DangerousDeleteTask,
    OverlappingToolsTask,
    DuplicateSideEffectTask,
    TimeoutTask,
    OversizedOutputTask,
    MisleadingToolNamesTask,
    DestructiveCommandTask,
    MultiStepVerificationTask,
    ContextOverflowTask,
    OutOfWorkspaceWriteTask,
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
        TimeoutTask(),
        OversizedOutputTask(),
        MisleadingToolNamesTask(),
        DestructiveCommandTask(),
        MultiStepVerificationTask(),
        ContextOverflowTask(),
        OutOfWorkspaceWriteTask(),
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
    "TimeoutTask",
    "OversizedOutputTask",
    "MisleadingToolNamesTask",
    "DestructiveCommandTask",
    "MultiStepVerificationTask",
    "ContextOverflowTask",
    "OutOfWorkspaceWriteTask",
    "get_all_tasks",
    "get_task_by_id",
]
