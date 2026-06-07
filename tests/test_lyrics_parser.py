"""Pruebas del parser de letra pegada."""

from __future__ import annotations

from utils.lyrics_parser import parse_lyrics, TRAILING_NOTE_SLOTS


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
