from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


JsonDict = Dict[str, Any]


class ProfilesStorageError(Exception):
    """Base exception for profiles storage."""


class ProfileNotFoundError(ProfilesStorageError):
    """Raised when a profile file does not exist."""


class ProfileAlreadyExistsError(ProfilesStorageError):
    """Raised when creating a profile that already exists."""


class InvalidProfileDataError(ProfilesStorageError):
    """Raised when profile data is malformed."""


class ProfilesStorage:
    """
    Storage layer cho profiles.

    Mặc định lưu tại:
      data/profiles/<name>.json
    """

    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.dir_path = self.base_dir / "profiles"
        self.dir_path.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> List[str]:
        return sorted(path.stem for path in self.dir_path.glob("*.json"))

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def save(self, profile: JsonDict, overwrite: bool = True) -> Path:
        self._validate_profile(profile)
        name = self._normalize_name(profile["name"])
        path = self._path(name)

        if path.exists() and not overwrite:
            raise ProfileAlreadyExistsError(f"Profile '{name}' already exists.")

        self._write_json(path, profile)
        return path

    def load(self, name: str) -> JsonDict:
        safe_name = self._normalize_name(name)
        path = self._path(safe_name)

        if not path.exists():
            raise ProfileNotFoundError(f"Profile '{safe_name}' not found.")

        data = self._read_json(path)
        self._validate_profile(data)
        return data

    def delete(self, name: str) -> None:
        safe_name = self._normalize_name(name)
        path = self._path(safe_name)

        if not path.exists():
            raise ProfileNotFoundError(f"Profile '{safe_name}' not found.")

        path.unlink()

    def get_summary(self, name: str) -> JsonDict:
        profile = self.load(name)
        return {
            "name": profile["name"],
            "ed25519_public_key": profile["ed25519"]["public_key"],
            "ed25519_fingerprint": profile["ed25519"]["fingerprint"],
            "x25519_public_key": profile["x25519"]["public_key"],
            "x25519_fingerprint": profile["x25519"]["fingerprint"],
        }

    def _path(self, name: str) -> Path:
        return self.dir_path / f"{self._normalize_name(name)}.json"

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise InvalidProfileDataError("Profile name must be a non-empty string.")
        return name.strip()

    @staticmethod
    def _read_json(path: Path) -> JsonDict:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise InvalidProfileDataError(f"Invalid JSON in profile file: {path}") from exc

        if not isinstance(data, dict):
            raise InvalidProfileDataError(f"Profile JSON root must be an object: {path}")

        return data

    @staticmethod
    def _write_json(path: Path, data: JsonDict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def _validate_profile(profile: JsonDict) -> None:
        if not isinstance(profile, dict):
            raise InvalidProfileDataError("Profile must be a dict.")

        if not isinstance(profile.get("name"), str) or not profile["name"].strip():
            raise InvalidProfileDataError("Profile missing valid 'name'.")

        ed = profile.get("ed25519")
        x = profile.get("x25519")

        if not isinstance(ed, dict):
            raise InvalidProfileDataError("Profile missing 'ed25519' section.")
        if not isinstance(x, dict):
            raise InvalidProfileDataError("Profile missing 'x25519' section.")

        for field in ("private_key", "public_key", "fingerprint"):
            if not isinstance(ed.get(field), str) or not ed[field].strip():
                raise InvalidProfileDataError(f"Profile ed25519 missing '{field}'.")
            if not isinstance(x.get(field), str) or not x[field].strip():
                raise InvalidProfileDataError(f"Profile x25519 missing '{field}'.")