from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from app.utils import b64e, ensure_dir, read_json, write_bytes, write_json


@dataclass
class ProfilePaths:
    root: Path
    ed25519_private: Path
    ed25519_public: Path
    x25519_private: Path
    x25519_public: Path
    profile_meta: Path


def get_profile_paths(data_dir: Path, profile_name: str) -> ProfilePaths:
    root = data_dir / "profiles" / profile_name
    return ProfilePaths(
        root=root,
        ed25519_private=root / "ed25519_private.key",
        ed25519_public=root / "ed25519_public.key",
        x25519_private=root / "x25519_private.key",
        x25519_public=root / "x25519_public.key",
        profile_meta=root / "profile.json",
    )


def generate_profile(data_dir: Path, profile_name: str) -> dict:
    paths = get_profile_paths(data_dir, profile_name)
    ensure_dir(paths.root)

    ed_priv = ed25519.Ed25519PrivateKey.generate()
    ed_pub = ed_priv.public_key()

    x_priv = x25519.X25519PrivateKey.generate()
    x_pub = x_priv.public_key()

    ed_priv_raw = ed_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    ed_pub_raw = ed_pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    x_priv_raw = x_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    x_pub_raw = x_pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    write_bytes(paths.ed25519_private, ed_priv_raw)
    write_bytes(paths.ed25519_public, ed_pub_raw)
    write_bytes(paths.x25519_private, x_priv_raw)
    write_bytes(paths.x25519_public, x_pub_raw)

    meta = {
        "profile_name": profile_name,
        "ed25519_public_b64": b64e(ed_pub_raw),
        "x25519_public_b64": b64e(x_pub_raw),
    }
    write_json(paths.profile_meta, meta)
    return meta


def load_profile_public_info(data_dir: Path, profile_name: str) -> dict:
    paths = get_profile_paths(data_dir, profile_name)
    return read_json(paths.profile_meta)


def load_ed25519_private_key(data_dir: Path, profile_name: str) -> ed25519.Ed25519PrivateKey:
    paths = get_profile_paths(data_dir, profile_name)
    raw = paths.ed25519_private.read_bytes()
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def load_ed25519_public_key(data_dir: Path, profile_name: str) -> ed25519.Ed25519PublicKey:
    paths = get_profile_paths(data_dir, profile_name)
    raw = paths.ed25519_public.read_bytes()
    return ed25519.Ed25519PublicKey.from_public_bytes(raw)


def load_x25519_private_key(data_dir: Path, profile_name: str) -> x25519.X25519PrivateKey:
    paths = get_profile_paths(data_dir, profile_name)
    raw = paths.x25519_private.read_bytes()
    return x25519.X25519PrivateKey.from_private_bytes(raw)


def load_x25519_public_key(data_dir: Path, profile_name: str) -> x25519.X25519PublicKey:
    paths = get_profile_paths(data_dir, profile_name)
    raw = paths.x25519_public.read_bytes()
    return x25519.X25519PublicKey.from_public_bytes(raw)