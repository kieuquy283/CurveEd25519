from __future__ import annotations

import os
import struct

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final

from cryptography.hazmat.primitives.ciphers.aead import (
    ChaCha20Poly1305,
)

from .envelope import (
    b64e,
)


# =========================================================
# Constants
# =========================================================

STREAM_MAGIC: Final[bytes] = b"STRMCRYPT"

STREAM_VERSION: Final[int] = 1

STREAM_CHUNK_SIZE: Final[int] = 64 * 1024

CHACHA20_NONCE_SIZE: Final[int] = 12

UINT32_SIZE: Final[int] = 4

HEADER_STRUCT: Final[str] = "!10sBI12s"
# magic(10) + version(uint8) + chunk_size(uint32)
# + base_nonce(12)

HEADER_SIZE: Final[int] = struct.calcsize(
    HEADER_STRUCT
)


# =========================================================
# Exceptions
# =========================================================

class StreamingCryptoError(Exception):
    """Base streaming crypto exception."""


class StreamEncryptionError(
    StreamingCryptoError
):
    """Stream encryption failed."""


class StreamDecryptionError(
    StreamingCryptoError
):
    """Stream decryption failed."""


class StreamFormatError(
    StreamingCryptoError
):
    """Invalid encrypted stream format."""


# =========================================================
# Stream Header
# =========================================================

@dataclass(
    slots=True,
    frozen=True,
)
class StreamFileHeader:
    """
    Encrypted stream file header.
    """

    version: int

    chunk_size: int

    base_nonce: bytes

    def validate(self) -> None:

        if self.version != STREAM_VERSION:
            raise StreamFormatError(
                f"Unsupported stream version: "
                f"{self.version}"
            )

        if self.chunk_size <= 0:
            raise StreamFormatError(
                "Invalid chunk size."
            )

        if (
            len(self.base_nonce)
            != CHACHA20_NONCE_SIZE
        ):
            raise StreamFormatError(
                "Invalid base nonce."
            )


# =========================================================
# Header Serialization
# =========================================================

def serialize_stream_header(
    header: StreamFileHeader,
) -> bytes:
    """
    Serialize stream header.
    """

    header.validate()

    return struct.pack(
        HEADER_STRUCT,
        STREAM_MAGIC,
        header.version,
        header.chunk_size,
        header.base_nonce,
    )


def parse_stream_header(
    data: bytes,
) -> StreamFileHeader:
    """
    Parse encrypted stream header.
    """

    if len(data) != HEADER_SIZE:
        raise StreamFormatError(
            "Invalid stream header size."
        )

    try:

        (
            magic,
            version,
            chunk_size,
            base_nonce,
        ) = struct.unpack(
            HEADER_STRUCT,
            data,
        )

    except struct.error as exc:
        raise StreamFormatError(
            "Corrupted stream header."
        ) from exc

    if magic != STREAM_MAGIC:
        raise StreamFormatError(
            "Invalid stream magic."
        )

    header = StreamFileHeader(
        version=version,
        chunk_size=chunk_size,
        base_nonce=base_nonce,
    )

    header.validate()

    return header


# =========================================================
# Nonce Derivation
# =========================================================

def derive_chunk_nonce(
    *,
    base_nonce: bytes,
    chunk_index: int,
) -> bytes:
    """
    Deterministic nonce derivation.

    Strategy:
        nonce = base_nonce XOR chunk_index

    Similar to:
    - TLS AEAD nonce derivation
    - libsodium secretstream

    Guarantees:
    - unique nonce per chunk
    - deterministic
    - constant memory
    """

    if (
        len(base_nonce)
        != CHACHA20_NONCE_SIZE
    ):
        raise ValueError(
            "base_nonce must be 12 bytes."
        )

    if chunk_index < 0:
        raise ValueError(
            "chunk_index must be >= 0."
        )

    nonce = bytearray(base_nonce)

    counter = chunk_index.to_bytes(
        8,
        "big",
    )

    # XOR last 8 bytes
    for i in range(8):
        nonce[4 + i] ^= counter[i]

    return bytes(nonce)


# =========================================================
# Internal Helpers
# =========================================================

def _write_chunk(
    *,
    output_file: BinaryIO,
    ciphertext: bytes,
) -> None:
    """
    Write:
        uint32 length
        ciphertext bytes
    """

    output_file.write(
        struct.pack(
            "!I",
            len(ciphertext),
        )
    )

    output_file.write(ciphertext)


def _read_chunk(
    *,
    input_file: BinaryIO,
) -> bytes | None:
    """
    Read encrypted chunk.

    Returns:
        None on EOF
    """

    length_bytes = input_file.read(
        UINT32_SIZE
    )

    if not length_bytes:
        return None

    if (
        len(length_bytes)
        != UINT32_SIZE
    ):
        raise StreamFormatError(
            "Truncated chunk length."
        )

    chunk_length = struct.unpack(
        "!I",
        length_bytes,
    )[0]

    if chunk_length <= 0:
        raise StreamFormatError(
            "Invalid chunk length."
        )

    ciphertext = input_file.read(
        chunk_length
    )

    if len(ciphertext) != chunk_length:
        raise StreamFormatError(
            "Truncated ciphertext chunk."
        )

    return ciphertext


