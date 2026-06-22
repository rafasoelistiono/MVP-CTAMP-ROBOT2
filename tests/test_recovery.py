from execution.recovery import RecoveryAction, RecoveryPolicy
from task_planning.types import Step


def test_pick_retry_is_bounded():
    policy = RecoveryPolicy(max_retries_per_object=2)
    step = Step(0, "pick", "cube1")
    assert policy.decide(step, 1, "not_lifted", object_still_held=False).action == RecoveryAction.RETRY
    assert policy.decide(step, 3, "not_lifted", object_still_held=False).action == RecoveryAction.ABORT


def test_fragile_obstacle_failure_aborts_immediately():
    policy = RecoveryPolicy(max_retries_per_object=3)
    step = Step(0, "pick", "cube1")
    decision = policy.decide(
        step, 1, "obstacle_displaced:obstacle1", object_still_held=False
    )
    assert decision.action == RecoveryAction.ABORT
