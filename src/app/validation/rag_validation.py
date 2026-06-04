from fastapi import UploadFile

from app.common.responses import ErrorResponse

# File upload constraints
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def validate_file_upload(file: UploadFile) -> None:
    """Validate file type and extension before upload"""
    # Validate file extension
    file_name = file.filename if file.filename else ""

    file_ext = file_name.lower().split(".")[-1] if "." in file_name else ""
    if f".{file_ext}" not in SUPPORTED_EXTENSIONS:
        raise ErrorResponse(
            400,
            f"Unsupported file type. Allowed extensions: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    # Validate MIME type
    if file.content_type and file.content_type not in SUPPORTED_MIME_TYPES:
        raise ErrorResponse(
            400,
            f"Unsupported content type: {file.content_type}. Allowed types: PDF, DOCX, TXT",
        )


async def validate_file_size(file: UploadFile) -> float:
    """Read and validate file size, returns file size in MB"""
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)

    if len(file_content) == 0:
        raise ErrorResponse(400, "Empty file uploaded")

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise ErrorResponse(
            400,
            f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB",
        )

    return file_size_mb
