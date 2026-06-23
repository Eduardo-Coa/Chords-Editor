"""Pruebas del export a PDF (genera archivos PDF válidos sin lanzar)."""

from __future__ import annotations

from models.song import Song, Section, Line, Syllable, Chord
from utils.pdf_export import song_to_pdf, _fit_font_size, _build_body


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


def test_fit_font_size_se_reduce_con_lineas_largas():
    corta = [("lyric", "abc")]
    larga = [("lyric", "x" * 200)]
    assert _fit_font_size(corta) > _fit_font_size(larga)
    assert 7.0 <= _fit_font_size(larga) <= 11.0


def test_build_body_marca_tipos():
    body = _build_body(_song())
    kinds = {k for k, _ in body}
    assert "section" in kinds   # [Coro]
    assert "chord" in kinds
    assert "lyric" in kinds
