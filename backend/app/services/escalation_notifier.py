from typing import Protocol

from app.schemas.escalation import EscalationMessageRequest, EscalationRequest


class EscalationNotifier(Protocol):
    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        pass

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        pass


class NoopEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []
        self.sent_handoff_ids: list[str | None] = []
        self.sent_message_requests: list[EscalationMessageRequest] = []
        self.sent_message_handoff_ids: list[str] = []

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        self.sent_requests.append(escalation_request)
        self.sent_handoff_ids.append(handoff_id)

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        self.sent_message_requests.append(message_request)
        self.sent_message_handoff_ids.append(handoff_id)
