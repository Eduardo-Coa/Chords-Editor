"""Pruebas de transposición de acordes."""

from __future__ import annotations
import pytest

from models.song import Song, Section, Line, Syllable, Chord
from models.transposer import transpose_chord, transpose_song, display_song


def _cv(song: Song, sec: int, line: int = 0, syl: int = 0) -> str:
    """Valor del acorde de una sílaba (estrecha el tipo Chord|None para el linter)."""
    chord = song.sections[sec].lines[line].syllables[syl].chord
    assert chord is not None
    return chord.value


def _song_dos_secciones() -> Song:
    """Canción de prueba con dos secciones, cada una con un acorde."""
    song = Song(id=None, title="T", key="C")
    for value in ("C", "G"):
        sec = Section(id=None, position=0, type="verse", label=None)
        line = Line(id=None, position=0)
        line.syllables.append(
            Syllable(id=None, position=0, text="a", chord=Chord(id=None, value=value))
        )
        sec.lines.append(line)
        song.sections.append(sec)
    return song


@pytest.mark.parametrize("chord, semitones, expected", [
    ("Am7", 2, "Bm7"),
    ("C", 1, "C#"),
    ("G", 5, "C"),
    ("Bb", 1, "B"),
    ("F#m", -1, "Fm"),
    ("Dsus4", 0, "Dsus4"),
    ("C", 12, "C"),
])
def test_transpose_chord(chord, semitones, expected):
    assert transpose_chord(chord, semitones) == expected


def test_transpose_song_no_muta_original():
    song = Song(id=None, title="T", key="C")
    sec = Section(id=None, position=0, type="verse", label=None)
    line = Line(id=None, position=0)
    line.syllables.append(
        Syllable(id=None, position=0, text="a", chord=Chord(id=None, value="Am"))
    )
    sec.lines.append(line)
    song.sections.append(sec)

    result = transpose_song(song, 2)

    assert result.key == "D"
    assert _cv(result, 0) == "Bm"
    # El original no cambia
    assert song.key == "C"
    assert _cv(song, 0) == "Am"


@pytest.mark.parametrize("chord, semitones, key, expected", [
    ("A", 1, "E", "Bb"),    # Mi+1 = Fa (bemoles): el IV es Bb, no A#
    ("E", 1, "E", "F"),     # la tónica Mi+1 = Fa
    ("B7", 1, "E", "C7"),   # conserva el sufijo
    ("G#", 2, "A", "A#"),   # La+2 = Si (sostenidos): aquí el pitch 10 sí es A#
    ("C", 1, "C", "Db"),    # Do+1 = Reb (bemoles, menos alteraciones que Do#)
    ("D", 2, "G", "E"),     # Sol+2 = La (sostenidos), D+2 natural = E
    ("F", 2, None, "G"),    # sin tono: comportamiento por defecto (sostenidos)
])
def test_transpose_chord_consciente_del_tono(chord, semitones, key, expected):
    assert transpose_chord(chord, semitones, key) == expected


def test_display_song_sin_offsets_devuelve_el_modelo_real():
    """Sin transposición efectiva, display_song devuelve la misma instancia."""
    song = _song_dos_secciones()
    assert display_song(song, 0) is song


def test_display_song_modula_solo_el_bloque():
    """La modulación de una sección solo afecta a esa sección, no a las demás."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2  # subir 2 semitonos solo el segundo bloque

    shown = display_song(song, 0)

    assert _cv(shown, 0) == "C"  # intacto
    assert _cv(shown, 1) == "A"  # G + 2
    # No es destructivo: el modelo original conserva su acorde
    assert _cv(song, 1) == "G"
    # La sección sin modular se devuelve por referencia (editable)
    assert shown.sections[0] is song.sections[0]


def test_display_song_suma_offset_global_y_de_bloque():
    """El total por sección es global + section.transpose."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2

    shown = display_song(song, 1)  # global +1

    # C+1 = Db (tono de bemoles): el deletreo sigue al tono de destino
    assert shown.key == "Db"
    assert _cv(shown, 0) == "Db"  # C + 1
    assert _cv(shown, 1) == "Bb"  # G + 3 (tono Eb)
