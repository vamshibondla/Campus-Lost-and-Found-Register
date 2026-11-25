"""Crash-safe persistence and CSV import/export handlers with atomic operations and locking."""

import csv
import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
from abc import ABC, abstractmethod
from contextlib import closing, contextmanager
from datetime import datetime
from models import ItemRecord, CATEGORIES, RECORD_TYPES, STATUSES

logger = logging.getLogger(__name__)

DEFAULT_FILE = "records.json"
CSV_FIELDS = [
    "record_id",
    "record_type",
    "item_name",
    "category",
    "location",
    "date_reported",
    "description",
    "contact",
    "status",
    "date_claimed",
]

_THREAD_LOCK = threading.RLock()


@contextmanager
def file_lock(lock_path: str):
    """Cross-platform advisory file lock using msvcrt (Windows) or fcntl (POSIX).

    Guarantees thread-safe access within the current process via a module-level
    threading lock, and inter-process safety via an OS file lock.
    """
    with _THREAD_LOCK:
        target_dir = os.path.dirname(os.path.abspath(lock_path)) or "."
        os.makedirs(target_dir, exist_ok=True)
        with open(lock_path, "a+b") as lock_file:
            if lock_file.tell() == 0:
                lock_file.write(b"x")
                lock_file.flush()
            lock_file.seek(0)
            fileno = lock_file.fileno()

            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(fileno, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fileno, fcntl.LOCK_EX)

            try:
                yield
            finally:
                try:
                    lock_file.seek(0)
                    if sys.platform == "win32":
                        import msvcrt
                        msvcrt.locking(fileno, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fileno, fcntl.LOCK_UN)
                except Exception as exc:
                    logger.warning("Failed to release file lock on %s: %s", lock_path, exc)


class StorageBackend(ABC):
    """Abstract base class defining storage operations for ItemRecord collections."""

    @abstractmethod
    def load_records(self) -> list[ItemRecord]:
        """Loads all records from persistent storage.

        Returns:
            List of ItemRecord instances.
        """
        pass

    @abstractmethod
    def save_records(self, records: list[ItemRecord]) -> None:
        """Persists all records to storage.

        Args:
            records: List of ItemRecord instances to persist.
        """
        pass


class JsonStorage(StorageBackend):
    """JSON file persistence backend with thread safety, file locks, and atomic replacement."""

    def __init__(self, filepath: str = DEFAULT_FILE):
        self.filepath = filepath
        self.lock_path = f"{filepath}.lock"

    def load_records(self) -> list[ItemRecord]:
        """Loads records from JSON file. Auto-creates clean file if missing or corrupted."""
        if not os.path.exists(self.filepath):
            self.save_records([])
            return []
        try:
            with file_lock(self.lock_path):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    if not isinstance(raw_data, list):
                        raise ValueError("Root JSON element must be a list.")
                    return [ItemRecord.from_dict(item) for item in raw_data]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Corrupted data file (%s). Initializing clean template.", e)
            self.save_records([])
            return []

    def save_records(self, records: list[ItemRecord]) -> None:
        """Atomically saves records by writing to a temporary file, flushing, and replacing."""
        target_dir = os.path.dirname(os.path.abspath(self.filepath)) or "."
        os.makedirs(target_dir, exist_ok=True)
        with file_lock(self.lock_path):
            temp_fd, temp_path = tempfile.mkstemp(
                prefix="tmp_records_", suffix=".tmp", dir=target_dir
            )
            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump([r.to_dict() for r in records], f, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, self.filepath)
            except Exception:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                raise


