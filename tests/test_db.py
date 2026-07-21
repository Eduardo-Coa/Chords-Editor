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


def _song(title, author=None, key=None):
    return Song(id=None, title=title, author=author, key=key)


def test_filter_by_author(db):
    db.save_song(_song("Sublime Gracia", author="Himnario Adventista"))
    db.save_song(_song("Cuán Grande", author="Himnario Adventista"))
    db.save_song(_song("Otra", author="Otro Autor"))

    result = db.list_songs(filters={"author": "Himnario Adventista"})
    assert len(result) == 2
    titles = {r["title"] for r in result}
    assert titles == {"Sublime Gracia", "Cuán Grande"}


def test_filter_combines_with_search(db):
    db.save_song(_song("Sublime Gracia", author="Himnario Adventista"))
    db.save_song(_song("Cuán Grande", author="Himnario Adventista"))

    result = db.list_songs(query="sublime", filters={"author": "Himnario Adventista"})
    assert len(result) == 1
    assert result[0]["title"] == "Sublime Gracia"


def test_distinct_values_authors(db):
    db.save_song(_song("A", author="Autor Uno"))
    db.save_song(_song("B", author="Autor Dos"))
    db.save_song(_song("C", author="Autor Uno"))
    db.save_song(_song("D", author=None))  # sin autor: no aparece

    assert db.distinct_values("author") == ["Autor Dos", "Autor Uno"]


def test_distinct_values_campo_invalido(db):
    import pytest
    with pytest.raises(ValueError):
        db.distinct_values("title")  # no está en _FILTER_COLUMNS


def test_rename_author_propaga_a_todas(db):
    db.save_song(_song("A", author="Hinnario Aventista"))
    db.save_song(_song("B", author="Hinnario Aventista"))
    db.save_song(_song("C", author="Otro"))

    db.rename_author("Hinnario Aventista", "Himnario Adventista")

    assert db.distinct_values("author") == ["Himnario Adventista", "Otro"]
    assert len(db.list_songs(filters={"author": "Himnario Adventista"})) == 2


def test_rename_author_fusiona(db):
    db.save_song(_song("A", author="Himnario Adventista"))
    db.save_song(_song("B", author="Hinnario Aventista"))  # errata

    db.rename_author("Hinnario Aventista", "Himnario Adventista")

    # Quedan fusionados bajo un solo autor
    assert db.distinct_values("author") == ["Himnario Adventista"]
    assert len(db.list_songs(filters={"author": "Himnario Adventista"})) == 2


def test_autor_se_normaliza_con_trim(db):
    sid = db.save_song(_song("A", author="  Himnario Adventista  "))
    loaded = db.load_song(sid)
    assert loaded.author == "Himnario Adventista"


def test_update_existing_song(db):
    song = _sample_song()
    sid = db.save_song(song)

    song.title = "Título actualizado"
    db.save_song(song)

    loaded = db.load_song(sid)
    assert loaded.title == "Título actualizado"
    # No se duplicó: sigue habiendo una sola canción
    assert len(db.list_songs()) == 1


# ---------------------------------------------------------------------------
# Tono original (original_key)
# ---------------------------------------------------------------------------

def test_save_and_load_preserves_original_key(db):
    song = _sample_song()
    song.key = "G"
    song.original_key = "Ab"          # se toca en Sol, original en Lab
    sid = db.save_song(song)
    loaded = db.load_song(sid)
    assert loaded.key == "G"
    assert loaded.original_key == "Ab"


def test_original_key_por_defecto_es_none(db):
    sid = db.save_song(_sample_song())
    assert db.load_song(sid).original_key is None


def test_migracion_agrega_original_key_a_bd_vieja(tmp_path):
    """Una BD sin la columna ``original_key`` se migra sin perder datos."""
    import sqlite3
    from database.config import DBConfig
    from database.db import Database

    path = tmp_path / "vieja.db"
    # Esquema ANTIGUO de songs (sin original_key)
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, author TEXT, `key` TEXT,
            rhythm TEXT, capo INTEGER DEFAULT 0, notes TEXT,
            created_at TEXT, updated_at TEXT
        )
    """)
    conn.execute("INSERT INTO songs (title, `key`) VALUES ('Vieja', 'C')")
    conn.commit()
    conn.close()

    # init_schema debe añadir la columna con ALTER TABLE
    database = Database(DBConfig(path=path))
    database.init_schema()
    cur = database._connect().execute("PRAGMA table_info(songs)")
    columnas = [row[1] for row in cur.fetchall()]
    assert "original_key" in columnas
    # y se puede guardar/leer una canción con tono original en la BD migrada
    song = _sample_song()
    song.original_key = "Bb"
    sid = database.save_song(song)
    assert database.load_song(sid).original_key == "Bb"
    database.close()
