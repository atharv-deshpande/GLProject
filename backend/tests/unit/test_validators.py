
import pytest

from fastapi import HTTPException, UploadFile
from io import BytesIO

from app.modules.ingestion.validators import validate_upload


def make_upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=None,
    )


@pytest.mark.asyncio
async def test_valid_pdf():
    content = b"%PDF-1.7\nsample PDF content"
    upload = make_upload("policy.pdf", content)

    result = await validate_upload(upload)

    assert result.extension == ".pdf"
    assert result.size == len(content)


@pytest.mark.asyncio
async def test_reject_unsupported_extension():
    upload = make_upload("malware.exe", b"some content")

    with pytest.raises(HTTPException) as exc:
        await validate_upload(upload)

    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_reject_invalid_pdf():
    upload = make_upload("fake.pdf", b"This is not a PDF")

    with pytest.raises(HTTPException) as exc:
        await validate_upload(upload)

    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_reject_empty_file():
    upload = make_upload("empty.pdf", b"")

    with pytest.raises(HTTPException) as exc:
        await validate_upload(upload)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_reject_oversized_file():
    upload = make_upload("large.pdf", b"%PDF-" + b"A" * 100)

    with pytest.raises(HTTPException) as exc:
        await validate_upload(upload, max_file_size=50)

    assert exc.value.status_code == 413
