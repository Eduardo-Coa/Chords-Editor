"""Pruebas del parser de letra pegada."""

from __future__ import annotations

from models.song import Chord, Song
from utils.lyrics_parser import (
    parse_lyrics, merge_lyrics, is_chord_line, CHORD_LINE_SLOTS,
    is_section_header, parse_section_header, detect_header,
)


def _lyric_lines(song, sec=0):
    """Líneas de letra de una sección (omite la línea de acordes inicial)."""
    return [l for l in song.sections[sec].lines if not is_chord_line(l)]


def _chord_line(song, sec=0):
    """Devuelve la línea de acordes de una sección."""
    return next(l for l in song.sections[sec].lines if is_chord_line(l))


def _first_chord(line):
    """(texto_silaba, acorde) de la primera sílaba con acorde de una línea."""
    for s in line.syllables:
        if s.chord:
            return s.text.strip(), s.chord.value
    return None


# ---------------------------------------------------------------------------
# Parseo básico
# ---------------------------------------------------------------------------

def test_sin_casillas_automaticas_en_letra():
    # Las casillas en las líneas de letra son manuales: el parser no agrega ninguna
    song = parse_lyrics("Cristo vive", title="Test")
    assert song.title == "Test"
    line = _lyric_lines(song)[0]
    assert [s for s in line.syllables if s.text == ""] == []


def test_lineas_vacias_se_conservan():
    song = parse_lyrics("Linea uno\n\nLinea dos")
    lyric = _lyric_lines(song)
    assert len(lyric) == 3
    assert lyric[1].syllables == []  # separador en medio


def test_silabas_reconstruyen_texto():
    song = parse_lyrics("gloria a Dios")
    line = _lyric_lines(song)[0]
    texto = "".join(s.text for s in line.syllables).strip()
    assert texto == "gloria a Dios"


# ---------------------------------------------------------------------------
# Línea de acordes por sección
# ---------------------------------------------------------------------------

def test_cada_seccion_tiene_linea_de_acordes():
    song = parse_lyrics("[Estrofa 1]\nGracias te doy\n[Coro]\nJesús te ama")
    for section in song.sections:
        chord_line = section.lines[0]
        assert is_chord_line(chord_line)
        assert len(chord_line.syllables) == CHORD_LINE_SLOTS


def test_linea_de_acordes_va_primero():
    song = parse_lyrics("Gracias te doy")
    assert is_chord_line(song.sections[0].lines[0])
    assert not is_chord_line(song.sections[0].lines[1])


# ---------------------------------------------------------------------------
# Secciones con corchetes
# ---------------------------------------------------------------------------

def test_detecta_encabezado_seccion():
    assert is_section_header("[Coro]")
    assert is_section_header("  [Estrofa 1]  ")
    assert not is_section_header("Cristo vive")
    assert not is_section_header("vive [en mi]")


def test_tipo_seccion_por_palabra_clave():
    assert parse_section_header("[Coro]") == ("Coro", "chorus")
    assert parse_section_header("[Estrofa 1]") == ("Estrofa 1", "verse")
    assert parse_section_header("[Puente]") == ("Puente", "bridge")
    assert parse_section_header("[Intro]") == ("Intro", "intro")
    assert parse_section_header("[Instrumental]") == ("Instrumental", "verse")


def test_parse_con_secciones():
    song = parse_lyrics("[Estrofa 1]\nGracias te doy\n[Coro]\nJesús te ama")
    assert len(song.sections) == 2
    assert song.sections[0].label == "Estrofa 1"
    assert song.sections[0].type == "verse"
    assert song.sections[1].label == "Coro"
    assert song.sections[1].type == "chorus"
    assert _lyric_lines(song, 0)[0].syllables[0].text.startswith("Gra")


def test_letra_antes_de_encabezado_va_en_seccion_por_defecto():
    song = parse_lyrics("Línea suelta\n[Coro]\nletra del coro")
    assert song.sections[0].label is None
    assert song.sections[1].label == "Coro"


