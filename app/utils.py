from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any


APP_VERSION = 1
SUITE_NAME = "X25519+HKDF-SHA256+ChaCha20-Poly1305+Ed25519"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_bytes(path: Path, data: bytes) -> None:
    ensure_dir(path.parent)
    path.write_bytes(data)


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def sha256_short_id(data: bytes, size: int = 8) -> bytes:
    from hashlib import sha256
    return sha256(data).digest()[:size]


def canonical_dumps(obj: dict[str, Any]) -> bytes:
    """
    Serialize deterministically for signing / AAD.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")