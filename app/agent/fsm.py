"""
Task State Machine & Lifecycle Management
"""

from typing import Dict, Set
from app.models.state import TaskState


class InvalidStateTransitionError(Exception):
    """Raised when an illegal FSM transition is attempted."""
    pass


class TaskStateMachine:
    """Manages and enforces valid state transitions for tasks."""

    VALID_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
        TaskState.NEW: {
            TaskState.UNDERSTANDING,
            TaskState.PLANNING,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.UNDERSTANDING: {
            TaskState.PLANNING,
            TaskState.EXECUTING,
            TaskState.WAITING_FOR_USER,
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.PLANNING: {
            TaskState.EXECUTING,
            TaskState.WAITING_FOR_USER,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.WAITING_FOR_USER: {
            TaskState.EXECUTING,
            TaskState.PLANNING,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.EXECUTING: {
            TaskState.OBSERVING,
            TaskState.VERIFYING,
            TaskState.RECOVERING,
            TaskState.FAILED,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
        },
        TaskState.OBSERVING: {
            TaskState.VERIFYING,
            TaskState.RECOVERING,
            TaskState.EXECUTING,
            TaskState.PLANNING,
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.VERIFYING: {
            TaskState.COMPLETED,
            TaskState.RECOVERING,
            TaskState.PLANNING,
            TaskState.UNDERSTANDING,
            TaskState.EXECUTING,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.RECOVERING: {
            TaskState.EXECUTING,
            TaskState.PLANNING,
            TaskState.WAITING_FOR_USER,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.COMPLETED: set(),
        TaskState.FAILED: set(),
        TaskState.CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, current: TaskState, target: TaskState) -> bool:
        """Check if transition from current to target is allowed."""
        if current == target:
            return True
        allowed = cls.VALID_TRANSITIONS.get(current, set())
        return target in allowed

    @classmethod
    def validate_transition(cls, current: TaskState, target: TaskState) -> None:
        """Validate transition, raising InvalidStateTransitionError if illegal."""
        if not cls.can_transition(current, target):
            msg = f"Illegal task state transition: {current.value} -> {target.value}"
            raise InvalidStateTransitionError(msg)
