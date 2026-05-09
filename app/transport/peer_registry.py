from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# =========================================================
# Exceptions
# =========================================================

class PeerRegistryError(Exception):
    """Base peer registry error."""


class PeerAlreadyExistsError(
    PeerRegistryError
):
    """Peer already exists."""


class PeerNotFoundError(
    PeerRegistryError
):
    """Peer not found."""


class InvalidPeerError(
    PeerRegistryError
):
    """Invalid peer record."""


# =========================================================
# Peer Record
# =========================================================

@dataclass(slots=True)
class PeerRecord:
    """
    Trusted peer/contact record.
    """

    peer_id: str

    display_name: str

    ed25519_public_key_b64: str

    x25519_public_key_b64: str

    ed25519_fingerprint: str

    x25519_fingerprint: str

    created_at: float = field(
        default_factory=time.time
    )

    updated_at: float = field(
        default_factory=time.time
    )

    last_seen_at: Optional[
        float
    ] = None

    is_blocked: bool = False

    is_trusted: bool = True

    metadata: Dict = field(
        default_factory=dict
    )

    def validate(self) -> None:

        if not self.peer_id.strip():
            raise InvalidPeerError(
                "peer_id required."
            )

        if not self.display_name.strip():
            raise InvalidPeerError(
                "display_name required."
            )

        if not self.ed25519_public_key_b64:
            raise InvalidPeerError(
                "ed25519 key required."
            )

        if not self.x25519_public_key_b64:
            raise InvalidPeerError(
                "x25519 key required."
            )

        if not self.ed25519_fingerprint:
            raise InvalidPeerError(
                "ed25519 fingerprint required."
            )

        if not self.x25519_fingerprint:
            raise InvalidPeerError(
                "x25519 fingerprint required."
            )


# =========================================================
# Peer Registry
# =========================================================

