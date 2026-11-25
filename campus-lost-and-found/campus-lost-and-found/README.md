# Campus Lost-and-Found Register

A modular Python application for campus lost-and-found management. Use the command-line interface or the Streamlit browser UI to log reports, find possible matches, resolve claims, and view analytics.

The Streamlit browser interface shares the CLI's JSON register, validation rules, matching, search, claim-resolution, and analytics modules.

> **Requires Python 3.10 or later.**

## Setup

### Windows (PowerShell)

Open PowerShell in the project directory and create/activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

Run the command-line interface:

```powershell
python main.py
```

Or launch the browser UI:

```powershell
streamlit run app.py
```

The browser UI and CLI use the local `records.json` file, which is **auto-created on first run**. On a fresh checkout, use **Load Demo Data** in the browser sidebar to populate an empty register. Runtime records and generated reports/charts are ignored by Git.

This is a Python-only project: no `node_modules/` directory, Node.js install, or frontend build step is required. Virtual environments, Python caches, and generated build output are excluded from Git.

---

## Running Automated Tests

Run the full pytest suite with verbose output:

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Or using active Python environment:

```powershell
python -m pytest -v
```

### macOS / Linux

```bash
pytest -v
```

The test suite covers:
- `tests/test_validators.py`: `@mrtc.edu.in` email format, 10-digit phone regex, date boundaries (blocking future dates), and string constraints.
- `tests/test_engine.py`: Identifier generation per-type, fuzzy/exact match scoring, overdue thresholds, multi-field search, claim transitions, and summary metrics.
- `tests/test_storage.py`: Atomic JSON read/write, missing/corrupted file recovery, SQLite backend roundtrip, CSV import/export, and thread-safe concurrent writes with `ThreadPoolExecutor`.

---

## Internal Engine API

The core business logic is encapsulated in `engine.py` and persistent storage is abstracted in `storage.py`.

### Public Functions (`engine.py`)

- `generate_next_id(records: list[ItemRecord], record_type: str) -> str`
  Counts records matching the requested type and produces a zero-padded identifier (`LST-0001` or `FND-0001`). Raises `ValueError` for unsupported types.
- `find_potential_matches(new_item: ItemRecord, records: list[ItemRecord], min_score: float = 4.0) -> list[ItemRecord]`
  Scans all `OPEN` records of the opposite type (`LOST` $\leftrightarrow$ `FOUND`) and scores candidate matches against the threshold.
- `is_overdue(record: ItemRecord, days: int = 14) -> bool`
  Returns `True` if an `OPEN` record was reported more than `days` ago; returns `False` for `CLAIMED` items.
- `get_overdue_records(records: list[ItemRecord], days: int = 14) -> list[ItemRecord]`
  Filters the collection to return all active overdue records.
- `search_records(records: list[ItemRecord], keyword: str = "", category: str = "", status: str = "") -> list[ItemRecord]`
  Multi-parameter filter supporting partial case-insensitive search across item name, description (safely handling `None`), and location.
- `mark_as_claimed(records: list[ItemRecord], record_id: str) -> bool`
  Atomically transitions an `OPEN` record to `CLAIMED` and stamps `date_claimed` with the current date.
- `compute_summary(records: list[ItemRecord]) -> dict`
  Calculates aggregate metrics: total items, open/claimed counts, recovery percentage, average claim resolution days, category distribution, and hotspot locations.

### Match Scoring Formula

`find_potential_matches` evaluates opposite-type candidate records across six weighted dimensions:

$$\text{Match Score} = S_{\text{category}} + S_{\text{location}} + S_{\text{date}} + S_{\text{title}} + S_{\text{fuzzy}} + S_{\text{desc}}$$

| Dimension | Points | Description |
|---|:---:|---|
| **Category Match** | $+2.0$ | Exact category match (`r.category == new_item.category`). |
| **Location Match** | $+2.0$ or $+1.0$ | $+2.0$ for exact case-insensitive match; $+1.0$ for substring containment. |
| **Date Proximity** | $+0.5$ to $+2.0$ | $+2.0$ if $\le 3$ days apart; $+1.0$ if $\le 7$ days; $+0.5$ if $\le 14$ days. |
| **Title Keyword Overlap** | $+2.5$ / token | Multiplied by the number of matching words in the item titles. |
| **Fuzzy Title Similarity** | up to $+3.0$ | `difflib.SequenceMatcher.ratio() * 3.0` capturing typos and slight name variations. |
| **Description Overlap** | up to $+2.0$ | $+0.5$ per overlapping token between titles and descriptions. |

Records scoring $\ge 4.0$ (configurable via `min_score`) qualify as potential matches and are returned sorted by descending confidence.

### Storage Backends (`storage.py`)

All file persistence operations use a module-level `threading.Lock()` and cross-platform advisory file locking (`msvcrt` on Windows, `fcntl` on POSIX) to guarantee safety across threads and processes.

- `StorageBackend` (Abstract Base Class): Defines the persistence interface with `load_records() -> list[ItemRecord]` and `save_records(records: list[ItemRecord]) -> None`.
- `JsonStorage(filepath: str)` (Default): Stores records as human-readable JSON. Uses atomic writes by streaming to a temporary file on the same volume, calling `flush()` and `os.fsync()`, and executing `os.replace()`. Recovers automatically from missing or corrupted files.
- `SQLiteStorage(db_path: str)` (Optional): Built-in relational storage using `sqlite3` with automated schema migrations and transaction rollback on error.
- Backward-compatible top-level wrappers: `load_records(filepath)` and `save_records(records, filepath)` default directly to `JsonStorage`.

---

## Key Features
* **Smart Match Detection:** Automatically cross-references newly logged `LOST` and `FOUND` records using weighted scoring across category, item-name keywords, and campus location to alert users immediately.
* **Defensive Input Validation:** Prevents runtime crashes by enforcing non-empty text, valid calendar dates (blocking future dates), strict category selections, and regex-validated email addresses or 10-digit phone numbers.
* **Dual Persistence & Recovery:** Automatically saves records to `records.json` (with built-in recovery if the file is missing or corrupted) and supports one-click CSV export and row-validated bulk CSV import.
* **Overdue Item Alerts:** Automatically flags `OPEN` records older than 14 days with yellow ANSI `[OVERDUE]` highlights in the terminal register.
* **Executive Analytics & Reporting:** Computes recovery rates, average resolution time in days, and campus hotspots, exporting both a 3-panel Matplotlib chart (`campus_summary_charts.png`) and a formatted Markdown report (`campus_report.md`).

---

## Project Architecture

```text
├── main.py                      # Terminal UI, menu loop, ANSI alerts, and Markdown report export
├── app.py                       # Streamlit browser UI
├── models.py                    # ItemRecord dataclass, category definitions, and serialization
├── storage.py                   # Thread-safe atomic JSON persistence, SQLiteStorage, and CSV handlers
├── validators.py                # Input sanitization, date checks, and email/phone regex validation
├── engine.py                    # Weighted fuzzy match scoring, search, claim updates, and analytics
├── visualizer.py                # 3-panel Matplotlib chart generator (Category, Status, Campus Hotspots)
├── tests/                       # Automated pytest test suite
│   ├── test_validators.py       # Validation boundary, email, and phone tests
│   ├── test_engine.py           # Match detection, search, and analytics tests
│   └── test_storage.py          # Atomic writes, recovery, SQLite, and concurrency tests
├── .streamlit/config.toml       # Browser UI theme configuration
└── requirements.txt             # Python dependencies
```
