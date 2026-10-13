"""F02 listing rules LI1 to LI8.

Every expected value comes from docs/specs/F02.md; each test names the rule it checks.
"""

from datetime import timedelta
from urllib.parse import quote

import pytest
from f02_helpers import NOW, call, iso, login


def listing(client, query=""):
    response = call(client, "GET", "/bookings" + query)
    assert response.status_code == 200, response.get_json()
    assert response.content_type == "application/json"
    return response.get_json()


def ids(client, query=""):
    return [item["id"] for item in listing(client, query)["items"]]


def fields(client, query):
    response = call(client, "GET", "/bookings" + query)
    assert response.status_code == 400
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["error"] == "validation_failed"
    return body["fields"]


def set_state(db, booking_id, state):
    db.execute("UPDATE bookings SET state = %s WHERE id = %s", (state, booking_id))


@pytest.fixture
def three(make_booking, clock):
    """Three bookings submitted an hour apart: oldest first in this list."""
    made = []
    for index, (day, number) in enumerate([(3, 1), (1, 2), (2, 3)]):
        clock.now = NOW + timedelta(minutes=index)
        made.append(make_booking(day, number))
    return made


# --- LI7 and LI8: the response


def test_li7_empty_list(admin_client):
    assert listing(admin_client) == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_li8_item_holds_exactly_the_listed_fields(admin_client, make_booking):
    booking_id = make_booking(1, 1, details="Birthday party", guest_count=75)

    body = listing(admin_client)

    assert body["total"] == 1
    assert body["items"] == [
        {
            "id": booking_id,
            "state": "submitted",
            "name": "Person 1",
            "email": "person1@example.com",
            "phone": "07700 900001",
            "guest_count": 75,
            "starts_at": "2026-04-01T10:00",
            "ends_at": "2026-04-01T14:00",
            "details": "Birthday party",
            "submitted_at": iso(NOW),
            "auto_declined": False,
        }
    ]


def test_li8_details_are_null_when_the_client_gave_none(admin_client, make_booking):
    make_booking(1, 1)

    assert listing(admin_client)["items"][0]["details"] is None


def test_li8_times_are_london_local_times_in_winter_and_summer(admin_client, make_booking, clock):
    # Submitted in winter time; the booking itself is in summer time.
    clock.now = NOW.replace(hour=23, minute=45)
    make_booking(1, 1, starts_at="2026-04-01T00:30", ends_at="2026-04-01T02:00")
    login(admin_client)

    item = listing(admin_client)["items"][0]

    assert item["starts_at"] == "2026-04-01T00:30"
    assert item["ends_at"] == "2026-04-01T02:00"
    assert item["submitted_at"] == "2026-03-10T23:45"


def test_li8_text_is_exactly_as_stored(admin_client, make_booking):
    name = "<script>alert('x')</script> O'Brien & Sons"
    details = "Tom & Jerry <b>party</b>\nsecond line"
    make_booking(1, 1, name=name, details=details)

    item = listing(admin_client)["items"][0]

    assert item["name"] == name
    assert item["details"] == details


def test_li8_network_address_is_not_included(admin_client, make_booking):
    make_booking(1, 1)

    response = call(admin_client, "GET", "/bookings")

    assert response.status_code == 200
    assert len(response.get_json()["items"]) == 1
    assert "198.51.100." not in response.get_data(as_text=True)
    assert "client_ip" not in response.get_data(as_text=True)


# --- LI4: sorting


def test_li4_default_is_newest_submitted_first(admin_client, three):
    oldest, middle, newest = three

    assert ids(admin_client) == [newest, middle, oldest]


def test_li4_sort_by_submitted_at_in_both_directions(admin_client, three):
    oldest, middle, newest = three

    assert ids(admin_client, "?sort=submitted_at&order=asc") == [oldest, middle, newest]
    assert ids(admin_client, "?sort=submitted_at&order=desc") == [newest, middle, oldest]
    assert ids(admin_client, "?order=asc") == [oldest, middle, newest]


def test_li4_sort_by_starts_at(admin_client, three):
    day_3, day_1, day_2 = three

    assert ids(admin_client, "?sort=starts_at&order=asc") == [day_1, day_2, day_3]
    assert ids(admin_client, "?sort=starts_at") == [day_3, day_2, day_1]


def test_li4_sort_by_name_ignores_letter_case(admin_client, make_booking):
    carol = make_booking(1, 1, name="carol")
    alice = make_booking(2, 2, name="alice")
    bob = make_booking(3, 3, name="Bob")

    assert ids(admin_client, "?sort=name&order=asc") == [alice, bob, carol]
    assert ids(admin_client, "?sort=name&order=desc") == [carol, bob, alice]


