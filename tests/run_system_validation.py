from __future__ import annotations

import asyncio
import shutil
import traceback
from pathlib import Path
from typing import Awaitable, Callable

# =========================================================
# TEST REGISTRY
# =========================================================

TESTS: list[
    tuple[
        str,
        Callable[..., Awaitable[None]],
    ]
] = []


def test(name: str):

    def wrapper(fn):

        TESTS.append(
            (name, fn)
        )

        return fn

    return wrapper


# =========================================================
# ASSERT HELPERS
# =========================================================

def assert_true(
    condition,
    message: str = (
        "Assertion failed"
    ),
):

    if not condition:
        raise AssertionError(
            message
        )


def assert_equal(
    a,
    b,
    message=None,
):

    if a != b:

        raise AssertionError(
            message
            or f"{a!r} != {b!r}"
        )


# =========================================================
# IMPORTS
# =========================================================

from app.services.crypto_service import (
    CryptoService,
)

from app.services.protocol_service import (
    ProtocolService,
)

from app.services.event_bus import (
    EventBus,
)

from app.services.typing_service import (
    TypingService,
)

from app.services.notification_service import (
    NotificationService,
)

from app.transport.transport_packet import (
    TransportPacket,
)

from app.transport.transport_events import (
    TransportEvent,
    TransportEventType,
)

from app.core.packet_types import (
    PacketType,
)

from app.profiles.profile_service import (
    ProfileService,
)

from app.profiles.contact_service import (
    ContactService,
)

from app.profiles.trust_service import (
    TrustService,
    TrustLevel,
)

# =========================================================
# TEST DIRECTORIES
# =========================================================

TEST_PROFILES_DIR = (
    "test_profiles"
)

TEST_CONTACTS_DIR = (
    "test_contacts"
)

TEST_TRUST_DIR = (
    "test_trust"
)

# =========================================================
# MOCK TRANSPORT
# =========================================================

class MockTransport:

    def __init__(self):

        self.sent_packets = []

    async def send_packet(
        self,
        packet,
    ):

        self.sent_packets.append(
            packet
        )

        return True


# =========================================================
# SERVICES
# =========================================================

_profile_service = (
    ProfileService(
        profiles_dir=(
            TEST_PROFILES_DIR
        )
    )
)

_contact_service = (
    ContactService(
        contacts_dir=(
            TEST_CONTACTS_DIR
        )
    )
)

_trust_service = (
    TrustService(
        contact_service=(
            _contact_service
        ),
        trust_dir=(
            TEST_TRUST_DIR
        ),
    )
)

# =========================================================
# FIXTURES
# =========================================================

_profile_counter = 0


def build_profiles():

    global _profile_counter

    _profile_counter += 1

    suffix = str(
        _profile_counter
    )

    alice = (
        _profile_service
        .create_profile(
            f"alice_{suffix}",
            save=False,
        )
    )

    bob = (
        _profile_service
        .create_profile(
            f"bob_{suffix}",
            save=False,
        )
    )

    return alice, bob


# =========================================================
# CRYPTO TESTS
# =========================================================

@test("crypto.sign_verify")
async def test_sign_verify():

    alice, _ = (
        build_profiles()
    )

    message = (
        b"hello secure world"
    )

    signature = (
        CryptoService.sign_bytes(
            private_key_b64=(
                alice[
                    "ed25519"
                ][
                    "private_key"
                ]
            ),
            data=message,
        )
    )

    verified = (
        CryptoService
        .verify_bytes(
            public_key_b64=(
                alice[
                    "ed25519"
                ][
                    "public_key"
                ]
            ),
            data=message,
            signature=signature,
        )
    )

    assert_true(
        verified,
        "Signature verification failed",
    )


