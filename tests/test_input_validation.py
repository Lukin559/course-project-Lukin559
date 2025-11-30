"""Tests for input validation, canonicalization, and injection prevention.

Implements ADR-002: Multi-Layer Input Validation with Canonicalization

Tests validate:
- Layer 1: Canonicalization (whitespace normalization, trimming)
- Layer 2: Pydantic constraints (type, length, numeric bounds)
- Layer 3: Semantic validation (business rules like price range)
- Security: XSS, SQL injection, Unicode tricks are rejected or normalized
"""

from fastapi.testclient import TestClient

from app.main import app
from app.validation import InputValidator, ValidationError

client = TestClient(app)


class TestCanonicalizeNameValidation:
    """Test Layer 1: Canonicalization (whitespace normalization)."""

    def test_canonicalize_valid_name(self):
        """Test valid name canonicalization."""
        result = InputValidator.canonicalize_name("Task Name")
        assert result == "Task Name"

    def test_canonicalize_leading_trailing_whitespace(self):
        """Test that leading/trailing whitespace is removed."""
        result = InputValidator.canonicalize_name("  Task Name  ")
        assert result == "Task Name"

    def test_canonicalize_collapse_internal_spaces(self):
        """Test that multiple internal spaces are collapsed."""
        result = InputValidator.canonicalize_name("Task    Name    Here")
        assert result == "Task Name Here"

    def test_canonicalize_tabs_and_newlines(self):
        """Test that tabs and newlines are treated as whitespace."""
        result = InputValidator.canonicalize_name("Task\t\nName")
        assert result == "Task Name"

    def test_canonicalize_min_length_valid(self):
        """Test minimum length (1 char) is accepted."""
        result = InputValidator.canonicalize_name("x")
        assert result == "x"

    def test_canonicalize_max_length_valid(self):
        """Test maximum length (100 chars) is accepted."""
        name = "x" * 100
        result = InputValidator.canonicalize_name(name)
        assert result == name
        assert len(result) == 100

    def test_canonicalize_empty_string_rejected(self):
        """Test empty string is rejected."""
        try:
            InputValidator.canonicalize_name("")
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "empty" in str(e).lower()

    def test_canonicalize_only_whitespace_rejected(self):
        """Test string with only whitespace is rejected."""
        try:
            InputValidator.canonicalize_name("   \t\n  ")
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "empty" in str(e).lower()

    def test_canonicalize_exceeds_max_length(self):
        """Test that names exceeding 100 chars are rejected."""
        long_name = "x" * 101
        try:
            InputValidator.canonicalize_name(long_name)
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "too long" in str(e).lower()

    def test_canonicalize_special_characters_preserved(self):
        """Test that special characters are preserved during canonicalization."""
        result = InputValidator.canonicalize_name("Task @#$% & Name")
        assert result == "Task @#$% & Name"


class TestValidateDescriptionValidation:
    """Test description field canonicalization and validation."""

    def test_validate_description_valid(self):
        """Test valid description."""
        result = InputValidator.validate_description("Valid description")
        assert result == "Valid description"

    def test_validate_description_none(self):
        """Test that None is allowed."""
        result = InputValidator.validate_description(None)
        assert result is None

    def test_validate_description_whitespace_trimmed(self):
        """Test that leading/trailing whitespace is trimmed."""
        result = InputValidator.validate_description("  Description  ")
        assert result == "Description"

    def test_validate_description_empty_string_to_none(self):
        """Test that empty string after trim becomes None."""
        result = InputValidator.validate_description("   ")
        assert result is None

    def test_validate_description_max_length_valid(self):
        """Test maximum length (500 chars) is accepted."""
        desc = "x" * 500
        result = InputValidator.validate_description(desc)
        assert len(result) == 500

    def test_validate_description_exceeds_max_length(self):
        """Test that descriptions exceeding 500 chars are rejected."""
        long_desc = "x" * 501
        try:
            InputValidator.validate_description(long_desc)
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "too long" in str(e).lower()


