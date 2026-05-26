import html
from typing import Protocol

from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.schemas.contact import ContactRequest, ContactResponse


class ContactConfigurationError(Exception):
    pass


class ContactDeliveryError(Exception):
    pass


class ContactEmailSender(Protocol):
    async def send(self, contact_request: ContactRequest) -> None:
        pass


class NoopContactEmailSender:
    def __init__(self) -> None:
        self.sent_requests: list[ContactRequest] = []

    async def send(self, contact_request: ContactRequest) -> None:
        self.sent_requests.append(contact_request)


class ResendContactEmailSender:
    def __init__(self, *, api_key: str, target_email: str, from_email: str) -> None:
        self._api_key = api_key
        self._target_email = target_email
        self._from_email = from_email

    async def send(self, contact_request: ContactRequest) -> None:
        await run_in_threadpool(self._send_sync, contact_request)

    def _send_sync(self, contact_request: ContactRequest) -> None:
        import resend

        resend.api_key = self._api_key
        params: resend.Emails.SendParams = {
            "from": self._from_email,
            "to": [self._target_email],
            "subject": f"New alextym.com contact from {contact_request.name}",
            "html": _build_contact_email_html(contact_request),
            "reply_to": contact_request.email,
        }

        try:
            resend.Emails.send(params)
        except Exception as exc:
            raise ContactDeliveryError("Contact message could not be delivered.") from exc


class ContactService:
    def __init__(self, *, sender: ContactEmailSender | None) -> None:
        self._sender = sender

    @classmethod
    def from_settings(cls, settings: Settings) -> "ContactService":
        configured_values = (
            settings.resend_api_key,
            settings.contact_target_email,
            settings.contact_from_email,
        )
        is_configured = all(configured_values)
        has_partial_config = any(configured_values)

        if is_configured:
            return cls(
                sender=ResendContactEmailSender(
                    api_key=settings.resend_api_key,
                    target_email=settings.contact_target_email,
                    from_email=settings.contact_from_email,
                )
            )

        if settings.environment in {"local", "test"} and not has_partial_config:
            return cls(sender=NoopContactEmailSender())

        return cls(sender=None)

    async def submit(self, contact_request: ContactRequest) -> ContactResponse:
        if contact_request.is_honeypot_filled:
            return ContactResponse()

        if self._sender is None:
            raise ContactConfigurationError("Contact form is not configured.")

        await self._sender.send(contact_request)
        return ContactResponse()


def _build_contact_email_html(contact_request: ContactRequest) -> str:
    name = html.escape(contact_request.name)
    email = html.escape(contact_request.email)
    message = html.escape(contact_request.message).replace("\n", "<br>")

    return (
        "<h2>New contact form message</h2>"
        f"<p><strong>Name:</strong> {name}</p>"
        f"<p><strong>Email:</strong> {email}</p>"
        f"<p><strong>Message:</strong></p><p>{message}</p>"
    )
