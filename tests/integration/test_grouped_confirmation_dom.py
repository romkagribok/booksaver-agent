"""Exercise the actual rendered-header reader against browser DOM ordering and icon markup."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, sync_playwright

from booksaver.infrastructure.browser.grouped_inventory_reader import _READ

HOTEL = 'https://www.booking.com/hotel/lt/synthetic.en-us.html'


@pytest.fixture(scope='module')
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser.new_page()
        browser.close()


def read(page: Page, content: str):
    page.set_content(content)
    return json.loads(page.evaluate(_READ))['hotels']


def test_fragmented_confirmation_heading_binds_only_actual_property(page: Page):
    content = f'''
    <a href="{HOTEL}">Unrelated previous recommendation</a>
    <h1>Your stay <span aria-hidden="true"><svg></svg></span>is confirmed</h1>
    <span><a href="{HOTEL}">Synthetic Hotel</a><span>Address omitted</span></span>
    <h3>Check-in</h3><p>Fri, Oct 23, 2026</p>
    <div hidden>Check-in</div>
    <a href="{HOTEL}">Children and extra beds policies</a>
    '''
    assert read(page, content) == [{'url': HOTEL, 'text': 'Synthetic Hotel'}]


@pytest.mark.parametrize('extra', ['<h1>Your stay is confirmed</h1>', '<h3>Check-in</h3>'])
def test_ambiguous_visible_header_does_not_supply_property(page: Page, extra: str):
    assert read(page, f'<h1>Your stay is confirmed</h1><a href="{HOTEL}">Hotel</a>'
                f'<h3>Check-in</h3>{extra}') == []


def test_link_after_checkin_is_not_property_evidence(page: Page):
    assert read(page, f'<h1>Your stay is confirmed</h1><h3>Check-in</h3>'
                f'<a href="{HOTEL}">Policy</a>') == []


def test_multiple_header_properties_remain_ambiguous_for_parser(page: Page):
    result = read(page, f'<h1>Your stay is confirmed</h1><a href="{HOTEL}">One</a>'
                  f'<a href="{HOTEL}">Two</a><h3>Check-in</h3>')
    assert len(result) == 2


def test_trip_count_is_read_from_its_element_not_concatenated_dates(page: Page):
    page.set_content('<a href="https://secure.booking.com/mytrips.html?trip_id=1">'
                     '<span>Europe</span><span>Sep 13 – Sep 19</span><span>4 bookings</span></a>')
    link = json.loads(page.evaluate(_READ))['links'][0]
    assert link['text'].endswith('Sep 194 bookings')
    assert link['booking_count'] == 4


def test_conflicting_rendered_trip_counts_stay_unknown(page: Page):
    page.set_content('<a href="https://secure.booking.com/mytrips.html?trip_id=1">'
                     '<span>4 bookings</span><span>5 bookings</span></a>')
    assert json.loads(page.evaluate(_READ))['links'][0]['booking_count'] is None


def test_hidden_trip_count_does_not_override_visible_evidence(page: Page):
    page.set_content('<a href="https://secure.booking.com/mytrips.html?trip_id=1">'
                     '<span>4 bookings</span><span hidden>5 bookings</span></a>')
    assert json.loads(page.evaluate(_READ))['links'][0]['booking_count'] == 4