@test("crypto.encrypt_decrypt")
async def test_encrypt_decrypt():

    alice, bob = (
        build_profiles()
    )

    plaintext = (
        b"top secret payload"
    )

    enc = (
        CryptoService
        .encrypt_payload(
            receiver_x25519_public_b64=(
                bob[
                    "x25519"
                ][
                    "public_key"
                ]
            ),
            plaintext=plaintext,
        )
    )

    envelope = {

        "header": {

            "version": 1,

            "message_id":
                "test-message",

            "sender": {

                "name":
                    "alice",

                "ed25519_public_key":
                    alice[
                        "ed25519"
                    ][
                        "public_key"
                    ],
            },

            "receiver": {
                "name": "bob",
            },

            "crypto": {

                "ephemeral_x25519_public_key":
                    enc[
                        "ephemeral_public_key_b64"
                    ],

                "salt_wrap":
                    enc[
                        "salt_wrap_b64"
                    ],

                "payload_nonce":
                    enc[
                        "payload_nonce_b64"
                    ],
            },
        },

        "wrapped_key":
            enc[
                "wrapped_key_b64"
            ],

        "ciphertext":
            enc[
                "ciphertext_b64"
            ],

        "signature": {

            "algorithm":
                "Ed25519",

            "value": "",
        },
    }

    decrypted = (
        CryptoService
        .decrypt_payload(
            receiver_x25519_private_b64=(
                bob[
                    "x25519"
                ][
                    "private_key"
                ]
            ),
            envelope=envelope,
        )
    )

    assert_equal(
        decrypted,
        plaintext,
    )


# =========================================================
# PROTOCOL TEST
# =========================================================

@test("protocol.send_receive")
async def test_protocol_send_receive():

    alice, bob = (
        build_profiles()
    )

    result = (
        ProtocolService
        .send_message(
            sender_profile=alice,
            receiver_contact=bob,
            plaintext="hello bob",
        )
    )

    envelope = (
        result[
            "envelope"
        ]
    )

    recv = (
        ProtocolService
        .receive_message(
            receiver_profile=bob,
            envelope=envelope,
            sender_contact=alice,
        )
    )

    assert_true(
        recv["verified"],
        "Protocol verification failed",
    )

    assert_equal(
        recv["plaintext"],
        "hello bob",
    )


# =========================================================
# EVENT BUS TEST
# =========================================================

@test("event_bus.emit")
async def test_event_bus():

    bus = EventBus()

    received = []

    async def callback(
        event,
    ):

        received.append(
            event
        )

    bus.subscribe(
        TransportEventType
        .MESSAGE_RECEIVED,

        callback,
    )

    if hasattr(
        bus,
        "start",
    ):
        await bus.start()

    await bus.emit(
        TransportEvent(
            event_type=(
                TransportEventType
                .MESSAGE_RECEIVED
            ),

            peer_id="bob",

            metadata={
                "text":
                    "hello"
            },
        )
    )

    await asyncio.sleep(
        0.2
    )

    if hasattr(
        bus,
        "stop",
    ):
        await bus.stop()

    assert_equal(
        len(received),
        1,
    )


# =========================================================
# TYPING SERVICE TEST
# =========================================================

@test("typing.start_stop")
async def test_typing_service():

    transport = (
        MockTransport()
    )

    bus = EventBus()

    if hasattr(
        bus,
        "start",
    ):
        await bus.start()

    service = (
        TypingService(
            local_peer_id=(
                "alice"
            ),

            transport=transport,

            event_bus=bus,
        )
    )

    if hasattr(
        service,
        "start",
    ):
        await service.start()

    sent = (
        await service
        .send_typing_start(
            "bob"
        )
    )

    assert_true(
        sent,
        "Typing start not sent",
    )

    assert_equal(
        len(
            transport
            .sent_packets
        ),
        1,
    )

    packet = (
        transport
        .sent_packets[0]
    )

    assert_equal(
        packet.packet_type,
        PacketType
        .TYPING_START,
    )

    stopped = (
        await service
        .send_typing_stop(
            "bob"
        )
    )

    assert_true(
        stopped,
        "Typing stop not sent",
    )

    if hasattr(
        service,
        "stop",
    ):
        await service.stop()

    if hasattr(
        bus,
        "stop",
    ):
        await bus.stop()


# =========================================================
# NOTIFICATION TEST
# =========================================================

