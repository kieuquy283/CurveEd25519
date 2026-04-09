from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from app.contacts import export_contact_card, import_contact_card
from app.envelope import (
    detached_sign_file,
    detached_verify_file,
    encrypt_and_sign_message,
    verify_and_decrypt_message,
)
from app.keygen import generate_profile
from app.utils import ensure_dir


app = typer.Typer(help="Curve25519 demo app: X25519 + Ed25519 + HKDF + ChaCha20-Poly1305")


def get_data_dir(custom_data_dir: Optional[str]) -> Path:
    if custom_data_dir:
        path = Path(custom_data_dir)
    else:
        path = Path("data")
    ensure_dir(path)
    ensure_dir(path / "profiles")
    ensure_dir(path / "contacts")
    ensure_dir(path / "messages")
    return path


@app.command()
def keygen(
    profile: str = typer.Option(..., help="Profile name, e.g. alice"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Generate Ed25519 and X25519 keypairs for a profile.
    """
    dd = get_data_dir(data_dir)
    meta = generate_profile(dd, profile)
    typer.echo(f"[OK] Generated profile: {profile}")
    typer.echo(f"    Ed25519 public: {meta['ed25519_public_b64']}")
    typer.echo(f"    X25519 public : {meta['x25519_public_b64']}")


@app.command("export-contact")
def export_contact(
    profile: str = typer.Option(..., help="Local profile name"),
    out: Optional[str] = typer.Option(None, help="Output contact file"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Export a contact card JSON from a local profile.
    """
    dd = get_data_dir(data_dir)
    out_path = Path(out) if out else None
    final_path = export_contact_card(dd, profile, out_path)
    typer.echo(f"[OK] Contact exported to: {final_path}")


@app.command("import-contact")
def import_contact(
    contact_file: str = typer.Option(..., help="Path to *.contact.json"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Import a contact card JSON into local contacts store.
    """
    dd = get_data_dir(data_dir)
    final_path = import_contact_card(dd, Path(contact_file))
    typer.echo(f"[OK] Contact imported to: {final_path}")


@app.command()
def encrypt(
    from_profile: str = typer.Option(..., "--from", help="Sender local profile"),
    to_contact: str = typer.Option(..., "--to", help="Recipient contact name"),
    message: Optional[str] = typer.Option(None, help="Plain text message"),
    in_file: Optional[str] = typer.Option(None, "--in", help="Input plaintext file"),
    out: Optional[str] = typer.Option(None, help="Output encrypted JSON file"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Encrypt + sign a message to a recipient.
    """
    dd = get_data_dir(data_dir)

    if message is None and in_file is None:
        raise typer.BadParameter("Provide either --message or --in")
    if message is not None and in_file is not None:
        raise typer.BadParameter("Use only one of --message or --in")

    if message is not None:
        plaintext = message.encode("utf-8")
    else:
        plaintext = Path(in_file).read_bytes()

    out_path = Path(out) if out else dd / "messages" / f"{from_profile}_to_{to_contact}.enc.json"

    encrypt_and_sign_message(
        data_dir=dd,
        sender_profile=from_profile,
        recipient_contact_name=to_contact,
        plaintext=plaintext,
        out_path=out_path,
    )
    typer.echo(f"[OK] Encrypted message saved to: {out_path}")


@app.command()
def decrypt(
    profile: str = typer.Option(..., help="Recipient local profile"),
    in_file: str = typer.Option(..., "--in", help="Encrypted JSON file"),
    out: Optional[str] = typer.Option(None, help="Output plaintext file"),
    trusted_sender: Optional[str] = typer.Option(
        None,
        help="Trusted sender contact name to check sender public key",
    ),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Verify signature + decrypt a received message.
    """
    dd = get_data_dir(data_dir)

    plaintext, meta = verify_and_decrypt_message(
        data_dir=dd,
        recipient_profile=profile,
        envelope_path=Path(in_file),
        trusted_sender_contact_name=trusted_sender,
    )

    typer.echo("[OK] Signature valid and decryption successful")
    typer.echo(f"    Sender   : {meta['sender_name']}")
    typer.echo(f"    Recipient: {meta['recipient_name']}")
    typer.echo(f"    Suite    : {meta['suite']}")

    if out:
        Path(out).write_bytes(plaintext)
        typer.echo(f"[OK] Plaintext written to: {out}")
    else:
        try:
            typer.echo("----- PLAINTEXT -----")
            typer.echo(plaintext.decode("utf-8"))
        except UnicodeDecodeError:
            typer.echo("----- PLAINTEXT (binary) -----")
            typer.echo(plaintext.hex())


@app.command()
def sign(
    profile: str = typer.Option(..., help="Signer local profile"),
    in_file: str = typer.Option(..., "--in", help="Input file"),
    out: Optional[str] = typer.Option(None, help="Output signature JSON"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Detached sign a file using Ed25519.
    """
    dd = get_data_dir(data_dir)
    in_path = Path(in_file)
    out_path = Path(out) if out else in_path.with_suffix(in_path.suffix + ".sig.json")

    detached_sign_file(dd, profile, in_path, out_path)
    typer.echo(f"[OK] Signature written to: {out_path}")


@app.command()
def verify(
    contact: str = typer.Option(..., help="Trusted contact name"),
    in_file: str = typer.Option(..., "--in", help="Input file"),
    sig: str = typer.Option(..., help="Signature JSON file"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Detached verify a file using imported contact public key.
    """
    dd = get_data_dir(data_dir)
    ok = detached_verify_file(dd, contact, Path(in_file), Path(sig))
    if ok:
        typer.echo("[OK] Signature is valid")
    else:
        typer.echo("[FAIL] Signature is invalid")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()