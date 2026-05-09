from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final


# =========================================================
# Constants
# =========================================================

DEFAULT_CHUNK_SIZE: Final[int] = 64 * 1024

MAX_FILENAME_LENGTH: Final[int] = 255

MAX_ATTACHMENT_SIZE: Final[int] = 1024 * 1024 * 100
# 100 MB


# =========================================================
# Exceptions
# =========================================================

class AttachmentError(Exception):
    """Base attachment exception."""


class AttachmentValidationError(
    AttachmentError
):
    """Attachment metadata invalid."""


class AttachmentFileError(
    AttachmentError
):
    """Attachment file operation failed."""


# =========================================================
# Attachment Metadata
# =========================================================

@dataclass(
    slots=True,
    frozen=True,
)
class AttachmentMetadata:
    """
    Secure attachment metadata.

    IMPORTANT:
    Metadata itself is NOT encrypted here.
    Encryption handled by attachment_service.

    attachment_id:
        Globally unique attachment identifier.

    filename:
        Original filename.

    mime_type:
        MIME content type.

    size:
        Original plaintext size in bytes.

    sha256:
        SHA256 hash of plaintext file.

    created_at:
        ISO8601 UTC timestamp.
    """

    attachment_id: str

    filename: str

    mime_type: str

    size: int

    sha256: str

    created_at: str

    # =====================================================
    # Validation
    # =====================================================

    def validate(self) -> None:

        # ---------------------------------------------
        # attachment_id
        # ---------------------------------------------

        if not isinstance(
            self.attachment_id,
            str,
        ):
            raise AttachmentValidationError(
                "attachment_id must be string."
            )

        if not self.attachment_id.strip():
            raise AttachmentValidationError(
                "attachment_id required."
            )

        # ---------------------------------------------
        # filename
        # ---------------------------------------------

        if not isinstance(
            self.filename,
            str,
        ):
            raise AttachmentValidationError(
                "filename must be string."
            )

        if not self.filename.strip():
            raise AttachmentValidationError(
                "filename required."
            )

        if (
            len(self.filename)
            > MAX_FILENAME_LENGTH
        ):
            raise AttachmentValidationError(
                "filename too long."
            )

        # ---------------------------------------------
        # mime_type
        # ---------------------------------------------

        if not isinstance(
            self.mime_type,
            str,
        ):
            raise AttachmentValidationError(
                "mime_type must be string."
            )

        if not self.mime_type.strip():
            raise AttachmentValidationError(
                "mime_type required."
            )

        # ---------------------------------------------
        # size
        # ---------------------------------------------

        if not isinstance(
            self.size,
            int,
        ):
            raise AttachmentValidationError(
                "size must be integer."
            )

        if self.size <= 0:
            raise AttachmentValidationError(
                "attachment size invalid."
            )

        if (
            self.size
            > MAX_ATTACHMENT_SIZE
        ):
            raise AttachmentValidationError(
                "attachment exceeds max size."
            )

        # ---------------------------------------------
        # sha256
        # ---------------------------------------------

        if not isinstance(
            self.sha256,
            str,
        ):
            raise AttachmentValidationError(
                "sha256 must be string."
            )

        if len(self.sha256) != 64:
            raise AttachmentValidationError(
                "invalid sha256."
            )

        try:
            int(self.sha256, 16)

        except Exception as exc:
            raise AttachmentValidationError(
                "sha256 must be hexadecimal."
            ) from exc

        # ---------------------------------------------
        # created_at
        # ---------------------------------------------

        if not isinstance(
            self.created_at,
            str,
        ):
            raise AttachmentValidationError(
                "created_at must be string."
            )

        if not self.created_at.strip():
            raise AttachmentValidationError(
                "created_at required."
            )

    # =====================================================
    # Serialization
    # =====================================================

    def to_dict(self) -> dict:

        return {
            "attachment_id":
                self.attachment_id,

            "filename":
                self.filename,

            "mime_type":
                self.mime_type,

            "size":
                self.size,

            "sha256":
                self.sha256,

            "created_at":
                self.created_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "AttachmentMetadata":

        if not isinstance(data, dict):
            raise AttachmentValidationError(
                "metadata must be dict."
            )

        metadata = cls(
            attachment_id=data[
                "attachment_id"
            ],

            filename=data[
                "filename"
            ],

            mime_type=data[
                "mime_type"
            ],

            size=data[
                "size"
            ],

            sha256=data[
                "sha256"
            ],

            created_at=data[
                "created_at"
            ],
        )

        metadata.validate()

        return metadata


# =========================================================
# File Hashing
# =========================================================

def sha256_file(
    path: str | Path,
) -> str:
    """
    Compute SHA256 of file.

    Streaming implementation:
    avoids loading large file into memory.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise AttachmentFileError(
            f"File not found: {file_path}"
        )

    if not file_path.is_file():
        raise AttachmentFileError(
            f"Not a file: {file_path}"
        )

    sha = hashlib.sha256()

    try:

        with file_path.open(
            "rb"
        ) as f:

            while chunk := f.read(
                DEFAULT_CHUNK_SIZE
            ):
                sha.update(chunk)

        return sha.hexdigest()

    except OSError as exc:
        raise AttachmentFileError(
            f"Failed hashing file: {file_path}"
        ) from exc


# =========================================================
# MIME Detection
# =========================================================

def detect_mime_type(
    filename: str,
) -> str:
    """
    Detect MIME type from filename.
    """

    mime, _ = mimetypes.guess_type(
        filename
    )

    return (
        mime
        or "application/octet-stream"
    )


# =========================================================
# Metadata Builder
# =========================================================

def build_attachment_metadata(
    path: str | Path,
) -> AttachmentMetadata:
    """
    Build validated attachment metadata
    from plaintext file.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise AttachmentFileError(
            f"File not found: {file_path}"
        )

    if not file_path.is_file():
        raise AttachmentFileError(
            f"Not a file: {file_path}"
        )

    # =====================================================
    # Basic file info
    # =====================================================

    filename = file_path.name

    size = file_path.stat().st_size

    # =====================================================
    # Hash
    # =====================================================

    sha256 = sha256_file(
        file_path
    )

    # =====================================================
    # MIME
    # =====================================================

    mime_type = detect_mime_type(
        filename
    )

    # =====================================================
    # Timestamp
    # =====================================================

    created_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # =====================================================
    # Attachment ID
    # =====================================================

    attachment_id = (
        uuid.uuid4().hex
    )

    # =====================================================
    # Build metadata
    # =====================================================

    metadata = AttachmentMetadata(
        attachment_id=attachment_id,

        filename=filename,

        mime_type=mime_type,

        size=size,

        sha256=sha256,

        created_at=created_at,
    )

    metadata.validate()

    return metadata


# =========================================================
# Export
# =========================================================

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "MAX_FILENAME_LENGTH",
    "MAX_ATTACHMENT_SIZE",

    "AttachmentError",
    "AttachmentValidationError",
    "AttachmentFileError",

    "AttachmentMetadata",

    "sha256_file",
    "detect_mime_type",
    "build_attachment_metadata",
]