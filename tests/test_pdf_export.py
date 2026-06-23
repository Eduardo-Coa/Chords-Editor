"""Pruebas del export a PDF (genera archivos PDF válidos y elige layout)."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable, Chord
from utils.pdf_export import (
    song_to_pdf, _build_blocks, _choose_layout, _packs_one_page, _MIN_PT, _MAX_PT,
)


def _song() -> Song:
    song = Song(id=None, title="Eterna Roca", author="Himnario", key="E",
                rhythm="Balada", capo=2)
    sec = Section(id=None, position=0, type="chorus", label="Coro")
    line = Line(id=None, position=0)
    for i, (t, c) in enumerate([("Cris", "G"), ("to", None), (" tu ", None),
                                ("gran", "C"), (" amor", None)]):
        chord = Chord(id=None, value=c) if c else None
        line.syllables.append(Syllable(id=None, position=i, text=t, chord=chord))
    sec.lines.append(line)
    song.sections.append(sec)
    return song


def _long_song(n_lines: int) -> Song:
    """Canción de ``n_lines`` líneas cortas (fuerza el paso a 2 columnas)."""
    song = Song(id=None, title="Larga")
    sec = Section(id=None, position=0, type="verse", label=None)
    for p in range(n_lines):
        line = Line(id=None, position=p)
        chord = Chord(id=None, value="C") if p % 4 == 0 else None
        line.syllables.append(Syllable(id=None, position=0, text="aleluya", chord=chord))
        sec.lines.append(line)
    song.sections.append(sec)
    return song


def test_song_to_pdf_crea_pdf_valido(tmp_path):
    out = tmp_path / "x.pdf"
    song_to_pdf(_song(), out)
    assert out.exists()
    data = out.read_bytes()
    assert data[:5] == b"%PDF-"   # cabecera de PDF válida
    assert len(data) > 500


def test_song_to_pdf_lineas_largas_no_lanza(tmp_path):
    """Una línea muy larga fuerza el auto-ajuste de fuente; no debe lanzar."""
    song = Song(id=None, title="T")
    sec = Section(id=None, position=0, type="verse", label=None)
    line = Line(id=None, position=0)
    for i in range(80):
        chord = Chord(id=None, value="C") if i % 6 == 0 else None
        line.syllables.append(Syllable(id=None, position=i, text="la ", chord=chord))
    sec.lines.append(line)
    song.sections.append(sec)

    out = tmp_path / "largo.pdf"
    song_to_pdf(song, out)
    assert out.exists() and out.read_bytes()[:5] == b"%PDF-"


def test_song_to_pdf_cancion_larga_no_lanza(tmp_path):
    """Muchas líneas → 2 columnas / posible multipágina; debe generar PDF válido."""
    out = tmp_path / "muchas.pdf"
    song_to_pdf(_long_song(180), out)
    assert out.exists() and out.read_bytes()[:5] == b"%PDF-"


def test_build_blocks_marca_tipos():
    kinds = {k for blk in _build_blocks(_song()) for k, _ in blk}
    assert "section" in kinds   # [Coro]
    assert "chord" in kinds
    assert "lyric" in kinds


def test_build_blocks_pega_encabezado_a_primera_linea():
    """El encabezado de sección viaja en el mismo bloque que su 1ª línea."""
    blocks = _build_blocks(_song())
    primero = next(blk for blk in blocks if any(k == "section" for k, _ in blk))
    assert primero[0][0] == "section"
    assert any(k in ("chord", "lyric") for k, _ in primero)  # no queda huérfano


def test_cancion_corta_usa_una_columna():
    blocks = _build_blocks(_song())
    longest = max(len(t) for blk in blocks for _, t in blk)
    size, columns = _choose_layout(blocks, longest, header_h=18.0)
    assert columns == 1
    assert size == _MAX_PT          # corta → fuente al tope


def test_cancion_larga_usa_dos_columnas():
    blocks = _build_blocks(_long_song(180))
    longest = max(len(t) for blk in blocks for _, t in blk)
    size, columns = _choose_layout(blocks, longest, header_h=12.0)
    assert columns == 2
    assert _MIN_PT <= size <= _MAX_PT


def test_choose_layout_respeta_rango():
    blocks = _build_blocks(_long_song(60))
    longest = max(len(t) for blk in blocks for _, t in blk)
    size, _ = _choose_layout(blocks, longest, header_h=12.0)
    assert _MIN_PT <= size <= _MAX_PT


def test_packs_one_page_falla_si_no_entra():
    """Con muchísimas líneas y 1 sola columna, no entra en una página."""
    blocks = _build_blocks(_long_song(300))
    assert _packs_one_page(blocks, _MIN_PT, columns=1, header_h=12.0) is False