def test_li4_equal_values_are_ordered_by_id_in_the_same_direction(admin_client, make_booking):
    first = make_booking(1, 1, name="Same Name")
    second = make_booking(2, 2, name="same name")
    third = make_booking(3, 3, name="SAME NAME")

    assert ids(admin_client, "?sort=name&order=asc") == [first, second, third]
    assert ids(admin_client, "?sort=name&order=desc") == [third, second, first]
    # All three were submitted at the same instant.
    assert ids(admin_client) == [third, second, first]
    assert ids(admin_client, "?order=asc") == [first, second, third]


@pytest.mark.parametrize(
    "query, expected",
    [
        pytest.param("?sort=email", {"sort": "invalid"}, id="unknown-sort"),
        pytest.param("?sort=id", {"sort": "invalid"}, id="sort-by-id"),
        pytest.param("?sort=NAME", {"sort": "invalid"}, id="sort-in-capitals"),
        pytest.param("?sort=", {"sort": "invalid"}, id="empty-sort"),
        pytest.param("?order=up", {"order": "invalid"}, id="unknown-order"),
        pytest.param("?order=ASC", {"order": "invalid"}, id="order-in-capitals"),
        pytest.param(
            "?sort=" + quote("name;DROP TABLE bookings") + "&order=x",
            {"sort": "invalid", "order": "invalid"},
            id="both",
        ),
    ],
)
def test_li4_bad_sort_or_order_is_refused(admin_client, query, expected):
    assert fields(admin_client, query) == expected


# --- LI1: state filter


@pytest.fixture
def one_per_state(make_booking, db):
    made = {}
    for day, state in enumerate(["submitted", "contacted", "accepted", "declined"], start=1):
        made[state] = make_booking(day, day)
        set_state(db, made[state], state)
    return made


@pytest.mark.parametrize("state", ["submitted", "contacted", "accepted", "declined"])
def test_li1_state_filter_lists_only_that_state(admin_client, one_per_state, state):
    body = listing(admin_client, f"?state={state}")

    assert [item["id"] for item in body["items"]] == [one_per_state[state]]
    assert body["items"][0]["state"] == state
    assert body["total"] == 1


def test_li1_without_a_filter_every_state_is_listed_declined_included(admin_client, one_per_state):
    body = listing(admin_client)

    assert body["total"] == 4
    assert {item["state"] for item in body["items"]} == {
        "submitted",
        "contacted",
        "accepted",
        "declined",
    }


@pytest.mark.parametrize("state", ["cancelled", "Accepted", "", "submitted,accepted", "1"])
def test_li1_unknown_state_is_refused(admin_client, state):
    assert fields(admin_client, f"?state={state}") == {"state": "invalid"}


# --- LI2: date filter


@pytest.fixture
def april_1_to_5(make_booking):
    return {day: make_booking(day, day) for day in range(1, 6)}


def test_li2_from_and_to_are_inclusive(admin_client, april_1_to_5):
    listed = ids(admin_client, "?from=2026-04-02&to=2026-04-04&sort=starts_at&order=asc")

    assert listed == [april_1_to_5[2], april_1_to_5[3], april_1_to_5[4]]


def test_li2_from_alone(admin_client, april_1_to_5):
    listed = ids(admin_client, "?from=2026-04-04&sort=starts_at&order=asc")

    assert listed == [april_1_to_5[4], april_1_to_5[5]]


def test_li2_to_alone(admin_client, april_1_to_5):
    listed = ids(admin_client, "?to=2026-04-02&sort=starts_at&order=asc")

    assert listed == [april_1_to_5[1], april_1_to_5[2]]


def test_li2_one_day(admin_client, april_1_to_5):
    assert ids(admin_client, "?from=2026-04-03&to=2026-04-03") == [april_1_to_5[3]]


def test_li2_days_are_london_days(admin_client, make_booking):
    # In summer time 00:30 on 1 April in London is 23:30 on 31 March in UTC.
    early = make_booking(1, 1, starts_at="2026-04-01T00:30", ends_at="2026-04-01T02:00")
    # It runs past midnight, but it starts on 2 April: the filter is on the start.
    late = make_booking(2, 2, starts_at="2026-04-02T23:00", ends_at="2026-04-03T01:00")

    assert ids(admin_client, "?from=2026-04-01&to=2026-04-01") == [early]
    assert ids(admin_client, "?to=2026-03-31") == []
    assert ids(admin_client, "?from=2026-04-02&to=2026-04-02") == [late]
    assert ids(admin_client, "?from=2026-04-03") == []