# ---------------------------------------------------------------------------
# Encabezados implícitos: números y palabras clave sin corchetes
# ---------------------------------------------------------------------------

def test_detect_header_numero_es_estrofa():
    assert detect_header("1") == ("Estrofa 1", "verse")
    assert detect_header("2") == ("Estrofa 2", "verse")
    assert detect_header("3.") == ("Estrofa 3", "verse")


def test_detect_header_palabra_clave():
    assert detect_header("Coro:") == ("Coro", "chorus")
    assert detect_header("coro") == ("Coro", "chorus")
    assert detect_header("Puente") == ("Puente", "bridge")
    assert detect_header("Estrofa 2") == ("Estrofa 2", "verse")


def test_detect_header_linea_normal_no_es_encabezado():
    assert detect_header("Vivo por Cristo, confiando en su amor,") is None
    assert detect_header("es de mi senda Jesús guía fiel.") is None
    assert detect_header("") is None


def test_parse_con_numeros_y_coro_implicitos():
    texto = (
        "1\nVivo por Cristo\nvida me imparte\n"
        "Coro:\n\n¡Oh, Salvador bendito!\n"
        "2\nVivo por Cristo, murió por mí"
    )
    song = parse_lyrics(texto)
    labels = [(s.label, s.type) for s in song.sections]
    assert labels == [
        ("Estrofa 1", "verse"),
        ("Coro", "chorus"),
        ("Estrofa 2", "verse"),
    ]
    # La línea en blanco tras "Coro:" no deja un separador al inicio del coro
    coro_lyric = [l for l in song.sections[1].lines if not is_chord_line(l)]
    primera = "".join(s.text for s in coro_lyric[0].syllables).strip()
    assert primera == "¡Oh, Salvador bendito!"


# ---------------------------------------------------------------------------
# merge_lyrics: editar letra conservando acordes
# ---------------------------------------------------------------------------

def _song_con_acordes() -> Song:
    """Canción con id, acordes en las líneas de letra y en la línea de acordes."""
    song = parse_lyrics("Gracias te doy\nque pronto volverás")
    song.id = 42
    lyric = _lyric_lines(song)
    lyric[0].syllables[0].chord = Chord(id=None, value="D")
    lyric[1].syllables[0].chord = Chord(id=None, value="G")
    # Acorde en la línea de acordes (intro de la sección)
    _chord_line(song).syllables[0].chord = Chord(id=None, value="A")
    return song


def test_merge_conserva_id():
    merged = merge_lyrics(_song_con_acordes(), "Gracias te doy\nque pronto volverás")
    assert merged.id == 42


def test_merge_agregar_linea_conserva_acordes_previos():
    nuevo = "Gracias te doy\nque pronto volverás\nuna línea nueva"
    merged = merge_lyrics(_song_con_acordes(), nuevo)
    lyric = _lyric_lines(merged)
    assert _first_chord(lyric[0]) == ("Gra", "D")
    assert _first_chord(lyric[1]) == ("que", "G")
    assert _first_chord(lyric[2]) is None  # línea nueva sin acordes


def test_merge_linea_editada_pierde_sus_acordes_pero_otras_no():
    nuevo = "Gracias te doy\nque muy pronto volverás"
    merged = merge_lyrics(_song_con_acordes(), nuevo)
    lyric = _lyric_lines(merged)
    assert _first_chord(lyric[0]) == ("Gra", "D")  # intacta
    assert _first_chord(lyric[1]) is None          # editada, sin acordes


def test_merge_conserva_linea_de_acordes_por_seccion():
    # Al editar la letra, la línea de acordes (intro) conserva su acorde
    merged = merge_lyrics(_song_con_acordes(), "Gracias te doy\nque pronto volverás")
    assert _first_chord(_chord_line(merged)) == ("", "A")