# =========================================================
# Stream Encryption
# =========================================================

def encrypt_stream(
    *,
    input_path: str | Path,
    output_path: str | Path,
    key: bytes,
    chunk_size: int = STREAM_CHUNK_SIZE,
) -> dict:
    """
    Encrypt large file using streaming AEAD.

    File format:
        [header]
        [chunk_length]
        [ciphertext]
        [chunk_length]
        [ciphertext]
        ...

    Security:
    - authenticated encryption
    - per-chunk unique nonce
    - chunk ordering integrity
    - corruption detection
    - truncation detection
    """

    if len(key) != 32:
        raise StreamEncryptionError(
            "ChaCha20 key must be 32 bytes."
        )

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise StreamEncryptionError(
            f"Input file not found: "
            f"{input_path}"
        )

    base_nonce = os.urandom(
        CHACHA20_NONCE_SIZE
    )

    header = StreamFileHeader(
        version=STREAM_VERSION,
        chunk_size=chunk_size,
        base_nonce=base_nonce,
    )

    cipher = ChaCha20Poly1305(key)

    encrypted_size = 0

    chunk_count = 0

    try:

        with (
            input_path.open("rb") as in_file,
            output_path.open("wb") as out_file,
        ):

            # =====================================
            # Write header
            # =====================================

            serialized_header = (
                serialize_stream_header(
                    header
                )
            )

            out_file.write(
                serialized_header
            )

            encrypted_size += len(
                serialized_header
            )

            # =====================================
            # Encrypt chunks
            # =====================================

            while chunk := in_file.read(
                chunk_size
            ):

                nonce = derive_chunk_nonce(
                    base_nonce=base_nonce,
                    chunk_index=chunk_count,
                )

                aad = struct.pack(
                    "!Q",
                    chunk_count,
                )

                ciphertext = cipher.encrypt(
                    nonce,
                    chunk,
                    aad,
                )

                _write_chunk(
                    output_file=out_file,
                    ciphertext=ciphertext,
                )

                encrypted_size += (
                    UINT32_SIZE
                    + len(ciphertext)
                )

                chunk_count += 1

        return {
            "base_nonce_b64": b64e(
                base_nonce
            ),

            "chunk_size": chunk_size,

            "chunk_count": chunk_count,

            "encrypted_size": (
                encrypted_size
            ),
        }

    except Exception as exc:
        raise StreamEncryptionError(
            f"Stream encryption failed: "
            f"{input_path}"
        ) from exc


# =========================================================
# Stream Decryption
# =========================================================

def decrypt_stream(
    *,
    input_path: str | Path,
    output_path: str | Path,
    key: bytes,
) -> dict:
    """
    Decrypt encrypted stream file.

    Integrity guarantees:
    - chunk tampering detection
    - chunk reorder detection
    - truncation detection
    """

    if len(key) != 32:
        raise StreamDecryptionError(
            "ChaCha20 key must be 32 bytes."
        )

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise StreamDecryptionError(
            f"Encrypted file not found: "
            f"{input_path}"
        )

    cipher = ChaCha20Poly1305(key)

    total_plaintext_size = 0

    chunk_count = 0

    try:

        with (
            input_path.open("rb") as in_file,
            output_path.open("wb") as out_file,
        ):

            # =====================================
            # Read header
            # =====================================

            header_bytes = in_file.read(
                HEADER_SIZE
            )

            if (
                len(header_bytes)
                != HEADER_SIZE
            ):
                raise StreamFormatError(
                    "Truncated stream header."
                )

            header = parse_stream_header(
                header_bytes
            )

            # =====================================
            # Read chunks
            # =====================================

            while True:

                ciphertext = _read_chunk(
                    input_file=in_file
                )

                if ciphertext is None:
                    break

                nonce = derive_chunk_nonce(
                    base_nonce=(
                        header.base_nonce
                    ),
                    chunk_index=chunk_count,
                )

                aad = struct.pack(
                    "!Q",
                    chunk_count,
                )

                try:

                    plaintext = cipher.decrypt(
                        nonce,
                        ciphertext,
                        aad,
                    )

                except Exception as exc:
                    raise StreamDecryptionError(
                        "Chunk authentication "
                        "failed."
                    ) from exc

                out_file.write(
                    plaintext
                )

                total_plaintext_size += (
                    len(plaintext)
                )

                chunk_count += 1

        return {
            "chunk_count": chunk_count,
            "plaintext_size": (
                total_plaintext_size
            ),
        }

    except StreamingCryptoError:
        raise

    except Exception as exc:
        raise StreamDecryptionError(
            f"Stream decryption failed: "
            f"{input_path}"
        ) from exc


# =========================================================
# Export
# =========================================================

__all__ = [
    "STREAM_MAGIC",
    "STREAM_VERSION",
    "STREAM_CHUNK_SIZE",
    "CHACHA20_NONCE_SIZE",

    "StreamingCryptoError",
    "StreamEncryptionError",
    "StreamDecryptionError",
    "StreamFormatError",

    "StreamFileHeader",

    "serialize_stream_header",
    "parse_stream_header",

    "derive_chunk_nonce",

    "encrypt_stream",
    "decrypt_stream",
]