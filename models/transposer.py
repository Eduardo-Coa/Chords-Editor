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


def display_song(song: Song, global_offset: int = 0) -> Song:
    """
    Devuelve la canción lista para mostrar, aplicando a cada sección un total de
    ``global_offset + section.transpose`` semitonos (modulación por bloque).

    No es destructiva. Para que la edición de acordes siga operando sobre el
    modelo real, las secciones cuyo total es 0 se devuelven por referencia (sin
    copiar); solo se copian y transponen las que tienen modulación efectiva. Cada
    sección conserva su ``transpose`` para que la UI muestre el valor del bloque.
    """
    if global_offset == 0 and all(s.transpose == 0 for s in song.sections):
        return song  # nada que transponer: modelo real, totalmente editable

    shown = Song(
        id=song.id, title=song.title, author=song.author,
        key=transpose_chord(song.key, global_offset) if song.key else song.key,
        rhythm=song.rhythm, capo=song.capo, notes=song.notes,
    )
    for section in song.sections:
        total = global_offset + section.transpose
        if total == 0:
            shown.sections.append(section)  # sin cambios: sección real (editable)
            continue
        sec_copy = copy.deepcopy(section)
        for line in sec_copy.lines:
            for syllable in line.syllables:
                if syllable.chord is not None:
                    syllable.chord.value = transpose_chord(syllable.chord.value, total)
        shown.sections.append(sec_copy)
    return shown
