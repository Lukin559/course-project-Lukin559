"""Payment validation with Decimal and UTC datetime (P06 Secure Coding).

Control: Валидация и нормализация ввода (Decimal для денег, UTC для времени)
Related: NFR-005 (100% validation), R003 (tampering prevention)
"""

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Payment(BaseModel):
    """Payment request with strict Decimal and UTC validation.
    
    Security: Decimal prevents float rounding errors; UTC ensures consistency.
    """
    
    model_config = dict(extra='forbid')  # Reject unknown fields
    
    amount: Decimal = Field(
        ...,
        gt=0,  # Must be positive
        decimal_places=2,
        description="Amount in currency (2 decimal places)"
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g., USD, EUR)"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Payment description"
    )
    occurred_at: datetime = Field(
        ...,
        description="Payment timestamp (will be normalized to UTC)"
    )
    
    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is Decimal, not float."""
        if isinstance(v, float):
            # Float can have precision errors (0.1 + 0.2 != 0.3)
            raise ValueError("amount must be Decimal or string, not float (precision loss)")
        
        if isinstance(v, str):
            try:
                v = Decimal(v)
            except (InvalidOperation, ValueError):
                raise ValueError(f"Invalid amount: {v}")
        
        if not isinstance(v, Decimal):
            raise ValueError(f"amount must be Decimal, got {type(v)}")
        
        # Check bounds
        if v <= 0:
            raise ValueError("amount must be positive")
        if v > Decimal("999999999.99"):
            raise ValueError("amount too large (max 999999999.99)")
        
        return v
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        """Validate currency code format."""
        v = v.upper()
        if not v.isalpha():
            raise ValueError("currency must contain only letters")
        return v
    
    @field_validator("occurred_at", mode="before")
    @classmethod
    def normalize_to_utc(cls, v):
        """Normalize datetime to UTC."""
        if isinstance(v, str):
            # Parse ISO 8601 string
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        
        if not isinstance(v, datetime):
            raise ValueError(f"occurred_at must be datetime, got {type(v)}")
        
        # Convert to UTC if naive or has timezone
        if v.tzinfo is None:
            # Naive datetime — assume UTC
            v = v.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC
            v = v.astimezone(timezone.utc)
        
        # Remove timezone info for storage (we know it's UTC)
        return v.replace(tzinfo=None)


def parse_payment_json(raw_json: str) -> Payment:
    """Safely parse JSON payment without float precision loss.
    
    Security: parse_float=str prevents float intermediates.
    """
    import json
    
    # Parse JSON with strings for float values (prevent precision loss)
    data = json.loads(raw_json, parse_float=str)
    
    # Pydantic will convert Decimal strings to Decimal
    return Payment.model_validate(data)

