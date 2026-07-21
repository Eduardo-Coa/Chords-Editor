"""Resolución de rutas a recursos empaquetados (íconos, etc.).

En desarrollo los recursos viven en la raíz del proyecto. Dentro del ``.exe`` de
PyInstaller los datos se descomprimen en ``sys._MEIPASS``. Este helper devuelve la
ruta correcta en ambos casos.
"""

from __future__ import annotations
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Ruta a un recurso empaquetado, válida en dev y en el .exe de PyInstaller."""
    base = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parent.parent))
    return Path(base) / rel
