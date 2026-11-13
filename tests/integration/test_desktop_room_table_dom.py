"""Intent 041: the price reader on Booking.com's desktop room table, in a real browser DOM.

The markup mirrors what public desktop property pages served on 2026-11-12: the room cell spans
its rates' rows, and the displayed price sits inside aria-hidden markup.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from playwright.sync_api import Page, sync_playwright

from booksaver.infrastructure.browser.jev_page_snapshot import (
    OFFER_SNAPSHOT_JS,
    OfferPageSnapshot,
    parse_offer_snapshot,
)
from booksaver.infrastructure.browser.jev_price_executor import _ground_total, _price_options

URL = "https://www.booking.com/hotel/nl/synthetic.html?group_adults=2&no_rooms=1"


def _row(room: str, people: int, price: str, conditions: str) -> str:
    room_cell = (
        f'<th class="hprt-table-cell hprt-table-cell-roomtype" rowspan="2">'
        f"<a><span>{room}</span></a><div>1 full bed</div></th>"
        if room
        else ""
    )
    return f"""<tr>{room_cell}
      <td class="hprt-table-cell hprt-table-cell-occupancy"><span>Max. people: {people}</span></td>
      <td class="hprt-table-cell hprt-table-cell-price">{price}
        <div aria-hidden="true">2 nights</div>
        <div style="display:none"><div>Total before taxes</div><div>€ 330.92</div></div>
        <div>Includes taxes and charges</div></td>
      <td class="hprt-table-cell hprt-table-cell-conditions"><ul>
        <li><span>Very good</span> breakfast € 24.50</li>{conditions}</ul></td>
      <td class="hprt-table-cell hprt-table-room-select"><label>Select Rooms</label>
        <select><option>0</option><option>1 (€ 331)</option><option>2 (€ 662)</option></select>
      </td></tr>"""


DISCOUNTED = """<span>€ 165</span><span>per night</span>
  <div aria-hidden="true"><div style="text-decoration: line-through">€ 360</div>
  <div><span>€ 331</span></div><span>Original price € 360 Current price € 331</span></div>"""
PLAIN = """<span>€ 194</span><span>per night</span>
  <div><div aria-hidden="true"><span>€ 387</span></div><span>Price € 387</span></div>"""
SINGLE = """<span>€ 150</span><span>per night</span>
  <div><div aria-hidden="true"><span>€ 300</span></div><span>Price € 300</span></div>"""
TABLE = (
    '<h2>Hotel Synthetic</h2><table id="hprt-table"><tbody>'
    + _row("Double Room", 2, DISCOUNTED, "<li>Non-refundable</li>")
    + _row("", 2, PLAIN, "<li><span>Free cancellation</span> <span>before January 10</span></li>")
    + _row("Twin Room", 1, SINGLE, "<li>Free cancellation</li>")
    + _row("", 2, PLAIN, "<li>Free cancellation</li>")
    + "</tbody></table>"
)
CARDS = """<h2>Hotel Synthetic</h2>
<div data-testid="room-card"><h3>Double Room</h3><div>1 full bed</div>
  <div data-testid="rate-card"><div>Free cancellation</div><div>€ 178</div><div>per night</div>
    <div>€ 356</div><div>Original price € 387 Current price € 356</div>
    <div aria-hidden="true">€ 999</div></div>
</div>"""


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser.new_page()
        browser.close()


def _read(page: Page, body: str) -> OfferPageSnapshot:
    page.route(URL, lambda route: route.fulfill(content_type="text/html; charset=utf-8", body=body))
    page.goto(URL)
    snapshot = parse_offer_snapshot(page.evaluate(OFFER_SNAPSHOT_JS))
    page.unroute(URL)
    assert snapshot is not None
    return snapshot


def test_room_table_is_read_as_rooms_with_their_rates(page: Page) -> None:
    rooms = _read(page, TABLE).rooms
    assert [room.lines[0] for room in rooms] == ["Double Room", "Twin Room"]
    # Twin Room's first row is for one guest; the search is for two.
    assert [len(room.rates) for room in rooms] == [2, 1]
    discounted, plain = rooms[0].rates
    assert discounted == (
        "Max. people: 2", "€ 165", "per night", "€ 331",
        "Original price € 360 Current price € 331", "2 nights", "Includes taxes and charges",
        "Very good", "Non-refundable", "Select Rooms",
    )
    assert plain[1:5] == ("€ 194", "per night", "€ 387", "Price € 387")
    assert plain[-4:-1] == ("Very good", "Free cancellation", "before January 10")
    assert rooms[1].rates[0][1:5] == plain[1:5]


def test_table_rates_ground_to_their_whole_stay_total(page: Page) -> None:
    discounted, plain = _read(page, TABLE).rooms[0].rates
    for rate, choice, expected in ((discounted, "p4", "331"), (plain, "p4", "387")):
        total, reason = _ground_total(choice, rate, _price_options(rate), "EUR", 2)
        assert reason == "ok" and total is not None and total.amount == Decimal(expected)


def test_rate_cards_are_read_as_before_even_beside_a_room_table(page: Page) -> None:
    expected = (
        (
            ("Double Room", "1 full bed"),
            (("Free cancellation", "€ 178", "per night", "€ 356",
              "Original price € 387 Current price € 356"),),
        ),
    )
    for body in (CARDS, CARDS + TABLE):
        rooms = _read(page, body).rooms
        assert tuple((room.lines, room.rates) for room in rooms) == expected