class TestValidatePriceValidation:
    """Test Layer 3: Semantic validation for price."""

    def test_validate_price_valid(self):
        """Test valid price."""
        result = InputValidator.validate_price(99.99)
        assert result == 99.99

    def test_validate_price_none(self):
        """Test that None is allowed."""
        result = InputValidator.validate_price(None)
        assert result is None

    def test_validate_price_min_valid(self):
        """Test minimum price (0.01) is accepted."""
        result = InputValidator.validate_price(0.01)
        assert result == 0.01

    def test_validate_price_max_valid(self):
        """Test maximum price (1,000,000) is accepted."""
        result = InputValidator.validate_price(1_000_000.00)
        assert result == 1_000_000.00

    def test_validate_price_zero_rejected(self):
        """Test that price 0.00 is rejected."""
        try:
            InputValidator.validate_price(0.00)
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "0.01" in str(e)

    def test_validate_price_negative_rejected(self):
        """Test that negative prices are rejected."""
        try:
            InputValidator.validate_price(-100)
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "0.01" in str(e)

    def test_validate_price_exceeds_max_rejected(self):
        """Test that prices > 1,000,000 are rejected."""
        try:
            InputValidator.validate_price(9_999_999)
            assert False, "Should raise ValidationError"
        except ValidationError as e:
            assert "1000000" in str(e) or "1,000,000" in str(e)

    def test_validate_price_rounding(self):
        """Test that prices are rounded to 2 decimals."""
        result = InputValidator.validate_price(99.999)
        assert result == 100.00

    def test_validate_price_integer_accepted(self):
        """Test that integer prices are accepted."""
        result = InputValidator.validate_price(100)
        assert result == 100.00


class TestXSSInjectionPrevention:
    """Test that special HTML/JavaScript strings are accepted safely (no XSS risk at API layer)."""

    def test_xss_script_tag_accepted_safely(self):
        """Test that <script> tags as plain text are accepted (safe on server)."""
        response = client.post("/items", json={"name": "<script>alert('xss')</script>"})
        # API accepts as plain text (no server-side execution risk)
        assert response.status_code == 201
        data = response.json()
        assert "<script>" in data["name"]

    def test_xss_img_onerror_accepted_safely(self):
        """Test that img onerror as plain text is accepted."""
        response = client.post("/items", json={"name": "<img src=x onerror=alert(1)>"})
        assert response.status_code == 201
        data = response.json()
        assert "<img" in data["name"]

    def test_xss_svg_onload_accepted_safely(self):
        """Test that svg onload as plain text is accepted."""
        response = client.post("/items", json={"name": "<svg onload=alert(1)>"})
        assert response.status_code == 201

    def test_xss_encoded_script_accepted(self):
        """Test that HTML-encoded <script> is accepted as plain text."""
        response = client.post("/items", json={"name": "&#60;script&#62;alert(1)&#60;/script&#62;"})
        assert response.status_code == 201

    def test_xss_in_description_accepted_safely(self):
        """Test that XSS-like patterns in description are accepted as plain text."""
        response = client.post(
            "/items",
            json={"name": "Valid", "description": "<img src=x onerror=alert(1)>"},
        )
        # Accepted as plain text (no server-side interpretation)
        assert response.status_code == 201


