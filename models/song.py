"""Modelos de datos en memoria para HymnChords."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Chord:
    """Acorde asignado a una sílaba."""

    id: int | None
    value: str


@dataclass
class Syllable:
    """Sílaba de una línea, con su acorde opcional."""

    id: int | None
    position: int
    text: str
    chord: Chord | None = None


@dataclass
class Line:
    """Línea de texto dentro de una sección."""

    id: int | None
    position: int
    syllables: list[Syllable] = field(default_factory=list)


@dataclass
class Section:
    """Sección de una canción (estrofa, coro, puente, etc.)."""

    id: int | None
    position: int
    type: str          # 'verse' | 'chorus' | 'bridge' | 'intro' | 'outro'
    label: str | None
    # Modulación propia del bloque (semitonos), no destructiva: se suma al offset
    # global al mostrar. 0 = sin modulación. Solo aplica de la 2ª sección en adelante.
    transpose: int = 0
    lines: list[Line] = field(default_factory=list)


@dataclass
class Song:
    """Canción completa con todas sus secciones."""

    id: int | None
    title: str
    author: str | None = None
    # `key` = círculo armónico con el que se toca (guía las sugerencias de acordes).
    # `original_key` = tono original de la canción (informativo). Pueden diferir:
    # p. ej. original La♭ pero se toca en Sol con capo en el 1er traste.
    key: str | None = None
    original_key: str | None = None
    rhythm: str | None = None
    capo: int = 0
    notes: str | None = None
    sections: list[Section] = field(default_factory=list)

    def all_syllables(self) -> list[Syllable]:
        """Devuelve todas las sílabas de la canción en orden."""
        result = []
        for section in self.sections:
            for line in section.lines:
                result.extend(line.syllables)
        return result