class SQLiteStorage(StorageBackend):
    """SQLite database storage backend using Python's built-in sqlite3 with timeout and closing."""

    def __init__(self, db_path: str = "records.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initializes database schema if tables do not exist."""
        with _THREAD_LOCK:
            target_dir = os.path.dirname(os.path.abspath(self.db_path)) or "."
            os.makedirs(target_dir, exist_ok=True)
            with closing(sqlite3.connect(self.db_path, timeout=10.0)) as conn:
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS records (
                            record_id TEXT PRIMARY KEY,
                            record_type TEXT NOT NULL,
                            item_name TEXT NOT NULL,
                            category TEXT NOT NULL,
                            location TEXT NOT NULL,
                            date_reported TEXT NOT NULL,
                            description TEXT,
                            contact TEXT NOT NULL,
                            status TEXT NOT NULL,
                            date_claimed TEXT
                        )
                    """)

    def load_records(self) -> list[ItemRecord]:
        """Loads all records from the SQLite database."""
        with _THREAD_LOCK:
            if not os.path.exists(self.db_path):
                self._init_db()
                return []
            try:
                with closing(sqlite3.connect(self.db_path, timeout=10.0)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT record_id, record_type, item_name, category, location,
                               date_reported, description, contact, status, date_claimed
                        FROM records
                    """)
                    rows = cursor.fetchall()
                    return [
                        ItemRecord(
                            record_id=row[0],
                            record_type=row[1],
                            item_name=row[2],
                            category=row[3],
                            location=row[4],
                            date_reported=row[5],
                            description=row[6] or "",
                            contact=row[7],
                            status=row[8],
                            date_claimed=row[9],
                        )
                        for row in rows
                    ]
            except Exception as e:
                logger.warning("Error reading SQLite database %s: %s", self.db_path, e)
                return []

    def save_records(self, records: list[ItemRecord]) -> None:
        """Replaces all rows in the database with the provided records."""
        with _THREAD_LOCK:
            self._init_db()
            with closing(sqlite3.connect(self.db_path, timeout=10.0)) as conn:
                with conn:
                    conn.execute("DELETE FROM records")
                    conn.executemany("""
                        INSERT INTO records (
                            record_id, record_type, item_name, category, location,
                            date_reported, description, contact, status, date_claimed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        (
                            r.record_id,
                            r.record_type,
                            r.item_name,
                            r.category,
                            r.location,
                            r.date_reported,
                            r.description,
                            r.contact,
                            r.status,
                            r.date_claimed,
                        )
                        for r in records
                    ])


def load_records(filepath: str = DEFAULT_FILE) -> list[ItemRecord]:
    """Default backward-compatible function to load records from a JSON file."""
    return JsonStorage(filepath).load_records()


def save_records(records: list[ItemRecord], filepath: str = DEFAULT_FILE) -> None:
    """Default backward-compatible function to save records to a JSON file."""
    JsonStorage(filepath).save_records(records)


def export_to_csv(records: list[ItemRecord], filepath: str = "records_export.csv") -> None:
    """Exports all records to a CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow(r.to_dict())


def import_from_csv(filepath: str) -> tuple[list[ItemRecord], list[str]]:
    """Imports valid records from CSV and logs row-level validation errors."""
    valid_records, errors = [], []
    if not os.path.exists(filepath):
        logger.warning("File '%s' not found for CSV import.", filepath)
        return valid_records, [f"File '{filepath}' not found."]

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            try:
                rec_type = row["record_type"].strip().upper()
                cat = row["category"].strip()
                status = row.get("status", "OPEN").strip().upper()
                datetime.strptime(row["date_reported"].strip(), "%Y-%m-%d")

                if rec_type not in RECORD_TYPES or cat not in CATEGORIES or status not in STATUSES:
                    raise ValueError("Invalid type, category, or status.")
                if len(row["item_name"].strip()) < 2:
                    raise ValueError("Item name too short.")

                valid_records.append(
                    ItemRecord(
                        record_id=row["record_id"].strip(),
                        record_type=rec_type,
                        item_name=row["item_name"].strip(),
                        category=cat,
                        location=row["location"].strip(),
                        date_reported=row["date_reported"].strip(),
                        description=row.get("description", "").strip(),
                        contact=row["contact"].strip(),
                        status=status,
                        date_claimed=row.get("date_claimed") or None,
                    )
                )
            except Exception as e:
                logger.warning("CSV import error at row %d: %s", row_num, e)
                errors.append(f"Row {row_num}: {e}")
    return valid_records, errors
