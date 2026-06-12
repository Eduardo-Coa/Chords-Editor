"""Pruebas de transposición de acordes."""

from __future__ import annotations
import pytest

from models.song import Song, Section, Line, Syllable, Chord
from models.transposer import transpose_chord, transpose_song, display_song


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
    assert result.sections[0].lines[0].syllables[0].chord.value == "Bm"
    # El original no cambia
    assert song.key == "C"
    assert song.sections[0].lines[0].syllables[0].chord.value == "Am"


def test_display_song_sin_offsets_devuelve_el_modelo_real():
    """Sin transposición efectiva, display_song devuelve la misma instancia."""
    song = _song_dos_secciones()
    assert display_song(song, 0) is song


def test_display_song_modula_solo_el_bloque():
    """La modulación de una sección solo afecta a esa sección, no a las demás."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2  # subir 2 semitonos solo el segundo bloque

    shown = display_song(song, 0)

    assert shown.sections[0].lines[0].syllables[0].chord.value == "C"  # intacto
    assert shown.sections[1].lines[0].syllables[0].chord.value == "A"  # G + 2
    # No es destructivo: el modelo original conserva su acorde
    assert song.sections[1].lines[0].syllables[0].chord.value == "G"
    # La sección sin modular se devuelve por referencia (editable)
    assert shown.sections[0] is song.sections[0]


def test_display_song_suma_offset_global_y_de_bloque():
    """El total por sección es global + section.transpose."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2

    shown = display_song(song, 1)  # global +1

    assert shown.key == "C#"  # la tonalidad sigue solo al global
    assert shown.sections[0].lines[0].syllables[0].chord.value == "C#"  # C + 1
    assert shown.sections[1].lines[0].syllables[0].chord.value == "A#"  # G + 1 + 2