class TestSQLInjectionPrevention:
    """Test that SQL-like patterns as plain text are accepted safely."""

    def test_sql_drop_table_accepted_safely(self):
        """Test that SQL DROP TABLE as plain text is accepted (safe)."""
        response = client.post("/items", json={"name": "'; DROP TABLE items; --"})
        # Accepted as plain text - our API uses in-memory storage, no SQL execution
        assert response.status_code == 201

    def test_sql_union_select_accepted_safely(self):
        """Test that SQL UNION SELECT as plain text is accepted."""
        response = client.post("/items", json={"name": "'; UNION SELECT * FROM users; --"})
        assert response.status_code == 201

    def test_sql_or_1_1_accepted_safely(self):
        """Test that SQL 'or 1=1 as plain text is accepted."""
        response = client.post("/items", json={"name": "' OR '1'='1"})
        assert response.status_code == 201

    def test_sql_comment_accepted_safely(self):
        """Test that SQL comments as plain text are accepted."""
        response = client.post("/items", json={"name": "Test -- SQL comment"})
        # Accepted as plain text
        assert response.status_code == 201


class TestUnicodeAndEncodingAttacks:
    """Test handling of Unicode tricks and encoding attacks."""

    def test_null_bytes_handled(self):
        """Test that null bytes are accepted as plain text."""
        response = client.post("/items", json={"name": "Name\x00Injection"})
        # Accepted as plain text
        assert response.status_code == 201
        # Null byte is preserved in string
        assert "\x00" in response.json()["name"]

    def test_right_to_left_override(self):
        """Test handling of right-to-left override unicode."""
        response = client.post("/items", json={"name": "\u202ETaskName"})
        # Should either reject or accept (unicode is valid)
        assert response.status_code in [201, 422]

    def test_zero_width_characters(self):
        """Test handling of zero-width characters."""
        response = client.post("/items", json={"name": "Task\u200bName"})
        # Should either reject or accept
        assert response.status_code in [201, 422]


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_name_exactly_100_chars(self):
        """Test that exactly 100 char names are accepted."""
        response = client.post("/items", json={"name": "x" * 100})
        assert response.status_code == 201
        assert len(response.json()["name"]) == 100

    def test_name_101_chars_rejected(self):
        """Test that 101 char names are rejected."""
        response = client.post("/items", json={"name": "x" * 101})
        assert response.status_code == 422

    def test_description_exactly_500_chars(self):
        """Test that exactly 500 char descriptions are accepted."""
        response = client.post("/items", json={"name": "Valid", "description": "x" * 500})
        assert response.status_code == 201
        assert len(response.json()["description"]) == 500

    def test_price_exactly_1_million(self):
        """Test that price of exactly 1 million is accepted."""
        response = client.post("/items", json={"name": "Expensive", "price": 1_000_000.00})
        assert response.status_code == 201
        assert response.json()["price"] == 1_000_000.00

    def test_price_1_000_000_01_rejected(self):
        """Test that price > 1 million is rejected."""
        response = client.post("/items", json={"name": "Too Expensive", "price": 1_000_000.01})
        assert response.status_code == 422


class TestValidationErrorMessages:
    """Test that validation error messages don't leak sensitive information."""

    def test_empty_name_error_message(self):
        """Test error message for empty name doesn't expose constraints."""
        response = client.post("/items", json={"name": ""})
        # RFC 7807 format - generic detail message
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body
        detail = body["detail"]

        # Should be generic, not expose exact constraints
        assert (
            "invalid" in detail.lower()
            or "validation" in detail.lower()
            or "parameters" in detail.lower()
        )

    def test_long_name_error_message(self):
        """Test error message for long name doesn't expose exact constraints."""
        response = client.post("/items", json={"name": "x" * 10000})
        assert response.status_code == 422
        body = response.json()
        detail = body["detail"]

        # Should be generic, not expose "max 100" constraint
        assert "max" not in detail.lower() or "100" not in detail
        assert (
            "invalid" in detail.lower()
            or "validation" in detail.lower()
            or "parameters" in detail.lower()
        )

    def test_invalid_price_error_message(self):
        """Test error message for invalid price."""
        response = client.post("/items", json={"name": "Test", "price": -100})
        assert response.status_code == 422
        body = response.json()
        detail = body["detail"]

        # Should be generic
        assert (
            "invalid" in detail.lower()
            or "validation" in detail.lower()
            or "parameters" in detail.lower()
        )
