"""Preferencias de la aplicación, persistidas en preferences.json (raíz del proyecto)."""

from __future__ import annotations
import json
from pathlib import Path

_PREF_PATH = Path(__file__).parent.parent / "preferences.json"


def load_preferences(path: Path | None = None) -> dict:
    """Lee las preferencias guardadas; devuelve {} si no existe o está corrupto."""
    path = path or _PREF_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_preference(key: str, value, path: Path | None = None) -> None:
    """Guarda (o actualiza) una preferencia conservando las demás."""
    path = path or _PREF_PATH
    prefs = load_preferences(path)
    prefs[key] = value
    path.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")
