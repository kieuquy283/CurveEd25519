from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from app.logger import banner, error, info, kv, step, success, warning
from app.contacts import export_contact_card, import_contact_card
from app.envelope import (
    detached_sign_file,
    detached_verify_file,
    encrypt_and_sign_message,
    verify_and_decrypt_message,
)
from app.keygen import generate_profile
from app.utils import ensure_dir


app = typer.Typer(
    help="Curve25519 demo app: X25519 + Ed25519 + HKDF + ChaCha20-Poly1305",
    no_args_is_help=True,
)


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
    banner("Curve25519 Crypto App", "Key Generation")

    try:
        dd = get_data_dir(data_dir)

        step("Preparing data directory")
        kv("Data directory", str(dd))

        step("Generating key pairs")
        meta = generate_profile(dd, profile)

        success(f"Generated profile: {profile}")
        kv("Ed25519 public", meta["ed25519_public_b64"])
        kv("X25519 public", meta["x25519_public_b64"])

    except Exception as exc:
        error(f"Key generation failed: {exc}")
        raise typer.Exit(code=1)


@app.command("export-contact")
def export_contact(
    profile: str = typer.Option(..., help="Local profile name"),
    out: Optional[str] = typer.Option(None, help="Output contact file"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Export a contact card JSON from a local profile.
    """
    banner("Curve25519 Crypto App", "Export Contact")

    try:
        dd = get_data_dir(data_dir)
        out_path = Path(out) if out else None

        step("Exporting contact card")
        kv("Profile", profile)
        if out_path:
            kv("Requested output", str(out_path))

        final_path = export_contact_card(dd, profile, out_path)

        success("Contact exported successfully")
        kv("Saved to", str(final_path))

    except Exception as exc:
        error(f"Export contact failed: {exc}")
        raise typer.Exit(code=1)


@app.command("import-contact")
def import_contact(
    contact_file: str = typer.Option(..., help="Path to *.contact.json"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    """
    Import a contact card JSON into local contacts store.
    """
    banner("Curve25519 Crypto App", "Import Contact")

    try:
        dd = get_data_dir(data_dir)
        contact_path = Path(contact_file)

        step("Importing contact")
        kv("Input file", str(contact_path))

        final_path = import_contact_card(dd, contact_path)

        success("Contact imported successfully")
        kv("Stored at", str(final_path))

    except Exception as exc:
        error(f"Import contact failed: {exc}")
        raise typer.Exit(code=1)


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
    banner("Curve25519 Crypto App", "Encrypt + Sign")

    try:
        dd = get_data_dir(data_dir)

        if message is None and in_file is None:
            raise typer.BadParameter("Provide either --message or --in")

        if message is not None and in_file is not None:
            raise typer.BadParameter("Use only one of --message or --in")

        step("Preparing plaintext")
        kv("Sender profile", from_profile)
        kv("Recipient contact", to_contact)

        if message is not None:
            plaintext = message.encode("utf-8")
            info("Using plaintext from --message")
            kv("Plaintext length", f"{len(plaintext)} bytes")
        else:
            file_path = Path(in_file)
            plaintext = file_path.read_bytes()
            info("Using plaintext from input file")
            kv("Input file", str(file_path))
            kv("Plaintext length", f"{len(plaintext)} bytes")

        out_path = Path(out) if out else dd / "messages" / f"{from_profile}_to_{to_contact}.enc.json"

        step("Running hybrid encryption pipeline")
        encrypt_and_sign_message(
            data_dir=dd,
            sender_profile=from_profile,
            recipient_contact_name=to_contact,
            plaintext=plaintext,
            out_path=out_path,
        )

        success("Encryption and signing completed")
        kv("Encrypted file", str(out_path))

    except typer.BadParameter as exc:
        error(str(exc))
        raise typer.Exit(code=1)
    except Exception as exc:
        error(f"Encrypt failed: {exc}")
        raise typer.Exit(code=1)


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
    banner("Curve25519 Crypto App", "Verify + Decrypt")

    try:
        dd = get_data_dir(data_dir)

        step("Loading encrypted container")
        kv("Recipient profile", profile)
        kv("Encrypted file", in_file)
        if trusted_sender:
            kv("Trusted sender", trusted_sender)
        else:
            warning("No trusted sender provided; envelope public key will be used directly")

        step("Running verification and decryption pipeline")
        plaintext, meta = verify_and_decrypt_message(
            data_dir=dd,
            recipient_profile=profile,
            envelope_path=Path(in_file),
            trusted_sender_contact_name=trusted_sender,
        )

        success("Signature valid and decryption successful")
        kv("Sender", meta["sender_name"])
        kv("Recipient", meta["recipient_name"])
        kv("Suite", meta["suite"])
        kv("Message ID", meta["msg_id_b64"])

        if out:
            output_path = Path(out)
            output_path.write_bytes(plaintext)
            success("Plaintext written to file")
            kv("Output file", str(output_path))
        else:
            step("Recovered plaintext")
            try:
                typer.echo(plaintext.decode("utf-8"))
            except UnicodeDecodeError:
                warning("Plaintext is not valid UTF-8; showing hex output")
                typer.echo(plaintext.hex())

    except Exception as exc:
        error(f"Decrypt failed: {exc}")
        raise typer.Exit(code=1)


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
    banner("Curve25519 Crypto App", "Detached Sign")

    try:
        dd = get_data_dir(data_dir)
        in_path = Path(in_file)
        out_path = Path(out) if out else in_path.with_suffix(in_path.suffix + ".sig.json")

        step("Signing file")
        kv("Profile", profile)
        kv("Input file", str(in_path))
        kv("Output signature", str(out_path))

        detached_sign_file(dd, profile, in_path, out_path)

        success("Signature created successfully")
        kv("Signature file", str(out_path))

    except Exception as exc:
        error(f"Sign failed: {exc}")
        raise typer.Exit(code=1)


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
    banner("Curve25519 Crypto App", "Detached Verify")

    try:
        dd = get_data_dir(data_dir)

        step("Verifying detached signature")
        kv("Trusted contact", contact)
        kv("Input file", in_file)
        kv("Signature file", sig)

        ok = detached_verify_file(dd, contact, Path(in_file), Path(sig))

        if ok:
            success("Signature is valid")
        else:
            error("Signature is invalid")
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as exc:
        error(f"Verify failed: {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()