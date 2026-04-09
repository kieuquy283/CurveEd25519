from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.x25519 import (
    export_full_keypair_record as export_x25519_full_keypair_record,
    generate_keypair as generate_x25519_keypair,
)
from app.storage.contacts import ContactsStorage
from app.storage.profiles import ProfilesStorage


JsonDict = Dict[str, Any]


class KeyServiceError(Exception):
    """Base exception for key service."""


class ProfileExistsError(KeyServiceError):
    """Raised when trying to create a profile that already exists."""


class ProfileNotFoundError(KeyServiceError):
    """Raised when a profile does not exist."""


class ContactNotFoundError(KeyServiceError):
    """Raised when a contact does not exist."""


class InvalidContactError(KeyServiceError):
    """Raised when contact JSON is malformed."""


class KeyService:
    """
    Service layer quản lý key/profile/contact.

    Dùng:
    - ProfilesStorage
    - ContactsStorage
    """

    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.profiles_store = ProfilesStorage(self.base_dir)
        self.contacts_store = ContactsStorage(self.base_dir)

    # =========================
    # Public API - profiles
    # =========================

    def create_profile(self, name: str, overwrite: bool = False) -> JsonDict:
        safe_name = self._normalize_name(name)

        if self.profiles_store.exists(safe_name) and not overwrite:
            raise ProfileExistsError(f"Profile '{safe_name}' already exists.")

        ed25519_record = self._generate_ed25519_full_keypair_record()
        x25519_keypair = generate_x25519_keypair()
        x25519_record = export_x25519_full_keypair_record(x25519_keypair)

        profile = {
            "name": safe_name,
            "ed25519": ed25519_record,
            "x25519": x25519_record,
        }

        self.save_profile(profile)
        return profile

    def save_profile(self, profile: JsonDict) -> Path:
        try:
            return self.profiles_store.save(profile, overwrite=True)
        except Exception as exc:
            raise KeyServiceError(f"Failed to save profile: {exc}") from exc

    def load_profile(self, name: str) -> JsonDict:
        try:
            return self.profiles_store.load(name)
        except Exception as exc:
            raise ProfileNotFoundError(f"Profile '{name}' not found.") from exc

    def delete_profile(self, name: str) -> None:
        try:
            self.profiles_store.delete(name)
        except Exception as exc:
            raise ProfileNotFoundError(f"Profile '{name}' not found.") from exc

    def list_profiles(self) -> List[str]:
        return self.profiles_store.list_names()

    def export_contact_from_profile(
        self,
        profile_name: str,
        save_to_contacts: bool = True,
    ) -> JsonDict:
        profile = self.load_profile(profile_name)
        contact = self.build_contact_from_profile(profile)

        if save_to_contacts:
            self.save_contact(contact)

        return contact

    def build_contact_from_profile(self, profile: JsonDict) -> JsonDict:
        self._validate_profile(profile)

        contact = {
            "name": profile["name"],
            "ed25519": {
                "algorithm": "Ed25519",
                "public_key": profile["ed25519"]["public_key"],
                "fingerprint": profile["ed25519"]["fingerprint"],
            },
            "x25519": {
                "algorithm": "X25519",
                "public_key": profile["x25519"]["public_key"],
                "fingerprint": profile["x25519"]["fingerprint"],
            },
        }
        self._validate_contact(contact)
        return contact

    # =========================
    # Public API - contacts
    # =========================

    def save_contact(self, contact: JsonDict) -> Path:
        try:
            return self.contacts_store.save(contact, overwrite=True)
        except Exception as exc:
            raise KeyServiceError(f"Failed to save contact: {exc}") from exc

    def load_contact(self, name: str) -> JsonDict:
        try:
            return self.contacts_store.load(name)
        except Exception as exc:
            raise ContactNotFoundError(f"Contact '{name}' not found.") from exc

    def delete_contact(self, name: str) -> None:
        try:
            self.contacts_store.delete(name)
        except Exception as exc:
            raise ContactNotFoundError(f"Contact '{name}' not found.") from exc

    def list_contacts(self) -> List[str]:
        return self.contacts_store.list_names()

    def import_contact_from_file(self, file_path: str | Path, save: bool = True) -> JsonDict:
        try:
            contact = self.contacts_store.import_from_file(file_path, overwrite=True)
            if save:
                self.contacts_store.save(contact, overwrite=True)
            return contact
        except Exception as exc:
            raise InvalidContactError(f"Failed to import contact: {exc}") from exc

    def export_contact_to_file(self, contact_name: str, output_path: str | Path) -> Path:
        try:
            return self.contacts_store.export_to_file(contact_name, output_path)
        except Exception as exc:
            raise ContactNotFoundError(f"Contact '{contact_name}' not found.") from exc

    # =========================
    # Public API - convenience
    # =========================

    def get_profile_summary(self, name: str) -> JsonDict:
        try:
            return self.profiles_store.get_summary(name)
        except Exception as exc:
            raise ProfileNotFoundError(f"Profile '{name}' not found.") from exc

    def get_contact_summary(self, name: str) -> JsonDict:
        try:
            return self.contacts_store.get_summary(name)
        except Exception as exc:
            raise ContactNotFoundError(f"Contact '{name}' not found.") from exc

    # =========================
    # Helpers - ed25519 generation
    # =========================

    @staticmethod
    def _generate_ed25519_full_keypair_record() -> JsonDict:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_raw = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        private_b64 = base64.b64encode(private_raw).decode("utf-8")
        public_b64 = base64.b64encode(public_raw).decode("utf-8")
        fingerprint = hashlib.sha256(public_raw).hexdigest()[:16]

        return {
            "algorithm": "Ed25519",
            "private_key": private_b64,
            "public_key": public_b64,
            "fingerprint": fingerprint,
        }

    # =========================
    # Helpers - validation
    # =========================

    @staticmethod
    def _validate_profile(profile: JsonDict) -> None:
        if not isinstance(profile, dict):
            raise KeyServiceError("Profile must be a dict.")

        if not isinstance(profile.get("name"), str) or not profile["name"].strip():
            raise KeyServiceError("Profile missing valid 'name'.")

        ed = profile.get("ed25519")
        x = profile.get("x25519")

        if not isinstance(ed, dict):
            raise KeyServiceError("Profile missing 'ed25519' section.")
        if not isinstance(x, dict):
            raise KeyServiceError("Profile missing 'x25519' section.")

        for field in ("private_key", "public_key", "fingerprint"):
            if not isinstance(ed.get(field), str) or not ed[field].strip():
                raise KeyServiceError(f"Profile ed25519 missing '{field}'.")
            if not isinstance(x.get(field), str) or not x[field].strip():
                raise KeyServiceError(f"Profile x25519 missing '{field}'.")

    @staticmethod
    def _validate_contact(contact: JsonDict) -> None:
        if not isinstance(contact, dict):
            raise InvalidContactError("Contact must be a dict.")

        if not isinstance(contact.get("name"), str) or not contact["name"].strip():
            raise InvalidContactError("Contact missing valid 'name'.")

        ed = contact.get("ed25519")
        x = contact.get("x25519")

        if not isinstance(ed, dict):
            raise InvalidContactError("Contact missing 'ed25519' section.")
        if not isinstance(x, dict):
            raise InvalidContactError("Contact missing 'x25519' section.")

        for field in ("public_key", "fingerprint"):
            if not isinstance(ed.get(field), str) or not ed[field].strip():
                raise InvalidContactError(f"Contact ed25519 missing '{field}'.")
            if not isinstance(x.get(field), str) or not x[field].strip():
                raise InvalidContactError(f"Contact x25519 missing '{field}'.")

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise KeyServiceError("Name must be a non-empty string.")
        return name.strip()