@pytest.mark.parametrize(
    "query, expected",
    [
        pytest.param("?from=2026-4-1", {"from": "invalid"}, id="unpadded"),
        pytest.param("?from=01/04/2026", {"from": "invalid"}, id="uk-format"),
        pytest.param("?from=2026-02-30", {"from": "invalid"}, id="30-february"),
        pytest.param("?from=2026-04-01T10:00", {"from": "invalid"}, id="with-time"),
        pytest.param("?from=", {"from": "invalid"}, id="empty"),
        pytest.param("?to=tomorrow", {"to": "invalid"}, id="word"),
        pytest.param("?to=0000-01-01", {"to": "invalid"}, id="year-0000"),
        pytest.param("?from=x&to=y", {"from": "invalid", "to": "invalid"}, id="both"),
        pytest.param("?from=2026-04-05&to=2026-04-04", {"to": "invalid"}, id="to-before-from"),
    ],
)
def test_li2_bad_dates_are_refused(admin_client, query, expected):
    assert fields(admin_client, query) == expected


# --- LI3: search


@pytest.fixture
def people(make_booking):
    return {
        "alice": make_booking(
            1, 1, name="Alice Smith", email="alice@example.com", phone="07700 900111"
        ),
        "bob": make_booking(
            2, 2, name="Bob Jones", email="bob.j@work.example", phone="07700 900222"
        ),
        "carol": make_booking(
            3, 3, name="Carol Smithson", email="CAROL@Example.com", phone="+44 7700 900-333"
        ),
    }


@pytest.mark.parametrize(
    "search, found",
    [
        pytest.param("smith", ["alice", "carol"], id="name-part-ignoring-case"),
        pytest.param("SMITHSON", ["carol"], id="name-in-capitals"),
        pytest.param("bob.j@work", ["bob"], id="email-part"),
        pytest.param("example.com", ["alice", "carol"], id="email-domain-ignoring-case"),
        pytest.param("900222", ["bob"], id="phone-part"),
        pytest.param("900-333", ["carol"], id="phone-as-stored"),
        pytest.param("07700", ["alice", "bob"], id="phone-prefix-as-stored"),
        pytest.param("  jones  ", ["bob"], id="trimmed"),
        pytest.param("nobody", [], id="no-match"),
        pytest.param("", ["alice", "bob", "carol"], id="empty-means-no-search"),
        pytest.param("   ", ["alice", "bob", "carol"], id="only-spaces-means-no-search"),
    ],
)
def test_li3_search_matches_name_email_or_phone(admin_client, people, search, found):
    listed = ids(admin_client, "?sort=name&order=asc&search=" + quote(search))

    assert listed == [people[key] for key in found]


def test_li3_search_does_not_look_at_details(admin_client, make_booking):
    make_booking(1, 1, details="A zebra themed party")

    assert listing(admin_client, "?search=zebra")["total"] == 0


@pytest.mark.parametrize(
    "search, name_found, name_not_found",
    [
        pytest.param("%25", "100% Fun Ltd", "Hundred Fun Ltd", id="percent"),
        pytest.param("a_b", "a_b events", "axb events", id="underscore"),
        pytest.param("a%5Cb", "a\\b events", "ab events", id="backslash"),
        pytest.param("%25%25", "really 100%% sure", "really 100% sure", id="two-percents"),
    ],
)
def test_li3_wildcard_characters_are_ordinary_characters(
    admin_client, make_booking, search, name_found, name_not_found
):
    wanted = make_booking(1, 1, name=name_found)
    make_booking(2, 2, name=name_not_found)

    assert ids(admin_client, f"?search={search}") == [wanted]


def test_li3_search_of_100_characters_is_accepted(admin_client):
    assert listing(admin_client, "?search=" + "a" * 100)["total"] == 0


def test_li3_search_over_100_characters_is_refused(admin_client):
    assert fields(admin_client, "?search=" + "a" * 101) == {"search": "too_long"}


def test_li3_sql_in_search_is_only_text(admin_client, make_booking, db):
    make_booking(1, 1)

    assert listing(admin_client, "?search=" + quote("' OR 1=1 --"))["total"] == 0
    assert listing(admin_client, "?search=" + quote("'; DROP TABLE bookings; --"))["total"] == 0
    assert db.execute("SELECT count(*) FROM bookings").fetchone()[0] == 1


# --- LI5: pages


@pytest.fixture
def five(make_booking, clock):
    made = []
    for index in range(5):
        clock.now = NOW + timedelta(minutes=index)
        made.append(make_booking(index + 1, index + 1))
    return made  # oldest first


