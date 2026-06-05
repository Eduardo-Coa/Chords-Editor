"""Convierte texto de letra pegado en un modelo Song con sílabas."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable
from utils.syllabifier import syllabify

PUNCTUATION = set(",.;:!¡?¿…\"'()-—«»")

# Ranuras vacías al final de cada línea para acordes de paso/enlace
# (notas entre líneas que no van sobre ninguna sílaba, ej: (D7) antes de G).
TRAILING_NOTE_SLOTS = 4


def _split_word(word: str) -> list[str]:
    """
    Separa un 'word' en partes: puntuación inicial, sílabas del núcleo y
    puntuación final, cada una como string independiente.
    """
    leading = ""
    while word and word[0] in PUNCTUATION:
        leading += word[0]
        word = word[1:]

    trailing = ""
    while word and word[-1] in PUNCTUATION:
        trailing = word[-1] + trailing
        word = word[:-1]

    parts: list[str] = []
    if leading:
        parts.append(leading)
    if word:
        parts.extend(syllabify(word))
    if trailing:
        parts.append(trailing)
    return parts


def _parse_line(text: str, position: int) -> Line:
    """Convierte una línea de texto en un Line con sus sílabas."""
    line = Line(id=None, position=position)

    words = [w for w in text.split(" ") if w != ""]
    pos = 0
    for wi, word in enumerate(words):
        parts = _split_word(word)
        if not parts:
            continue
        # Separar palabras con un espacio al final de la última parte
        if wi < len(words) - 1:
            parts[-1] = parts[-1] + " "
        for part in parts:
            line.syllables.append(Syllable(id=None, position=pos, text=part))
            pos += 1

    # Ranuras de acordes de paso al final de la línea (solo si hay contenido)
    if line.syllables:
        for _ in range(TRAILING_NOTE_SLOTS):
            line.syllables.append(Syllable(id=None, position=pos, text=""))
            pos += 1
    return line


def parse_lyrics(text: str, title: str = "Sin título") -> Song:
    """
    Construye una Song a partir del texto pegado.

    Todas las líneas van en una única sección 'verse'. Las líneas vacías se
    conservan como separadores visuales (Line sin sílabas).
    """
    song = Song(id=None, title=title)
    section = Section(id=None, position=0, type="verse", label=None)

    for i, raw_line in enumerate(text.split("\n")):
        section.lines.append(_parse_line(raw_line.strip(), i))

    song.sections.append(section)
    return song
