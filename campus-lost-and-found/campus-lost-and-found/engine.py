"""Core matching, search, claim resolution, and analytics engine.

This module provides business logic for the Campus Lost-and-Found Register,
including identifier generation, intelligent cross-record match detection,
search filtering, claim lifecycle management, and metric summaries.
"""

import logging
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from models import ItemRecord

logger = logging.getLogger(__name__)


def generate_next_id(records: list[ItemRecord], record_type: str) -> str:
    """Generates the next sequential formatted identifier for a record type.

    Counts existing records matching the requested type and formats a 4-digit
    zero-padded identifier prefixed with 'LST-' for lost items or 'FND-' for
    found items.

    Args:
        records: Collection of existing ItemRecord objects.
        record_type: Either 'LOST' or 'FOUND'.

    Returns:
        Formatted record identifier string, e.g., 'LST-0001' or 'FND-0002'.

    Raises:
        ValueError: If record_type is not 'LOST' or 'FOUND'.
    """
    rec_type_upper = record_type.strip().upper()
    if rec_type_upper not in ("LOST", "FOUND"):
        logger.error("Invalid record_type provided: %s", record_type)
        raise ValueError(f"Invalid record_type: {record_type}. Expected 'LOST' or 'FOUND'.")

    prefix = "LST" if rec_type_upper == "LOST" else "FND"
    same_type = [r for r in records if r.record_type == rec_type_upper]
    next_id = f"{prefix}-{len(same_type) + 1:04d}"
    logger.debug("Generated identifier %s for type %s", next_id, rec_type_upper)
    return next_id


