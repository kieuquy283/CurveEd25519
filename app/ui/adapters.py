from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


class AdapterError(RuntimeError):
    pass


def call_first(obj: Any, names: Iterable[str], *args, **kwargs):
    for name in names:
        fn = getattr(obj, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AdapterError(
        f"Không tìm thấy hàm phù hợp. Đã thử: {', '.join(names)} trên {obj!r}"
    )


def normalize_result(value: Any) -> dict:
    if isinstance(value, dict):
        if "ok" in value:
            return value
        return {"ok": True, "data": value, "error": None}

    return {"ok": True, "data": value, "error": None}


def ensure_path_text(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    return path