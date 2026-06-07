"""Pruebas de la capa de base de datos (contra la base de pruebas aislada)."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable, Chord


def _sample_song() -> Song:
    song = Song(id=None, title="Canción de prueba", author="Autor", key="C")
    section = Section(id=None, position=0, type="verse", label="Estrofa 1")
    line = Line(id=None, position=0)
    line.syllables = [
        Syllable(id=None, position=0, text="Glo", chord=Chord(id=None, value="C")),
        Syllable(id=None, position=1, text="ria"),
        Syllable(id=None, position=2, text="a", chord=Chord(id=None, value="G")),
    ]
    section.lines.append(line)
    song.sections.append(section)
    return song


def test_save_assigns_id(db):
    sid = db.save_song(_sample_song())
    assert isinstance(sid, int) and sid > 0


def test_save_and_load_preserves_content(db):
    sid = db.save_song(_sample_song())
    loaded = db.load_song(sid)

    assert loaded.title == "Canción de prueba"
    assert loaded.author == "Autor"
    assert loaded.key == "C"

    syllables = loaded.sections[0].lines[0].syllables
    assert [s.text for s in syllables] == ["Glo", "ria", "a"]
    assert syllables[0].chord.value == "C"
    assert syllables[1].chord is None
    assert syllables[2].chord.value == "G"


def test_list_songs(db):
    db.save_song(_sample_song())
    songs = db.list_songs()
    assert len(songs) == 1
    assert songs[0]["title"] == "Canción de prueba"


def test_search_filter(db):
    db.save_song(_sample_song())
    assert len(db.list_songs("prueba")) == 1
    assert len(db.list_songs("inexistente")) == 0


def test_delete_song(db):
    sid = db.save_song(_sample_song())
    db.delete_song(sid)
    assert db.list_songs() == []


def test_update_existing_song(db):
    song = _sample_song()
    sid = db.save_song(song)

    song.title = "Título actualizado"
    db.save_song(song)

    loaded = db.load_song(sid)
    assert loaded.title == "Título actualizado"
    # No se duplicó: sigue habiendo una sola canción
    assert len(db.list_songs()) == 1
