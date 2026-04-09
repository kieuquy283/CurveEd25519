from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from app.services.crypto_service import CryptoService
from app.services.key_service import KeyService
from app.storage.messages import MessagesStorage


app = typer.Typer(
    help="Curve25519 demo app: X25519 + Ed25519 + HKDF + ChaCha20-Poly1305",
    no_args_is_help=True,
)


def get_data_dir(custom_data_dir: Optional[str]) -> Path:
    path = Path(custom_data_dir) if custom_data_dir else Path("data")
    path.mkdir(parents=True, exist_ok=True)
    (path / "profiles").mkdir(parents=True, exist_ok=True)
    (path / "contacts").mkdir(parents=True, exist_ok=True)
    (path / "messages").mkdir(parents=True, exist_ok=True)
    return path


@app.command()
def keygen(
    profile: str = typer.Option(..., help="Profile name, e.g. alice"),
    overwrite: bool = typer.Option(False, help="Overwrite profile if exists"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        profile_data = ks.create_profile(profile, overwrite=overwrite)
        summary = ks.get_profile_summary(profile)

        typer.echo(f"[OK] Generated profile: {profile_data['name']}")
        typer.echo(f"Ed25519 public: {summary['ed25519_public_key']}")
        typer.echo(f"Ed25519 fingerprint: {summary['ed25519_fingerprint']}")
        typer.echo(f"X25519 public: {summary['x25519_public_key']}")
        typer.echo(f"X25519 fingerprint: {summary['x25519_fingerprint']}")

    except Exception as exc:
        typer.echo(f"[ERROR] Key generation failed: {exc}")
        raise typer.Exit(code=1)


@app.command("export-contact")
def export_contact(
    profile: str = typer.Option(..., help="Local profile name"),
    out: Optional[str] = typer.Option(None, help="Optional export file path"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        contact = ks.export_contact_from_profile(profile, save_to_contacts=True)

        if out:
            out_path = ks.export_contact_to_file(profile, out)
            typer.echo(f"[OK] Contact exported to: {out_path}")
        else:
            typer.echo(f"[OK] Contact stored in local contacts for: {contact['name']}")

        typer.echo(json.dumps(contact, ensure_ascii=False, indent=2))

    except Exception as exc:
        typer.echo(f"[ERROR] Export contact failed: {exc}")
        raise typer.Exit(code=1)


@app.command("import-contact")
def import_contact(
    contact_file: str = typer.Option(..., help="Path to contact JSON"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        contact = ks.import_contact_from_file(contact_file, save=True)

        typer.echo(f"[OK] Contact imported: {contact['name']}")
        typer.echo(json.dumps(contact, ensure_ascii=False, indent=2))

    except Exception as exc:
        typer.echo(f"[ERROR] Import contact failed: {exc}")
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
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)
        ms = MessagesStorage(dd)

        if message is None and in_file is None:
            raise typer.BadParameter("Provide either --message or --in")
        if message is not None and in_file is not None:
            raise typer.BadParameter("Use only one of --message or --in")

        sender_profile = ks.load_profile(from_profile)
        receiver_contact = ks.load_contact(to_contact)

        plaintext = message if message is not None else Path(in_file).read_bytes()

        result = CryptoService.encrypt_message(
            sender_profile=sender_profile,
            receiver_contact=receiver_contact,
            plaintext=plaintext,
            include_debug=True,
        )

        envelope = result["envelope"]
        output_path = Path(out) if out else dd / "messages" / f"{from_profile}_to_{to_contact}.enc"
        ms.save_to_path(output_path, envelope)

        typer.echo("[OK] Encryption and signing completed")
        typer.echo(f"Saved to: {output_path}")

    except typer.BadParameter as exc:
        typer.echo(f"[ERROR] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"[ERROR] Encrypt failed: {exc}")
        raise typer.Exit(code=1)


@app.command()
def decrypt(
    profile: str = typer.Option(..., help="Recipient local profile"),
    in_file: str = typer.Option(..., "--in", help="Encrypted JSON file"),
    out: Optional[str] = typer.Option(None, help="Output plaintext file"),
    trusted_sender: Optional[str] = typer.Option(None, help="Trusted sender contact name"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)
        ms = MessagesStorage(dd)

        receiver_profile = ks.load_profile(profile)
        sender_contact = ks.load_contact(trusted_sender) if trusted_sender else None
        envelope = ms.load_from_path(in_file)

        result = CryptoService.decrypt_message(
            receiver_profile=receiver_profile,
            envelope=envelope,
            sender_contact=sender_contact,
            verify_before_decrypt=True,
            include_debug=True,
        )

        typer.echo("[OK] Signature valid and decryption successful")

        if "plaintext" in result:
            plaintext_value = result["plaintext"]
            if out:
                Path(out).write_text(plaintext_value, encoding="utf-8")
                typer.echo(f"Plaintext written to: {out}")
            else:
                typer.echo(plaintext_value)
        else:
            plaintext_b64 = result["plaintext_bytes_b64"]
            if out:
                Path(out).write_text(plaintext_b64, encoding="utf-8")
                typer.echo(f"Binary plaintext (base64) written to: {out}")
            else:
                typer.echo(plaintext_b64)

    except Exception as exc:
        typer.echo(f"[ERROR] Decrypt failed: {exc}")
        raise typer.Exit(code=1)


@app.command()
def sign(
    profile: str = typer.Option(..., help="Signer local profile"),
    message: Optional[str] = typer.Option(None, help="Message text"),
    in_file: Optional[str] = typer.Option(None, "--in", help="Input file"),
    out: Optional[str] = typer.Option(None, help="Output signature JSON"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        if message is None and in_file is None:
            raise typer.BadParameter("Provide either --message or --in")
        if message is not None and in_file is not None:
            raise typer.BadParameter("Use only one of --message or --in")

        signer_profile = ks.load_profile(profile)
        payload = message if message is not None else Path(in_file).read_bytes()

        result = CryptoService.sign_message(signer_profile, payload)

        if out:
            Path(out).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            typer.echo(f"[OK] Signature written to: {out}")
        else:
            typer.echo(json.dumps(result, ensure_ascii=False, indent=2))

    except typer.BadParameter as exc:
        typer.echo(f"[ERROR] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"[ERROR] Sign failed: {exc}")
        raise typer.Exit(code=1)


@app.command()
def verify(
    contact: str = typer.Option(..., help="Trusted contact name"),
    message: Optional[str] = typer.Option(None, help="Message text"),
    in_file: Optional[str] = typer.Option(None, "--in", help="Input file"),
    sig: str = typer.Option(..., help="Signature JSON file"),
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        if message is None and in_file is None:
            raise typer.BadParameter("Provide either --message or --in")
        if message is not None and in_file is not None:
            raise typer.BadParameter("Use only one of --message or --in")

        trusted_contact = ks.load_contact(contact)
        payload = message if message is not None else Path(in_file).read_bytes()

        sig_payload = json.loads(Path(sig).read_text(encoding="utf-8"))
        signature_b64 = sig_payload["signature"]

        ok = CryptoService.verify_message(
            signer_contact=trusted_contact,
            message=payload,
            signature_b64=signature_b64,
        )

        if ok:
            typer.echo("[OK] Signature is valid")
        else:
            typer.echo("[ERROR] Signature is invalid")
            raise typer.Exit(code=1)

    except typer.BadParameter as exc:
        typer.echo(f"[ERROR] {exc}")
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"[ERROR] Verify failed: {exc}")
        raise typer.Exit(code=1)


@app.command("list-profiles")
def list_profiles(
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        profiles = ks.list_profiles()
        if not profiles:
            typer.echo("No profiles found.")
            return

        for name in profiles:
            typer.echo(name)

    except Exception as exc:
        typer.echo(f"[ERROR] List profiles failed: {exc}")
        raise typer.Exit(code=1)


@app.command("list-contacts")
def list_contacts(
    data_dir: Optional[str] = typer.Option(None, help="Data directory"),
):
    try:
        dd = get_data_dir(data_dir)
        ks = KeyService(dd)

        contacts = ks.list_contacts()
        if not contacts:
            typer.echo("No contacts found.")
            return

        for name in contacts:
            typer.echo(name)

    except Exception as exc:
        typer.echo(f"[ERROR] List contacts failed: {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()