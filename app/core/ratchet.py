from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


# =========================================================
# Constants
# =========================================================

ROOT_RATCHET_INFO = b"double-ratchet-root"
CHAIN_RATCHET_INFO = b"double-ratchet-chain"

ROOT_KEY_LEN = 32
CHAIN_KEY_LEN = 32
MESSAGE_KEY_LEN = 32


# =========================================================
# Exceptions
# =========================================================

class RatchetError(Exception):
    pass


class SkippedMessageKeyNotFound(RatchetError):
    pass


# =========================================================
# Message Key
# =========================================================

@dataclass(slots=True)
class MessageKey:
    key: bytes
    index: int


# =========================================================
# Chain State
# =========================================================

@dataclass(slots=True)
class ChainState:
    chain_key: bytes
    message_index: int = 0

    def next_message_key(self) -> MessageKey:
        """
        Advance chain:
            CK(n+1), MK(n)
        """

        mk = hmac.new(
            self.chain_key,
            b"\x01",
            hashlib.sha256,
        ).digest()

        next_ck = hmac.new(
            self.chain_key,
            b"\x02",
            hashlib.sha256,
        ).digest()

        msg_index = self.message_index

        self.chain_key = next_ck
        self.message_index += 1

        return MessageKey(
            key=mk[:MESSAGE_KEY_LEN],
            index=msg_index,
        )


# =========================================================
# Ratchet State
# =========================================================

@dataclass(slots=True)
class RatchetState:
    """
    Core Double Ratchet state.
    """

    # Root state
    root_key: bytes

    # DH ratchet public/private
    dh_private_b64: Optional[str] = None
    dh_public_b64: Optional[str] = None

    remote_public_b64: Optional[str] = None

    # Sending / Receiving chains
    sending_chain: Optional[ChainState] = None
    receiving_chain: Optional[ChainState] = None

    # Counters
    previous_sending_chain_length: int = 0

    # Skipped keys
    skipped_message_keys: Dict[
        Tuple[str, int],
        bytes
    ] = field(default_factory=dict)

    # =====================================================
    # Root Ratchet
    # =====================================================

    def perform_dh_ratchet(
        self,
        *,
        shared_secret: bytes,
    ) -> None:
        """
        Root ratchet step.

        Produces:
            new root key
            new sending chain
            new receiving chain
        """

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=96,
            salt=self.root_key,
            info=ROOT_RATCHET_INFO,
        )

        material = hkdf.derive(shared_secret)

        new_root = material[:32]
        recv_ck = material[32:64]
        send_ck = material[64:96]

        self.root_key = new_root

        self.receiving_chain = ChainState(
            chain_key=recv_ck
        )

        self.sending_chain = ChainState(
            chain_key=send_ck
        )

        self.previous_sending_chain_length = 0

    # =====================================================
    # Sending
    # =====================================================

    def next_sending_message_key(self) -> MessageKey:

        if self.sending_chain is None:
            raise RatchetError(
                "Sending chain not initialized."
            )

        return self.sending_chain.next_message_key()

    # =====================================================
    # Receiving
    # =====================================================

    def next_receiving_message_key(self) -> MessageKey:

        if self.receiving_chain is None:
            raise RatchetError(
                "Receiving chain not initialized."
            )

        return self.receiving_chain.next_message_key()

    # =====================================================
    # Skipped Keys
    # =====================================================

    def store_skipped_key(
        self,
        *,
        ratchet_pub: str,
        index: int,
        key: bytes,
    ) -> None:

        self.skipped_message_keys[
            (ratchet_pub, index)
        ] = key

    def pop_skipped_key(
        self,
        *,
        ratchet_pub: str,
        index: int,
    ) -> bytes:

        value = self.skipped_message_keys.pop(
            (ratchet_pub, index),
            None,
        )

        if value is None:
            raise SkippedMessageKeyNotFound(
                f"Skipped key not found: "
                f"{ratchet_pub}:{index}"
            )

        return value