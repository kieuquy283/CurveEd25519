from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional


# =========================================================
# Exceptions
# =========================================================

class AttachmentStorageError(Exception):
    """Base attachment storage exception."""


class AttachmentNotFoundError(AttachmentStorageError):
    """Attachment not found."""


class AttachmentAlreadyExistsError(AttachmentStorageError):
    """Attachment already exists."""


class InvalidAttachmentPathError(AttachmentStorageError):
    """Unsafe or invalid attachment path."""


# =========================================================
# Metadata
# =========================================================

@dataclass(slots=True, frozen=True)
class AttachmentStorageRecord:
    """
    Persistent attachment record.
    """

    attachment_id: str

    relative_path: str

    sha256: str

    size_bytes: int

    created_at_unix: float


# =========================================================
# Attachment Storage
# =========================================================

class AttachmentStorage:
    """
    Secure attachment storage layer.

    Responsibilities:
    - atomic file writes
    - secure path normalization
    - attachment persistence
    - attachment retrieval
    - attachment deletion
    - SHA256 integrity verification

    Design:
    --------
    storage_root/
        attachments/
            aa/
                bb/
                    attachment_id.bin

    Benefits:
    - scalable filesystem layout
    - avoids huge single directories
    - deterministic lookup
    """

    DEFAULT_EXTENSION = ".bin"

    def __init__(
        self,
        *,
        storage_root: str | Path = "./storage",
        attachment_dir: str = "attachments",
    ) -> None:

        self.storage_root = Path(storage_root).resolve()

        self.attachment_root = (
            self.storage_root / attachment_dir
        ).resolve()

        self.attachment_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =====================================================
    # Public API
    # =====================================================

    def save_bytes(
        self,
        *,
        attachment_id: str,
        data: bytes,
        extension: str | None = None,
        overwrite: bool = False,
    ) -> AttachmentStorageRecord:
        """
        Persist attachment bytes atomically.
        """

        self._validate_attachment_id(
            attachment_id
        )

        ext = self._normalize_extension(
            extension
        )

        path = self._build_storage_path(
            attachment_id,
            ext,
        )

        if (
            path.exists()
            and not overwrite
        ):
            raise AttachmentAlreadyExistsError(
                f"Attachment already exists: "
                f"{attachment_id}"
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        sha256 = hashlib.sha256(
            data
        ).hexdigest()

        size_bytes = len(data)

        self._atomic_write(
            path,
            data,
        )

        return AttachmentStorageRecord(
            attachment_id=attachment_id,
            relative_path=str(
                path.relative_to(
                    self.storage_root
                )
            ),
            sha256=sha256,
            size_bytes=size_bytes,
            created_at_unix=path.stat().st_ctime,
        )

    def save_file(
        self,
        *,
        attachment_id: str,
        source_path: str | Path,
        extension: str | None = None,
        overwrite: bool = False,
    ) -> AttachmentStorageRecord:
        """
        Save existing file into storage.
        """

        source_path = Path(
            source_path
        ).resolve()

        if not source_path.exists():
            raise AttachmentNotFoundError(
                f"Source file not found: "
                f"{source_path}"
            )

        with source_path.open(
            "rb"
        ) as f:
            data = f.read()

        return self.save_bytes(
            attachment_id=attachment_id,
            data=data,
            extension=(
                extension
                or source_path.suffix
            ),
            overwrite=overwrite,
        )

    def open_read(
        self,
        *,
        attachment_id: str,
        extension: str | None = None,
    ) -> BinaryIO:
        """
        Open attachment for reading.
        """

        path = self.get_path(
            attachment_id=attachment_id,
            extension=extension,
        )

        return path.open("rb")

    def read_bytes(
        self,
        *,
        attachment_id: str,
        extension: str | None = None,
    ) -> bytes:
        """
        Read attachment bytes.
        """

        path = self.get_path(
            attachment_id=attachment_id,
            extension=extension,
        )

        return path.read_bytes()

    def delete(
        self,
        *,
        attachment_id: str,
        extension: str | None = None,
        missing_ok: bool = True,
    ) -> None:
        """
        Delete attachment.
        """

        path = self.get_path(
            attachment_id=attachment_id,
            extension=extension,
            must_exist=False,
        )

        if not path.exists():

            if missing_ok:
                return

            raise AttachmentNotFoundError(
                f"Attachment not found: "
                f"{attachment_id}"
            )

        path.unlink()

    def exists(
        self,
        *,
        attachment_id: str,
        extension: str | None = None,
    ) -> bool:
        """
        Check attachment existence.
        """

        try:
            path = self.get_path(
                attachment_id=attachment_id,
                extension=extension,
                must_exist=False,
            )

            return path.exists()

        except Exception:
            return False

    def get_path(
        self,
        *,
        attachment_id: str,
        extension: str | None = None,
        must_exist: bool = True,
    ) -> Path:
        """
        Resolve attachment path safely.
        """

        self._validate_attachment_id(
            attachment_id
        )

        ext = self._normalize_extension(
            extension
        )

        path = self._build_storage_path(
            attachment_id,
            ext,
        )

        self._ensure_safe_path(path)

        if (
            must_exist
            and not path.exists()
        ):
            raise AttachmentNotFoundError(
                f"Attachment not found: "
                f"{attachment_id}"
            )

        return path

    def compute_sha256(
        self,
        *,
        attachment_id: str,
        extension: str | None = None,
    ) -> str:
        """
        Compute attachment SHA256.
        """

        path = self.get_path(
            attachment_id=attachment_id,
            extension=extension,
        )

        h = hashlib.sha256()

        with path.open("rb") as f:

            while True:

                chunk = f.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                h.update(chunk)

        return h.hexdigest()

    def verify_integrity(
        self,
        *,
        attachment_id: str,
        expected_sha256: str,
        extension: str | None = None,
    ) -> bool:
        """
        Verify attachment integrity.
        """

        actual = self.compute_sha256(
            attachment_id=attachment_id,
            extension=extension,
        )

        return (
            actual.lower()
            == expected_sha256.lower()
        )

    # =====================================================
    # Internal helpers
    # =====================================================

    def _build_storage_path(
        self,
        attachment_id: str,
        extension: str,
    ) -> Path:
        """
        Build deterministic storage path.
        """

        shard_1 = attachment_id[:2]
        shard_2 = attachment_id[2:4]

        filename = (
            f"{attachment_id}"
            f"{extension}"
        )

        return (
            self.attachment_root
            / shard_1
            / shard_2
            / filename
        )

    @staticmethod
    def _normalize_extension(
        extension: Optional[str],
    ) -> str:

        if not extension:
            return (
                AttachmentStorage
                .DEFAULT_EXTENSION
            )

        extension = extension.strip()

        if not extension.startswith("."):
            extension = "." + extension

        return extension.lower()

    @staticmethod
    def _validate_attachment_id(
        attachment_id: str,
    ) -> None:

        if not isinstance(
            attachment_id,
            str,
        ):
            raise InvalidAttachmentPathError(
                "attachment_id must be string."
            )

        attachment_id = (
            attachment_id.strip()
        )

        if not attachment_id:
            raise InvalidAttachmentPathError(
                "attachment_id empty."
            )

        allowed = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789-_"
        )

        for ch in attachment_id:

            if ch not in allowed:
                raise InvalidAttachmentPathError(
                    f"Invalid character in "
                    f"attachment_id: {ch}"
                )

    def _ensure_safe_path(
        self,
        path: Path,
    ) -> None:
        """
        Prevent path traversal.
        """

        resolved = path.resolve()

        if (
            self.attachment_root
            not in resolved.parents
            and resolved
            != self.attachment_root
        ):
            raise InvalidAttachmentPathError(
                "Unsafe attachment path."
            )

    @staticmethod
    def _atomic_write(
        path: Path,
        data: bytes,
    ) -> None:
        """
        Atomic filesystem write.
        """

        tmp_fd, tmp_name = (
            tempfile.mkstemp(
                dir=str(path.parent)
            )
        )

        try:

            with os.fdopen(
                tmp_fd,
                "wb",
            ) as tmp_file:

                tmp_file.write(data)

                tmp_file.flush()

                os.fsync(
                    tmp_file.fileno()
                )

            shutil.move(
                tmp_name,
                path,
            )

        finally:

            if os.path.exists(tmp_name):

                try:
                    os.remove(tmp_name)
                except Exception:
                    pass


__all__ = [
    "AttachmentStorageError",
    "AttachmentNotFoundError",
    "AttachmentAlreadyExistsError",
    "InvalidAttachmentPathError",
    "AttachmentStorageRecord",
    "AttachmentStorage",
]