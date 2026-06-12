"""Lógica de transposición de acordes para HymnChords.

La transposición es *consciente del tono*: el acorde resultante se deletrea con
bemoles o sostenidos según la tonalidad de destino (en Fa el IV es "Bb", en Mi
es "A#"). Sin un tono de contexto, por defecto usa sostenidos.
"""

from __future__ import annotations
import copy
import re
from models.song import Song

SHARP_SCALE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_SCALE = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
FLAT_MAP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

# Altura (clase de tono 0-11) de cada nombre de nota, para interpretar el tono.
_NOTE_PITCH = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5,
    "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11,
}

# Tonalidades que se escriben con bemoles (por clase de tono de la tónica).
# Mayores: Db, Eb, F, Ab, Bb.   Menores: Cm, Dm, Ebm, Fm, Gm, Bbm.
_MAJOR_FLAT_PITCHES = {1, 3, 5, 8, 10}
_MINOR_FLAT_PITCHES = {0, 2, 3, 5, 7, 10}

# Patrón para extraer la nota raíz de un acorde (ej: "Am7" → raíz "A", sufijo "m7")
_ROOT_PATTERN = re.compile(r"^([A-G][b#]?)(.*)")


def _parse_key_pitch(key: str) -> tuple[int, bool] | None:
    """Devuelve (clase de tono de la tónica, es_menor) del tono, o None si no es válido."""
    key = key.strip()
    if not key:
        return None
    is_minor = key.endswith("m") and not key.endswith("dim")
    root = key[:-1] if is_minor else key
    pitch = _NOTE_PITCH.get(root.upper())
    if pitch is None:
        return None
    return pitch, is_minor


def _key_prefers_flats(pitch: int, is_minor: bool) -> bool:
    """True si la tonalidad indicada se escribe con bemoles."""
    return pitch in (_MINOR_FLAT_PITCHES if is_minor else _MAJOR_FLAT_PITCHES)


def transpose_chord(chord: str, semitones: int, key: str | None = None) -> str:
    """
    Transpone un acorde por el número de semitonos indicado.

    Preserva el sufijo de calidad (m, maj7, sus4, dim, 7, etc.). Si se pasa
    ``key`` (el tono ORIGEN), el resultado se deletrea según el tono de destino
    (origen + semitonos): bemoles para tonos de bemoles, sostenidos para el resto.
    Ejemplo: transpose_chord("A", 1, key="E") → "Bb"  (Mi+1 = Fa, tono de bemoles)
    """
    if semitones == 0:
        return chord

    match = _ROOT_PATTERN.match(chord)
    if not match:
        return chord

    root, suffix = match.group(1), match.group(2)
    root = FLAT_MAP.get(root, root)  # normalizar bemoles a su índice sostenido
    if root not in SHARP_SCALE:
        return chord

    new_index = (SHARP_SCALE.index(root) + semitones) % 12

    use_flats = False
    parsed = _parse_key_pitch(key) if key else None
    if parsed is not None:
        target_pitch = (parsed[0] + semitones) % 12
        use_flats = _key_prefers_flats(target_pitch, parsed[1])

    scale = FLAT_SCALE if use_flats else SHARP_SCALE
    return scale[new_index] + suffix


def transpose_song(song: Song, semitones: int) -> Song:
    """
    Devuelve una copia de la canción con todos los acordes transpuestos.

    No modifica el objeto original. El tono base de la copia se actualiza y los
    acordes se deletrean según el tono de destino.
    """
    song_copy = copy.deepcopy(song)

    if semitones == 0:
        return song_copy

    key = song.key
    for section in song_copy.sections:
        for line in section.lines:
            for syllable in line.syllables:
                if syllable.chord is not None:
                    syllable.chord.value = transpose_chord(
                        syllable.chord.value, semitones, key
                    )

    if song_copy.key:
        song_copy.key = transpose_chord(song_copy.key, semitones, key)

    return song_copy


def display_song(song: Song, global_offset: int = 0) -> Song:
    """
    Devuelve la canción lista para mostrar, aplicando a cada sección un total de
    ``global_offset + section.transpose`` semitonos (modulación por bloque).

    No es destructiva. Para que la edición de acordes siga operando sobre el
    modelo real, las secciones cuyo total es 0 se devuelven por referencia (sin
    copiar); solo se copian y transponen las que tienen modulación efectiva. Cada
    sección conserva su ``transpose`` para que la UI muestre el valor del bloque.
    Los acordes se deletrean según el tono de destino (origen + total).
    """
    if global_offset == 0 and all(s.transpose == 0 for s in song.sections):
        return song  # nada que transponer: modelo real, totalmente editable

    key = song.key
    shown = Song(
        id=song.id, title=song.title, author=song.author,
        key=transpose_chord(song.key, global_offset, key) if song.key else song.key,
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
                    syllable.chord.value = transpose_chord(
                        syllable.chord.value, total, key
                    )
        shown.sections.append(sec_copy)
    return shown
