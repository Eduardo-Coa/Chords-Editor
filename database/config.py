"""Configuración de la base de datos SQLite de Ilahi.

SQLite no necesita servidor ni credenciales: la base es un único archivo. Se
guarda en la carpeta de datos del usuario (no junto al ejecutable, que puede ser
de solo lectura), de modo que cada usuario tiene su propia biblioteca portable.

La app se llamó **HymnChords** hasta la versión anterior. ``migrate_legacy_data_dir``
mueve la carpeta de datos antigua a la nueva la primera vez que se arranca, para
que nadie pierda su biblioteca al actualizar.
"""

from __future__ import annotations
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "Ilahi"
DB_FILENAME = "ilahi.db"

# Nombres heredados de HymnChords (solo se usan para migrar una única vez).
LEGACY_APP_DIR_NAME = "HymnChords"
LEGACY_DB_FILENAME = "hymnchords.db"
_LEGACY_FILE_RENAMES = {
    LEGACY_DB_FILENAME: DB_FILENAME,
    "hymnchords.log": "ilahi.log",
}
_LEGACY_BACKUP_PREFIX = "hymnchords-"
BACKUP_PREFIX = "ilahi-"

_log = logging.getLogger("ilahi.config")


@dataclass
class DBConfig:
    """Ubicación del archivo SQLite de la aplicación."""

    path: Path


def _app_data_root() -> Path:
    """Carpeta contenedora de los datos de apps del usuario."""
    appdata = os.environ.get("APPDATA")  # Windows
    return Path(appdata) if appdata else Path.home()


def _dir_for(app_name: str) -> Path:
    """Carpeta de datos para un nombre de app dado (oculta fuera de Windows)."""
    root = _app_data_root()
    if os.environ.get("APPDATA"):
        return root / app_name
    # macOS / Linux: carpeta oculta en el home
    return root / f".{app_name.lower()}"


def data_dir() -> Path:
    """Carpeta de datos del usuario donde viven la base, preferencias y logs."""
    return _dir_for(APP_DIR_NAME)


def legacy_data_dir() -> Path:
    """Carpeta de datos de la versión anterior (HymnChords)."""
    return _dir_for(LEGACY_APP_DIR_NAME)


def migrate_legacy_data_dir(
    new_dir: Path | None = None, old_dir: Path | None = None
) -> bool:
    """Mueve la carpeta de datos de HymnChords a la de Ilahi. Devuelve si migró.

    Solo actúa si la carpeta vieja existe y la nueva **no**: nunca pisa datos ya
    creados con el nombre nuevo. Tras mover, renombra la base, el log y los
    respaldos al prefijo nuevo. Cualquier fallo de E/S se registra y se ignora
    (la app arranca igual, con la biblioteca vieja intacta donde estaba).

    Debe llamarse antes de abrir la base o configurar el logging: en Windows un
    archivo abierto bloquea el movimiento de su carpeta.
    """
    new = new_dir or data_dir()
    old = old_dir or legacy_data_dir()
    if new.exists() or not old.is_dir():
        return False

    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))
        _rename_legacy_files(new)
    except OSError:
        _log.exception("no se pudo migrar la carpeta de datos %s -> %s", old, new)
        return False
    _log.info("carpeta de datos migrada: %s -> %s", old, new)
    return True


def _rename_legacy_files(directory: Path) -> None:
    """Renombra base, log y respaldos de ``hymnchords*`` a ``ilahi*``."""
    for old_name, new_name in _LEGACY_FILE_RENAMES.items():
        source = directory / old_name
        if source.exists() and not (directory / new_name).exists():
            source.rename(directory / new_name)

    backups = directory / "backups"
    if not backups.is_dir():
        return
    for backup in backups.glob(f"{_LEGACY_BACKUP_PREFIX}*.db"):
        target = backups / (BACKUP_PREFIX + backup.name[len(_LEGACY_BACKUP_PREFIX):])
        if not target.exists():
            backup.rename(target)


def load_config(path: Path | None = None) -> DBConfig:
    """
    Devuelve la configuración con la ruta al archivo SQLite.

    Si no se indica ``path``, se usa ``<carpeta de datos>/ilahi.db``. Los tests
    pasan una ruta temporal propia para no tocar nunca la base real.
    """
    if path is None:
        path = data_dir() / DB_FILENAME
    return DBConfig(path=path)
