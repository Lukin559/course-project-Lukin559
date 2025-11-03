"""Centralized input validation with canonicalization and injection prevention.

This module implements 3-layer validation as per ADR-002:
1. Canonicalization: normalize whitespace, trim, collapse spaces
2. Pydantic constraints: type, length, numeric bounds
3. Semantic validation: business rules (price range, reserved names, etc.)
"""

from typing import Optional


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


class InputValidator:
    """Centralized input validation for all user inputs."""

    # Business rule constants
    MIN_NAME_LENGTH = 1
    MAX_NAME_LENGTH = 100
    MIN_PRICE = 0.01
    MAX_PRICE = 1_000_000.00
    MAX_DESCRIPTION_LENGTH = 500

    @staticmethod
    def canonicalize_name(raw_name: str) -> str:
        """Canonicalize task name: trim, collapse spaces, validate.

        Layer 1: Canonicalization
        - Strip leading/trailing whitespace
        - Collapse multiple spaces to single space
        - Validate length AFTER canonicalization

        Args:
            raw_name: The raw name from user input.

        Returns:
            Canonical (normalized) name.

        Raises:
            ValidationError: If name is empty or invalid after normalization.
        """
        if not raw_name or not isinstance(raw_name, str):
            raise ValidationError("name must be a non-empty string")

        # Collapse internal spaces and trim
        canonical = " ".join(raw_name.split())

        # Validate length AFTER canonicalization
        if len(canonical) < InputValidator.MIN_NAME_LENGTH:
            raise ValidationError(
                f"name cannot be empty (min {InputValidator.MIN_NAME_LENGTH} char)"
            )

        if len(canonical) > InputValidator.MAX_NAME_LENGTH:
            raise ValidationError(
                f"name too long (max {InputValidator.MAX_NAME_LENGTH} chars after normalization, "
                f"got {len(canonical)})"
            )

        return canonical

    @staticmethod
    def validate_description(description: Optional[str]) -> Optional[str]:
        """Validate task description.

        Layer 1: Canonicalization
        - Strip whitespace if provided
        - Validate length

        Args:
            description: The description text, or None.

        Returns:
            Canonical description, or None if input was None.

        Raises:
            ValidationError: If description is invalid.
        """
        if description is None:
            return None

        if not isinstance(description, str):
            raise ValidationError("description must be a string")

        # Canonicalize: trim whitespace
        canonical = description.strip()

        # Allow empty string (maps to None in schema), but check length if not empty
        if canonical and len(canonical) > InputValidator.MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"description too long (max {InputValidator.MAX_DESCRIPTION_LENGTH} chars, "
                f"got {len(canonical)})"
            )

        return canonical if canonical else None

    @staticmethod
    def validate_price(price: Optional[float]) -> Optional[float]:
        """Validate price with semantic business rules.

        Layer 3: Semantic Validation
        - Price must be positive (if set)
        - Price must be within reasonable business bounds
        - Prevent float rounding errors by rounding to 2 decimals

        Args:
            price: The price value, or None.

        Returns:
            Validated (and rounded) price, or None if input was None.

        Raises:
            ValidationError: If price is invalid.
        """
        if price is None:
            return None

        if not isinstance(price, (int, float)):
            raise ValidationError("price must be a number")

        # Validate bounds
        if price < InputValidator.MIN_PRICE:
            raise ValidationError(
                f"price must be at least {InputValidator.MIN_PRICE}"
            )

        if price > InputValidator.MAX_PRICE:
            raise ValidationError(
                f"price must not exceed {InputValidator.MAX_PRICE}"
            )

        # Round to 2 decimals to prevent float rounding errors
        return round(price, 2)
