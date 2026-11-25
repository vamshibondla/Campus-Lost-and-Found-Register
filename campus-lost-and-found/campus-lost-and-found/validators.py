"""Input validation and sanitization utilities for CLI entries."""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def validate_non_empty_string(value: str, min_len: int = 2) -> bool:
    """Validates that a string contains at least `min_len` non-whitespace characters."""
    return len(value.strip()) >= min_len


def validate_date(value: str) -> Optional[str]:
    """Validates date format (YYYY-MM-DD) and ensures it is not in the future.

    Returns:
        Error message string if invalid; None if the date is valid.
    """
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD (e.g., 2026-11-17)."
    if parsed.date() > datetime.now().date():
        return "Date cannot be in the future."
    return None


def validate_contact(value: str) -> bool:
    """Validates that contact is a valid email address or 10-digit phone number."""
    email_pattern = r"^[\w\.-]+@([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
    phone_pattern = r"^\d{10}$"
    value = value.strip()
    return bool(re.match(email_pattern, value) or re.match(phone_pattern, value))


def get_non_empty_string(prompt: str, min_len: int = 2) -> str:
    """Prompts CLI user until a string of at least `min_len` characters is provided."""
    while True:
        val = input(prompt).strip()
        if validate_non_empty_string(val, min_len):
            return val
        logger.warning("Input must be at least %d characters long.", min_len)


def get_choice(prompt: str, options: list[str]) -> str:
    """Prompts CLI user until a valid choice from the listed options is entered."""
    options_upper = [opt.upper() for opt in options]
    while True:
        print(f"  Options: {', '.join(options)}")
        val = input(prompt).strip()
        if val.upper() in options_upper:
            return options[options_upper.index(val.upper())]
        logger.warning("Invalid selection. Choose from the listed options.")


def get_valid_date(prompt: str = "Date (YYYY-MM-DD): ") -> str:
    """Prompts CLI user until a valid past or present YYYY-MM-DD date is entered."""
    while True:
        val = input(prompt).strip()
        error = validate_date(val)
        if not error:
            return val
        logger.warning("%s", error)


def get_valid_contact(prompt: str = "Contact (Email or 10-digit phone): ") -> str:
    """Prompts CLI user until a valid email or 10-digit phone number is entered."""
    while True:
        val = input(prompt).strip()
        if validate_contact(val):
            return val
        logger.warning("Enter a valid email address or 10-digit phone number.")
