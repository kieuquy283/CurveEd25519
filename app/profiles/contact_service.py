from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


JsonDict = Dict[str, Any]


# =========================================================
# Exceptions
# =========================================================

class ContactServiceError(Exception):
    """Base contact service error."""


class ContactAlreadyExistsError(
    ContactServiceError
):
    """Contact already exists."""


class ContactNotFoundError(
    ContactServiceError
):
    """Contact not found."""


class InvalidContactError(
    ContactServiceError
):
    """Invalid contact."""


# =========================================================
# Contact Metadata
# =========================================================

@dataclass(slots=True)
class ContactMetadata:

    peer_id: str

    username: str

    display_name: str

    fingerprint: str

    trusted: bool

    blocked: bool

    created_at: str

    last_seen: Optional[str] = None


# =========================================================
# Contact Service
# =========================================================

class ContactService:
    """
    Contact / peer identity management.

    Responsibilities
    ------------------------------------------------
    - add/remove contacts
    - trust tracking
    - blocklist
    - public identity storage
    - lookup by username/fingerprint
    - lightweight presence metadata
    - contact export/import

    Contact Structure
    ------------------------------------------------
    {
        "peer_id": "...",
        "username": "...",
        "display_name": "...",

        "fingerprint": "...",

        "trusted": false,
        "blocked": false,

        "created_at": "...",
        "last_seen": null,

        "ed25519": {
            "public_key": "..."
        },

        "x25519": {
            "public_key": "..."
        },

        "metadata": {}
    }
    """

    CONTACT_VERSION = 1

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        contacts_dir: str = "contacts_data",
    ) -> None:

        self.contacts_dir = Path(
            contacts_dir
        )

        self.contacts_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =====================================================
    # Add Contact
    # =====================================================

    def add_contact(
        self,
        contact_card: JsonDict,
        *,
        trusted: bool = False,
        overwrite: bool = False,
    ) -> JsonDict:
        """
        Add public identity contact.
        """

        self.validate_contact_card(
            contact_card
        )

        peer_id = (
            contact_card["profile_id"]
        )

        existing = (
            self.find_contact(
                peer_id
            )
        )

        if existing and not overwrite:

            raise (
                ContactAlreadyExistsError(
                    peer_id
                )
            )

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        contact: JsonDict = {

            "version":
                self.CONTACT_VERSION,

            "peer_id":
                peer_id,

            "username":
                contact_card[
                    "username"
                ],

            "display_name":
                contact_card.get(
                    "display_name"
                )
                or contact_card[
                    "username"
                ],

            "fingerprint":
                contact_card[
                    "fingerprint"
                ],

            "trusted":
                trusted,

            "blocked":
                False,

            "created_at":
                now,

            "last_seen":
                None,

            "ed25519": {

                "public_key":
                    contact_card[
                        "ed25519"
                    ][
                        "public_key"
                    ],
            },

            "x25519": {

                "public_key":
                    contact_card[
                        "x25519"
                    ][
                        "public_key"
                    ],
            },

            "metadata":
                contact_card.get(
                    "metadata",
                    {},
                ),
        }

        self.save_contact(
            contact
        )

        return contact

    # =====================================================
    # Save / Load
    # =====================================================

    def save_contact(
        self,
        contact: JsonDict,
    ) -> Path:

        self.validate_contact(
            contact
        )

        path = self._contact_path(
            contact["peer_id"]
        )

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            json.dumps(
                contact,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    def load_contact(
        self,
        peer_id: str,
    ) -> JsonDict:

        path = self._contact_path(
            peer_id
        )

        if not path.exists():

            raise (
                ContactNotFoundError(
                    peer_id
                )
            )

        contact = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        self.validate_contact(
            contact
        )

        return contact

    def delete_contact(
        self,
        peer_id: str,
    ) -> bool:

        path = self._contact_path(
            peer_id
        )

        if not path.exists():
            return False

        path.unlink()

        return True

    # =====================================================
    # Lookup
    # =====================================================

    def list_contacts(
        self,
    ) -> List[ContactMetadata]:

        result = []

        for file in (
            self.contacts_dir.glob(
                "*.json"
            )
        ):

            try:

                contact = json.loads(
                    file.read_text(
                        encoding="utf-8"
                    )
                )

                result.append(
                    ContactMetadata(
                        peer_id=(
                            contact[
                                "peer_id"
                            ]
                        ),

                        username=(
                            contact[
                                "username"
                            ]
                        ),

                        display_name=(
                            contact[
                                "display_name"
                            ]
                        ),

                        fingerprint=(
                            contact[
                                "fingerprint"
                            ]
                        ),

                        trusted=(
                            contact[
                                "trusted"
                            ]
                        ),

                        blocked=(
                            contact[
                                "blocked"
                            ]
                        ),

                        created_at=(
                            contact[
                                "created_at"
                            ]
                        ),

                        last_seen=(
                            contact.get(
                                "last_seen"
                            )
                        ),
                    )
                )

            except Exception:
                continue

        return sorted(
            result,
            key=lambda x: (
                x.display_name
                .lower()
            ),
        )

    def find_contact(
        self,
        peer_id: str,
    ) -> Optional[JsonDict]:

        path = self._contact_path(
            peer_id
        )

        if not path.exists():
            return None

        return self.load_contact(
            peer_id
        )

    def find_by_username(
        self,
        username: str,
    ) -> Optional[JsonDict]:

        username = (
            username.lower()
        )

        for meta in (
            self.list_contacts()
        ):

            if (
                meta.username
                == username
            ):

                return self.load_contact(
                    meta.peer_id
                )

        return None

    def find_by_fingerprint(
        self,
        fingerprint: str,
    ) -> Optional[JsonDict]:

        for meta in (
            self.list_contacts()
        ):

            if (
                meta.fingerprint
                == fingerprint
            ):

                return self.load_contact(
                    meta.peer_id
                )

        return None

    # =====================================================
    # Trust Management
    # =====================================================

    def trust_contact(
        self,
        peer_id: str,
    ) -> JsonDict:

        contact = self.load_contact(
            peer_id
        )

        contact["trusted"] = True

        self.save_contact(
            contact
        )

        return contact

    def untrust_contact(
        self,
        peer_id: str,
    ) -> JsonDict:

        contact = self.load_contact(
            peer_id
        )

        contact["trusted"] = False

        self.save_contact(
            contact
        )

        return contact

    def trusted_contacts(
        self,
    ) -> List[JsonDict]:

        return [

            self.load_contact(
                meta.peer_id
            )

            for meta in (
                self.list_contacts()
            )

            if meta.trusted
        ]

    # =====================================================
    # Blocking
    # =====================================================

    def block_contact(
        self,
        peer_id: str,
    ) -> JsonDict:

        contact = self.load_contact(
            peer_id
        )

        contact["blocked"] = True

        self.save_contact(
            contact
        )

        return contact

    def unblock_contact(
        self,
        peer_id: str,
    ) -> JsonDict:

        contact = self.load_contact(
            peer_id
        )

        contact["blocked"] = False

        self.save_contact(
            contact
        )

        return contact

    def blocked_contacts(
        self,
    ) -> List[JsonDict]:

        return [

            self.load_contact(
                meta.peer_id
            )

            for meta in (
                self.list_contacts()
            )

            if meta.blocked
        ]

    # =====================================================
    # Presence
    # =====================================================

    def update_last_seen(
        self,
        peer_id: str,
    ) -> JsonDict:

        contact = self.load_contact(
            peer_id
        )

        contact["last_seen"] = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        self.save_contact(
            contact
        )

        return contact

    # =====================================================
    # Export / Import
    # =====================================================

    def export_contact(
        self,
        peer_id: str,
        export_path: str,
    ) -> Path:

        contact = self.load_contact(
            peer_id
        )

        path = Path(export_path)

        path.write_text(
            json.dumps(
                contact,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    def import_contact(
        self,
        path: str,
        *,
        overwrite: bool = False,
    ) -> JsonDict:

        file_path = Path(path)

        if not file_path.exists():

            raise FileNotFoundError(
                path
            )

        contact = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

        self.validate_contact(
            contact
        )

        existing = (
            self.find_contact(
                contact["peer_id"]
            )
        )

        if existing and not overwrite:

            raise (
                ContactAlreadyExistsError(
                    contact[
                        "peer_id"
                    ]
                )
            )

        self.save_contact(
            contact
        )

        return contact

    # =====================================================
    # Validation
    # =====================================================

    def validate_contact_card(
        self,
        card: JsonDict,
    ) -> None:

        required = [

            "profile_id",
            "username",
            "fingerprint",

            "ed25519",
            "x25519",
        ]

        for field in required:

            if field not in card:

                raise (
                    InvalidContactError(
                        f"Missing field: "
                        f"{field}"
                    )
                )

    def validate_contact(
        self,
        contact: JsonDict,
    ) -> None:

        required = [

            "peer_id",
            "username",
            "display_name",
            "fingerprint",

            "trusted",
            "blocked",

            "ed25519",
            "x25519",
        ]

        for field in required:

            if field not in contact:

                raise (
                    InvalidContactError(
                        f"Missing field: "
                        f"{field}"
                    )
                )

    # =====================================================
    # Helpers
    # =====================================================

    def _contact_path(
        self,
        peer_id: str,
    ) -> Path:

        return (
            self.contacts_dir
            / f"{peer_id}.json"
        )

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> JsonDict:

        contacts = (
            self.list_contacts()
        )

        return {

            "contacts":
                len(contacts),

            "trusted":
                len([
                    c for c
                    in contacts
                    if c.trusted
                ]),

            "blocked":
                len([
                    c for c
                    in contacts
                    if c.blocked
                ]),
        }


__all__ = [

    "ContactService",

    "ContactMetadata",

    "ContactServiceError",

    "ContactAlreadyExistsError",

    "ContactNotFoundError",

    "InvalidContactError",
]