class PeerRegistry:
    """
    Persistent trusted peer registry.

    Responsibilities
    ------------------------------------------------
    - peer/contact storage
    - identity lookup
    - fingerprint verification
    - trust management
    - peer metadata
    - blocked peer management

    Storage
    ------------------------------------------------
    SQLite-backed persistent registry.
    """

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        db_path: str = (
            "data/peer_registry.db"
        ),
    ) -> None:

        self.db_path = db_path

        Path(db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()

        self._initialize_database()

    # =====================================================
    # Database
    # =====================================================

    def _connect(self):

        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )

        conn.row_factory = (
            sqlite3.Row
        )

        return conn

    def _initialize_database(
        self,
    ) -> None:

        with self._connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS peers (

                    peer_id TEXT PRIMARY KEY,

                    display_name TEXT NOT NULL,

                    ed25519_public_key_b64 TEXT NOT NULL,

                    x25519_public_key_b64 TEXT NOT NULL,

                    ed25519_fingerprint TEXT NOT NULL,

                    x25519_fingerprint TEXT NOT NULL,

                    created_at REAL NOT NULL,

                    updated_at REAL NOT NULL,

                    last_seen_at REAL,

                    is_blocked INTEGER NOT NULL,

                    is_trusted INTEGER NOT NULL,

                    metadata_json TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_peer_ed25519_fp

                ON peers (
                    ed25519_fingerprint
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_peer_x25519_fp

                ON peers (
                    x25519_fingerprint
                )
                """
            )

            conn.commit()

    # =====================================================
    # Add Peer
    # =====================================================

    def add_peer(
        self,
        peer: PeerRecord,
    ) -> None:

        peer.validate()

        with self._lock:

            if self.exists(
                peer.peer_id
            ):
                raise (
                    PeerAlreadyExistsError(
                        f"Peer exists: "
                        f"{peer.peer_id}"
                    )
                )

            now = time.time()

            peer.created_at = now
            peer.updated_at = now

            with self._connect() as conn:

                conn.execute(
                    """
                    INSERT INTO peers (

                        peer_id,
                        display_name,

                        ed25519_public_key_b64,
                        x25519_public_key_b64,

                        ed25519_fingerprint,
                        x25519_fingerprint,

                        created_at,
                        updated_at,
                        last_seen_at,

                        is_blocked,
                        is_trusted,

                        metadata_json

                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        peer.peer_id,
                        peer.display_name,

                        peer.ed25519_public_key_b64,
                        peer.x25519_public_key_b64,

                        peer.ed25519_fingerprint,
                        peer.x25519_fingerprint,

                        peer.created_at,
                        peer.updated_at,
                        peer.last_seen_at,

                        int(
                            peer.is_blocked
                        ),

                        int(
                            peer.is_trusted
                        ),

                        json.dumps(
                            peer.metadata
                        ),
                    ),
                )

                conn.commit()

    # =====================================================
    # Update Peer
    # =====================================================

    def update_peer(
        self,
        peer: PeerRecord,
    ) -> None:

        peer.validate()

        with self._lock:

            if not self.exists(
                peer.peer_id
            ):
                raise (
                    PeerNotFoundError(
                        peer.peer_id
                    )
                )

            peer.updated_at = (
                time.time()
            )

            with self._connect() as conn:

                conn.execute(
                    """
                    UPDATE peers
                    SET

                        display_name=?,

                        ed25519_public_key_b64=?,
                        x25519_public_key_b64=?,

                        ed25519_fingerprint=?,
                        x25519_fingerprint=?,

                        updated_at=?,
                        last_seen_at=?,

                        is_blocked=?,
                        is_trusted=?,

                        metadata_json=?

                    WHERE peer_id=?
                    """,
                    (
                        peer.display_name,

                        peer.ed25519_public_key_b64,
                        peer.x25519_public_key_b64,

                        peer.ed25519_fingerprint,
                        peer.x25519_fingerprint,

                        peer.updated_at,
                        peer.last_seen_at,

                        int(
                            peer.is_blocked
                        ),

                        int(
                            peer.is_trusted
                        ),

                        json.dumps(
                            peer.metadata
                        ),

                        peer.peer_id,
                    ),
                )

                conn.commit()

    # =====================================================
    # Get Peer
    # =====================================================

    def get_peer(
        self,
        peer_id: str,
    ) -> PeerRecord:

        with self._lock:

            with self._connect() as conn:

                row = conn.execute(
                    """
                    SELECT *
                    FROM peers
                    WHERE peer_id=?
                    """,
                    (peer_id,),
                ).fetchone()

        if row is None:
            raise (
                PeerNotFoundError(
                    peer_id
                )
            )

        return self._row_to_peer(
            row
        )

    # =====================================================
    # Lookup by Fingerprint
    # =====================================================

    def get_peer_by_ed25519_fingerprint(
        self,
        fingerprint: str,
    ) -> Optional[
        PeerRecord
    ]:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM peers
                WHERE ed25519_fingerprint=?
                """,
                (fingerprint,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_peer(
            row
        )

    def get_peer_by_x25519_fingerprint(
        self,
        fingerprint: str,
    ) -> Optional[
        PeerRecord
    ]:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM peers
                WHERE x25519_fingerprint=?
                """,
                (fingerprint,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_peer(
            row
        )

    # =====================================================
    # Remove Peer
    # =====================================================

    def remove_peer(
        self,
        peer_id: str,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    DELETE FROM peers
                    WHERE peer_id=?
                    """,
                    (peer_id,),
                )

                conn.commit()

    # =====================================================
    # Trust / Block
    # =====================================================

    def block_peer(
        self,
        peer_id: str,
    ) -> None:

        self._update_flag(
            peer_id,
            field_name="is_blocked",
            value=True,
        )

    def unblock_peer(
        self,
        peer_id: str,
    ) -> None:

        self._update_flag(
            peer_id,
            field_name="is_blocked",
            value=False,
        )

    def trust_peer(
        self,
        peer_id: str,
    ) -> None:

        self._update_flag(
            peer_id,
            field_name="is_trusted",
            value=True,
        )

    def untrust_peer(
        self,
        peer_id: str,
    ) -> None:

        self._update_flag(
            peer_id,
            field_name="is_trusted",
            value=False,
        )

    def _update_flag(
        self,
        peer_id: str,
        *,
        field_name: str,
        value: bool,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    f"""
                    UPDATE peers
                    SET {field_name}=?,
                        updated_at=?
                    WHERE peer_id=?
                    """,
                    (
                        int(value),
                        time.time(),
                        peer_id,
                    ),
                )

                conn.commit()

    # =====================================================
    # Presence
    # =====================================================

    def update_last_seen(
        self,
        peer_id: str,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    UPDATE peers
                    SET
                        last_seen_at=?,
                        updated_at=?
                    WHERE peer_id=?
                    """,
                    (
                        time.time(),
                        time.time(),
                        peer_id,
                    ),
                )

                conn.commit()

    # =====================================================
    # Queries
    # =====================================================

    def exists(
        self,
        peer_id: str,
    ) -> bool:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT 1
                FROM peers
                WHERE peer_id=?
                """,
                (peer_id,),
            ).fetchone()

        return row is not None

    def list_peers(
        self,
        *,
        trusted_only: bool = False,
        include_blocked: bool = False,
    ) -> List[
        PeerRecord
    ]:

        query = (
            "SELECT * FROM peers "
            "WHERE 1=1 "
        )

        params = []

        if trusted_only:
            query += (
                "AND is_trusted=1 "
            )

        if not include_blocked:
            query += (
                "AND is_blocked=0 "
            )

        query += (
            "ORDER BY display_name ASC"
        )

        with self._connect() as conn:

            rows = conn.execute(
                query,
                params,
            ).fetchall()

        return [
            self._row_to_peer(row)
            for row in rows
        ]

    def count_peers(
        self,
    ) -> int:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM peers
                """
            ).fetchone()

        return int(row[0])

    # =====================================================
    # Serialization
    # =====================================================

    @staticmethod
    def _row_to_peer(
        row: sqlite3.Row,
    ) -> PeerRecord:

        return PeerRecord(
            peer_id=row["peer_id"],

            display_name=row[
                "display_name"
            ],

            ed25519_public_key_b64=row[
                "ed25519_public_key_b64"
            ],

            x25519_public_key_b64=row[
                "x25519_public_key_b64"
            ],

            ed25519_fingerprint=row[
                "ed25519_fingerprint"
            ],

            x25519_fingerprint=row[
                "x25519_fingerprint"
            ],

            created_at=row[
                "created_at"
            ],

            updated_at=row[
                "updated_at"
            ],

            last_seen_at=row[
                "last_seen_at"
            ],

            is_blocked=bool(
                row["is_blocked"]
            ),

            is_trusted=bool(
                row["is_trusted"]
            ),

            metadata=json.loads(
                row["metadata_json"]
            ),
        )

    # =====================================================
    # Export
    # =====================================================

    def export_peers(
        self,
    ) -> List[dict]:

        return [
            asdict(peer)
            for peer in self.list_peers(
                include_blocked=True
            )
        ]

    # =====================================================
    # Stats
    # =====================================================

    def stats(
        self,
    ) -> dict:

        peers = self.list_peers(
            include_blocked=True
        )

        return {
            "total_peers": len(peers),

            "trusted_peers": sum(
                1
                for p in peers
                if p.is_trusted
            ),

            "blocked_peers": sum(
                1
                for p in peers
                if p.is_blocked
            ),
        }