@test("notification.receive")
async def test_notifications():

    bus = EventBus()

    if hasattr(
        bus,
        "start",
    ):
        await bus.start()

    service = (
        NotificationService(
            event_bus=bus,

            enable_desktop=False,

            enable_sound=False,
        )
    )

    if hasattr(
        service,
        "start",
    ):
        await service.start()

    await bus.emit(
        TransportEvent(
            event_type=(
                TransportEventType
                .MESSAGE_RECEIVED
            ),

            peer_id="bob",

            metadata={

                "sender_name":
                    "Bob",

                "plaintext":
                    "hello alice",
            },
        )
    )

    await asyncio.sleep(
        0.2
    )

    if hasattr(
        service,
        "notifications",
    ):

        notifications = (
            service
            .notifications()
        )

    else:

        notifications = (
            service
            .get_notifications()
        )

    assert_equal(
        len(notifications),
        1,
    )

    notif = (
        notifications[0]
    )

    assert_equal(
        notif.title,
        "Bob",
    )

    if hasattr(
        service,
        "stop",
    ):
        await service.stop()

    if hasattr(
        bus,
        "stop",
    ):
        await bus.stop()


# =========================================================
# PROFILE / CONTACT / TRUST TEST
# =========================================================

@test("identity.profile.contact.trust")
async def test_identity_services():

    alice, bob = (
        build_profiles()
    )

    bob_card = (
        _profile_service
        .public_contact_card(
            bob
        )
    )

    contact = (
        _contact_service
        .add_contact(
            bob_card,
            overwrite=True,
        )
    )

    assert_equal(
        contact["username"],
        bob["username"],
    )

    trust = (
        _trust_service
        .verify_fingerprint(

            peer_id=(
                contact[
                    "peer_id"
                ]
            ),

            fingerprint=(
                contact[
                    "fingerprint"
                ]
            ),
        )
    )

    assert_equal(
        trust[
            "trust_level"
        ],
        TrustLevel
        .VERIFIED
        .value,
    )

    trusted = (
        _trust_service
        .is_trusted(
            contact[
                "peer_id"
            ]
        )
    )

    assert_true(
        trusted,
        "Peer should be trusted",
    )


# =========================================================
# TRANSPORT PACKET TEST
# =========================================================

@test("transport.packet")
async def test_transport_packet():

    packet = (
        TransportPacket(
            packet_type=(
                PacketType
                .MESSAGE
            ),

            sender_peer_id=(
                "alice"
            ),

            receiver_peer_id=(
                "bob"
            ),

            payload={
                "hello":
                    "world"
            },
        )
    )

    assert_equal(
        packet.sender_peer_id,
        "alice",
    )

    assert_equal(
        packet.receiver_peer_id,
        "bob",
    )


# =========================================================
# CLEANUP
# =========================================================

def cleanup():

    for folder in [

        TEST_PROFILES_DIR,
        TEST_CONTACTS_DIR,
        TEST_TRUST_DIR,
    ]:

        shutil.rmtree(
            folder,
            ignore_errors=True,
        )


# =========================================================
# MAIN RUNNER
# =========================================================

async def main():

    cleanup()

    passed = 0
    failed = 0

    print("\n")
    print("=" * 60)
    print(
        " SECURE MESSENGER "
        "SYSTEM VALIDATION "
    )
    print("=" * 60)

    for name, fn in TESTS:

        try:

            print(
                f"\n[ RUN  ] {name}"
            )

            await fn()

            print(
                f"[ PASS ] {name}"
            )

            passed += 1

        except Exception as exc:

            print(
                f"[ FAIL ] {name}"
            )

            print(
                f"Reason: {exc}"
            )

            traceback.print_exc()

            failed += 1

    print("\n")
    print("=" * 60)
    print(" RESULTS ")
    print("=" * 60)

    print(
        f"PASSED: {passed}"
    )

    print(
        f"FAILED: {failed}"
    )

    print(
        f"TOTAL : "
        f"{passed + failed}"
    )

    print("\n")

    if failed == 0:

        print(
            "SYSTEM VALIDATION "
            "SUCCESS"
        )

    else:

        print(
            "SYSTEM VALIDATION "
            "FAILED"
        )

    cleanup()


if __name__ == "__main__":

    asyncio.run(main())