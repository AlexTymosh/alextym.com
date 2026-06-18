from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import Settings

DEFAULT_HANDOFF_TIMEZONE = "Europe/London"
DEFAULT_HANDOFF_START = "09:00"
DEFAULT_HANDOFF_END = "21:00"
CONTACT_PATH = "/contact"
DEFAULT_HANDOFF_RETRY_LINE = "Please try again during those hours or use the contact form."


@dataclass(frozen=True)
class HandoffAvailabilityStatus:
    is_available: bool
    start_time: str
    end_time: str
    timezone: str
    contact_path: str = CONTACT_PATH

    @property
    def message(self) -> str:
        return (
            "Live handoff is available from "
            f"{self.start_time} to {self.end_time} {self.timezone} time. "
            f"{DEFAULT_HANDOFF_RETRY_LINE}"
        )

    def to_http_detail(self) -> dict[str, str]:
        return {
            "code": "handoff_outside_hours",
            "message": self.message,
            "contact_path": self.contact_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timezone": self.timezone,
        }


class HandoffUnavailableError(Exception):
    def __init__(self, status: HandoffAvailabilityStatus) -> None:
        self.status = status
        super().__init__(status.message)


class HandoffAvailabilityChecker:
    def ensure_available(self) -> None:
        raise NotImplementedError


class AlwaysAvailableHandoffAvailabilityChecker(HandoffAvailabilityChecker):
    def ensure_available(self) -> None:
        return None


class ScheduledHandoffAvailabilityChecker(HandoffAvailabilityChecker):
    def __init__(
        self,
        *,
        timezone_name: str,
        start_time: str,
        end_time: str,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._timezone_name = timezone_name.strip() or DEFAULT_HANDOFF_TIMEZONE
        self._timezone = _safe_zoneinfo(self._timezone_name)
        self._start_time_text = _safe_time_text(start_time, DEFAULT_HANDOFF_START)
        self._end_time_text = _safe_time_text(end_time, DEFAULT_HANDOFF_END)
        self._start_time = _parse_clock_time(self._start_time_text)
        self._end_time = _parse_clock_time(self._end_time_text)
        self._now_provider = now_provider or datetime.now

    def ensure_available(self) -> None:
        status = self.status()
        if not status.is_available:
            raise HandoffUnavailableError(status)

    def status(self) -> HandoffAvailabilityStatus:
        local_now = _local_datetime(self._now_provider(), self._timezone)
        is_available = _is_clock_time_available(
            local_now.time(),
            self._start_time,
            self._end_time,
        )
        return HandoffAvailabilityStatus(
            is_available=is_available,
            start_time=self._start_time_text,
            end_time=self._end_time_text,
            timezone=self._timezone_name,
        )


def build_handoff_availability_checker(
    settings: Settings,
) -> HandoffAvailabilityChecker:
    if not settings.handoff_availability_enabled:
        return AlwaysAvailableHandoffAvailabilityChecker()

    return ScheduledHandoffAvailabilityChecker(
        timezone_name=settings.handoff_availability_timezone,
        start_time=settings.handoff_availability_start,
        end_time=settings.handoff_availability_end,
    )


def _safe_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_HANDOFF_TIMEZONE)


def _safe_time_text(value: str, fallback: str) -> str:
    try:
        _parse_clock_time(value)
    except ValueError:
        return fallback
    return value


def _parse_clock_time(value: str) -> time:
    raw_hour, raw_minute = value.strip().split(":", 1)
    hour = int(raw_hour)
    minute = int(raw_minute)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("Clock time is outside the allowed range.")
    return time(hour=hour, minute=minute)


def _local_datetime(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def _is_clock_time_available(
    current_time: time,
    start_time: time,
    end_time: time,
) -> bool:
    current_minutes = _minutes_since_midnight(current_time)
    start_minutes = _minutes_since_midnight(start_time)
    end_minutes = _minutes_since_midnight(end_time)

    if start_minutes == end_minutes:
        return False
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def _minutes_since_midnight(value: time) -> int:
    return value.hour * 60 + value.minute
