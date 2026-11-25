"""Data models, categories, and serialization for Campus Lost-and-Found Register."""

from dataclasses import dataclass, asdict
from typing import Optional

CATEGORIES = ["Electronics", "ID & Cards", "Books & Stationery", "Clothing & Accessories", "Keys & Bottles", "Other"]
RECORD_TYPES = ["LOST", "FOUND"]
STATUSES = ["OPEN", "CLAIMED"]

@dataclass
class ItemRecord:
    record_id: str
    record_type: str        # "LOST" or "FOUND"
    item_name: str
    category: str
    location: str
    date_reported: str      # Format: YYYY-MM-DD
    description: str
    contact: str
    status: str = "OPEN"    # "OPEN" or "CLAIMED"
    date_claimed: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ItemRecord":
        return cls(
            record_id=data["record_id"],
            record_type=data["record_type"],
            item_name=data["item_name"],
            category=data["category"],
            location=data["location"],
            date_reported=data["date_reported"],
            description=data.get("description", ""),
            contact=data["contact"],
            status=data.get("status", "OPEN"),
            date_claimed=data.get("date_claimed")
        )