def find_potential_matches(
    new_item: ItemRecord,
    records: list[ItemRecord],
    min_score: float = 4.0,
) -> list[ItemRecord]:
    """Scores and ranks opposite-type OPEN records using weighted multi-attribute matching.

    Combines weighted attribute overlap, date proximity, fuzzy string similarity
    via difflib.SequenceMatcher, and normalized keyword token overlap across
    titles and descriptions to find candidate matches between LOST and FOUND items.

    Scoring Weights:
        - Category Match: +2.0 points if categories are identical.
        - Location Match: +2.0 points for exact match (case-insensitive);
          +1.0 point for partial substring containment.
        - Date Proximity: +2.0 points if reported within 3 days;
          +1.0 point if within 7 days; +0.5 points if within 14 days.
        - Title Keyword Overlap: +2.5 points per shared word token in item titles.
        - Fuzzy Title Similarity: SequenceMatcher ratio multiplied by 3.0 (up to +3.0 points).
        - Description Overlap: +0.5 points per token overlap involving descriptions
          (capped at +2.0 points maximum).

    Args:
        new_item: The newly reported ItemRecord to compare against existing records.
        records: Collection of existing ItemRecord objects to search through.
        min_score: Minimum total score required to qualify as a potential match (default: 4.0).

    Returns:
        List of matching ItemRecord objects sorted in descending order of match confidence.
    """
    target_type = "FOUND" if new_item.record_type == "LOST" else "LOST"
    new_title_tokens = set(re.findall(r"\w+", new_item.item_name.lower()))
    new_desc_tokens = set(re.findall(r"\w+", (new_item.description or "").lower()))

    try:
        new_date = datetime.strptime(new_item.date_reported, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        new_date = None

    scored_matches: list[tuple[float, ItemRecord]] = []

    for r in records:
        if r.record_type != target_type or r.status != "OPEN":
            continue

        score = 0.0

        # 1. Category Match
        if r.category == new_item.category:
            score += 2.0

        # 2. Location Match
        r_loc = r.location.strip().lower()
        new_loc = new_item.location.strip().lower()
        if r_loc == new_loc and r_loc:
            score += 2.0
        elif (r_loc in new_loc or new_loc in r_loc) and (r_loc and new_loc):
            score += 1.0

        # 3. Date Proximity
        if new_date:
            try:
                r_date = datetime.strptime(r.date_reported, "%Y-%m-%d").date()
                diff_days = abs((new_date - r_date).days)
                if diff_days <= 3:
                    score += 2.0
                elif diff_days <= 7:
                    score += 1.0
                elif diff_days <= 14:
                    score += 0.5
            except (ValueError, TypeError):
                pass

        # 4. Title Keyword Overlap
        r_title_tokens = set(re.findall(r"\w+", r.item_name.lower()))
        common_title_tokens = new_title_tokens & r_title_tokens
        score += len(common_title_tokens) * 2.5

        # 5. Fuzzy Title Similarity via difflib.SequenceMatcher
        fuzzy_ratio = SequenceMatcher(
            None,
            new_item.item_name.strip().lower(),
            r.item_name.strip().lower(),
        ).ratio()
        score += round(fuzzy_ratio * 3.0, 2)

        # 6. Description / Cross-token Overlap
        r_desc_tokens = set(re.findall(r"\w+", (r.description or "").lower()))
        desc_overlap = (
            (new_title_tokens & r_desc_tokens)
            | (r_title_tokens & new_desc_tokens)
            | (new_desc_tokens & r_desc_tokens)
        )
        if desc_overlap:
            score += min(2.0, len(desc_overlap) * 0.5)

        if score >= min_score:
            scored_matches.append((score, r))

    scored_matches.sort(key=lambda pair: pair[0], reverse=True)
    logger.debug(
        "Match detection for %s (%s) found %d candidate(s) above threshold %.1f",
        new_item.record_id,
        new_item.item_name,
        len(scored_matches),
        min_score,
    )
    return [r for _, r in scored_matches]


def is_overdue(record: ItemRecord, days: int = 14) -> bool:
    """Determines if an open record has exceeded the active resolution threshold.

    Args:
        record: ItemRecord instance to evaluate.
        days: Threshold in days to consider a record overdue (default: 14).

    Returns:
        True if the record status is 'OPEN' and elapsed days exceed the threshold;
        False otherwise (including when status is 'CLAIMED').
    """
    if record.status != "OPEN":
        return False
    try:
        reported = datetime.strptime(record.date_reported, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning("Invalid date format in record %s: %s", record.record_id, record.date_reported)
        return False
    return (datetime.now().date() - reported).days > days


def get_overdue_records(records: list[ItemRecord], days: int = 14) -> list[ItemRecord]:
    """Filters records to return all currently open, overdue items.

    Args:
        records: Collection of ItemRecord objects to filter.
        days: Threshold in days for overdue classification (default: 14).

    Returns:
        List of ItemRecord instances that are OPEN and older than `days`.
    """
    return [r for r in records if is_overdue(r, days)]


def search_records(
    records: list[ItemRecord],
    keyword: str = "",
    category: str = "",
    status: str = "",
) -> list[ItemRecord]:
    """Filters records by case-insensitive keyword, category, and status.

    Keyword search inspects item_name, description (safely handling None), and location.

    Args:
        records: Collection of ItemRecord objects to search.
        keyword: Case-insensitive search term matching name, description, or location.
        category: Exact category filter (case-insensitive); empty string skips filter.
        status: Exact status filter ('OPEN' or 'CLAIMED', case-insensitive); empty string skips.

    Returns:
        Filtered list of ItemRecord objects satisfying all applied criteria.
    """
    results = records
    if keyword:
        kw = keyword.strip().lower()
        results = [
            r
            for r in results
            if kw in r.item_name.lower()
            or kw in (r.description or "").lower()
            or kw in r.location.lower()
        ]
    if category:
        cat_lower = category.strip().lower()
        results = [r for r in results if r.category.lower() == cat_lower]
    if status:
        st_upper = status.strip().upper()
        results = [r for r in results if r.status.upper() == st_upper]
    return results


def mark_as_claimed(records: list[ItemRecord], record_id: str) -> bool:
    """Updates an open record's status to CLAIMED and records today's date.

    Args:
        records: Collection of ItemRecord objects to modify in-place.
        record_id: Identifier of the record to mark claimed (case-insensitive).

    Returns:
        True if the record was found and updated from OPEN to CLAIMED; False otherwise.
    """
    target_id = record_id.strip().upper()
    for r in records:
        if r.record_id.upper() == target_id and r.status == "OPEN":
            r.status = "CLAIMED"
            r.date_claimed = datetime.now().strftime("%Y-%m-%d")
            logger.info("Record %s marked as CLAIMED on %s", r.record_id, r.date_claimed)
            return True
    logger.warning("Record %s not found or not in OPEN status for claim resolution.", record_id)
    return False


def compute_summary(records: list[ItemRecord]) -> dict:
    """Computes executive statistics and operational metrics across all records.

    Calculates totals, lost/found breakdown, open/claimed counts, overdue count,
    claim resolution rate, average days to resolution for claimed records,
    category distribution, and top location hotspots.

    Args:
        records: Collection of ItemRecord objects to analyze.

    Returns:
        Dictionary containing aggregate summary metrics:
            - 'total' (int): Total number of records.
            - 'lost' (int): Total lost records.
            - 'found' (int): Total found records.
            - 'claimed' (int): Total claimed records.
            - 'open' (int): Total open records.
            - 'overdue' (int): Count of open records older than 14 days.
            - 'claim_rate' (float): Percentage of claimed items (0.0 to 100.0).
            - 'avg_resolution_days' (float): Mean days from report to claim.
            - 'by_category' (dict[str, int]): Count of records per category.
            - 'by_location' (dict[str, int]): Count for top 5 locations.
            - 'top_locations' (list[tuple[str, int]]): Top 3 location tuples.
    """
    total = len(records)
    lost_count = sum(1 for r in records if r.record_type == "LOST")
    found_count = sum(1 for r in records if r.record_type == "FOUND")
    claimed_records = [r for r in records if r.status == "CLAIMED"]
    claimed_count = len(claimed_records)
    claim_rate = (claimed_count / total * 100) if total > 0 else 0.0

    resolution_days = []
    for r in claimed_records:
        if r.date_claimed:
            try:
                d1 = datetime.strptime(r.date_reported, "%Y-%m-%d").date()
                d2 = datetime.strptime(r.date_claimed, "%Y-%m-%d").date()
                resolution_days.append(max(0, (d2 - d1).days))
            except (ValueError, TypeError):
                pass
    avg_days = round(sum(resolution_days) / len(resolution_days), 1) if resolution_days else 0.0

    return {
        "total": total,
        "lost": lost_count,
        "found": found_count,
        "claimed": claimed_count,
        "open": total - claimed_count,
        "overdue": len(get_overdue_records(records)),
        "claim_rate": round(claim_rate, 1),
        "avg_resolution_days": avg_days,
        "by_category": dict(Counter(r.category for r in records)),
        "by_location": dict(Counter(r.location for r in records).most_common(5)),
        "top_locations": Counter(r.location for r in records).most_common(3),
    }
