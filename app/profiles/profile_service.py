from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
)

from ..core.envelope import (
    b64e,
    b64d,
)

from ..services.crypto_service import (
    CryptoService,
)

JsonDict = Dict[str, Any]


# =========================================================
# Exceptions
# =========================================================

class ProfileServiceError(Exception):
    """Base profile service error."""


class ProfileAlreadyExistsError(
    ProfileServiceError
):
    """Profile already exists."""


class ProfileNotFoundError(
    ProfileServiceError
):
    """Profile not found."""


class InvalidProfileError(
    ProfileServiceError
):
    """Invalid profile."""


# =========================================================
# Profile Metadata
# =========================================================

@dataclass(slots=True)
class ProfileMetadata:

    profile_id: str

    username: str

    display_name: str

    created_at: str

    fingerprint: str


# =========================================================
# Profile Service
# =========================================================

class ProfileService:
    """
    Identity + profile management service.

    Responsibilities
    ------------------------------------------------
    - create identities
    - load/save profiles
    - export/import profiles
    - derive fingerprints
    - manage active profile
    - lightweight trust bootstrap

    Profile Structure
    ------------------------------------------------
    {
        "profile_id": "...",
        "username": "...",
        "display_name": "...",

        "created_at": "...",

        "ed25519": {
            "private_key": "...",
            "public_key": "...",
        },

        "x25519": {
            "private_key": "...",
            "public_key": "...",
        },

        "metadata": {...}
    }
    """

    PROFILE_VERSION = 1

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        profiles_dir: str = "profiles_data",
    ) -> None:

        self.profiles_dir = Path(
            profiles_dir
        )

        self.profiles_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._active_profile_id: Optional[
            str
        ] = None

    # =====================================================
    # Create Profile
    # =====================================================

    def create_profile(
        self,
        username: str,
        *,
        display_name: Optional[
            str
        ] = None,
        metadata: Optional[
            JsonDict
        ] = None,
        save: bool = True,
    ) -> JsonDict:
        """
        Create new secure identity profile.
        """

        username = (
            username.strip()
            .lower()
        )

        if not username:
            raise InvalidProfileError(
                "Username required."
            )

        profile_id = (
            self._generate_profile_id()
        )

        existing = (
            self.find_by_username(
                username
            )
        )

        if existing:
            raise (
                ProfileAlreadyExistsError(
                    f"Profile exists: "
                    f"{username}"
                )
            )

        # =============================================
        # Generate Ed25519
        # =============================================

        ed_private = (
            Ed25519PrivateKey.generate()
        )

        ed_public = (
            ed_private.public_key()
        )

        # =============================================
        # Generate X25519
        # =============================================

        x_private = (
            X25519PrivateKey.generate()
        )

        x_public = (
            x_private.public_key()
        )

        # =============================================
        # Build profile
        # =============================================

        created_at = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        ed_public_b64 = b64e(
            ed_public.public_bytes_raw()
        )

        profile: JsonDict = {

            "version":
                self.PROFILE_VERSION,

            "profile_id":
                profile_id,

            "username":
                username,

            "display_name":
                display_name
                or username,

            "created_at":
                created_at,

            "ed25519": {

                "private_key": b64e(
                    ed_private
                    .private_bytes_raw()
                ),

                "public_key":
                    ed_public_b64,
            },

            "x25519": {

                "private_key": b64e(
                    x_private
                    .private_bytes_raw()
                ),

                "public_key": b64e(
                    x_public
                    .public_bytes_raw()
                ),
            },

            "fingerprint":
                CryptoService
                .fingerprint_public_key(
                    ed_public_b64
                ),

            "metadata":
                metadata or {},
        }

        if save:
            self.save_profile(
                profile
            )

        return profile

    # =====================================================
    # Save / Load
    # =====================================================

    def save_profile(
        self,
        profile: JsonDict,
    ) -> Path:
        """
        Save profile to disk.
        """

        self.validate_profile(
            profile
        )

        profile_path = (
            self._profile_path(
                profile["profile_id"]
            )
        )

        profile_path.write_text(
            json.dumps(
                profile,
                indent=2,
            ),
            encoding="utf-8",
        )

        return profile_path

    def load_profile(
        self,
        profile_id: str,
    ) -> JsonDict:
        """
        Load profile by ID.
        """

        profile_path = (
            self._profile_path(
                profile_id
            )
        )

        if not profile_path.exists():

            raise (
                ProfileNotFoundError(
                    profile_id
                )
            )

        profile = json.loads(
            profile_path.read_text(
                encoding="utf-8"
            )
        )

        self.validate_profile(
            profile
        )

        return profile

    def delete_profile(
        self,
        profile_id: str,
    ) -> bool:
        """
        Delete stored profile.
        """

        path = self._profile_path(
            profile_id
        )

        if not path.exists():
            return False

        path.unlink()

        if (
            self._active_profile_id
            == profile_id
        ):
            self._active_profile_id = None

        return True

    # =====================================================
    # Active Profile
    # =====================================================

    def set_active_profile(
        self,
        profile_id: str,
    ) -> None:

        self.load_profile(
            profile_id
        )

        self._active_profile_id = (
            profile_id
        )

    def active_profile(
        self,
    ) -> Optional[JsonDict]:

        if not (
            self._active_profile_id
        ):
            return None

        return self.load_profile(
            self._active_profile_id
        )

    # =====================================================
    # Lookup
    # =====================================================

    def list_profiles(
        self,
    ) -> List[ProfileMetadata]:

        result = []

        for file in (
            self.profiles_dir.glob(
                "*.json"
            )
        ):

            try:

                profile = json.loads(
                    file.read_text(
                        encoding="utf-8"
                    )
                )

                result.append(
                    ProfileMetadata(
                        profile_id=(
                            profile[
                                "profile_id"
                            ]
                        ),

                        username=(
                            profile[
                                "username"
                            ]
                        ),

                        display_name=(
                            profile[
                                "display_name"
                            ]
                        ),

                        created_at=(
                            profile[
                                "created_at"
                            ]
                        ),

                        fingerprint=(
                            profile[
                                "fingerprint"
                            ]
                        ),
                    )
                )

            except Exception:
                continue

        return sorted(
            result,
            key=lambda x: (
                x.created_at
            ),
        )

    def find_by_username(
        self,
        username: str,
    ) -> Optional[JsonDict]:

        username = (
            username.lower()
        )

        for meta in (
            self.list_profiles()
        ):

            if (
                meta.username
                == username
            ):

                return self.load_profile(
                    meta.profile_id
                )

        return None

    # =====================================================
    # Export / Import
    # =====================================================

    def export_profile(
        self,
        profile_id: str,
        export_path: str,
    ) -> Path:
        """
        Export profile to external file.
        """

        profile = self.load_profile(
            profile_id
        )

        path = Path(export_path)

        path.write_text(
            json.dumps(
                profile,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    def import_profile(
        self,
        path: str,
        *,
        overwrite: bool = False,
    ) -> JsonDict:
        """
        Import profile from JSON file.
        """

        file_path = Path(path)

        if not file_path.exists():

            raise (
                FileNotFoundError(
                    path
                )
            )

        profile = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

        self.validate_profile(
            profile
        )

        existing = (
            self.find_by_username(
                profile[
                    "username"
                ]
            )
        )

        if existing and not overwrite:

            raise (
                ProfileAlreadyExistsError(
                    profile[
                        "username"
                    ]
                )
            )

        self.save_profile(
            profile
        )

        return profile

    # =====================================================
    # Public Contact Card
    # =====================================================

    def public_contact_card(
        self,
        profile: JsonDict,
    ) -> JsonDict:
        """
        Export public-safe identity.
        """

        return {

            "profile_id":
                profile[
                    "profile_id"
                ],

            "username":
                profile[
                    "username"
                ],

            "display_name":
                profile[
                    "display_name"
                ],

            "created_at":
                profile[
                    "created_at"
                ],

            "fingerprint":
                profile[
                    "fingerprint"
                ],

            "ed25519": {

                "public_key":
                    profile[
                        "ed25519"
                    ][
                        "public_key"
                    ],
            },

            "x25519": {

                "public_key":
                    profile[
                        "x25519"
                    ][
                        "public_key"
                    ],
            },
        }

    # =====================================================
    # Validation
    # =====================================================

    def validate_profile(
        self,
        profile: JsonDict,
    ) -> None:
        """
        Validate profile structure.
        """

        required = [

            "profile_id",
            "username",
            "display_name",
            "created_at",

            "ed25519",
            "x25519",
        ]

        for field in required:

            if field not in profile:

                raise (
                    InvalidProfileError(
                        f"Missing field: "
                        f"{field}"
                    )
                )

        for key_type in [

            "ed25519",
            "x25519",
        ]:

            obj = profile[
                key_type
            ]

            if (
                "private_key"
                not in obj
            ):

                raise (
                    InvalidProfileError(
                        f"Missing "
                        f"{key_type} "
                        f"private key."
                    )
                )

            if (
                "public_key"
                not in obj
            ):

                raise (
                    InvalidProfileError(
                        f"Missing "
                        f"{key_type} "
                        f"public key."
                    )
                )

    # =====================================================
    # Fingerprints
    # =====================================================

    def fingerprint(
        self,
        profile: JsonDict,
    ) -> str:

        return str(
            profile.get(
                "fingerprint"
            )
        )

    # =====================================================
    # Helpers
    # =====================================================

    def _generate_profile_id(
        self,
    ) -> str:

        return secrets.token_hex(
            16
        )

    def _profile_path(
        self,
        profile_id: str,
    ) -> Path:

        return (
            self.profiles_dir
            / f"{profile_id}.json"
        )

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> JsonDict:

        return {

            "profiles":
                len(
                    self.list_profiles()
                ),

            "active_profile":
                self._active_profile_id,
        }


__all__ = [

    "ProfileService",

    "ProfileMetadata",

    "ProfileServiceError",

    "ProfileAlreadyExistsError",

    "ProfileNotFoundError",

    "InvalidProfileError",
]