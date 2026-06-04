import io

import pillow_heif
from PIL import Image

from app.common.responses import ErrorResponse

pillow_heif.register_heif_opener()

_HEIC_BRANDS = {b"heic", b"heix", b"mif1", b"msf1"}

_MIME_TO_EXT: dict[str, str] = {
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/aac": "aac",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/x-msvideo": "avi",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/msword": "doc",
    "application/vnd.ms-excel": "xls",
    "application/vnd.ms-powerpoint": "ppt",
}

# Reverse mapping: extension to MIME type
_EXT_TO_MIME: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "heic": "image/heic",
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "mp4": "video/mp4",
    "3gp": "video/3gpp",
    "webm": "video/webm",
    "avi": "video/x-msvideo",
    "mov": "video/quicktime",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
}

_SIZE_LIMITS_MB: dict[str, float] = {
    "image": 5,
    "video": 5,
    "audio": 5,
    "document": 5,
    "document_text": 5,  # CSV, TXT
}

_OFFICE_ZIP: dict[str, tuple[str, str]] = {
    "docx": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "xlsx": (
        "xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "pptx": (
        "pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "odt": ("odt", "application/vnd.oasis.opendocument.text"),
    "ods": ("ods", "application/vnd.oasis.opendocument.spreadsheet"),
}

_OFFICE_OLE: dict[str, tuple[str, str]] = {
    "doc": ("doc", "application/msword"),
    "xls": ("xls", "application/vnd.ms-excel"),
    "ppt": ("ppt", "application/vnd.ms-powerpoint"),
}

GEMINI_SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "audio/mpeg",
    "audio/ogg",
    "audio/aac",
    "audio/mp4",
    "audio/wav",
    "audio/flac",
    "audio/webm",
    "video/mp4",
    "video/webm",
    "video/x-msvideo",
    "video/quicktime",
    "application/pdf",
}


def mime_to_hint_ext(mime_type: str) -> str:
    """Derive a file-extension hint from a MIME type string.

    Strips codec suffixes (e.g. 'audio/ogg; codecs=opus') before lookup.
    Returns empty string when the MIME type is unknown.
    """
    base = mime_type.split(";")[0].strip().lower()
    return _MIME_TO_EXT.get(base, "")


def ext_to_mime(ext: str) -> str:
    """Convert file extension to MIME type.

    Returns 'application/octet-stream' for unknown extensions.
    """
    return _EXT_TO_MIME.get(ext.lower().strip(), "application/octet-stream")


def mime_from_url(url: str) -> str:
    """Infer MIME type from the file extension in a URL.

    Strips query parameters and extracts extension.
    Returns 'image/jpeg' as default for unknown extensions.
    """
    path = url.split("?")[0]  # strip query params
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _EXT_TO_MIME.get(ext, "image/jpeg")


def to_jpeg_if_needed(content: bytes, hint_ext: str) -> tuple[bytes, str]:
    """Convert HEIC/HEIF or WEBP to JPEG before S3 upload.

    WhatsApp image type (via URL link) only supports JPEG and PNG.
    HEIC and WEBP are rejected silently by the delivery layer.
    """
    header = content[:12]
    is_heic = (header[4:8] == b"ftyp" and header[8:12] in _HEIC_BRANDS) or hint_ext in {
        "heic",
        "heif",
    }
    is_webp = (header[:4] == b"RIFF" and header[8:12] == b"WEBP") or hint_ext == "webp"
    if is_heic or is_webp:
        image = Image.open(io.BytesIO(content)).convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90)
        return output.getvalue(), "jpg"
    return content, hint_ext


