from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


JsonDict = Dict[str, Any]


class ContactsStorageError(Exception):
    """Base exception for contacts storage."""


class ContactNotFoundError(ContactsStorageError):
    """Raised when a contact file does not exist."""


class ContactAlreadyExistsError(ContactsStorageError):
    """Raised when creating a contact that already exists."""


class InvalidContactDataError(ContactsStorageError):
    """Raised when contact data is malformed."""


class ContactsStorage:
    """
    Storage layer cho imported/exported contacts.

    Mặc định lưu tại:
      data/contacts/<name>.contact.json
    """

    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.dir_path = self.base_dir / "contacts"
        self.dir_path.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> List[str]:
        result: List[str] = []
        for path in sorted(self.dir_path.glob("*.contact.json")):
            result.append(path.name.replace(".contact.json", ""))
        return result

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def save(self, contact: JsonDict, overwrite: bool = True) -> Path:
        self._validate_contact(contact)
        name = self._normalize_name(contact["name"])
        path = self._path(name)

        if path.exists() and not overwrite:
            raise ContactAlreadyExistsError(f"Contact '{name}' already exists.")

        self._write_json(path, contact)
        return path

    def load(self, name: str) -> JsonDict:
        safe_name = self._normalize_name(name)
        path = self._path(safe_name)

        if not path.exists():
            raise ContactNotFoundError(f"Contact '{safe_name}' not found.")

        data = self._read_json(path)
        self._validate_contact(data)
        return data

    def delete(self, name: str) -> None:
        safe_name = self._normalize_name(name)
        path = self._path(safe_name)

        if not path.exists():
            raise ContactNotFoundError(f"Contact '{safe_name}' not found.")

        path.unlink()

    def import_from_file(self, file_path: str | Path, overwrite: bool = True) -> JsonDict:
        path = Path(file_path)
        if not path.exists():
            raise ContactNotFoundError(f"Contact file not found: {path}")

        data = self._read_json(path)
        self._validate_contact(data)
        self.save(data, overwrite=overwrite)
        return data

    def export_to_file(self, name: str, output_path: str | Path) -> Path:
        contact = self.load(name)
        out_path = Path(output_path)
        self._write_json(out_path, contact)
        return out_path

    def get_summary(self, name: str) -> JsonDict:
        contact = self.load(name)
        return {
            "name": contact["name"],
            "ed25519_public_key": contact["ed25519"]["public_key"],
            "ed25519_fingerprint": contact["ed25519"]["fingerprint"],
            "x25519_public_key": contact["x25519"]["public_key"],
            "x25519_fingerprint": contact["x25519"]["fingerprint"],
        }

    def _path(self, name: str) -> Path:
        return self.dir_path / f"{self._normalize_name(name)}.contact.json"

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise InvalidContactDataError("Contact name must be a non-empty string.")
        return name.strip()

    @staticmethod
    def _read_json(path: Path) -> JsonDict:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise InvalidContactDataError(f"Invalid JSON in contact file: {path}") from exc

        if not isinstance(data, dict):
            raise InvalidContactDataError(f"Contact JSON root must be an object: {path}")

        return data

    @staticmethod
    def _write_json(path: Path, data: JsonDict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def _validate_contact(contact: JsonDict) -> None:
        if not isinstance(contact, dict):
            raise InvalidContactDataError("Contact must be a dict.")

        if not isinstance(contact.get("name"), str) or not contact["name"].strip():
            raise InvalidContactDataError("Contact missing valid 'name'.")

        ed = contact.get("ed25519")
        x = contact.get("x25519")

        if not isinstance(ed, dict):
            raise InvalidContactDataError("Contact missing 'ed25519' section.")
        if not isinstance(x, dict):
            raise InvalidContactDataError("Contact missing 'x25519' section.")

        for field in ("public_key", "fingerprint"):
            if not isinstance(ed.get(field), str) or not ed[field].strip():
                raise InvalidContactDataError(f"Contact ed25519 missing '{field}'.")
            if not isinstance(x.get(field), str) or not x[field].strip():
                raise InvalidContactDataError(f"Contact x25519 missing '{field}'.")