import pytest

from booksaver.domain.value_objects import Occupancy


class TestOccupancy:
    def test_valid_occupancy(self):
        occ = Occupancy(adults=2, children=1, rooms=1)
        assert (occ.adults, occ.children, occ.rooms) == (2, 1, 1)

    def test_defaults_children_zero_rooms_one(self):
        occ = Occupancy(adults=1)
        assert occ.children == 0
        assert occ.rooms == 1

    def test_zero_adults_rejected(self):
        with pytest.raises(ValueError, match="at least 1 adult"):
            Occupancy(adults=0)

    def test_negative_children_rejected(self):
        with pytest.raises(ValueError, match="children"):
            Occupancy(adults=2, children=-1)

    def test_zero_rooms_rejected(self):
        with pytest.raises(ValueError, match="at least 1 room"):
            Occupancy(adults=2, rooms=0)

    def test_string_format_for_cli_display(self):
        assert str(Occupancy(adults=2, children=1, rooms=2)) == "2+1/2"
