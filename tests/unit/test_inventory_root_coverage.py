"""Only an exhausted, identity-bound Active page can prove root coverage."""

from __future__ import annotations

import copy
import json

import pytest

from booksaver.infrastructure.browser.inventory_root_coverage import verified_active_trip_urls


def evidence():
    args = {"input": {"headerSize": [{"height": 378, "width": 672}],
                      "pagination": {"paginationToken": None, "rowsPerPage": 10},
                      "stages": ["CURRENT", "UPCOMING"]}}
    page = {"__typename": "GetTripsList", "trips": [{"__ref": "Trip:11"}, {"__ref": "Trip:22"}],
            "backfillStatus": None,
            "nextPageData": {"__typename": "PaginationData", "paginationToken": None}}
    return {"selected_active": True, "store": {
        "ROOT_QUERY": {"__typename": "Query", "tripsQueries": {
            "__typename": "TripsQueries", "getTrips(" + json.dumps(args) + ")": page}},
        **{f"Trip:{identity}": {"__typename": "Trip", "id": identity,
            "numberOfReservations": 4, "numberOfNonCancelledReservations": 4, "canceled": False}
           for identity in ("11", "22")}},
        "links": [{"url": f"https://secure.booking.com/mytrips.html?trip_id={identity}&aid=123",
                   "booking_count": 4} for identity in ("11", "22")]}


def queries(value):
    return value["store"]["ROOT_QUERY"]["tripsQueries"]


def page(value):
    return next(v for k, v in queries(value).items() if k != "__typename")


def change_args(value, change):
    q = queries(value)
    key = next(k for k in q if k != "__typename")
    args = json.loads(key[9:-1])
    change(args["input"])
    q["getTrips(" + json.dumps(args) + ")"] = q.pop(key)


def test_actual_shape_binds_original_rendered_urls_and_ignores_unreferenced_cache_history():
    value = evidence()
    value["store"]["Trip:33"] = {"__typename": "Trip", "id": "33"}
    before = copy.deepcopy(value)
    assert verified_active_trip_urls(value) == tuple(x["url"] for x in value["links"])
    assert value == before


def test_explicit_empty_cache_returns_empty_but_missing_cache_does_not():
    value = evidence()
    page(value)["trips"] = []
    value["links"] = []
    assert verified_active_trip_urls(value) == ()
    del page(value)["nextPageData"]
    assert verified_active_trip_urls(value) is None


@pytest.mark.parametrize("change", [
    lambda v: v.update(selected_active=False),
    lambda v: v.update(selected_active=1),
    lambda v: page(v).pop("backfillStatus"),
    lambda v: page(v).update(backfillStatus="PENDING"),
    lambda v: page(v).update(nextPageData=None),
    lambda v: page(v)["nextPageData"].pop("paginationToken"),
    lambda v: page(v)["nextPageData"].update(paginationToken="next-private-token"),
    lambda v: page(v)["nextPageData"].update(__typename="Other"),
    lambda v: page(v).update(__typename="Other"),
    lambda v: queries(v).update(other={}),
    lambda v: change_args(v, lambda a: a.update(stages=["CURRENT"])),
    lambda v: change_args(v, lambda a: a.update(stages=["CURRENT", "UPCOMING", "CANCELED"])),
    lambda v: change_args(v, lambda a: a.update(stages=["UPCOMING", "UPCOMING"])),
    lambda v: change_args(v, lambda a: a.update(extraFilter="private")),
    lambda v: change_args(v, lambda a: a["pagination"].pop("paginationToken")),
    lambda v: change_args(v, lambda a: a["pagination"].update(paginationToken="later")),
    lambda v: change_args(v, lambda a: a["pagination"].update(rowsPerPage=True)),
    lambda v: change_args(v, lambda a: a["pagination"].update(rowsPerPage=1)),
    lambda v: change_args(v, lambda a: a["pagination"].update(rowsPerPage=26)),
    lambda v: change_args(v, lambda a: a.update(headerSize=[{"width": 1}])),
])
def test_partial_or_ambiguous_query_never_supplies_coverage(change):
    value = evidence()
    change(value)
    assert verified_active_trip_urls(value) is None


