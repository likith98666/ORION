from orion.core.recovery.recovery_action import (
    RecoveryAction,
    RecoveryActionType,
)


class RecoveryExecutor:
    """Executes validated recovery actions."""

    def execute(self, action: RecoveryAction) -> RecoveryAction:
        """Execute a recovery action and return the applied action."""

        if not isinstance(action, RecoveryAction):
            raise TypeError(
                "action must be a RecoveryAction instance."
            )

        handlers = {
            RecoveryActionType.RETRY_TASK: self._retry_task,
            RecoveryActionType.CHANGE_AGENT: self._change_agent,
            RecoveryActionType.CHANGE_TOOL: self._change_tool,
            RecoveryActionType.CHANGE_MODEL: self._change_model,
            RecoveryActionType.MODIFY_TASK: self._modify_task,
            RecoveryActionType.CHANGE_TASK_ORDER: self._change_task_order,
            RecoveryActionType.SKIP_TASK: self._skip_task,
            RecoveryActionType.ESCALATE_TO_HUMAN: self._escalate_to_human,
        }

        return handlers[action.action_type](action)

    def _retry_task(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _change_agent(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _change_tool(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _change_model(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _modify_task(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _change_task_order(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _skip_task(self, action: RecoveryAction) -> RecoveryAction:
        return action

    def _escalate_to_human(self, action: RecoveryAction) -> RecoveryAction:
        return action
