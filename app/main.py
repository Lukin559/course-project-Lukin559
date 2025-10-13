import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Task Tracker - SecDev Course App",
    version="0.1.0",
    description="A secure task management application with threat modeling controls",
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status


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


# Example minimal entity (for tests/demo)
_DB = {"items": []}


@app.post("/items")
@limiter.limit("200/minute")  # NFR-008: Task creation rate limiting
def create_item(request: Request, name: str):
    """Create a new task item with rate limiting and validation"""
    logger.info(f"Creating task item: {name}")

    # NFR-005: Input validation
    if not name or len(name) > 100:
        logger.warning(f"Validation error for task name: {name}")
        raise ApiError(
            code="validation_error", message="name must be 1..100 chars", status=422
        )

    # NFR-007: Audit logging
    item = {"id": len(_DB["items"]) + 1, "name": name}
    _DB["items"].append(item)
    logger.info(f"Task item created successfully with ID: {item['id']}")
    return item


@app.get("/items/{item_id}")
@limiter.limit("300/minute")  # NFR-008: Task retrieval rate limiting
def get_item(request: Request, item_id: int):
    """Get a task item by ID with rate limiting and audit logging"""
    logger.info(f"Retrieving task item with ID: {item_id}")

    for it in _DB["items"]:
        if it["id"] == item_id:
            logger.info(f"Task item found: {it['name']}")
            return it

    logger.warning(f"Task item not found with ID: {item_id}")
    raise ApiError(code="not_found", message="item not found", status=404)
