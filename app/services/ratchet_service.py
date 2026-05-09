from __future__ import annotations

from typing import Optional

from ..core.ratchet import (
    RatchetState,
    MessageKey,
    RatchetError,
)

from ..core.x25519 import (
    derive_shared_secret_from_b64,
    generate_ephemeral_keypair,
)

from ..storage.session_store import (
    BaseSessionStore,
)


class RatchetServiceError(Exception):
    pass


class RatchetService:
    """
    Double Ratchet orchestration layer.
    """

    MAX_SKIPPED_KEYS = 1024

    def __init__(
        self,
        *,
        session_store: BaseSessionStore,
    ) -> None:

        self.session_store = session_store

    # =====================================================
    # Session bootstrap
    # =====================================================

    def initialize_session_ratchet(
        self,
        *,
        session_id: str,
        root_key: bytes,
        local_private_b64: str,
        local_public_b64: str,
        remote_public_b64: str,
    ) -> RatchetState:

        state = RatchetState(
            root_key=root_key,
            dh_private_b64=local_private_b64,
            dh_public_b64=local_public_b64,
            remote_public_b64=remote_public_b64,
        )

        shared_secret = derive_shared_secret_from_b64(
            private_key_b64=local_private_b64,
            peer_public_key_b64=remote_public_b64,
        )

        state.perform_dh_ratchet(
            shared_secret=shared_secret
        )

        self.session_store.save_ratchet_state(
            session_id,
            state,
        )

        return state

    # =====================================================
    # Sending
    # =====================================================

    def next_outbound_message_key(
        self,
        *,
        session_id: str,
    ) -> tuple[MessageKey, RatchetState]:

        state = self.session_store.load_ratchet_state(
            session_id
        )

        mk = state.next_sending_message_key()

        self.session_store.save_ratchet_state(
            session_id,
            state,
        )

        return mk, state

    # =====================================================
    # Receiving
    # =====================================================

    def next_inbound_message_key(
        self,
        *,
        session_id: str,
    ) -> MessageKey:

        state = self.session_store.load_ratchet_state(
            session_id
        )

        mk = state.next_receiving_message_key()

        self.session_store.save_ratchet_state(
            session_id,
            state,
        )

        return mk

    # =====================================================
    # DH Ratchet Rotation
    # =====================================================

    def rotate_ratchet(
        self,
        *,
        session_id: str,
        remote_public_b64: str,
    ) -> RatchetState:

        state = self.session_store.load_ratchet_state(
            session_id
        )

        new_local = generate_ephemeral_keypair()

        shared_secret = derive_shared_secret_from_b64(
            private_key_b64=new_local.private_key_b64,
            peer_public_key_b64=remote_public_b64,
        )

        state.dh_private_b64 = (
            new_local.private_key_b64
        )

        state.dh_public_b64 = (
            new_local.public_key_b64
        )

        state.remote_public_b64 = (
            remote_public_b64
        )

        state.perform_dh_ratchet(
            shared_secret=shared_secret
        )

        self.session_store.save_ratchet_state(
            session_id,
            state,
        )

        return state