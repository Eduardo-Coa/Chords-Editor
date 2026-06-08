"""Pruebas del parser de letra pegada."""

from __future__ import annotations

from models.song import Chord, Song
from utils.lyrics_parser import (
    parse_lyrics, merge_lyrics, TRAILING_NOTE_SLOTS,
    is_section_header, parse_section_header,
)


def _first_chord_of_line(song, sec=0, line=0):
    """Devuelve (texto_silaba, acorde) de la primera sílaba con acorde de una línea."""
    for s in song.sections[sec].lines[line].syllables:
        if s.chord:
            return s.text.strip(), s.chord.value
    return None


def test_una_linea_con_ranuras():
    song = parse_lyrics("Cristo vive", title="Test")
    assert song.title == "Test"
    line = song.sections[0].lines[0]
    slots = [s for s in line.syllables if s.text == ""]
    assert len(slots) == TRAILING_NOTE_SLOTS


def test_lineas_vacias_se_conservan():
    song = parse_lyrics("Linea uno\n\nLinea dos")
    lines = song.sections[0].lines
    assert len(lines) == 3
    # La línea del medio está vacía (separador), sin ranuras
    assert lines[1].syllables == []


def test_silabas_reconstruyen_texto():
    song = parse_lyrics("gloria a Dios")
    line = song.sections[0].lines[0]
    texto = "".join(s.text for s in line.syllables).strip()
    assert texto == "gloria a Dios"


def test_detecta_encabezado_seccion():
    assert is_section_header("[Coro]")
    assert is_section_header("  [Estrofa 1]  ")
    assert not is_section_header("Cristo vive")
    assert not is_section_header("vive [en mi]")  # corchete a mitad, no es encabezado


def test_tipo_seccion_por_palabra_clave():
    assert parse_section_header("[Coro]") == ("Coro", "chorus")
    assert parse_section_header("[Estrofa 1]") == ("Estrofa 1", "verse")
    assert parse_section_header("[Puente]") == ("Puente", "bridge")
    assert parse_section_header("[Intro]") == ("Intro", "intro")
    assert parse_section_header("[Instrumental]") == ("Instrumental", "verse")  # libre


def test_parse_con_secciones():
    text = "[Estrofa 1]\nGracias te doy\n[Coro]\nJesús te ama"
    song = parse_lyrics(text)
    assert len(song.sections) == 2
    assert song.sections[0].label == "Estrofa 1"
    assert song.sections[0].type == "verse"
    assert song.sections[1].label == "Coro"
    assert song.sections[1].type == "chorus"
    # Cada sección tiene su línea de letra
    assert song.sections[0].lines[0].syllables[0].text.startswith("Gra")


def test_letra_antes_de_encabezado_va_en_seccion_por_defecto():
    song = parse_lyrics("Línea suelta\n[Coro]\nletra del coro")
    assert song.sections[0].label is None
    assert song.sections[1].label == "Coro"


# ---------------------------------------------------------------------------
# merge_lyrics: editar letra conservando acordes
# ---------------------------------------------------------------------------

def _song_con_acordes() -> Song:
    """Canción de prueba con id y un acorde en la primera línea."""
    song = parse_lyrics("Gracias te doy\nque pronto volverás")
    song.id = 42
    # Poner un acorde en la primera sílaba de cada línea
    song.sections[0].lines[0].syllables[0].chord = Chord(id=None, value="D")
    song.sections[0].lines[1].syllables[0].chord = Chord(id=None, value="G")
    return song


def test_merge_conserva_id():
    song = _song_con_acordes()
    merged = merge_lyrics(song, "Gracias te doy\nque pronto volverás")
    assert merged.id == 42


def test_merge_agregar_linea_conserva_acordes_previos():
    song = _song_con_acordes()
    nuevo = "Gracias te doy\nque pronto volverás\nuna línea nueva"
    merged = merge_lyrics(song, nuevo)

    # Las dos líneas originales conservan sus acordes
    assert _first_chord_of_line(merged, 0, 0) == ("Gra", "D")
    assert _first_chord_of_line(merged, 0, 1) == ("que", "G")
    # La línea nueva no tiene acordes
    assert _first_chord_of_line(merged, 0, 2) is None


def test_merge_linea_editada_pierde_sus_acordes_pero_otras_no():
    song = _song_con_acordes()
    # Se modifica la segunda línea; la primera queda igual
    nuevo = "Gracias te doy\nque muy pronto volverás"
    merged = merge_lyrics(song, nuevo)

    assert _first_chord_of_line(merged, 0, 0) == ("Gra", "D")  # intacta
    assert _first_chord_of_line(merged, 0, 1) is None          # editada, sin acordes
