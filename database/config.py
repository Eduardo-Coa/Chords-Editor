"""Configuración de la base de datos SQLite de HymnChords.

SQLite no necesita servidor ni credenciales: la base es un único archivo. Se
guarda en la carpeta de datos del usuario (no junto al ejecutable, que puede ser
de solo lectura), de modo que cada usuario tiene su propia biblioteca portable.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "HymnChords"
DB_FILENAME = "hymnchords.db"


@dataclass
class DBConfig:
    """Ubicación del archivo SQLite de la aplicación."""

    path: Path


def data_dir() -> Path:
    """Carpeta de datos del usuario donde vive la base (y futuras preferencias)."""
    appdata = os.environ.get("APPDATA")  # Windows
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    # macOS / Linux: carpeta oculta en el home
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def load_config(path: Path | None = None) -> DBConfig:
    """
    Devuelve la configuración con la ruta al archivo SQLite.

    Si no se indica ``path``, se usa ``<carpeta de datos>/hymnchords.db``. Los
    tests pasan una ruta temporal propia para no tocar nunca la base real.
    """
    if path is None:
        path = data_dir() / DB_FILENAME
    return DBConfig(path=path)
