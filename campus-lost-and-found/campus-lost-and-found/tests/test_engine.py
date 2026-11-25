"""Tests for business logic, matching algorithms, and analytics in engine.py."""

import pytest
from datetime import date, timedelta
from models import ItemRecord
from engine import (
    compute_summary,
    find_potential_matches,
    generate_next_id,
    get_overdue_records,
    is_overdue,
    mark_as_claimed,
    search_records,
)


@pytest.fixture
def sample_records() -> list[ItemRecord]:
    """Provides a balanced sample of LOST and FOUND records."""
    today = date.today()
    return [
        ItemRecord(
            record_id="LST-0001",
            record_type="LOST",
            item_name="HP Laptop Charger",
            category="Electronics",
            location="Computer Lab 2",
            date_reported=(today - timedelta(days=2)).isoformat(),
            description="Black 65W charger with blue tip",
            contact="arjun.mehta@mrtc.edu.in",
            status="OPEN",
            date_claimed=None,
        ),
        ItemRecord(
            record_id="LST-0002",
            record_type="LOST",
            item_name="Student ID Card",
            category="ID & Cards",
            location="Main Library",
            date_reported=(today - timedelta(days=20)).isoformat(),
            description="Card for Priya Sharma",
            contact="9876543210",
            status="OPEN",
            date_claimed=None,
        ),
        ItemRecord(
            record_id="LST-0003",
            record_type="LOST",
            item_name="Hostel Room Key",
            category="Keys & Bottles",
            location="Basketball Court",
            date_reported=(today - timedelta(days=10)).isoformat(),
            description="Single brass key on red lanyard",
            contact="9123456780",
            status="CLAIMED",
            date_claimed=(today - timedelta(days=8)).isoformat(),
        ),
        ItemRecord(
            record_id="FND-0001",
            record_type="FOUND",
            item_name="Wireless Earbuds Case",
            category="Electronics",
            location="Canteen",
            date_reported=(today - timedelta(days=1)).isoformat(),
            description="White round charging case",
            contact="kavya.nair@mrtc.edu.in",
            status="OPEN",
            date_claimed=None,
        ),
        ItemRecord(
            record_id="FND-0002",
            record_type="FOUND",
            item_name="HP Charger",
            category="Electronics",
            location="Computer Lab 2",
            date_reported=(today - timedelta(days=2)).isoformat(),
            description="Black power adapter found near back row",
            contact="9988776655",
            status="OPEN",
            date_claimed=None,
        ),
    ]


class TestGenerateNextId:
    """Tests for generate_next_id with empty and non-empty records."""

    def test_empty_records(self):
        assert generate_next_id([], "LOST") == "LST-0001"
        assert generate_next_id([], "FOUND") == "FND-0001"

    def test_incrementing_per_type(self, sample_records):
        assert generate_next_id(sample_records, "LOST") == "LST-0004"
        assert generate_next_id(sample_records, "FOUND") == "FND-0003"

    def test_case_insensitive_type(self, sample_records):
        assert generate_next_id(sample_records, "lost") == "LST-0004"
        assert generate_next_id(sample_records, "found") == "FND-0003"

    def test_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid record_type"):
            generate_next_id([], "UNKNOWN")


class TestFindPotentialMatches:
    """Tests for multi-attribute matching and fuzzy scoring."""

    def test_exact_and_fuzzy_match(self, sample_records):
        # A newly lost HP laptop charger should strongly match FND-0002 (HP Charger in same lab)
        today = date.today().isoformat()
        new_lost = ItemRecord(
            record_id="LST-0099",
            record_type="LOST",
            item_name="HP Laptop Charger 65W",
            category="Electronics",
            location="Computer Lab 2",
            date_reported=today,
            description="Black adapter",
            contact="test@mrtc.edu.in",
        )
        matches = find_potential_matches(new_lost, sample_records)
        assert len(matches) >= 1
        assert matches[0].record_id == "FND-0002"

    def test_opposite_type_requirement(self, sample_records):
        # A LOST item must NOT match another LOST item even with identical details
        new_lost = ItemRecord(
            record_id="LST-0099",
            record_type="LOST",
            item_name="Student ID Card",
            category="ID & Cards",
            location="Main Library",
            date_reported=date.today().isoformat(),
            description="Priya Sharma",
            contact="test@mrtc.edu.in",
        )
        matches = find_potential_matches(new_lost, sample_records)
        # LST-0002 is also LOST, so it should not be returned
        assert not any(m.record_id == "LST-0002" for m in matches)

    def test_claimed_items_are_excluded(self, sample_records):
        # LST-0003 is CLAIMED; a new FOUND brass key must not match it
        new_found = ItemRecord(
            record_id="FND-0099",
            record_type="FOUND",
            item_name="Hostel Room Key",
            category="Keys & Bottles",
            location="Basketball Court",
            date_reported=date.today().isoformat(),
            description="Brass key on lanyard",
            contact="test@mrtc.edu.in",
        )
        matches = find_potential_matches(new_found, sample_records)
        assert not any(m.record_id == "LST-0003" for m in matches)

    def test_empty_records_returns_empty_list(self):
        new_item = ItemRecord(
            record_id="LST-0001",
            record_type="LOST",
            item_name="Water Bottle",
            category="Keys & Bottles",
            location="Gym",
            date_reported=date.today().isoformat(),
            description="Blue bottle",
            contact="test@mrtc.edu.in",
        )
        assert find_potential_matches(new_item, []) == []

    def test_dissimilar_records_below_threshold(self, sample_records):
        # Completely different category, location, and title
        new_lost = ItemRecord(
            record_id="LST-0099",
            record_type="LOST",
            item_name="Woolen Scarf",
            category="Clothing & Accessories",
            location="Auditorium",
            date_reported=date.today().isoformat(),
            description="Red scarf",
            contact="test@mrtc.edu.in",
        )
        matches = find_potential_matches(new_lost, sample_records)
        assert len(matches) == 0


