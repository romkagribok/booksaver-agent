"""Recognize an explicit empty initial trips page without authorizing absence changes."""

import asyncio
import json
import logging
import re
from typing import Any


def explicit_empty_upcoming(url: str, visible_text: str) -> bool:
    """Inspect only the initial active-trips page after code-owned authentication.

    Missing cards or a model's empty-account claim are insufficient. This observation is
    informational: saved reservations must remain untouched and account scope stays incomplete.
    """
    if (
        url != "https://secure.booking.com/mytrips.html"
        or not 0 < len(visible_text) <= 250_000
    ):
        return False
    text = " ".join(visible_text.casefold().replace("’", "'").split())
    return (
        "bookings & trips" in text
        and re.search(r"\bactive\b", text) is not None
        and "you haven't started any trips yet." in text
        and "once you make a booking, it'll appear here." in text
        and re.search(r"\b[1-9]\d*\s+bookings?\b(?!\.com)", text) is None
    )


async def observe_empty_upcoming(browser_session: Any) -> bool:
    """Read current rendered body text, which the model's DOM serializer can omit."""
    try:
        async with asyncio.timeout(5):
            target_id = browser_session.agent_focus_target_id
            if not isinstance(target_id, str) or not target_id:
                return False
            source_url = await browser_session.get_current_page_url()
            if source_url != "https://secure.booking.com/mytrips.html":
                return False

            async def unchanged() -> bool:
                current = await browser_session.get_current_page_url()
                return (
                    current == source_url
                    and browser_session.agent_focus_target_id == target_id
                    and len(browser_session.get_page_targets()) == 1
                )

            if not await unchanged():
                return False
            pooled = await browser_session.get_or_create_cdp_session(target_id, focus=False)
            if (
                pooled.target_id != target_id
                or not isinstance(pooled.session_id, str) or not pooled.session_id
                or not await unchanged()
            ):
                return False
            result = await pooled.cdp_client.send.Runtime.evaluate(
                params={
                    "expression": (
                        "JSON.stringify({url: location.href, "
                        "text: (document.body?.innerText || '').slice(0, 250001)})"
                    ),
                    "returnByValue": True,
                },
                session_id=pooled.session_id,
            )
            if not await unchanged():
                return False
        raw = result.get("result", {}).get("value")
        value = json.loads(raw) if isinstance(raw, str) else None
        if not isinstance(value, dict):
            return False
        url, text = value.get("url"), value.get("text")
        if not isinstance(url, str) or not isinstance(text, str):
            return False
        normalized = " ".join(text.casefold().replace("’", "'").split())
        logging.getLogger(__name__).warning(
            "Inventory empty-page check root=%s heading=%s active=%s empty_intro=%s "
            "empty_followup=%s booking_count=%s text_chars=%s",
            url == "https://secure.booking.com/mytrips.html",
            "bookings & trips" in normalized,
            re.search(r"\bactive\b", normalized) is not None,
            "you haven't started any trips yet." in normalized,
            "once you make a booking, it'll appear here." in normalized,
            re.search(r"\b[1-9]\d*\s+bookings?\b(?!\.com)", normalized) is not None,
            len(text),
        )
        return explicit_empty_upcoming(url, text)
    except Exception:
        return False
