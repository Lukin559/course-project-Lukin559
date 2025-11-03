import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status


# Pydantic models for request/response validation
class ItemCreate(BaseModel):
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
        if not v.strip():
            raise ValueError("Name cannot be empty or only whitespace")
        return v.strip()


class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[float] = Field(None, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty or only whitespace")
        return v.strip() if v else v


class ErrorResponse(BaseModel):
    error: dict = Field(..., description="Error details")


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Normalize FastAPI HTTPException into our error envelope
    detail = exc.detail if isinstance(exc.detail, str) else "http_error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": detail}},
    )


@app.get("/health")
@limiter.limit("100/minute")  # NFR-008: Health check rate limiting
def health(request: Request):
    """Health check endpoint with rate limiting"""
    logger.info("Health check requested")
    return {"status": "ok", "service": "task-tracker"}


# In-memory database with improved structure
_DB = {"items": [], "next_id": 1}


@app.post("/items", response_model=ItemResponse, status_code=201)
@limiter.limit("200/minute")  # NFR-008: Task creation rate limiting
def create_item(request: Request, item_data: ItemCreate):
    """Create a new item with validation and rate limiting."""
    logger.info(f"Creating new item: {item_data.name}")

    item = {
        "id": _DB["next_id"],
        "name": item_data.name,
        "description": item_data.description,
        "price": item_data.price,
        "created_at": datetime.now(),
    }

    _DB["items"].append(item)
    _DB["next_id"] += 1

    logger.info(f"Item created successfully with ID: {item['id']}")
    return item


@app.get("/items", response_model=List[ItemResponse])
@limiter.limit("300/minute")  # NFR-008: Task listing rate limiting
def list_items(request: Request):
    """Get all items with rate limiting."""
    logger.info(f"Listing {len(_DB['items'])} items")
    return _DB["items"]


@app.get("/items/{item_id}", response_model=ItemResponse)
@limiter.limit("300/minute")  # NFR-008: Task retrieval rate limiting
def get_item(request: Request, item_id: int):
    """Get a specific item by ID with rate limiting."""
    logger.info(f"Getting item with ID: {item_id}")

    for item in _DB["items"]:
        if item["id"] == item_id:
            logger.info(f"Item found: {item['name']}")
            return item

    logger.warning(f"Item not found with ID: {item_id}")
    raise ApiError(code="not_found", message="item not found", status=404)


@app.put("/items/{item_id}", response_model=ItemResponse)
@limiter.limit("200/minute")  # NFR-008: Task update rate limiting
def update_item(request: Request, item_id: int, item_data: ItemUpdate):
    """Update an existing item with rate limiting."""
    logger.info(f"Updating item with ID: {item_id}")

    for i, item in enumerate(_DB["items"]):
        if item["id"] == item_id:
            # Update only provided fields
            update_data = item_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                item[key] = value

            logger.info(f"Item updated successfully: {item['name']}")
            return item

    logger.warning(f"Item not found for update with ID: {item_id}")
    raise ApiError(code="not_found", message="item not found", status=404)


@app.delete("/items/{item_id}", status_code=204)
@limiter.limit("200/minute")  # NFR-008: Task deletion rate limiting
def delete_item(request: Request, item_id: int):
    """Delete an item with rate limiting."""
    logger.info(f"Deleting item with ID: {item_id}")

    for i, item in enumerate(_DB["items"]):
        if item["id"] == item_id:
            deleted_item = _DB["items"].pop(i)
            logger.info(f"Item deleted successfully: {deleted_item['name']}")
            return

    logger.warning(f"Item not found for deletion with ID: {item_id}")
    raise ApiError(code="not_found", message="item not found", status=404)
