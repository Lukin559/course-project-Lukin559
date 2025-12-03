"""Secure file upload handler (P06 Secure Coding).

Control: Валидация файлов, защита от path traversal, magic bytes
Related: NFR-005 (validation), R003 (tampering), R007 (data protection)
"""

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Magic bytes for supported formats
MAGIC_BYTES = {
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
}

MAX_FILE_SIZE = 5_000_000  # 5MB


class FileValidationError(ValueError):
    """File validation error (safe for logging)."""

    pass


def sniff_mimetype(data: bytes) -> tuple[str, str] | None:
    """Detect MIME type and extension from magic bytes.

    Args:
        data: File content (first N bytes)

    Returns:
        Tuple of (mimetype, extension) or None if unsupported.

    Security: Only allows known safe types.
    """
    if not data:
        return None

    for magic, (mimetype, ext) in MAGIC_BYTES.items():
        if data.startswith(magic):
            return (mimetype, ext)

    # Check for JPEG EOI marker for more reliable detection
    if data.startswith(b"\xff\xd8") and b"\xff\xd9" in data:
        return ("image/jpeg", ".jpg")

    return None


def validate_file_upload(data: bytes, max_size: int = MAX_FILE_SIZE) -> tuple[str, str]:
    """Validate uploaded file.

    Args:
        data: File content
        max_size: Maximum allowed size in bytes

    Returns:
        Tuple of (mimetype, extension)

    Raises:
        FileValidationError: If file is invalid

    Security:
        - Checks size first (DOS prevention)
        - Checks magic bytes (type validation)
        - No filename parsing (UUIDs only)
    """
    # Size check (DOS prevention)
    if len(data) > max_size:
        raise FileValidationError(f"file_too_large (max {max_size} bytes, got {len(data)})")

    if len(data) == 0:
        raise FileValidationError("file_empty")

    # Magic bytes check
    result = sniff_mimetype(data)
    if not result:
        raise FileValidationError("unsupported_file_type")

    return result


def secure_save_file(root: Path, data: bytes) -> Path:
    """Safely save uploaded file with path traversal prevention.

    Args:
        root: Upload directory (must exist)
        data: File content

    Returns:
        Path to saved file

    Raises:
        FileValidationError: If file is invalid or unsafe

    Security:
        1. Validate file type & size
        2. Use UUID filename (no user input)
        3. Check for path traversal
        4. Check for symlink attacks
    """
    # Step 1: Validate file
    mimetype, ext = validate_file_upload(data)

    # Step 2: Resolve upload directory (must exist and be readable)
    try:
        root_resolved = root.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise FileValidationError("upload_dir_not_found")

    # Step 3: Generate UUID filename (no user input)
    filename = f"{uuid.uuid4()}{ext}"
    file_path = root_resolved / filename

    # Step 4: Prevent path traversal
    try:
        file_path_resolved = file_path.resolve()
    except (RuntimeError, OSError) as e:
        logger.warning(
            "Path resolution failed (possible traversal attempt)",
            extra={"error": str(e), "filename": filename},
        )
        raise FileValidationError("invalid_path")

    # Check that resolved path is still within upload directory
    if not str(file_path_resolved).startswith(str(root_resolved)):
        logger.warning(
            "Path traversal attempt detected",
            extra={
                "attempted_path": str(file_path_resolved),
                "upload_dir": str(root_resolved),
            },
        )
        raise FileValidationError("path_traversal_detected")

    # Step 5: Check for symlink attacks (parents shouldn't be symlinks)
    for parent in file_path_resolved.parents:
        if parent.is_symlink():
            logger.warning(
                "Symlink in parent directory detected",
                extra={"symlink_path": str(parent)},
            )
            raise FileValidationError("symlink_in_path")

    # Step 6: Write file
    try:
        file_path_resolved.write_bytes(data)
        logger.info(
            "File uploaded successfully",
            extra={
                "filename": filename,
                "size": len(data),
                "mimetype": mimetype,
                "path": str(file_path_resolved),
            },
        )
        return file_path_resolved
    except (IOError, OSError) as e:
        logger.error("File write failed", extra={"error": str(e), "filename": filename})
        raise FileValidationError(f"file_write_failed: {str(e)}")
