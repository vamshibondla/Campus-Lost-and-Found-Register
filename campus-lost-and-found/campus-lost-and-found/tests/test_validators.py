"""Tests for input validation and sanitization functions in validators.py."""

from datetime import date, timedelta
from validators import (
    validate_contact,
    validate_date,
    validate_non_empty_string,
)


class TestValidateContact:
    """Tests for validate_contact covering emails and phone numbers."""

    def test_valid_mrtc_edu_in_emails(self):
        valid_emails = [
            "arjun.mehta@mrtc.edu.in",
            "rohan.gupta@mrtc.edu.in",
            "kavya.nair@mrtc.edu.in",
            "admin.dept@mrtc.edu.in",
            "student_2024@mrtc.edu.in",
        ]
        for email in valid_emails:
            assert validate_contact(email) is True, f"Failed for {email}"

    def test_valid_general_emails(self):
        valid_emails = [
            "student@campus.edu",
            "test.user@domain.com",
            "hello@sub.domain.org",
        ]
        for email in valid_emails:
            assert validate_contact(email) is True, f"Failed for {email}"

    def test_invalid_emails(self):
        invalid_emails = [
            "",
            "   ",
            "@mrtc.edu.in",
            "arjun.mehta@",
            "arjun.mehta",
            "arjun@mrtc..edu.in",
            "arjun mehta@mrtc.edu.in",
        ]
        for email in invalid_emails:
            assert validate_contact(email) is False, f"Should be invalid: {email}"

    def test_valid_phone_numbers(self):
        valid_phones = [
            "9876543210",
            "9123456780",
            "9988776655",
            "1234567890",
        ]
        for phone in valid_phones:
            assert validate_contact(phone) is True, f"Failed for {phone}"

    def test_invalid_phone_numbers(self):
        invalid_phones = [
            "12345",          # too short
            "123456789",      # 9 digits
            "12345678901",    # 11 digits
            "98765abcde",     # contains alpha
            "98765 43210",    # contains space
            "98765-43210",    # contains hyphen
        ]
        for phone in invalid_phones:
            assert validate_contact(phone) is False, f"Should be invalid: {phone}"


class TestValidateDate:
    """Tests for validate_date covering boundary dates and formats."""

    def test_today_is_valid(self):
        today_str = date.today().isoformat()
        assert validate_date(today_str) is None

    def test_past_date_is_valid(self):
        past_str = (date.today() - timedelta(days=30)).isoformat()
        assert validate_date(past_str) is None

    def test_future_date_is_invalid(self):
        future_str = (date.today() + timedelta(days=1)).isoformat()
        err = validate_date(future_str)
        assert err == "Date cannot be in the future."

    def test_far_future_date_is_invalid(self):
        err = validate_date("2099-12-31")
        assert err == "Date cannot be in the future."

    def test_malformed_date_formats(self):
        malformed = [
            "",
            "2026/11/17",
            "17-11-2026",
            "2026-13-01",
            "2026-02-30",
            "yesterday",
        ]
        for val in malformed:
            err = validate_date(val)
            assert err is not None
            assert "Invalid date format" in err


class TestValidateNonEmptyString:
    """Tests for validate_non_empty_string with varying min_len."""

    def test_valid_strings(self):
        assert validate_non_empty_string("Central Library") is True
        assert validate_non_empty_string("ab") is True
        assert validate_non_empty_string("  trimmed  ") is True

    def test_invalid_strings(self):
        assert validate_non_empty_string("") is False
        assert validate_non_empty_string("   ") is False
        assert validate_non_empty_string("a", min_len=2) is False

    def test_custom_min_len(self):
        assert validate_non_empty_string("abc", min_len=4) is False
        assert validate_non_empty_string("abcd", min_len=4) is True
