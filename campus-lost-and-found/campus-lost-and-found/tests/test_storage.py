"""Tests for storage backends, persistence, concurrency, and error recovery."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from models import ItemRecord
from storage import (
    JsonStorage,
    SQLiteStorage,
    export_to_csv,
    import_from_csv,
    load_records,
    save_records,
)


def create_sample_item(rec_id: str = "LST-0001", name: str = "Laptop") -> ItemRecord:
    """Helper to create a valid ItemRecord."""
    return ItemRecord(
        record_id=rec_id,
        record_type="LOST",
        item_name=name,
        category="Electronics",
        location="Lab 1",
        date_reported="2026-11-20",
        description="Sample description",
        contact="user@mrtc.edu.in",
        status="OPEN",
        date_claimed=None,
    )


class TestJsonStorage:
    """Tests for JsonStorage atomic persistence and recovery."""

    def test_load_missing_file_creates_empty(self, tmp_path):
        target = str(tmp_path / "missing.json")
        storage = JsonStorage(target)
        records = storage.load_records()
        assert records == []
        assert os.path.exists(target)

    def test_save_and_load_roundtrip(self, tmp_path):
        target = str(tmp_path / "records.json")
        storage = JsonStorage(target)
        items = [
            create_sample_item("LST-0001", "Item A"),
            create_sample_item("LST-0002", "Item B"),
        ]
        storage.save_records(items)

        loaded = storage.load_records()
        assert len(loaded) == 2
        assert loaded[0].record_id == "LST-0001"
        assert loaded[1].record_id == "LST-0002"

    def test_corrupted_json_recovery(self, tmp_path):
        target = str(tmp_path / "corrupted.json")
        with open(target, "w", encoding="utf-8") as f:
            f.write("{invalid-json-data")

        storage = JsonStorage(target)
        # Should catch error, log warning, and initialize empty list
        records = storage.load_records()
        assert records == []

    def test_non_list_root_recovery(self, tmp_path):
        target = str(tmp_path / "dict_root.json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump({"error": "not a list"}, f)

        storage = JsonStorage(target)
        records = storage.load_records()
        assert records == []

    def test_concurrent_multithreaded_writes(self, tmp_path):
        target = str(tmp_path / "concurrent.json")
        storage = JsonStorage(target)
        storage.save_records([])

        def write_worker(idx: int):
            records = [create_sample_item(f"LST-{idx:04d}", f"Item {idx}")]
            storage.save_records(records)
            return len(storage.load_records())

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_worker, i) for i in range(15)]
            results = [f.result() for f in futures]

        assert all(r == 1 for r in results)
        final_records = storage.load_records()
        assert len(final_records) == 1


class TestSQLiteStorage:
    """Tests for SQLiteStorage backend."""

    def test_sqlite_save_and_load_roundtrip(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        storage = SQLiteStorage(db_file)

        items = [
            create_sample_item("LST-0001", "MacBook"),
            create_sample_item("FND-0001", "Earbuds"),
        ]
        items[1].record_type = "FOUND"

        storage.save_records(items)
        loaded = storage.load_records()
        assert len(loaded) == 2
        assert loaded[0].item_name == "MacBook"
        assert loaded[1].item_name == "Earbuds"

    def test_sqlite_empty_records(self, tmp_path):
        db_file = str(tmp_path / "empty.db")
        storage = SQLiteStorage(db_file)
        assert storage.load_records() == []


class TestLegacyStorageFunctions:
    """Tests that module-level load_records and save_records work seamlessly."""

    def test_module_level_helpers(self, tmp_path):
        target = str(tmp_path / "legacy.json")
        items = [create_sample_item("LST-0001", "Legacy Item")]
        save_records(items, target)
        loaded = load_records(target)
        assert len(loaded) == 1
        assert loaded[0].item_name == "Legacy Item"


class TestCsvHandlers:
    """Tests for CSV export and import."""

    def test_export_and_import_roundtrip(self, tmp_path):
        csv_file = str(tmp_path / "export.csv")
        items = [
            create_sample_item("LST-0001", "Item One"),
            create_sample_item("FND-0001", "Item Two"),
        ]
        items[1].record_type = "FOUND"

        export_to_csv(items, csv_file)
        assert os.path.exists(csv_file)

        imported, errors = import_from_csv(csv_file)
        assert len(imported) == 2
        assert len(errors) == 0
        assert imported[0].record_id == "LST-0001"

    def test_import_missing_csv(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.csv")
        records, errors = import_from_csv(missing)
        assert records == []
        assert len(errors) == 1
        assert "not found" in errors[0]