class TestOverdueRecords:
    """Tests for is_overdue and get_overdue_records."""

    def test_is_overdue_boundary(self, sample_records):
        # LST-0001 reported 2 days ago -> False
        assert is_overdue(sample_records[0]) is False
        # LST-0002 reported 20 days ago and OPEN -> True
        assert is_overdue(sample_records[1]) is True
        # LST-0003 reported 10 days ago and CLAIMED -> False
        assert is_overdue(sample_records[2]) is False

    def test_get_overdue_records(self, sample_records):
        overdue = get_overdue_records(sample_records, days=14)
        assert len(overdue) == 1
        assert overdue[0].record_id == "LST-0002"


class TestSearchRecords:
    """Tests for search_records with keywords, category, and status."""

    def test_keyword_search_across_fields(self, sample_records):
        # By item name
        res = search_records(sample_records, keyword="charger")
        assert len(res) == 2

        # By location
        res = search_records(sample_records, keyword="Library")
        assert len(res) == 1
        assert res[0].record_id == "LST-0002"

        # By description
        res = search_records(sample_records, keyword="adapter")
        assert len(res) == 1
        assert res[0].record_id == "FND-0002"

    def test_search_with_none_description(self):
        rec = ItemRecord(
            record_id="LST-0001",
            record_type="LOST",
            item_name="Notebook",
            category="Books & Stationery",
            location="Room 1",
            date_reported="2026-11-20",
            description="",
            contact="test@mrtc.edu.in",
        )
        rec.description = None  # Force None
        res = search_records([rec], keyword="notebook")
        assert len(res) == 1

    def test_category_and_status_filters(self, sample_records):
        res = search_records(sample_records, category="Electronics", status="OPEN")
        assert len(res) == 3
        assert all(r.category == "Electronics" and r.status == "OPEN" for r in res)

    def test_no_matches_returns_empty_list(self, sample_records):
        res = search_records(sample_records, keyword="nonexistent-item-query")
        assert res == []


class TestMarkAsClaimed:
    """Tests for mark_as_claimed lifecycle transitions."""

    def test_mark_open_record(self, sample_records):
        assert mark_as_claimed(sample_records, "LST-0001") is True
        rec = next(r for r in sample_records if r.record_id == "LST-0001")
        assert rec.status == "CLAIMED"
        assert rec.date_claimed == date.today().isoformat()

    def test_mark_already_claimed_record(self, sample_records):
        assert mark_as_claimed(sample_records, "LST-0003") is False

    def test_mark_nonexistent_record(self, sample_records):
        assert mark_as_claimed(sample_records, "NON-EXISTENT") is False


class TestComputeSummary:
    """Tests for aggregate analytics computation."""

    def test_summary_metrics(self, sample_records):
        summary = compute_summary(sample_records)
        assert summary["total"] == 5
        assert summary["lost"] == 3
        assert summary["found"] == 2
        assert summary["claimed"] == 1
        assert summary["open"] == 4
        assert summary["overdue"] == 1
        assert summary["claim_rate"] == 20.0
        assert summary["avg_resolution_days"] == 2.0
        assert "Electronics" in summary["by_category"]
        assert summary["by_category"]["Electronics"] == 3

    def test_summary_empty_records(self):
        summary = compute_summary([])
        assert summary["total"] == 0
        assert summary["claim_rate"] == 0.0
        assert summary["avg_resolution_days"] == 0.0
        assert summary["overdue"] == 0
