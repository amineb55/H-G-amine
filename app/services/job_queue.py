"""Job dispatch interface.

Endpoints enqueue work through this module only, so the in-process
implementation can be swapped for a real broker later without touching them.
"""

from typing import Any, Awaitable, Callable, Protocol

from fastapi import BackgroundTasks

Job = Callable[..., Awaitable[Any]]


class JobQueue(Protocol):
    """Anything able to run a job outside the request/response cycle."""

    def enqueue(self, job: Job, *args: Any, **kwargs: Any) -> None:
        """Schedule a job for execution."""
        ...


class BackgroundTaskQueue:
    """Runs jobs in-process, after the response has been sent."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def enqueue(self, job: Job, *args: Any, **kwargs: Any) -> None:
        self._background_tasks.add_task(job, *args, **kwargs)


def get_queue(background_tasks: BackgroundTasks) -> JobQueue:
    """Return the queue implementation currently in use."""
    return BackgroundTaskQueue(background_tasks)
