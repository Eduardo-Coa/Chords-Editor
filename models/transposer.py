"""Lógica de transposición de acordes para HymnChords."""

from __future__ import annotations
import copy
import re
from models.song import Song

SHARP_SCALE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_MAP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

# Patrón para extraer la nota raíz de un acorde (ej: "Am7" → raíz "A", sufijo "m7")
_ROOT_PATTERN = re.compile(r"^([A-G][b#]?)(.*)")


def transpose_chord(chord: str, semitones: int) -> str:
    """
    Transpone un acorde por el número de semitonos indicado.

    Preserva el sufijo de calidad (m, maj7, sus4, dim, 7, etc.).
    Ejemplo: transpose_chord("Am7", 2) → "Bm7"
    """
    if semitones == 0:
        return chord

    match = _ROOT_PATTERN.match(chord)
    if not match:
        return chord

    root, suffix = match.group(1), match.group(2)

    # Normalizar bemoles al equivalente sostenido
    root = FLAT_MAP.get(root, root)

    if root not in SHARP_SCALE:
        return chord

    index = SHARP_SCALE.index(root)
    new_index = (index + semitones) % 12
    return SHARP_SCALE[new_index] + suffix


def transpose_song(song: Song, semitones: int) -> Song:
    """
    Devuelve una copia de la canción con todos los acordes transpuestos.

    No modifica el objeto original. El tono base de la copia se actualiza.
    """
    song_copy = copy.deepcopy(song)

    if semitones == 0:
        return song_copy

    for section in song_copy.sections:
        for line in section.lines:
            for syllable in line.syllables:
                if syllable.chord is not None:
                    syllable.chord.value = transpose_chord(
                        syllable.chord.value, semitones
                    )

    if song_copy.key:
        song_copy.key = transpose_chord(song_copy.key, semitones)

    return song_copy
