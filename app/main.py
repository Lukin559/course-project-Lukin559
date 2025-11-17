import logging
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi.exceptions import RequestValidationError

from app.correlation import get_correlation_id, set_correlation_id
from app.validation import InputValidator, ValidationError as InputValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize rate limiter (NFR-008: Task API Rate Limiting)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SecDev Course App",
    version="0.1.0",
    description=(
        "A comprehensive FastAPI application with proper validation, "
        "logging, error handling, and rate limiting"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============= Middleware: Correlation ID Injection =============
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """Middleware to inject correlation ID into request context.
    
    Implements ADR-003: Request Correlation & Distributed Tracing.
    - Generate UUID for every request if not provided
    - Store in context for access in handlers/loggers
    - Add to response headers for client tracing
    """
    # Get or generate correlation ID
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    set_correlation_id(cid)
    
    # Add to request state for later access
    request.state.correlation_id = cid
    
    logger.info(
        "HTTP request",
        extra={
            "correlation_id": cid,
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
        }
    )
    
    response = await call_next(request)
    
    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = cid
    
    logger.info(
        "HTTP response",
        extra={
            "correlation_id": cid,
            "status": response.status_code,
            "path": request.url.path,
        }
    )
    
    return response


# ============= RFC 7807 Error Format Handlers =============
class ApiError(Exception):
    """Custom API error with RFC 7807 formatting."""

    def __init__(self, code: str, message: str, status: int = 400, details: Optional[dict] = None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


class Rfc7807Response(BaseModel):
    """RFC 7807 Problem Details response format."""

    type: str = Field(..., description="Error type URI")
    title: str = Field(..., description="Short error title")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable error description")
    instance: Optional[str] = Field(None, description="Request path")
    correlation_id: str = Field(..., description="Request correlation ID for tracing")


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    """Handle custom API errors with RFC 7807 format."""
    correlation_id = get_correlation_id()
    path = str(request.url.path)
    
    logger.warning(
        f"API error: {exc.code} - {exc.message}",
        extra={
            "correlation_id": correlation_id,
            "error_code": exc.code,
            "error_message": exc.message,
            "error_status": exc.status,
            "request_path": path,
        }
    )
    
    return JSONResponse(
        status_code=exc.status,
        content={
            "type": f"https://api.secdev.example.com/errors/{exc.code}",
            "title": exc.code.replace("_", " ").title(),
            "status": exc.status,
            "detail": exc.message,
            "instance": path,
            "correlation_id": correlation_id,
            **({"errors": exc.details} if exc.details else {}),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTPException with RFC 7807 format (for validation errors, etc.)."""
    correlation_id = get_correlation_id()
    path = str(request.url.path)
    
    # Extract validation error details if available
    detail_str = exc.detail if isinstance(exc.detail, str) else "http_error"
    
    logger.warning(
        f"HTTP error: {exc.status_code}",
        extra={
            "correlation_id": correlation_id,
            "error_status": exc.status_code,
            "request_path": path,
            "detail": detail_str,
        }
    )
    
    # For validation errors (422), provide structured format
    error_code = "validation_error" if exc.status_code == 422 else "http_error"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"https://api.secdev.example.com/errors/{error_code}",
            "title": error_code.replace("_", " ").title(),
            "status": exc.status_code,
            "detail": detail_str,
            "instance": path,
            "correlation_id": correlation_id,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions with generic error to client, full log server-side."""
    correlation_id = get_correlation_id()
    path = str(request.url.path)
    
    # Log full details server-side
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "correlation_id": correlation_id,
            "request_path": path,
            "error_message": str(exc),
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )
    
    # Return generic error to client (never expose details)
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://api.secdev.example.com/errors/internal_error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An internal error occurred. Please contact support.",
            "instance": path,
            "correlation_id": correlation_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with RFC 7807 format."""
    correlation_id = get_correlation_id()
    path = str(request.url.path)
    
    # Extract field errors for logging
    errors_by_field = {}
    for error in exc.errors():
        field = ".".join(str(x) for x in error.get("loc", [])[1:])  # Skip 'body'
        if field:
            errors_by_field[field] = error.get("msg", "Invalid value")
    
    logger.warning(
        "Validation error",
        extra={
            "correlation_id": correlation_id,
            "request_path": path,
            "error_count": len(exc.errors()),
            "fields": list(errors_by_field.keys()),
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "type": "https://api.secdev.example.com/errors/validation_error",
            "title": "Validation Error",
            "status": 422,
            "detail": "Invalid request parameters",
            "instance": path,
            "correlation_id": correlation_id,
        },
    )


# ============= Pydantic Models with Integrated Validation =============
class ItemCreate(BaseModel):
    """Item creation request model with ADR-002 validation."""

    name: str = Field(..., min_length=1, max_length=100, description="Item name")
    description: Optional[str] = Field(
        None, max_length=500, description="Item description"
    )
    price: Optional[float] = Field(
        None, ge=0, description="Item price (must be non-negative)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Apply canonicalization and validation to name."""
        try:
            canonical = InputValidator.canonicalize_name(v)
            return canonical
        except InputValidationError as e:
            raise ValueError(str(e))

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        """Apply canonicalization to description."""
        try:
            canonical = InputValidator.validate_description(v)
            return canonical
        except InputValidationError as e:
            raise ValueError(str(e))

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        """Apply semantic validation to price."""
        try:
            validated = InputValidator.validate_price(v)
            return validated
        except InputValidationError as e:
            raise ValueError(str(e))


class ItemResponse(BaseModel):
    """Item response model."""

    id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemUpdate(BaseModel):
    """Item update request model with ADR-002 validation."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[float] = Field(None, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Apply canonicalization to name if provided."""
        if v is not None:
            try:
                canonical = InputValidator.canonicalize_name(v)
                return canonical
            except InputValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        """Apply canonicalization to description if provided."""
        if v is not None:
            try:
                canonical = InputValidator.validate_description(v)
                return canonical
            except InputValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        """Apply semantic validation to price if provided."""
        if v is not None:
            try:
                validated = InputValidator.validate_price(v)
                return validated
            except InputValidationError as e:
                raise ValueError(str(e))
        return v


class ErrorResponse(BaseModel):
    """Generic error response (RFC 7807)."""

    error: dict = Field(..., description="Error details")


# ============= In-Memory Database =============
_DB = {"items": [], "next_id": 1}


# ============= Endpoints with Logging & Rate Limiting =============
@app.get("/health")
@limiter.limit("100/minute")  # NFR-008: Health check rate limiting
def health(request: Request):
    """Health check endpoint with rate limiting.
    
    Returns correlation_id in response for tracing.
    """
    correlation_id = get_correlation_id()
    logger.info("Health check requested", extra={"correlation_id": correlation_id})
    return {
        "status": "ok",
        "service": "task-tracker",
        "correlation_id": correlation_id,
    }


@app.post("/items", response_model=ItemResponse, status_code=201)
@limiter.limit("200/minute")  # NFR-008: Task creation rate limiting
def create_item(request: Request, item_data: ItemCreate):
    """Create a new item with validation and rate limiting.
    
    Implements ADR-002 (validation) and ADR-001/ADR-003 (error handling + correlation).
    """
    correlation_id = get_correlation_id()
    logger.info(
        f"Creating new item: {item_data.name}",
        extra={
            "correlation_id": correlation_id,
            "item_name": item_data.name,
        }
    )

    item = {
        "id": _DB["next_id"],
        "name": item_data.name,
        "description": item_data.description,
        "price": item_data.price,
        "created_at": datetime.now(),
    }

    _DB["items"].append(item)
    _DB["next_id"] += 1

    logger.info(
        f"Item created: {item['id']}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item["id"],
            "item_name": item_data.name,
        }
    )
    return item


@app.get("/items", response_model=List[ItemResponse])
@limiter.limit("300/minute")  # NFR-008: Task listing rate limiting
def list_items(request: Request):
    """Get all items with rate limiting."""
    correlation_id = get_correlation_id()
    logger.info(
        f"Listing {len(_DB['items'])} items",
        extra={
            "correlation_id": correlation_id,
            "item_count": len(_DB["items"]),
        }
    )
    return _DB["items"]


@app.get("/items/{item_id}", response_model=ItemResponse)
@limiter.limit("300/minute")  # NFR-008: Task retrieval rate limiting
def get_item(request: Request, item_id: int):
    """Get a specific item by ID with rate limiting."""
    correlation_id = get_correlation_id()
    logger.info(
        f"Getting item: {item_id}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item_id,
        }
    )

    for item in _DB["items"]:
        if item["id"] == item_id:
            logger.info(
                f"Item found: {item['name']}",
                extra={
                    "correlation_id": correlation_id,
                    "item_id": item_id,
                    "item_name": item["name"],
                }
            )
            return item

    logger.warning(
        f"Item not found: {item_id}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item_id,
        }
    )
    raise ApiError(code="not_found", message="item not found", status=404)


