"""Resolve a rendered inventory anchor without navigating or granting new action powers.

This follows links, rather than clicking screenshot coordinates. A connected, rendered anchor
may be offscreen or overlapped; its real ancestry still passes the existing action guard.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, cast
from urllib.parse import parse_qsl, urljoin, urlsplit

from .browser_use_runtime import (
    _INTERACTIVE_CLICK_ATTRIBUTES,
    _INTERACTIVE_CLICK_ROLES,
    BrowserUseActionGuard,
    coordinate_chain_click_decision,
)
from .inventory_traversal import InventoryTraversal, inventory_page_kind

_READ_ANCHORS = """(() => {
  const rendered = element => {
    const style = getComputedStyle(element);
    return element.isConnected && element.getClientRects().length > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' && style.visibility !== 'collapse';
  };
  const anchors = Array.from(document.querySelectorAll('a[href]')).filter(rendered);
  return JSON.stringify({url:location.href,hrefs:anchors.slice(0,251).map(a=>a.href)});
})()"""

_READ_CHAIN = """(() => {
  const target = TARGET_JSON;
  const rendered = element => {
    const style = getComputedStyle(element);
    return element.isConnected && element.getClientRects().length > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' && style.visibility !== 'collapse';
  };
  const anchors = Array.from(document.querySelectorAll('a[href]'))
    .filter(a=>a.href === target && rendered(a));
  if (anchors.length !== 1) return JSON.stringify({matched:anchors.length});
  const anchor = anchors[0];
  const names = ['href','src','action','formaction','target','type','role','download',
    'contenteditable','disabled','aria-disabled','onclick'];
  let element = anchor;
  const chain = [];
  while (element && chain.length < 16) {
    const attributes = {};
    const eventNames = element.getAttributeNames().filter(n=>/^on/i.test(n));
    for (const name of new Set([...names, ...eventNames])) {
      if (element.hasAttribute(name)) attributes[name] = element.getAttribute(name);
    }
    const role = (attributes.role || element.tagName).trim().toLowerCase();
    const interactive = INTERACTIVE_ROLES_JSON.includes(role) ||
      Object.keys(attributes).some(n=>INTERACTIVE_ATTRIBUTES_JSON.includes(n) || /^on/i.test(n));
    const label = element === anchor || interactive ?
      element.getAttribute('aria-label') || element.innerText || element.textContent || '' : '';
    if (label.length > 1000 || Object.keys(attributes).length > 50 ||
        Object.values(attributes).some(value=>value.length > 1000))
      return JSON.stringify({overflow:true});
    chain.push({node_name:element.tagName.toLowerCase(),label,attributes,visible:rendered(element)});
    element = element.parentElement;
  }
  return JSON.stringify({url:location.href,href:anchor.href,matched:anchors.length,
    connected:anchor.isConnected,complete:element === null,chain});
})()""".replace("INTERACTIVE_ROLES_JSON", json.dumps(sorted(_INTERACTIVE_CLICK_ROLES))).replace(
    "INTERACTIVE_ATTRIBUTES_JSON",
    json.dumps(sorted(_INTERACTIVE_CLICK_ATTRIBUTES)),
)


@dataclass(frozen=True, slots=True)
class ResolvedInventoryLink:
    source_url: str = field(repr=False)
    target_url: str = field(repr=False)
    target_id: str = field(repr=False)
    chain: tuple[Mapping[str, object], ...] = field(repr=False)


def _decoded_result(result: object) -> dict[str, Any] | None:
    if not isinstance(result, dict) or not isinstance(result.get("result"), dict):
        return None
    raw = result["result"].get("value")
    if not isinstance(raw, str) or len(raw) > 1_100_000:
        return None
    value = json.loads(raw)
    return value if isinstance(value, dict) else None


def _validated_chain(value: object) -> list[Mapping[str, object]] | None:
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        return None
    for item in value:
        if not isinstance(item, dict) or item.get("visible") is not True:
            return None
        if not isinstance(item.get("node_name"), str) or len(item["node_name"]) > 100:
            return None
        if not isinstance(item.get("label"), str) or len(item["label"]) > 1_000:
            return None
        attributes = item.get("attributes")
        if not isinstance(attributes, dict) or len(attributes) > 50:
            return None
        if any(
            not isinstance(key, str)
            or len(key) > 100
            or not isinstance(attribute, str)
            or len(attribute) > 1_000
            for key, attribute in attributes.items()
        ):
            return None
    if value[0]["node_name"] != "a":
        return None
    return value


async def resolve_rendered_inventory_link(
    browser_session: Any,
    *,
    source_url: str,
    observed_target_url: str,
) -> ResolvedInventoryLink | None:
    """Resolve one fresh real anchor; callers must recheck invariants before replay."""
    if inventory_page_kind(source_url) not in {"root", "trip"}:
        return None
    if inventory_page_kind(observed_target_url) not in {"trip", "reservation_detail"}:
        return None
    return await _resolve_rendered_link(
        browser_session,
        source_url=source_url,
        observed_target_url=observed_target_url,
        confirmation_view=False,
    )


def _confirmation_query(url: str) -> dict[str, str] | None:
    if inventory_page_kind(url) != "reservation_detail":
        return None
    raw_parts = [part.partition("=") for part in urlsplit(url).query.split("&")]
    if any(
        not key or key != key.strip().casefold() or "%" in key or "+" in key
        for key, _, _ in raw_parts
    ):
        return None
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True, max_num_fields=200)
    if len(pairs) != len({key for key, _ in pairs}):
        return None
    query = dict(pairs)
    if not query.get("auth_key", "").strip():
        return None
    # Treat the opaque identity literally; alternate encodings do not qualify a new alias.
    if any(key == "auth_key" and raw != query["auth_key"] for key, _, raw in raw_parts):
        return None
    if "prefer_site_type" in query and any(
        key == "prefer_site_type" and raw != query["prefer_site_type"] for key, _, raw in raw_parts
    ):
        return None
    return query


def _same_confirmation_desktop_view(source_url: str, target_url: str) -> bool:
    source, target = _confirmation_query(source_url), _confirmation_query(target_url)
    if source is None or target is None:
        return False
    if source.get("prefer_site_type", "").strip().casefold() == "www":
        return False
    if target.get("prefer_site_type") != "www":
        return False
    if urlsplit(source_url).path != urlsplit(target_url).path:
        return False
    ignored = {"aid", "label", "source", "prefer_site_type"}
    return {key: value for key, value in source.items() if key not in ignored} == {
        key: value for key, value in target.items() if key not in ignored
    }


async def resolve_rendered_confirmation_view(
    browser_session: Any,
    *,
    source_url: str,
    observed_target_url: str,
) -> ResolvedInventoryLink | None:
    """Qualify only the observed same-confirmation Desktop version link.

    The caller must suppress session export after using this ephemeral inventory view.
    Ordinary inventory link resolution still cannot follow outbound confirmation links.
    """
    if not _same_confirmation_desktop_view(source_url, observed_target_url):
        return None
    return await _resolve_rendered_link(
        browser_session,
        source_url=source_url,
        observed_target_url=observed_target_url,
        confirmation_view=True,
    )


async def _resolve_rendered_link(
    browser_session: Any,
    *,
    source_url: str,
    observed_target_url: str,
    confirmation_view: bool,
) -> ResolvedInventoryLink | None:
    try:
        async with asyncio.timeout(5):
            target_id = browser_session.agent_focus_target_id
            if not isinstance(target_id, str) or not target_id:
                return None

            async def unchanged() -> bool:
                url = await browser_session.get_current_page_url()
                return (
                    url == source_url
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

            async def read(expression: str) -> dict[str, Any] | None:
                return _decoded_result(
                    await pooled.cdp_client.send.Runtime.evaluate(
                        params={"expression": expression, "returnByValue": True},
                        session_id=session_id,
                    )
                )

            anchors = await read(_READ_ANCHORS)
            if not await unchanged() or anchors is None or anchors.get("url") != source_url:
                return None
            hrefs = anchors.get("hrefs")
            if not isinstance(hrefs, list) or len(hrefs) > 250:
                return None
            if any(not isinstance(href, str) or len(href) > 4_000 for href in hrefs):
                return None
            target_key = InventoryTraversal._key(observed_target_url)
            target_path = urlsplit(observed_target_url).path
            candidates = [
                href
                for href in hrefs
                if (
                    _same_confirmation_desktop_view(source_url, href)
                    if confirmation_view
                    else (
                        inventory_page_kind(href) in {"trip", "reservation_detail"}
                        and urlsplit(href).path == target_path
                        and InventoryTraversal._key(href) == target_key
                    )
                )
            ]
            if len(candidates) != 1:
                return None
            candidate = candidates[0]
            evidence = await read(_READ_CHAIN.replace("TARGET_JSON", json.dumps(candidate)))
            if not await unchanged() or evidence is None:
                return None
            if (
                evidence.get("url") != source_url
                or evidence.get("href") != candidate
                or type(evidence.get("matched")) is not int
                or evidence.get("matched") != 1
                or evidence.get("connected") is not True
                or evidence.get("complete") is not True
                or evidence.get("overflow") is True
            ):
                return None
            chain = _validated_chain(evidence.get("chain"))
            if chain is None:
                return None
            if confirmation_view and chain[0]["label"] != "Desktop version":
                return None
            anchor_attributes = cast(Mapping[str, str], chain[0]["attributes"])
            anchor_href = anchor_attributes.get("href")
            if not anchor_href or urljoin(source_url, anchor_href) != candidate:
                return None
            if not coordinate_chain_click_decision(
                BrowserUseActionGuard(),
                chain=chain,
                current_url=source_url,
            ).allowed:
                return None
            return ResolvedInventoryLink(
                source_url,
                candidate,
                target_id,
                tuple(
                    MappingProxyType(
                        {
                            **item,
                            "attributes": MappingProxyType(
                                dict(
                                    cast(Mapping[str, str], item["attributes"]),
                                )
                            ),
                        }
                    )
                    for item in chain
                ),
            )
    except Exception:
        return None
