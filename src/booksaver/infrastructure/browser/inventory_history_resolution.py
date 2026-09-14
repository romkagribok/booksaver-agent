"""Qualify one earlier observed inventory parent without navigating or allocating actions."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .inventory_traversal import InventoryTraversal, inventory_page_kind


@dataclass(frozen=True, slots=True)
class ResolvedInventoryHistoryReturn:
    source_url: str = field(repr=False)
    target_url: str = field(repr=False)
    target_id: str = field(repr=False)
    entry_id: int = field(repr=False)
    session_id: str = field(repr=False)


async def resolve_inventory_history_return(
    browser_session: Any, *, observed_parent_url: str,
) -> ResolvedInventoryHistoryReturn | None:
    """Return a guarded native history entry; the caller rechecks and meters its replay."""
    try:
        async with asyncio.timeout(5):
            if (
                not isinstance(observed_parent_url, str)
                or not 1 <= len(observed_parent_url) <= 4_000
                or inventory_page_kind(observed_parent_url) not in {"root", "trip"}
            ):
                return None
            target_id = browser_session.agent_focus_target_id
            if not isinstance(target_id, str) or not target_id:
                return None
            source_url = await browser_session.get_current_page_url()
            if (
                not isinstance(source_url, str) or not 1 <= len(source_url) <= 4_000
                or inventory_page_kind(source_url) not in {"trip", "reservation_detail"}
            ):
                return None

            async def unchanged() -> bool:
                current = await browser_session.get_current_page_url()
                return (
                    current == source_url
                    and browser_session.agent_focus_target_id == target_id
                    and len(browser_session.get_page_targets()) == 1
                )

            if not await unchanged():
                return None
            pooled = await browser_session.get_or_create_cdp_session(target_id, focus=False)
            if (
                pooled.target_id != target_id
                or not isinstance(pooled.session_id, str) or not pooled.session_id
                or not await unchanged()
            ):
                return None
            session_id = pooled.session_id
            history = await pooled.cdp_client.send.Page.getNavigationHistory(
                params={}, session_id=session_id,
            )
            if not await unchanged() or not isinstance(history, dict):
                return None
            if len(json.dumps(history, ensure_ascii=True)) > 1_100_000:
                return None
            entries, current_index = history.get("entries"), history.get("currentIndex")
            if (
                not isinstance(entries, list) or not 1 <= len(entries) <= 100
                or type(current_index) is not int or not 0 <= current_index < len(entries)
            ):
                return None
            ids: set[int] = set()
            for entry in entries:
                if not isinstance(entry, dict):
                    return None
                entry_id, url = entry.get("id"), entry.get("url")
                if (
                    type(entry_id) is not int or not 0 <= entry_id <= 2_147_483_647
                    or entry_id in ids or not isinstance(url, str) or not 1 <= len(url) <= 4_000
                ):
                    return None
                ids.add(entry_id)
            if entries[current_index]["url"] != source_url:
                return None
            parent = urlsplit(observed_parent_url)
            parent_key = InventoryTraversal._key(observed_parent_url)
            matching = [
                index for index, entry in enumerate(entries[:current_index])
                if inventory_page_kind(entry["url"]) in {"root", "trip"}
                and urlsplit(entry["url"]).hostname == parent.hostname
                and urlsplit(entry["url"]).path == parent.path
                and InventoryTraversal._key(entry["url"]) == parent_key
            ]
            if not matching:
                return None
            parent_index = matching[-1]
            # Every skipped entry must also remain inside the qualified inventory surface.
            if any(
                inventory_page_kind(entry["url"]) is None
                for entry in entries[parent_index:current_index + 1]
            ):
                return None
            destination = entries[parent_index]
            return ResolvedInventoryHistoryReturn(
                source_url, destination["url"], target_id, destination["id"], session_id,
            )
    except Exception:
        return None
