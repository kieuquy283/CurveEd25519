from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from app.api.conversation_api import router as conversation_router

from app.profiles.profile_service import (
    ProfileService,
)

from app.profiles.contact_service import (
    ContactService,
)

from app.profiles.trust_service import (
    TrustService,
)

from app.services.protocol_service import (
    ProtocolService,
)

from app.services.notification_service import (
    NotificationService,
)

from app.services.typing_service import (
    TypingService,
)

from app.services.event_bus import (
    EventBus,
)

from app.transport.transport_server import (
    TransportServer,
)
from app.transport.transport_server import (
    TransportServerConfig,
)

from app.transport.connection_manager import (
    ConnectionManager,
)

from app.transport.peer_registry import (
    PeerRegistry,
)

from app.storage.message_store import (
    MessageStore,
)

from app.storage.queue_store import (
    QueueStore,
)

from app.models.delivery_record import (
    DeliveryState,
)

from tests.run_system_validation import (
    main as validation_main,
)


# =========================================================
# APP
# =========================================================

app = typer.Typer(
    help="Secure Messenger System",
    no_args_is_help=True,
)


# =========================================================
# PATHS
# =========================================================

def ensure_data_dirs(
    base_dir: Path,
) -> None:

    dirs = [
        "profiles",
        "contacts",
        "messages",
        "queues",
        "trust",
        "attachments",
        "sessions",
    ]

    base_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for d in dirs:

        (
            base_dir / d
        ).mkdir(
            parents=True,
            exist_ok=True,
        )


def get_data_dir(
    custom_dir: Optional[str],
) -> Path:

    path = (
        Path(custom_dir)
        if custom_dir
        else Path("data")
    )

    ensure_data_dirs(path)

    return path


# =========================================================
# PROFILE COMMANDS
# =========================================================

@app.command("create-profile")
def create_profile(
    name: str,
    data_dir: Optional[str] = None,
):

    dd = get_data_dir(data_dir)

    service = ProfileService(
        profiles_dir=(
            dd / "profiles"
        )
    )

    profile = (
        service.create_profile(
            username=name,
            save=True,
        )
    )

    typer.echo(
        f"[OK] Created profile: {profile['username']}"
    )


@app.command("list-profiles")
def list_profiles(
    data_dir: Optional[str] = None,
):

    dd = get_data_dir(data_dir)

    service = ProfileService(
        profiles_dir=(
            dd / "profiles"
        )
    )

    profiles = (
        service.list_profiles()
    )

    for p in profiles:

        typer.echo(p)


# =========================================================
# CONTACT COMMANDS
# =========================================================

@app.command("add-contact")
def add_contact(
    profile_name: str,
    contact_file: str,
    data_dir: Optional[str] = None,
):

    dd = get_data_dir(data_dir)

    service = ContactService(
        contacts_dir=(
            dd / "contacts"
        )
    )

    contact = (
        service.import_contact(
            contact_file
        )
    )

    typer.echo(
        f"[OK] Imported contact: {contact['name']}"
    )


@app.command("list-contacts")
def list_contacts(
    data_dir: Optional[str] = None,
):

    dd = get_data_dir(data_dir)

    service = ContactService(
        contacts_dir=(
            dd / "contacts"
        )
    )

    contacts = (
        service.list_contacts()
    )

    for c in contacts:

        typer.echo(c)


# =========================================================
# TRUST COMMANDS
# =========================================================

@app.command("trust")
def trust_contact(
    contact_name: str,
    verified: bool = True,
    data_dir: Optional[str] = None,
):

    dd = get_data_dir(data_dir)

    trust = TrustService(
        trust_dir=(
            dd / "trust"
        )
    )

    trust.set_verified(
        contact_name=contact_name,
        verified=verified,
    )

    typer.echo(
        f"[OK] Trust updated for: {contact_name}"
    )


# =========================================================
# SERVER
# =========================================================

async def run_server_async(
    host: str,
    port: int,
):

    event_bus = EventBus()

    peer_registry = (
        PeerRegistry()
    )

    connection_manager = (
        ConnectionManager(
            peer_registry=
                peer_registry,
        )
    )

    config = TransportServerConfig(
        host=host,
        port=port,
    )

    transport_server = TransportServer(
        config=config,
    )

    # Register transport server with connection manager so
    # connection lifecycle and packet routing are wired.
    connection_manager.register_server(
        server_id="server",
        server=transport_server,
    )

    notification_service = (
        NotificationService(
            event_bus=event_bus,
        )
    )

    await event_bus.start()

    await notification_service.start()

    typer.echo(
        f"[OK] Secure transport server listening on ws://{host}:{port}"
    )

    # Start services and run server until interrupted (KeyboardInterrupt).
    try:
        await transport_server.start()

    except OSError as err:
        # Address already in use: try binding to an ephemeral port instead.
        if getattr(err, "errno", None) in (98, 10048):
            typer.echo(
                "Port in use, attempting to bind to an ephemeral port...",
            )
            # update config to 0 (OS-assigned port) and restart
            transport_server.config.port = 0
            await transport_server.start()
            # determine assigned port if available
            try:
                srv = transport_server.server
                if srv and getattr(srv, "sockets", None):
                    bound_port = srv.sockets[0].getsockname()[1]
                    typer.echo(f"[OK] Secure transport server listening on ws://{host}:{bound_port}")
            except Exception:
                pass
        else:
            raise

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        await transport_server.stop()


@app.command("server")
def run_server(
    host: str = "0.0.0.0",
    port: int = 8765,
):

    asyncio.run(
        run_server_async(
            host=host,
            port=port,
        )
    )


# =========================================================
# VALIDATION
# =========================================================

@app.command("validate")
def validate_system():

    asyncio.run(
        validation_main()
    )


# =========================================================
# UI
# =========================================================

@app.command("ui")
def run_ui():

    typer.echo(
        "[INFO] Start frontend separately:"
    )

    typer.echo(
        "cd ui && npm run dev"
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    app()
    app.include_router(conversation_router)