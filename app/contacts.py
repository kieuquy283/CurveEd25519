from __future__ import annotations

from pathlib import Path

from app.keygen import get_profile_paths, load_profile_public_info
from app.utils import b64d, b64e, ensure_dir, read_bytes, read_json, sha256_short_id, write_json


def build_contact_card(data_dir: Path, profile_name: str) -> dict:
    paths = get_profile_paths(data_dir, profile_name)

    ed_pub_raw = read_bytes(paths.ed25519_public)
    x_pub_raw = read_bytes(paths.x25519_public)

    card = {
        "profile_name": profile_name,
        "ed25519_public_b64": b64e(ed_pub_raw),
        "x25519_public_b64": b64e(x_pub_raw),
        "ed25519_fingerprint_b64": b64e(sha256_short_id(ed_pub_raw)),
        "x25519_fingerprint_b64": b64e(sha256_short_id(x_pub_raw)),
    }
    return card


def export_contact_card(data_dir: Path, profile_name: str, out_path: Path | None = None) -> Path:
    card = build_contact_card(data_dir, profile_name)
    if out_path is None:
        out_path = data_dir / "contacts" / f"{profile_name}.contact.json"
    write_json(out_path, card)
    return out_path


def import_contact_card(data_dir: Path, contact_path: Path) -> Path:
    card = read_json(contact_path)
    profile_name = card["profile_name"]
    dest = data_dir / "contacts" / f"{profile_name}.contact.json"
    write_json(dest, card)
    return dest


def load_contact(data_dir: Path, contact_name: str) -> dict:
    path = data_dir / "contacts" / f"{contact_name}.contact.json"
    return read_json(path)


def load_contact_by_path(contact_path: Path) -> dict:
    return read_json(contact_path)


def get_contact_x25519_public_bytes(contact: dict) -> bytes:
    return b64d(contact["x25519_public_b64"])


def get_contact_ed25519_public_bytes(contact: dict) -> bytes:
    return b64d(contact["ed25519_public_b64"])


def contact_exists(data_dir: Path, contact_name: str) -> bool:
    return (data_dir / "contacts" / f"{contact_name}.contact.json").exists()