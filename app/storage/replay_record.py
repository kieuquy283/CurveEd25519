from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    slots=True,
    frozen=True,
)
class ReplayCacheRecord:
    """
    Replay cache entry.

    replay_key:
        sender_fp:message_id

    created_at_unix:
        UTC unix timestamp.

    expires_at_unix:
        UTC expiration timestamp.
    """

    replay_key: str

    created_at_unix: float

    expires_at_unix: float

    message_id: str

    sender_fingerprint: str | None = None