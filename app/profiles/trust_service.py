from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..profiles.contact_service import (
    ContactService,
)

JsonDict = Dict[str, Any]


# =========================================================
# Trust Levels
# =========================================================

class TrustLevel(str, Enum):

    UNKNOWN = "unknown"

    UNTRUSTED = "untrusted"

    VERIFIED = "verified"

    TRUSTED = "trusted"

    BLOCKED = "blocked"


# =========================================================
# Verification Methods
# =========================================================

class VerificationMethod(str, Enum):

    MANUAL = "manual"

    FINGERPRINT = "fingerprint"

    QR_CODE = "qr_code"

    SAFETY_NUMBER = "safety_number"

    IMPORTED = "imported"

    TOFU = "tofu"  # trust on first use


# =========================================================
# Verification Record
# =========================================================

@dataclass(slots=True)
class VerificationRecord:

    peer_id: str

    fingerprint: str

    trust_level: TrustLevel

    verification_method: VerificationMethod

    verified_at: str

    notes: Optional[str] = None


# =========================================================
# Exceptions
# =========================================================

class TrustServiceError(Exception):
    """Base trust service error."""


class VerificationFailedError(
    TrustServiceError
):
    """Fingerprint verification failed."""


class IdentityChangedError(
    TrustServiceError
):
    """Peer identity changed."""


# =========================================================
# Trust Service
# =========================================================

