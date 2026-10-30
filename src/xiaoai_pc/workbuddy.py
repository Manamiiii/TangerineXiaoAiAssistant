"""Stage-three seam only. Mock NEVER connects to or operates WorkBuddy."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Submission:
    message_id: str
    status: str
    feedback: str


class WorkBuddyAdapter(Protocol):
    def submit(self, task: str) -> Submission: ...
    def status(self, message_id: str) -> Submission: ...


class DisabledWorkBuddy:
    def submit(self, task: str) -> Submission:
        return Submission("", "not_configured", "WorkBuddy 尚未授权，任务未提交")

    def status(self, message_id: str) -> Submission:
        return self.submit("")


class MockWorkBuddy:
    """Explicit simulation for adapter tests, not enabled in the voice bridge."""
    def __init__(self):
        self._messages: dict[str, Submission] = {}

    def submit(self, task: str) -> Submission:
        if not task.strip():
            raise ValueError("任务不能为空")
        mid = f"mock-{len(self._messages) + 1}"
        result = Submission(mid, "simulated", "模拟提交，未发送给 WorkBuddy，也未执行任务")
        self._messages[mid] = result
        return result

    def status(self, message_id: str) -> Submission:
        return self._messages[message_id]
