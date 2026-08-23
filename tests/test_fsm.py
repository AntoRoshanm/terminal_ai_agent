"""
Unit tests for Task Execution Finite State Machine.
"""

import pytest
from app.agent.fsm import InvalidStateTransitionError, TaskStateMachine
from app.models.state import TaskState


def test_valid_fsm_transitions():
    # NEW -> UNDERSTANDING
    assert TaskStateMachine.can_transition(TaskState.NEW, TaskState.UNDERSTANDING)
    TaskStateMachine.validate_transition(TaskState.NEW, TaskState.UNDERSTANDING)

    # UNDERSTANDING -> PLANNING -> EXECUTING -> OBSERVING -> VERIFYING -> COMPLETED
    assert TaskStateMachine.can_transition(TaskState.UNDERSTANDING, TaskState.PLANNING)
    assert TaskStateMachine.can_transition(TaskState.PLANNING, TaskState.EXECUTING)
    assert TaskStateMachine.can_transition(TaskState.EXECUTING, TaskState.OBSERVING)
    assert TaskStateMachine.can_transition(TaskState.OBSERVING, TaskState.VERIFYING)
    assert TaskStateMachine.can_transition(TaskState.VERIFYING, TaskState.COMPLETED)


def test_fsm_recovery_loop():
    # VERIFYING -> RECOVERING -> EXECUTING
    assert TaskStateMachine.can_transition(TaskState.VERIFYING, TaskState.RECOVERING)
    assert TaskStateMachine.can_transition(TaskState.RECOVERING, TaskState.EXECUTING)


def test_invalid_fsm_transition():
    # Direct jump from NEW to COMPLETED is invalid
    assert not TaskStateMachine.can_transition(TaskState.NEW, TaskState.COMPLETED)
    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.validate_transition(TaskState.NEW, TaskState.COMPLETED)

    # Transition from COMPLETED (terminal) is invalid
    assert not TaskStateMachine.can_transition(TaskState.COMPLETED, TaskState.EXECUTING)
    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.validate_transition(TaskState.COMPLETED, TaskState.EXECUTING)
