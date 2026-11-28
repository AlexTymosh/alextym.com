"""Operator-reviewed sources only. Built-in recorded loops are original test tones."""

import os
from urllib.parse import urlsplit

RECORDED = {"test_disco": 8000, "test_retro": 8000}
RADIOS = {"melodia_disco": "DISCO", "radio_roks": "ROCK", "retro_radio": "RETRO"}


def sources():
    result = {
        key: {"id": key, "mode": "recorded", "duration_ms": duration, "available": True}
        for key, duration in RECORDED.items()
    }
    for key, suffix in RADIOS.items():
        raw = os.getenv(f"SAMEPLACE_RADIO_{suffix}_URL", "").strip()
        allowed = False
        if (
            raw
            and len(raw) <= 1000
            and os.getenv(f"SAMEPLACE_RADIO_{suffix}_RIGHTS_VERIFIED") == "true"
        ):
            try:
                url = urlsplit(raw)
                allowed = bool(
                    url.scheme == "https"
                    and url.hostname
                    and not url.username
                    and not url.password
                    and not url.fragment
                    and not url.query
                )
            except ValueError:
                pass
        result[key] = {"id": key, "mode": "live_radio", "duration_ms": None, "available": allowed}
        if allowed:
            result[key]["url"] = raw
    return result
