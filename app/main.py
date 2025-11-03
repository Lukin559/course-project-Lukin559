import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SecDev Course App",
    version="0.1.0",
    description=(
        "A comprehensive FastAPI application with proper validation, "
        "logging, and error handling"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)


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
def health():
    return {"status": "ok"}


# In-memory database with improved structure
_DB = {"items": [], "next_id": 1}


@app.post("/items", response_model=ItemResponse, status_code=201)
def create_item(item_data: ItemCreate):
    """Create a new item with validation."""
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
def list_items():
    """Get all items."""
    logger.info(f"Listing {len(_DB['items'])} items")
    return _DB["items"]


@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int):
    """Get a specific item by ID."""
    logger.info(f"Getting item with ID: {item_id}")

    for item in _DB["items"]:
        if item["id"] == item_id:
            logger.info(f"Item found: {item['name']}")
            return item

    logger.warning(f"Item not found with ID: {item_id}")
    raise ApiError(code="not_found", message="item not found", status=404)


@app.put("/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item_data: ItemUpdate):
    """Update an existing item."""
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
def delete_item(item_id: int):
    """Delete an item."""
    logger.info(f"Deleting item with ID: {item_id}")

    for i, item in enumerate(_DB["items"]):
        if item["id"] == item_id:
            deleted_item = _DB["items"].pop(i)
            logger.info(f"Item deleted successfully: {deleted_item['name']}")
            return

    logger.warning(f"Item not found for deletion with ID: {item_id}")
    raise ApiError(code="not_found", message="item not found", status=404)
