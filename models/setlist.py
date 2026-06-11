"""Modelos de datos en memoria para las listas de canciones (setlists)."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SetlistItem:
    """Canción dentro de una lista, con su tono fijo para la presentación."""

    id: int | None
    song_id: int
    position: int
    transpose: int = 0
    # Datos para mostrar; se llenan al cargar (JOIN con songs), no se persisten aquí
    title: str = ""
    key: str | None = None


@dataclass
class Setlist:
    """Lista ordenada de canciones para tocar en una presentación."""

    id: int | None
    name: str
    items: list[SetlistItem] = field(default_factory=list)
