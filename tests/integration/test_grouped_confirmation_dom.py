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


def coverage_dom(*, size=2, position=2, selected='true', extra=''):
    return f'''
    <button role="tab" aria-selected="{selected}" aria-controls="active-panel">Active</button>
    <div id="active-panel"><div role="list">
      <div role="listitem" aria-setsize="{size}" aria-posinset="1">
        <a href="https://secure.booking.com/mytrips.html?trip_id=1">One</a></div>
      <div role="listitem" aria-setsize="{size}" aria-posinset="{position}">
        <a href="https://secure.booking.com/mytrips.html?trip_id=2">Two</a></div>
    </div>{extra}</div>'''


def test_accessible_total_is_positive_root_coverage_evidence(page: Page):
    page.set_content(coverage_dom())
    assert json.loads(page.evaluate(_READ))['activeRootTotal'] == 2


@pytest.mark.parametrize('kwargs', [
    {'size': 3}, {'position': 1}, {'selected': 'false'},
    {'extra': '<button>Load more</button>'},
    {'extra': '<span role="progressbar">Loading</span>'},
    {'extra': '<span aria-busy="true">Loading</span>'},
])
def test_incomplete_accessible_list_never_supplies_root_proof(page: Page, kwargs):
    page.set_content(coverage_dom(**kwargs))
    assert json.loads(page.evaluate(_READ))['activeRootTotal'] is None


def test_empty_root_requires_selected_active_panel_and_explicit_empty_text(page: Page):
    page.set_content('''
    <button role="tab" aria-selected="true" aria-controls="panel">Active</button>
    <div id="panel">You haven't started any trips yet.
    Once you make a booking, it'll appear here.</div>''')
    assert json.loads(page.evaluate(_READ))['activeRootTotal'] == 0
    page.locator('button').evaluate("e => e.setAttribute('aria-selected','false')")
    assert json.loads(page.evaluate(_READ))['activeRootTotal'] is None


def test_cancellation_status_must_be_a_unique_rendered_heading(page: Page):
    page.set_content('<p>Your booking is cancelled</p><p>Confirmation number: 123456</p>')
    assert not json.loads(page.evaluate(_READ))['cancelledHeader']
    page.set_content('<h1>Your booking is cancelled</h1><p>Confirmation number: 123456</p>')
    assert json.loads(page.evaluate(_READ))['cancelledHeader']
    page.set_content('<h1>Your booking is cancelled</h1><h2>Your stay is confirmed</h2>')
    assert not json.loads(page.evaluate(_READ))['cancelledHeader']


def active_cache_markup(*, token=None, extra_script=False, busy=False):
    query = 'getTrips(' + json.dumps({'input': {
        'stages': ['CURRENT', 'UPCOMING'],
        'pagination': {'paginationToken': None, 'rowsPerPage': 10},
    }}) + ')'
    store = {'ROOT_QUERY': {'__typename': 'Query', 'tripsQueries': {
        '__typename': 'TripsQueries', query: {
            '__typename': 'GetTripsList', 'trips': [{'__ref': 'Trip:100'}],
            'backfillStatus': None,
            'nextPageData': {'__typename': 'PaginationData', 'paginationToken': token},
        },
    }}, 'Trip:100': {'__typename': 'Trip', 'id': '100', 'numberOfReservations': 2,
                    'numberOfNonCancelledReservations': 2, 'canceled': False}}
    script = ('<script type="application/json" data-capla-store-data="apollo" '
              'data-capla-namespace="b-trips-frontend-trip-xp-mfeGfJLPGNT">'
              + json.dumps(store) + '</script>')
    return ('''<div id="mytrips-mfe">
      <button role="tab" aria-selected="true" aria-controls="active">Active</button>
      <div role="tabpanel" id="active"><a
        href="https://secure.booking.com/mytrips.html?trip_id=100">
        <span>Trip</span><span>2 bookings</span></a>'''
            + ('<div aria-busy="true"></div>' if busy else '')
            + '</div></div>' + script + (script if extra_script else ''))


def test_actual_page_cache_contract_binds_exhaustion_to_rendered_active_trips(page: Page):
    from booksaver.infrastructure.browser.inventory_root_coverage import verified_active_trip_urls
    page.set_content(active_cache_markup())
    evidence = json.loads(page.evaluate(_READ))['activeRootEvidence']
    assert verified_active_trip_urls(evidence) == (
        'https://secure.booking.com/mytrips.html?trip_id=100',
    )


@pytest.mark.parametrize('kwargs', [
    {'token': 'another-page'}, {'extra_script': True}, {'busy': True},
])
def test_pending_or_ambiguous_page_cache_never_grants_retirement(page: Page, kwargs):
    from booksaver.infrastructure.browser.inventory_root_coverage import verified_active_trip_urls
    page.set_content(active_cache_markup(**kwargs))
    evidence = json.loads(page.evaluate(_READ))['activeRootEvidence']
    assert verified_active_trip_urls(evidence) is None
