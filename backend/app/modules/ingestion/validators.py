
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile


MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".html",
    ".htm",
}


@dataclass
class ValidatedUpload:
    filename: str
    extension: str
    content_type: str
    size: int
    content: bytes


def _get_extension(filename: str) -> str:
    if not filename or "\x00" in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        )

    # Treat both Windows and Unix separators as path separators.
    safe_name = filename.replace("\\", "/").split("/")[-1]
    extension = PurePosixPath(safe_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file extension. Allowed: PDF, DOCX, HTML.",
        )

    return extension


def _validate_pdf(content: bytes) -> bool:
    # PDF header should occur near the beginning of the file.
    return content[:1024].lstrip().startswith(b"%PDF-")


def _validate_docx(content: bytes) -> bool:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())

            return (
                "[Content_Types].xml" in names
                and "word/document.xml" in names
            )
    except (BadZipFile, OSError):
        return False


def _validate_html(content: bytes) -> bool:
    try:
        decoded = content.decode("utf-8-sig").strip().lower()
    except UnicodeDecodeError:
        return False

    if not decoded:
        return False

    # Require recognizable HTML markup rather than accepting
    # arbitrary text files renamed to .html.
    markers = (
        "<!doctype html",
        "<html",
        "<head",
        "<body",
    )

    return any(marker in decoded[:4096] for marker in markers)


def _validate_content(extension: str, content: bytes) -> None:
    if extension == ".pdf" and not _validate_pdf(content):
        raise HTTPException(
            status_code=415,
            detail="File content does not appear to be a valid PDF.",
        )

    if extension == ".docx" and not _validate_docx(content):
        raise HTTPException(
            status_code=415,
            detail="File content does not appear to be a valid DOCX document.",
        )

    if extension in {".html", ".htm"} and not _validate_html(content):
        raise HTTPException(
            status_code=415,
            detail="File content does not appear to be valid HTML.",
        )


async def validate_upload(
    file: UploadFile,
    max_file_size: int = MAX_FILE_SIZE,
) -> ValidatedUpload:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    extension = _get_extension(file.filename)

    # Read at most one byte beyond the limit to detect oversized uploads.
    content = await file.read(max_file_size + 1)

    # Reset the stream so downstream processing can read it again.
    await file.seek(0)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(content) > max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum size of {max_file_size} bytes.",
        )

    _validate_content(extension, content)

    return ValidatedUpload(
        filename=file.filename.replace("\\", "/").split("/")[-1],
        extension=extension,
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
        content=content,
    )
