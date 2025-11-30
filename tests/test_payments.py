"""Tests for payment validation (P06 Secure Coding).

Control: Decimal/UTC validation
Tests: Positive, negative, boundary conditions
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.payments import Payment, parse_payment_json


class TestPaymentAmountValidation:
    """Test amount field validation with Decimal."""

    def test_valid_amount_decimal(self):
        """Test valid amount as Decimal."""
        p = Payment(
            amount=Decimal("99.99"),
            currency="USD",
            occurred_at=datetime.now(timezone.utc),
        )
        assert p.amount == Decimal("99.99")

    def test_valid_amount_string(self):
        """Test valid amount as string (converted to Decimal)."""
        p = Payment(
            amount="50.25",
            currency="EUR",
            occurred_at=datetime.now(timezone.utc),
        )
        assert p.amount == Decimal("50.25")

    def test_invalid_amount_float_rejected(self):
        """NEGATIVE: Float amounts rejected (precision loss risk)."""
        with pytest.raises(ValidationError) as exc_info:
            Payment(
                amount=0.1,  # Float!
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
            )
        assert "precision loss" in str(exc_info.value).lower()

    def test_invalid_amount_negative(self):
        """NEGATIVE: Negative amount rejected."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("-10.00"),
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_invalid_amount_zero(self):
        """NEGATIVE: Zero amount rejected."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("0.00"),
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_invalid_amount_too_large(self):
        """NEGATIVE: Amount exceeding max rejected."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("9999999999.99"),
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
            )


class TestPaymentCurrencyValidation:
    """Test currency field validation."""

    def test_valid_currency(self):
        """Test valid currency code."""
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            occurred_at=datetime.now(timezone.utc),
        )
        assert p.currency == "USD"

    def test_invalid_currency_too_short(self):
        """NEGATIVE: Currency too short."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("100.00"),
                currency="US",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_invalid_currency_too_long(self):
        """NEGATIVE: Currency too long."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("100.00"),
                currency="USDA",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_invalid_currency_with_numbers(self):
        """NEGATIVE: Currency with numbers rejected."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("100.00"),
                currency="US1",
                occurred_at=datetime.now(timezone.utc),
            )


class TestPaymentDatetimeValidation:
    """Test datetime normalization to UTC."""

    def test_valid_utc_datetime(self):
        """Test valid UTC datetime."""
        now_utc = datetime.now(timezone.utc).replace(microsecond=0)
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            occurred_at=now_utc,
        )
        # Should be stored without timezone info (but is UTC)
        assert p.occurred_at.tzinfo is None

    def test_naive_datetime_assumed_utc(self):
        """Test naive datetime assumed to be UTC."""
        now_naive = datetime.now().replace(microsecond=0)
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            occurred_at=now_naive,
        )
        # Should be stored without timezone (assumed UTC)
        assert p.occurred_at.tzinfo is None

    def test_iso_string_datetime(self):
        """Test ISO 8601 string parsed to UTC."""
        iso_str = "2025-01-15T10:30:45Z"
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            occurred_at=iso_str,
        )
        assert p.occurred_at == datetime(2025, 1, 15, 10, 30, 45)

    def test_timezone_datetime_converted_to_utc(self):
        """Test timezone-aware datetime converted to UTC."""
        # Create datetime in +02:00 timezone
        dt_plus_2 = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone(timedelta(hours=2)))
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            occurred_at=dt_plus_2,
        )
        # Should be converted to UTC (10:30:45)
        assert p.occurred_at == datetime(2025, 1, 15, 10, 30, 45)

    def test_future_datetime_accepted(self):
        """Test future datetime accepted."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            occurred_at=future,
        )
        assert p.occurred_at > datetime.now()


class TestPaymentJsonParsing:
    """Test JSON parsing with Decimal safety."""

    def test_parse_valid_payment_json(self):
        """Test parsing valid payment JSON."""
        json_str = '{"amount": "123.45", "currency": "USD", "occurred_at": "2025-01-15T10:30:45Z"}'
        p = parse_payment_json(json_str)
        assert p.amount == Decimal("123.45")
        assert p.currency == "USD"

    def test_parse_json_with_float_string(self):
        """Test parsing JSON with float string (converted safely)."""
        json_str = '{"amount": "99.99", "currency": "EUR", "occurred_at": "2025-01-15T10:30:45Z"}'
        p = parse_payment_json(json_str)
        assert p.amount == Decimal("99.99")

    def test_invalid_json(self):
        """NEGATIVE: Invalid JSON rejected."""
        with pytest.raises(Exception):  # json.JSONDecodeError
            parse_payment_json('{"amount": invalid}')

    def test_extra_fields_rejected(self):
        """NEGATIVE: Extra fields rejected (model_config forbid)."""
        json_str = (
            '{"amount": "100.00", "currency": "USD", '
            '"occurred_at": "2025-01-15T10:30:45Z", "extra_field": "value"}'
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_payment_json(json_str)
        assert "extra_field" in str(exc_info.value).lower()


class TestPaymentBoundaryConditions:
    """Test boundary and edge cases."""

    def test_min_amount_accepted(self):
        """Test minimum valid amount (0.01)."""
        p = Payment(
            amount=Decimal("0.01"),
            currency="USD",
            occurred_at=datetime.now(timezone.utc),
        )
        assert p.amount == Decimal("0.01")

    def test_max_amount_accepted(self):
        """Test maximum valid amount."""
        p = Payment(
            amount=Decimal("999999999.99"),
            currency="USD",
            occurred_at=datetime.now(timezone.utc),
        )
        assert p.amount == Decimal("999999999.99")

    def test_large_precision_decimal(self):
        """Test decimal with many decimal places (truncated)."""
        # Pydantic should validate decimal_places=2
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("100.123"),  # 3 decimal places
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_description_max_length(self):
        """Test description length limit."""
        p = Payment(
            amount=Decimal("100.00"),
            currency="USD",
            description="x" * 500,
            occurred_at=datetime.now(timezone.utc),
        )
        assert len(p.description) == 500

    def test_description_exceeds_max(self):
        """NEGATIVE: Description exceeding max length rejected."""
        with pytest.raises(ValidationError):
            Payment(
                amount=Decimal("100.00"),
                currency="USD",
                description="x" * 501,
                occurred_at=datetime.now(timezone.utc),
            )