def test_li5_pages_split_the_list(admin_client, five):
    newest_first = list(reversed(five))

    first = listing(admin_client, "?page_size=2")
    second = listing(admin_client, "?page_size=2&page=2")
    third = listing(admin_client, "?page_size=2&page=3")

    assert [item["id"] for item in first["items"]] == newest_first[0:2]
    assert [item["id"] for item in second["items"]] == newest_first[2:4]
    assert [item["id"] for item in third["items"]] == newest_first[4:5]
    assert (first["page"], first["page_size"], first["total"]) == (1, 2, 5)
    assert (third["page"], third["page_size"], third["total"]) == (3, 2, 5)


def test_li5_page_past_the_end_is_empty_not_an_error(admin_client, five):
    assert listing(admin_client, "?page_size=2&page=4") == {
        "items": [],
        "page": 4,
        "page_size": 2,
        "total": 5,
    }


def test_li5_default_page_size_is_20(admin_client, make_booking):
    for day in range(1, 22):
        make_booking(day, day)

    first = listing(admin_client)
    second = listing(admin_client, "?page=2")

    assert (len(first["items"]), first["page_size"], first["total"]) == (20, 20, 21)
    assert len(second["items"]) == 1


def test_li5_page_size_of_100_and_1_are_accepted(admin_client, five):
    assert len(listing(admin_client, "?page_size=100")["items"]) == 5
    assert len(listing(admin_client, "?page_size=1")["items"]) == 1


@pytest.mark.parametrize(
    "query, expected",
    [
        pytest.param("?page=0", {"page": "out_of_range"}, id="page-0"),
        pytest.param("?page=-1", {"page": "invalid"}, id="page-negative"),
        pytest.param("?page=abc", {"page": "invalid"}, id="page-word"),
        pytest.param("?page=1.5", {"page": "invalid"}, id="page-decimal"),
        pytest.param("?page=", {"page": "invalid"}, id="page-empty"),
        pytest.param("?page=%D9%A3", {"page": "invalid"}, id="page-arabic-indic-digit"),
        pytest.param("?page=%2B1", {"page": "invalid"}, id="page-plus-sign"),
        pytest.param("?page_size=0", {"page_size": "out_of_range"}, id="size-0"),
        pytest.param("?page_size=101", {"page_size": "out_of_range"}, id="size-101"),
        pytest.param("?page_size=ten", {"page_size": "invalid"}, id="size-word"),
        pytest.param(
            "?page=0&page_size=1000",
            {"page": "out_of_range", "page_size": "out_of_range"},
            id="both",
        ),
    ],
)
def test_li5_bad_page_values_are_refused(admin_client, query, expected):
    assert fields(admin_client, query) == expected


def test_li5_very_large_page_number_is_an_empty_page(admin_client, five):
    body = listing(admin_client, "?page=" + "9" * 30)

    assert body["items"] == []
    assert body["total"] == 5


# --- LI6: combining


def test_li6_filters_and_search_combine(admin_client, make_booking, db):
    wanted = make_booking(2, 1, name="Alice Smith")
    other_state = make_booking(3, 2, name="Alan Smith")
    set_state(db, other_state, "accepted")
    make_booking(9, 3, name="Anna Smith")  # outside the dates
    make_booking(4, 4, name="Bob Jones")  # not matched by the search

    body = listing(admin_client, "?state=submitted&from=2026-04-01&to=2026-04-05&search=smith")

    assert [item["id"] for item in body["items"]] == [wanted]
    assert body["total"] == 1


def test_li6_total_counts_everything_that_passes_not_just_the_page(admin_client, one_per_state, db):
    for state in ("submitted", "contacted"):
        set_state(db, one_per_state[state], "accepted")

    body = listing(admin_client, "?state=accepted&page_size=2")

    assert len(body["items"]) == 2
    assert body["total"] == 3


def test_li6_unknown_query_parameters_are_ignored(admin_client, five):
    assert listing(admin_client, "?colour=blue&limit=1&offset=3")["total"] == 5
    assert len(listing(admin_client, "?colour=blue&limit=1&offset=3")["items"]) == 5


def test_li6_all_bad_parameters_are_reported_together(admin_client):
    query = "?state=x&from=x&to=x&sort=x&order=x&page=x&page_size=x&search=" + "a" * 101

    assert fields(admin_client, query) == {
        "state": "invalid",
        "from": "invalid",
        "to": "invalid",
        "sort": "invalid",
        "order": "invalid",
        "page": "invalid",
        "page_size": "invalid",
        "search": "too_long",
    }