@app.put("/items/{item_id}", response_model=ItemResponse)
@limiter.limit("200/minute")  # NFR-008: Task update rate limiting
def update_item(request: Request, item_id: int, item_data: ItemUpdate):
    """Update an existing item with rate limiting."""
    correlation_id = get_correlation_id()
    logger.info(
        f"Updating item: {item_id}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item_id,
        }
    )

    for i, item in enumerate(_DB["items"]):
        if item["id"] == item_id:
            # Update only provided fields
            update_data = item_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                item[key] = value

            logger.info(
                f"Item updated: {item['name']}",
                extra={
                    "correlation_id": correlation_id,
                    "item_id": item_id,
                    "item_name": item["name"],
                }
            )
            return item

    logger.warning(
        f"Item not found for update: {item_id}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item_id,
        }
    )
    raise ApiError(code="not_found", message="item not found", status=404)


@app.delete("/items/{item_id}", status_code=204)
@limiter.limit("200/minute")  # NFR-008: Task deletion rate limiting
def delete_item(request: Request, item_id: int):
    """Delete an item with rate limiting."""
    correlation_id = get_correlation_id()
    logger.info(
        f"Deleting item: {item_id}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item_id,
        }
    )

    for i, item in enumerate(_DB["items"]):
        if item["id"] == item_id:
            deleted_item = _DB["items"].pop(i)
            logger.info(
                f"Item deleted: {deleted_item['name']}",
                extra={
                    "correlation_id": correlation_id,
                    "item_id": item_id,
                    "item_name": deleted_item["name"],
                }
            )
            return

    logger.warning(
        f"Item not found for deletion: {item_id}",
        extra={
            "correlation_id": correlation_id,
            "item_id": item_id,
        }
    )
    raise ApiError(code="not_found", message="item not found", status=404)
