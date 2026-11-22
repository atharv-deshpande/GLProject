import pytest

from app.modules.ingestion.processing.file_storage import (
    FileStorageError,
    delete_file,
    resolve_storage_path,
    store_file,
)


def test_store_and_delete_file(tmp_path):
    content = b"private source bytes"
    relative = store_file(content, ".pdf", tmp_path)
    stored = resolve_storage_path(relative, tmp_path)
    assert stored.read_bytes() == content
    delete_file(relative, tmp_path)
    assert not stored.exists()


def test_storage_rejects_invalid_extension(tmp_path):
    with pytest.raises(FileStorageError):
        store_file(b"x", "pdf", tmp_path)


def test_storage_path_cannot_escape_root(tmp_path):
    with pytest.raises(FileStorageError):
        resolve_storage_path("../outside.txt", tmp_path)
