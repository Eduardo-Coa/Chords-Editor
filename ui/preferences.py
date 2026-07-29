"""Preferencias de la aplicación, persistidas en preferences.json.

El archivo vive en la carpeta de datos del usuario (la misma que la base SQLite,
ver ``database.config.data_dir``) y no junto al ejecutable. Esto es imprescindible
para el ``.exe`` empaquetado con PyInstaller ``--onefile``: ahí la carpeta del
programa es temporal y de solo lectura, así que escribir junto a ``__file__``
perdería las preferencias en cada arranque.
"""

from __future__ import annotations
import json
from pathlib import Path

from database.config import data_dir

_PREF_PATH = data_dir() / "preferences.json"

# Clave del tamaño de fuente del modo escenario (compartido por la vista inline
# y la de pantalla completa, y por todas las canciones que se abran).
STAGE_FONT_SIZE_KEY = "stage_lyric_size"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")


def load_stage_font_size(default: int, path: Path | None = None) -> int:
    """Tamaño de fuente de escenario guardado; ``default`` si no hay o es inválido."""
    value = load_preferences(path).get(STAGE_FONT_SIZE_KEY)
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    return max(10, value)


def save_stage_font_size(size: int, path: Path | None = None) -> None:
    """Persiste el tamaño de fuente de escenario para las próximas canciones."""
    save_preference(STAGE_FONT_SIZE_KEY, int(size), path)