@pytest.mark.parametrize("change", [
    lambda v: page(v)["trips"].append({"__ref": "Trip:11"}),
    lambda v: page(v)["trips"][1].update(__ref="Trip:11"),
    lambda v: page(v)["trips"][0].update(__ref="Other:11"),
    lambda v: page(v)["trips"][0].update(__ref="Trip:private"),
    lambda v: v["store"].pop("Trip:11"),
    lambda v: v["store"]["Trip:11"].update(id="22"),
    lambda v: v["store"]["Trip:11"].update(id=11),
    lambda v: v["store"]["Trip:11"].update(canceled=True),
    lambda v: v["store"]["Trip:11"].pop("canceled"),
    lambda v: v["store"]["Trip:11"].update(numberOfReservations=3),
    lambda v: v["store"]["Trip:11"].update(numberOfNonCancelledReservations=3),
    lambda v: v["store"]["Trip:11"].update(numberOfReservations=True),
    lambda v: v["links"].pop(),
    lambda v: v["links"].append(dict(v["links"][0])),
    lambda v: v["links"][1].update(url=v["links"][0]["url"]),
    lambda v: v["links"][0].update(booking_count=True),
    lambda v: v["links"][0].update(booking_count=None),
])
def test_every_unique_trip_identity_and_card_count_must_match(change):
    value = evidence()
    change(value)
    assert verified_active_trip_urls(value) is None


@pytest.mark.parametrize("url", [
    "https://example.com/mytrips.html?trip_id=11",
    "http://secure.booking.com/mytrips.html?trip_id=11",
    "https://secure.booking.com:443/mytrips.html?trip_id=11",
    "https://user@secure.booking.com/mytrips.html?trip_id=11",
    "https://secure.booking.com/confirmation.html?auth_key=private",
    "https://secure.booking.com/mytrips.html?trip_id=11&trip_id=11",
    "https://secure.booking.com/mytrips.html?trip_id=11&scope=past",
    "https://secure.booking.com/mytrips.html?trip_id=11&filter=private",
    "https://secure.booking.com/mytrips.html?trip_id=11#fragment",
    "https://secure.booking.com/mytrips.html?trip_id=33",
    "https://secure.booking.com/mytrips.html?id=11",
])
def test_unqualified_or_unbound_rendered_links_are_not_substituted(url):
    value = evidence()
    value["links"][0]["url"] = url
    assert verified_active_trip_urls(value) is None


def test_duplicate_json_members_and_multiple_gettrips_queries_are_rejected():
    value = evidence()
    q = queries(value)
    key = next(k for k in q if k != "__typename")
    q[key.replace('"stages":', '"stages": ["PAST"], "stages":')] = q.pop(key)
    assert verified_active_trip_urls(value) is None
    value = evidence()
    q = queries(value)
    key = next(k for k in q if k != "__typename")
    q[key.replace('"CURRENT"', '"PAST"')] = copy.deepcopy(q[key])
    assert verified_active_trip_urls(value) is None


@pytest.mark.parametrize("value", [None, [], {}, {"selected_active": True, "store": []},
                                  {"selected_active": True, "store": {}, "links": []}])
def test_malformed_inputs_fail_closed(value):
    assert verified_active_trip_urls(value) is None


def test_bounded_and_private_on_rejection(caplog, capsys):
    value = evidence()
    value["store"].update({f"Trip:{n}": {} for n in range(200)})
    assert verified_active_trip_urls(value) is None
    value = evidence()
    q = queries(value)
    item = page(value)
    q.clear()
    q.update(__typename="TripsQueries")
    q["getTrips(" + "private" * 1_000 + ")"] = item
    assert verified_active_trip_urls(value) is None
    assert caplog.text == ""
    assert capsys.readouterr() == ("", "")
