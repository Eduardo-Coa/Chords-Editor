"""Pruebas del cancionero (bundle multi-canción .hymnchords) y la carga unificada."""

from __future__ import annotations
import json
import pytest

from models.song import Song, Section, Line, Syllable, Chord
from utils.song_io import (
    export_song, export_bundle, load_songs, bundle_to_dict, bundle_filename,
    SongIOError, BUNDLE_FORMAT_NAME, BUNDLE_FORMAT_VERSION,
)


def _song(title: str, author: str = "Autor") -> Song:
    song = Song(id=99, title=title, author=author, key="C", capo=1)
    sec = Section(id=3, position=0, type="verse", label="Estrofa")
    line = Line(id=5, position=0)
    line.syllables.append(
        Syllable(id=9, position=0, text="Ñan", chord=Chord(id=1, value="G"))
    )
    line.syllables.append(Syllable(id=10, position=1, text="dú", chord=None))
    sec.lines.append(line)
    song.sections.append(sec)
    return song


def test_bundle_round_trip_conserva_las_canciones(tmp_path):
    path = tmp_path / "autor.hymnchords"
    export_bundle([_song("Uno"), _song("Dos"), _song("Tres")], path, author="Autor")

    restored = load_songs(path)
    assert [s.title for s in restored] == ["Uno", "Dos", "Tres"]
    assert restored[0].sections[0].lines[0].syllables[0].chord.value == "G"


def test_bundle_lleva_formato_autor_y_conteo(tmp_path):
    path = tmp_path / "autor.hymnchords"
    export_bundle([_song("Uno"), _song("Dos")], path, author="Autor")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == BUNDLE_FORMAT_NAME
    assert data["version"] == BUNDLE_FORMAT_VERSION
    assert data["author"] == "Autor"
    assert data["count"] == 2


def test_bundle_resetea_ids_a_none(tmp_path):
    path = tmp_path / "b.hymnchords"
    export_bundle([_song("Uno")], path)
    song = load_songs(path)[0]
    assert song.id is None
    assert song.sections[0].id is None
    assert song.sections[0].lines[0].syllables[0].chord.id is None


def test_bundle_conserva_acentos_en_disco(tmp_path):
    path = tmp_path / "b.hymnchords"
    export_bundle([_song("Canción Ñandú")], path)
    assert "Ñandú" in path.read_text(encoding="utf-8")


def test_load_songs_acepta_cancion_suelta(tmp_path):
    """load_songs también lee una canción individual → lista de un elemento."""
    path = tmp_path / "suelta.hymnchords"
    export_song(_song("Sola"), path)
    songs = load_songs(path)
    assert len(songs) == 1
    assert songs[0].title == "Sola"


def test_load_songs_formato_desconocido(tmp_path):
    path = tmp_path / "raro.hymnchords"
    path.write_text(json.dumps({"format": "otra-cosa", "version": 1}), encoding="utf-8")
    with pytest.raises(SongIOError):
        load_songs(path)


def test_load_bundle_version_futura(tmp_path):
    path = tmp_path / "futuro.hymnchords"
    data = bundle_to_dict([_song("Uno")], author="Autor")
    data["version"] = BUNDLE_FORMAT_VERSION + 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SongIOError):
        load_songs(path)


def test_load_bundle_sin_lista_de_canciones(tmp_path):
    path = tmp_path / "vacio.hymnchords"
    path.write_text(
        json.dumps({"format": BUNDLE_FORMAT_NAME, "version": 1}), encoding="utf-8"
    )
    with pytest.raises(SongIOError):
        load_songs(path)


def test_bundle_vacio_da_lista_vacia(tmp_path):
    """Un bundle con cero canciones se lee como lista vacía (sin lanzar)."""
    path = tmp_path / "cero.hymnchords"
    export_bundle([], path, author="Nadie")
    assert load_songs(path) == []


def test_bundle_filename_sanea_autor():
    name = bundle_filename('Aviva: tu/fuego?')
    assert name.endswith(".hymnchords")
    for ch in '<>:"/\\|?*':
        assert ch not in name


def test_bundle_filename_sin_autor_usa_cancionero():
    assert bundle_filename(None).startswith("cancionero")
