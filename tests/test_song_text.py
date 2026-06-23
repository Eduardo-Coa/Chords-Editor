"""Pruebas de la representación de una canción como texto monoespaciado."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable, Chord
from utils.song_text import song_to_text, line_to_chord_lyric


def _line(pairs: list[tuple[str, str | None]]) -> Line:
    """Construye una Line desde pares (texto, acorde|None)."""
    line = Line(id=None, position=0)
    for i, (text, chord) in enumerate(pairs):
        c = Chord(id=None, value=chord) if chord else None
        line.syllables.append(Syllable(id=None, position=i, text=text, chord=c))
    return line


def test_line_alinea_acorde_sobre_silaba():
    chords, lyric = line_to_chord_lyric(_line([("Su", "C"), ("bli", None), ("me", "F")]))
    assert lyric == "Sublime"
    assert chords[0] == "C"                  # 'C' sobre la 1ª sílaba
    assert chords.index("F") == len("Subli")  # 'F' sobre el inicio de "me"


def test_line_solo_acordes():
    """Una línea de solo acordes (slots vacíos) produce fila de acordes sin letra."""
    chords, lyric = line_to_chord_lyric(_line([("", "G"), (" ", None), ("", "D")]))
    assert lyric == ""
    assert chords.startswith("G")
    assert "D" in chords


def test_song_to_text_estructura():
    song = Song(id=None, title="T", key="C")
    sec = Section(id=None, position=0, type="chorus", label="Coro")
    sec.lines.append(_line([("Glo", "C"), ("ria", None)]))
    song.sections.append(sec)

    lines = song_to_text(song).splitlines()
    assert lines[0] == "[Coro]"
    assert lines[1] == "C"        # fila de acordes
    assert lines[2] == "Gloria"   # fila de letra


def test_song_to_text_seccion_sin_label_usa_tipo():
    song = Song(id=None, title="T")
    sec = Section(id=None, position=0, type="verse", label=None)
    sec.lines.append(_line([("a", "G")]))
    song.sections.append(sec)
    assert "[Estrofa]" in song_to_text(song)


def test_song_header_lines():
    from utils.song_text import song_header_lines
    song = Song(id=None, title="T", author="A", key="C", rhythm="Vals", capo=3)
    lines = song_header_lines(song)
    assert lines[0] == "T"
    assert lines[1] == "A · Tono: C · Ritmo: Vals · Capo: traste 3"


def test_song_to_text_con_metadata():
    song = Song(id=None, title="Eterna Roca", author="Himnario", key="E",
                rhythm="Balada", capo=2)
    sec = Section(id=None, position=0, type="chorus", label="Coro")
    sec.lines.append(_line([("a", "E")]))
    song.sections.append(sec)

    lines = song_to_text(song, metadata=True).splitlines()
    assert lines[0] == "Eterna Roca"
    assert "Himnario" in lines[1]
    assert "Tono: E" in lines[1]
    assert "Ritmo: Balada" in lines[1]
    assert "Capo: traste 2" in lines[1]
    assert "[Coro]" in lines  # el cuerpo sigue presente


def test_song_to_text_omite_campos_ausentes():
    song = Song(id=None, title="X", author="A", key="C", rhythm=None, capo=0)
    sec = Section(id=None, position=0, type="verse", label=None)
    sec.lines.append(_line([("a", "C")]))
    song.sections.append(sec)

    text = song_to_text(song, metadata=True)
    assert "Capo" not in text   # capo=0 → no se muestra
    assert "Ritmo" not in text  # sin ritmo → no se muestra
    assert "Tono: C" in text


def test_song_to_text_sin_metadata_es_solo_cuerpo():
    """Por defecto (metadata=False) no antepone encabezado."""
    song = Song(id=None, title="X", author="A", key="C")
    sec = Section(id=None, position=0, type="chorus", label="Coro")
    sec.lines.append(_line([("a", "C")]))
    song.sections.append(sec)
    assert song_to_text(song).splitlines()[0] == "[Coro]"


def test_song_to_text_conserva_acentos():
    song = Song(id=None, title="T")
    sec = Section(id=None, position=0, type="verse", label=None)
    sec.lines.append(_line([("Ñan", "C"), ("dú", None)]))
    song.sections.append(sec)
    assert "Ñandú" in song_to_text(song)