def detect_media_type(
    content: bytes, hint_ext: str = ""
) -> tuple[str, str, str, float]:
    """
    Detect media type from raw bytes and optional filename extension hint.

    Returns (file_type, ext, content_type, size_limit_mb).
    Raises ErrorResponse(400) for unsupported formats.
    """
    # 1. Image (PIL: PNG, JPEG, WEBP, GIF …)
    try:
        image = Image.open(io.BytesIO(content))
        img_ext = (image.format or "jpg").lower()
        if img_ext not in {"jpg", "jpeg", "png"}:
            raise ValueError("not an allowed image format")
        ct = "image/jpeg" if img_ext in ("jpg", "jpeg") else f"image/{img_ext}"
        return "image", img_ext, ct, _SIZE_LIMITS_MB["image"]
    except Exception:
        pass

    header = content[:12]

    # 2. Video
    if header[4:8] == b"ftyp" and hint_ext != "m4a":
        return "video", "mp4", "video/mp4", _SIZE_LIMITS_MB["video"]
    if header[:4] == b"\x1aE\xdf\xa3":
        return "video", "webm", "video/webm", _SIZE_LIMITS_MB["video"]
    if header[:4] == b"RIFF" and header[8:12] == b"AVI ":
        return "video", "avi", "video/x-msvideo", _SIZE_LIMITS_MB["video"]

    # 3. Audio (WhatsApp-native: MP3, OGG, AAC, M4A)
    if header[:3] == b"ID3" or (header[0] == 0xFF and header[1] in (0xFB, 0xF3, 0xF2)):
        return "audio", "mp3", "audio/mpeg", _SIZE_LIMITS_MB["audio"]
    if header[:4] == b"OggS":
        return "audio", "ogg", "audio/ogg", _SIZE_LIMITS_MB["audio"]
    if header[0] == 0xFF and header[1] in (0xF1, 0xF9):
        return "audio", "aac", "audio/aac", _SIZE_LIMITS_MB["audio"]
    if header[4:8] == b"ftyp" and hint_ext == "m4a":
        return "audio", "m4a", "audio/mp4", _SIZE_LIMITS_MB["audio"]

    # WAV/FLAC — not supported as WhatsApp audio, treated as document
    if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "document", "wav", "audio/wav", _SIZE_LIMITS_MB["document"]
    if header[:4] == b"fLaC":
        return "document", "flac", "audio/flac", _SIZE_LIMITS_MB["document"]

    # 4. PDF
    if content[:5] == b"%PDF-":
        return "document", "pdf", "application/pdf", _SIZE_LIMITS_MB["document"]

    # 5. ZIP-based Office (DOCX, XLSX, PPTX, ODT, ODS)
    if header[:4] == b"PK\x03\x04":
        if hint_ext in _OFFICE_ZIP:
            ext, ct = _OFFICE_ZIP[hint_ext]
        else:
            ext = hint_ext or "docx"
            ct = _OFFICE_ZIP.get(ext, _OFFICE_ZIP["docx"])[1]
        return "document", ext, ct, _SIZE_LIMITS_MB["document"]

    # 6. OLE2-based Office (DOC, XLS, PPT)
    if header[:4] == b"\xd0\xcf\x11\xe0":
        if hint_ext in _OFFICE_OLE:
            ext, ct = _OFFICE_OLE[hint_ext]
        else:
            ext = hint_ext or "doc"
            ct = _OFFICE_OLE.get(ext, _OFFICE_OLE["doc"])[1]
        return "document", ext, ct, _SIZE_LIMITS_MB["document"]

    # 7. Plain-text (require extension hint)
    if hint_ext == "csv":
        return "document", "csv", "text/csv", _SIZE_LIMITS_MB["document_text"]
    if hint_ext == "txt":
        return "document", "txt", "text/plain", _SIZE_LIMITS_MB["document_text"]

    raise ErrorResponse(
        400,
        "Unsupported file format. Allowed images: PNG, JPG, JPEG, WEBP, HEIC | "
        "Videos: MP4, WEBM, AVI | "
        "Audio: MP3, OGG, AAC, M4A (WAV/FLAC sent as document) | "
        "Documents: PDF, DOCX, XLSX, PPTX, DOC, XLS, PPT, CSV, TXT",
    )