class TrustService:
    """
    Identity trust + verification service.

    Responsibilities
    ------------------------------------------------
    - fingerprint verification
    - trust levels
    - TOFU validation
    - identity change detection
    - safety number generation
    - verification persistence
    - trust history

    Security Model
    ------------------------------------------------
    UNKNOWN
        first contact

    TOFU
        automatically trusted first seen identity

    VERIFIED
        fingerprint manually checked

    TRUSTED
        explicitly trusted user

    BLOCKED
        rejected identity
    """

    TRUST_VERSION = 1

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        contact_service: ContactService,
        trust_dir: str = "trust_data",
    ) -> None:

        self.contact_service = (
            contact_service
        )

        self.trust_dir = Path(
            trust_dir
        )

        self.trust_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =====================================================
    # Trust State
    # =====================================================

    def trust_level(
        self,
        peer_id: str,
    ) -> TrustLevel:

        record = self.load_record(
            peer_id
        )

        if not record:

            return (
                TrustLevel.UNKNOWN
            )

        return TrustLevel(
            record["trust_level"]
        )

    def is_trusted(
        self,
        peer_id: str,
    ) -> bool:

        level = self.trust_level(
            peer_id
        )

        return level in {

            TrustLevel.VERIFIED,
            TrustLevel.TRUSTED,
        }

    def is_blocked(
        self,
        peer_id: str,
    ) -> bool:

        return (
            self.trust_level(
                peer_id
            )
            == TrustLevel.BLOCKED
        )

    # =====================================================
    # TOFU
    # =====================================================

    def trust_on_first_use(
        self,
        peer_id: str,
        fingerprint: str,
    ) -> JsonDict:
        """
        TOFU bootstrap.
        """

        existing = self.load_record(
            peer_id
        )

        if existing:

            stored = (
                existing[
                    "fingerprint"
                ]
            )

            if stored != fingerprint:

                raise (
                    IdentityChangedError(
                        f"Identity changed "
                        f"for peer: "
                        f"{peer_id}"
                    )
                )

            return existing

        record = self._build_record(

            peer_id=peer_id,

            fingerprint=fingerprint,

            trust_level=(
                TrustLevel.UNTRUSTED
            ),

            method=(
                VerificationMethod.TOFU
            ),
        )

        self.save_record(record)

        return record

    # =====================================================
    # Verification
    # =====================================================

    def verify_fingerprint(
        self,
        peer_id: str,
        fingerprint: str,
        *,
        method: VerificationMethod = (
            VerificationMethod
            .FINGERPRINT
        ),
        notes: Optional[
            str
        ] = None,
    ) -> JsonDict:
        """
        Verify peer identity.
        """

        contact = (
            self.contact_service
            .load_contact(
                peer_id
            )
        )

        expected = (
            contact["fingerprint"]
        )

        if expected != fingerprint:

            raise (
                VerificationFailedError(
                    "Fingerprint mismatch."
                )
            )

        record = self._build_record(

            peer_id=peer_id,

            fingerprint=fingerprint,

            trust_level=(
                TrustLevel.VERIFIED
            ),

            method=method,

            notes=notes,
        )

        self.save_record(record)

        return record

    def set_trust_level(
        self,
        peer_id: str,
        trust_level: TrustLevel,
        *,
        notes: Optional[
            str
        ] = None,
    ) -> JsonDict:

        contact = (
            self.contact_service
            .load_contact(
                peer_id
            )
        )

        record = self._build_record(

            peer_id=peer_id,

            fingerprint=(
                contact[
                    "fingerprint"
                ]
            ),

            trust_level=trust_level,

            method=(
                VerificationMethod
                .MANUAL
            ),

            notes=notes,
        )

        self.save_record(record)

        return record

    # =====================================================
    # Identity Validation
    # =====================================================

    def validate_identity(
        self,
        peer_id: str,
        fingerprint: str,
    ) -> bool:
        """
        Detect identity changes.
        """

        record = self.load_record(
            peer_id
        )

        if not record:
            return False

        stored = (
            record[
                "fingerprint"
            ]
        )

        if stored != fingerprint:

            raise (
                IdentityChangedError(
                    f"Identity mismatch "
                    f"for peer "
                    f"{peer_id}"
                )
            )

        return True

    # =====================================================
    # Safety Numbers
    # =====================================================

    def safety_number(
        self,
        peer_id: str,
    ) -> str:
        """
        Generate user-readable
        verification number.
        """

        contact = (
            self.contact_service
            .load_contact(
                peer_id
            )
        )

        fingerprint = (
            contact[
                "fingerprint"
            ]
        )

        chunks = [

            fingerprint[i:i + 5]

            for i in range(
                0,
                min(
                    len(fingerprint),
                    60,
                ),
                5,
            )
        ]

        return " ".join(
            chunks
        )

    # =====================================================
    # Persistence
    # =====================================================

    def save_record(
        self,
        record: JsonDict,
    ) -> Path:

        path = self._trust_path(
            record["peer_id"]
        )

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            json.dumps(
                record,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    def load_record(
        self,
        peer_id: str,
    ) -> Optional[JsonDict]:

        path = self._trust_path(
            peer_id
        )

        if not path.exists():
            return None

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    def remove_record(
        self,
        peer_id: str,
    ) -> bool:

        path = self._trust_path(
            peer_id
        )

        if not path.exists():
            return False

        path.unlink()

        return True

    # =====================================================
    # Queries
    # =====================================================

    def verified_peers(
        self,
    ) -> List[JsonDict]:

        return [

            record

            for record in (
                self.all_records()
            )

            if (
                record[
                    "trust_level"
                ]
                == TrustLevel.VERIFIED
            )
        ]

    def trusted_peers(
        self,
    ) -> List[JsonDict]:

        return [

            record

            for record in (
                self.all_records()
            )

            if (
                record[
                    "trust_level"
                ]
                == TrustLevel.TRUSTED
            )
        ]

    def blocked_peers(
        self,
    ) -> List[JsonDict]:

        return [

            record

            for record in (
                self.all_records()
            )

            if (
                record[
                    "trust_level"
                ]
                == TrustLevel.BLOCKED
            )
        ]

    def all_records(
        self,
    ) -> List[JsonDict]:

        records = []

        for file in (
            self.trust_dir.glob(
                "*.json"
            )
        ):

            try:

                records.append(
                    json.loads(
                        file.read_text(
                            encoding="utf-8"
                        )
                    )
                )

            except Exception:
                continue

        return sorted(
            records,
            key=lambda x: (
                x[
                    "verified_at"
                ]
            ),
        )

    # =====================================================
    # Helpers
    # =====================================================

    def _build_record(
        self,
        *,
        peer_id: str,
        fingerprint: str,
        trust_level: TrustLevel,
        method: VerificationMethod,
        notes: Optional[
            str
        ] = None,
    ) -> JsonDict:

        return {

            "version":
                self.TRUST_VERSION,

            "peer_id":
                peer_id,

            "fingerprint":
                fingerprint,

            "trust_level":
                trust_level.value,

            "verification_method":
                method.value,

            "verified_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "notes":
                notes,
        }

    def _trust_path(
        self,
        peer_id: str,
    ) -> Path:

        return (
            self.trust_dir
            / f"{peer_id}.json"
        )

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> JsonDict:

        records = (
            self.all_records()
        )

        return {

            "records":
                len(records),

            "verified":
                len([
                    r for r
                    in records
                    if r[
                        "trust_level"
                    ]
                    == TrustLevel
                    .VERIFIED
                ]),

            "trusted":
                len([
                    r for r
                    in records
                    if r[
                        "trust_level"
                    ]
                    == TrustLevel
                    .TRUSTED
                ]),

            "blocked":
                len([
                    r for r
                    in records
                    if r[
                        "trust_level"
                    ]
                    == TrustLevel
                    .BLOCKED
                ]),
        }


__all__ = [

    "TrustService",

    "TrustLevel",

    "VerificationMethod",

    "VerificationRecord",

    "TrustServiceError",

    "VerificationFailedError",

    "IdentityChangedError",
]