"""Pruebas de exportación/importación de canciones (.ilahi)."""

from __future__ import annotations
import json
import pytest

from models.song import Song, Section, Line, Syllable, Chord
from utils.song_io import (
    song_to_dict, dict_to_song, export_song, import_song,
    suggested_filename, SongIOError, FORMAT_NAME, FORMAT_VERSION,
)


def _song_ejemplo() -> Song:
    """Canción con ids reales, acentos y modulación de bloque para el round-trip."""
    song = Song(id=7, title="Canción Ñandú", author="Autor",
                key="C", rhythm="Balada", capo=2, notes="una nota")
    sec = Section(id=3, position=0, type="chorus", label="Coro", transpose=2)
    line = Line(id=5, position=0)
    line.syllables.append(
        Syllable(id=9, position=0, text="Glo", chord=Chord(id=1, value="C"))
    )
    line.syllables.append(Syllable(id=10, position=1, text="ria", chord=None))
    sec.lines.append(line)
    song.sections.append(sec)
    return song


def test_round_trip_conserva_contenido():
    restored = dict_to_song(song_to_dict(_song_ejemplo()))

    assert restored.title == "Canción Ñandú"
    assert restored.author == "Autor"
    assert restored.key == "C"
    assert restored.capo == 2
    assert restored.notes == "una nota"

    sec = restored.sections[0]
    assert sec.type == "chorus"
    assert sec.label == "Coro"
    assert sec.transpose == 2  # la modulación por bloque viaja en el archivo
    assert sec.lines[0].syllables[0].text == "Glo"
    assert sec.lines[0].syllables[0].chord.value == "C"
    assert sec.lines[0].syllables[1].chord is None


def test_export_no_incluye_ids_ni_position():
    data = song_to_dict(_song_ejemplo())
    assert "id" not in data
    assert "id" not in data["sections"][0]
    assert "position" not in data["sections"][0]
    syl = data["sections"][0]["lines"][0]["syllables"][0]
    assert set(syl.keys()) == {"text", "chord"}


def test_import_resetea_ids_a_none():
    restored = dict_to_song(song_to_dict(_song_ejemplo()))
    syl = restored.sections[0].lines[0].syllables[0]
    assert restored.id is None
    assert restored.sections[0].id is None
    assert restored.sections[0].lines[0].id is None
    assert syl.id is None
    assert syl.chord.id is None


def test_archivo_lleva_formato_y_version(tmp_path):
    path = tmp_path / "c.ilahi"
    export_song(_song_ejemplo(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == FORMAT_NAME
    assert data["version"] == FORMAT_VERSION


def test_round_trip_en_disco_conserva_acentos(tmp_path):
    path = tmp_path / "c.ilahi"
    export_song(_song_ejemplo(), path)
    # Acentos legibles en el archivo (no escapados como \uXXXX)
    assert "Ñandú" in path.read_text(encoding="utf-8")
    assert import_song(path).title == "Canción Ñandú"


def test_import_json_corrupto(tmp_path):
    path = tmp_path / "malo.ilahi"
    path.write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(SongIOError):
        import_song(path)


def test_import_formato_desconocido():
    with pytest.raises(SongIOError):
        dict_to_song({"format": "otra-cosa", "version": 1, "title": "x"})


def test_import_version_futura_no_compatible():
    data = song_to_dict(_song_ejemplo())
    data["version"] = FORMAT_VERSION + 1
    with pytest.raises(SongIOError):
        dict_to_song(data)


def test_import_tipo_seccion_invalido():
    data = song_to_dict(_song_ejemplo())
    data["sections"][0]["type"] = "estribillo"  # no está en el enum
    with pytest.raises(SongIOError):
        dict_to_song(data)


def test_import_sin_titulo():
    with pytest.raises(SongIOError):
        dict_to_song({"format": FORMAT_NAME, "version": 1, "title": "   "})


def test_suggested_filename_sanea_caracteres():
    name = suggested_filename(Song(id=None, title='Aviva: tu/fuego?'))
    assert name.endswith(".ilahi")
    for ch in '<>:"/\\|?*':
        assert ch not in name


def test_import_acepta_formato_heredado_hymnchords():
    """Los archivos exportados cuando la app se llamaba HymnChords siguen abriendo."""
    data = song_to_dict(_song_ejemplo())
    data["format"] = "hymnchords-song"
    restored = dict_to_song(data)
    assert restored.title == "Canción Ñandú"


def test_export_escribe_el_formato_nuevo(tmp_path):
    path = tmp_path / "c.ilahi"
    export_song(_song_ejemplo(), path)
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == "ilahi-song"
