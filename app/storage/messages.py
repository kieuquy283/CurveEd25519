from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


JsonDict = Dict[str, Any]


class MessagesStorageError(Exception):
    """Base exception for messages storage."""


class MessageNotFoundError(MessagesStorageError):
    """Raised when a message file does not exist."""


class InvalidMessageDataError(MessagesStorageError):
    """Raised when message envelope data is malformed."""


class MessagesStorage:
    """
    Storage layer cho encrypted envelopes / signed payload JSON.

    Mặc định lưu tại:
      data/messages/<name>.json
    """

    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.dir_path = self.base_dir / "messages"
        self.dir_path.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> List[str]:
        return sorted(path.stem for path in self.dir_path.glob("*.json"))

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def save_envelope(self, name: str, envelope: JsonDict, overwrite: bool = True) -> Path:
        self._validate_envelope(envelope)
        path = self._path(name)

        if path.exists() and not overwrite:
            raise InvalidMessageDataError(f"Message '{name}' already exists.")

        self._write_json(path, envelope)
        return path

    def load_envelope(self, name: str) -> JsonDict:
        path = self._path(name)
        if not path.exists():
            raise MessageNotFoundError(f"Message '{name}' not found.")

        data = self._read_json(path)
        self._validate_envelope(data)
        return data

    def save_to_path(self, output_path: str | Path, envelope: JsonDict) -> Path:
        self._validate_envelope(envelope)
        path = Path(output_path)
        self._write_json(path, envelope)
        return path

    def load_from_path(self, input_path: str | Path) -> JsonDict:
        path = Path(input_path)
        if not path.exists():
            raise MessageNotFoundError(f"Message file not found: {path}")

        data = self._read_json(path)
        self._validate_envelope(data)
        return data

    def delete(self, name: str) -> None:
        path = self._path(name)
        if not path.exists():
            raise MessageNotFoundError(f"Message '{name}' not found.")
        path.unlink()

    def get_summary(self, name: str) -> JsonDict:
        envelope = self.load_envelope(name)
        return self.extract_meta(envelope)

    def extract_meta(self, envelope: JsonDict) -> JsonDict:
        self._validate_envelope(envelope)

        header = envelope["header"]
        sender = header["sender"]
        receiver = header["receiver"]
        crypto = header["crypto"]

        return {
            "version": header["version"],
            "suite": header["suite"],
            "message_id": header["message_id"],
            "sender_name": sender["name"],
            "sender_ed25519_fingerprint": sender["ed25519_fingerprint"],
            "recipient_name": receiver["name"],
            "recipient_x25519_fingerprint": receiver["x25519_fingerprint"],
            "ephemeral_x25519_fingerprint": crypto["ephemeral_x25519_fingerprint"],
            "has_signature": True,
        }

    def _path(self, name: str) -> Path:
        safe = self._normalize_name(name)
        return self.dir_path / f"{safe}.json"

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise InvalidMessageDataError("Message name must be a non-empty string.")
        return name.strip()

    @staticmethod
    def _read_json(path: Path) -> JsonDict:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise InvalidMessageDataError(f"Invalid JSON in message file: {path}") from exc

        if not isinstance(data, dict):
            raise InvalidMessageDataError(f"Message JSON root must be an object: {path}")

        return data

    @staticmethod
    def _write_json(path: Path, data: JsonDict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def _validate_envelope(envelope: JsonDict) -> None:
        if not isinstance(envelope, dict):
            raise InvalidMessageDataError("Envelope must be a dict.")

        required_top = ("header", "wrapped_key", "ciphertext", "signature")
        for key in required_top:
            if key not in envelope:
                raise InvalidMessageDataError(f"Envelope missing field: {key}")

        header = envelope["header"]
        if not isinstance(header, dict):
            raise InvalidMessageDataError("Envelope header must be a dict.")

        for key in ("version", "suite", "message_id", "sender", "receiver", "crypto"):
            if key not in header:
                raise InvalidMessageDataError(f"Envelope header missing field: {key}")

        sender = header["sender"]
        receiver = header["receiver"]
        crypto = header["crypto"]
        signature = envelope["signature"]

        if not isinstance(sender, dict):
            raise InvalidMessageDataError("Envelope sender must be a dict.")
        if not isinstance(receiver, dict):
            raise InvalidMessageDataError("Envelope receiver must be a dict.")
        if not isinstance(crypto, dict):
            raise InvalidMessageDataError("Envelope crypto must be a dict.")
        if not isinstance(signature, dict):
            raise InvalidMessageDataError("Envelope signature must be a dict.")

        sender_required = ("name", "ed25519_public_key", "ed25519_fingerprint")
        for key in sender_required:
            if key not in sender:
                raise InvalidMessageDataError(f"Envelope sender missing field: {key}")

        receiver_required = ("name", "x25519_fingerprint")
        for key in receiver_required:
            if key not in receiver:
                raise InvalidMessageDataError(f"Envelope receiver missing field: {key}")

        crypto_required = (
            "ephemeral_x25519_public_key",
            "ephemeral_x25519_fingerprint",
            "salt_wrap",
            "payload_nonce",
        )
        for key in crypto_required:
            if key not in crypto:
                raise InvalidMessageDataError(f"Envelope crypto missing field: {key}")

        if "algorithm" not in signature:
            raise InvalidMessageDataError("Envelope signature missing field: algorithm.")
        if "value" not in signature:
            raise InvalidMessageDataError("Envelope signature missing field: value.")