"""Pruebas de transposición de acordes."""

from __future__ import annotations
import pytest

from models.song import Song, Section, Line, Syllable, Chord
from models.transposer import transpose_chord, transpose_song


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
