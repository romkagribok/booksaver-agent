from __future__ import annotations

from dataclasses import replace

import pytest
from tests.unit.browser.test_jev_price_executor import _request

from booksaver.infrastructure.browser.price_entry import (
    _price_entry_url,
    build_trusted_search_url,
)
from booksaver.infrastructure.browser.session_bootstrap import CodeOwnedSessionBootstrap


def test_code_owned_cookie_bootstrap_is_content_safe_and_domain_scoped() -> None:
    bootstrap = CodeOwnedSessionBootstrap()
    bootstrap.restore_session(b'[{"name":"s","value":"secret","domain":".booking.com"}]')
    assert "secret" not in repr(bootstrap)

    with pytest.raises(ValueError, match="outside Booking.com"):
        CodeOwnedSessionBootstrap._decode_cookies(  # noqa: SLF001 - pure validation fixture
            b'[{"name":"s","value":"secret","domain":"evil.example"}]'
        )


def test_trusted_search_url_contains_only_code_owned_query() -> None:
    url = build_trusted_search_url(_request())
    assert url.startswith("https://www.booking.com/searchresults.html?")
    assert "checkin=2026-11-24" in url
    assert "group_adults=2" in url
    assert "selected_currency=USD" in url


def test_price_entry_prefers_trusted_property_page_without_tracking() -> None:
    request = _request()
    request = replace(
        request,
        query=replace(
            request.query,
            property_reference="https://www.booking.com/hotel/us/example.html?old=tracking#top",
        ),
    )

    url, kind = _price_entry_url(request)

    assert kind == "property"
    assert url.startswith("https://www.booking.com/hotel/us/example.html?")
    assert "checkin=2026-11-24" in url
    assert "checkout=2026-11-25" in url
    assert "old=tracking" not in url
    assert "#" not in url


def test_price_entry_uses_search_for_name_only_reference() -> None:
    request = _request()
    request = replace(request, query=replace(request.query, property_reference="Hotel Test"))

    url, kind = _price_entry_url(request)

    assert kind == "search"
    assert url.startswith("https://www.booking.com/searchresults.html?")
