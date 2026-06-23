"""Exportar una canción a PDF (cifrado monoespaciado) con fpdf2.

Un clic → archivo .pdf. Acordes en color sobre la letra en negro, en fuente
monoespaciada (Courier, embebida en el PDF) → la alineación de los acordes no se
corre en ningún visor. Reutiliza ``utils.song_text`` (mismo formato y encabezado
que el copiado al portapapeles). El tamaño de fuente se auto-ajusta para que la
línea más larga entre en el ancho de la página.
"""

from __future__ import annotations
from pathlib import Path

from fpdf import FPDF

from models.song import Song
from utils.song_text import line_to_chord_lyric, song_header_lines, SECTION_LABELS

# Paleta clara para imprimir (papel blanco).
_CHORD_RGB = (200, 120, 40)    # acordes (dorado/ámbar, legible en blanco)
_LYRIC_RGB = (20, 20, 20)      # letra
_MUTED_RGB = (120, 120, 120)   # subtítulo del encabezado y etiquetas de sección
_MONO = "Courier"              # fuente núcleo del PDF: monoespaciada, sin bundlear
_SANS = "Helvetica"

_MARGIN = 15.0                 # mm
# Courier es monoespaciada: ancho de carácter = 0.6 em. 1 pt = 25.4/72 mm.
_CHAR_MM_PER_PT = 0.6 * 25.4 / 72
_MAX_PT = 11.0
_MIN_PT = 7.0
_A4_WIDTH_MM = 210.0


def song_to_pdf(song: Song, path: str | Path) -> None:
    """Genera el PDF de ``song`` en ``path`` (cifrado monoespaciado, claro)."""
    header = song_header_lines(song)
    body = _build_body(song)
    size = _fit_font_size(body)
    line_h = size * 25.4 / 72 * 1.25  # alto de línea en mm

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.set_auto_page_break(auto=True, margin=_MARGIN)
    pdf.add_page()

    # Encabezado: título + (autor · Tono · Ritmo · Capo)
    pdf.set_font(_SANS, "B", 16)
    pdf.set_text_color(*_LYRIC_RGB)
    pdf.cell(0, 9, header[0], new_x="LMARGIN", new_y="NEXT")
    if len(header) > 1:
        pdf.set_font(_SANS, "", 11)
        pdf.set_text_color(*_MUTED_RGB)
        pdf.cell(0, 6, header[1], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Cuerpo: acordes (color) sobre letra (negro), etiquetas de sección atenuadas
    for kind, text in body:
        if kind == "blank":
            pdf.ln(line_h)
            continue
        # Mantener juntos un acorde y su letra: si no caben 2 líneas, página nueva
        if kind == "chord" and pdf.get_y() + 2 * line_h > pdf.h - pdf.b_margin:
            pdf.add_page()
        if kind == "section":
            pdf.set_font(_MONO, "B", size)
            pdf.set_text_color(*_MUTED_RGB)
        elif kind == "chord":
            pdf.set_font(_MONO, "B", size)
            pdf.set_text_color(*_CHORD_RGB)
        else:  # lyric
            pdf.set_font(_MONO, "", size)
            pdf.set_text_color(*_LYRIC_RGB)
        pdf.cell(0, line_h, text, new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(path))


def _build_body(song: Song) -> list[tuple[str, str]]:
    """Lista de ``(tipo, texto)`` con tipo ∈ {'section','chord','lyric','blank'}."""
    out: list[tuple[str, str]] = []
    for section in song.sections:
        label = section.label or SECTION_LABELS.get(section.type, "")
        if label:
            out.append(("section", f"[{label}]"))
        for line in section.lines:
            chord_str, lyric_str = line_to_chord_lyric(line)
            if not chord_str and not lyric_str:
                out.append(("blank", ""))
                continue
            if chord_str:
                out.append(("chord", chord_str))
            if lyric_str:
                out.append(("lyric", lyric_str))
        out.append(("blank", ""))
    return out


def _fit_font_size(body: list[tuple[str, str]]) -> float:
    """Tamaño de fuente (pt) para que la línea más larga entre en el ancho útil."""
    longest = max((len(t) for k, t in body if k != "blank"), default=1)
    usable_mm = _A4_WIDTH_MM - 2 * _MARGIN
    fit = usable_mm / (max(longest, 1) * _CHAR_MM_PER_PT)
    return max(_MIN_PT, min(_MAX_PT, fit))
