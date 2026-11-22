import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4


class FileStorageError(Exception):
    """Raised when a document cannot be stored or removed."""


def store_file(content: bytes, extension: str, storage_root: Path) -> str:
    if not content:
        raise FileStorageError("Cannot store an empty file.")

    extension = extension.lower()
    if not extension.startswith(".") or len(extension) > 10:
        raise FileStorageError("Invalid file extension.")

    root = storage_root.expanduser().resolve()
    directory = root / str(uuid4())
    temporary_path: Path | None = None

    try:
        root.mkdir(parents=True, exist_ok=True)
        directory.mkdir(parents=False, exist_ok=False)
        destination = directory / f"{uuid4()}{extension}"

        with tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, prefix=".upload-", suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, destination)
        return destination.relative_to(root).as_posix()

    except OSError as exc:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        shutil.rmtree(directory, ignore_errors=True)
        raise FileStorageError("Unable to store uploaded document.") from exc


def resolve_storage_path(relative_path: str, storage_root: Path) -> Path:
    root = storage_root.expanduser().resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise FileStorageError("Invalid storage path.")
    return target


def delete_file(relative_path: str, storage_root: Path) -> None:
    target = resolve_storage_path(relative_path, storage_root)
    root = storage_root.expanduser().resolve()
    try:
        target.unlink(missing_ok=True)
        if target.parent != root and target.parent.exists():
            target.parent.rmdir()
    except OSError as exc:
        raise FileStorageError("Unable to remove stored document.") from exc
