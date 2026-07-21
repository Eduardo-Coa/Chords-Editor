"""Exportar una canción a PDF (cifrado monoespaciado) con fpdf2.

Un clic → archivo .pdf. Acordes en color sobre la letra en negro, en fuente
monoespaciada (Courier, embebida en el PDF) → la alineación de los acordes no se
corre en ningún visor. Reutiliza ``utils.song_text`` (mismo formato y encabezado
que el copiado al portapapeles).

Layout: el tamaño de fuente y el número de columnas (1 o 2) se eligen
**automáticamente** para que toda la canción entre en **una sola página** con la
fuente más grande posible. Se prefiere 1 columna a igualdad de tamaño; las
canciones largas pasan a 2 columnas (más capacidad vertical) para no derramar a
una segunda hoja. Si ni siquiera 2 columnas al mínimo legible alcanzan, el cuerpo
fluye a páginas adicionales sin romperse.
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
_RULE_RGB = (210, 210, 210)    # línea divisoria entre columnas
_MONO = "Courier"              # fuente núcleo del PDF: monoespaciada, sin bundlear
_SANS = "Helvetica"

# Geometría A4 vertical (mm).
_PAGE_W = 210.0
_PAGE_H = 297.0
_MARGIN = 15.0
_USABLE_W = _PAGE_W - 2 * _MARGIN   # 180 mm
_USABLE_H = _PAGE_H - 2 * _MARGIN   # 267 mm
_GUTTER = 8.0                       # canalón entre columnas

# Courier es monoespaciada: ancho de carácter = 0.6 em. 1 pt = 25.4/72 mm.
_MM_PER_PT = 25.4 / 72
_CHAR_MM_PER_PT = 0.6 * _MM_PER_PT
_LINE_SPACING = 1.25                # interlínea (alto de línea = tamaño × esto)
_MAX_PT = 11.0
_MIN_PT = 7.0
_STEP = 0.25                        # paso al buscar el tamaño que entra

# Un "bloque" es una lista de líneas (tipo, texto) que NO debe partirse entre
# columnas: un par acorde+letra, o un encabezado de sección con su primera línea.
Block = list[tuple[str, str]]


def song_to_pdf(song: Song, path: str | Path) -> None:
    """Genera el PDF de ``song`` en ``path`` (cifrado monoespaciado, claro)."""
    header = song_header_lines(song)
    blocks = _build_blocks(song)
    longest = max((len(t) for blk in blocks for _, t in blk), default=1)
    header_h = 9.0 + (6.0 if len(header) > 1 else 0.0) + 3.0  # título + subtítulo + hueco
    size, columns = _choose_layout(blocks, longest, header_h)

    line_h = size * _MM_PER_PT * _LINE_SPACING
    col_w = _col_width(columns)
    col_x = [_MARGIN + i * (col_w + _GUTTER) for i in range(columns)]
    bottom = _PAGE_H - _MARGIN

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.set_auto_page_break(auto=False)   # el flujo por columnas se gestiona a mano
    pdf.add_page()
    _draw_header(pdf, header)
    page_top = _MARGIN + header_h         # el contenido arranca debajo del encabezado
    _draw_dividers(pdf, columns, col_w, page_top, bottom)

    cur_col = 0
    y = page_top
    at_col_top = True
    for block in blocks:
        is_blank = block[0][0] == "blank"
        if at_col_top and is_blank:
            continue  # no abrir columna con una línea en blanco
        h = len(block) * line_h
        if y + h > bottom + 1e-6:         # no cabe en lo que queda de columna
            cur_col += 1
            if cur_col >= columns:        # se acabaron las columnas → página nueva
                pdf.add_page()
                cur_col = 0
                page_top = _MARGIN        # sin encabezado en páginas siguientes
                _draw_dividers(pdf, columns, col_w, page_top, bottom)
            y = page_top
            at_col_top = True
            if is_blank:
                continue
        _draw_block(pdf, block, col_x[cur_col], y, line_h, size, col_w)
        y += h
        at_col_top = False

    pdf.output(str(path))


def _col_width(columns: int) -> float:
    """Ancho útil de cada columna (mm) para ``columns`` columnas."""
    return (_USABLE_W - (columns - 1) * _GUTTER) / columns


def _draw_header(pdf: FPDF, header: list[str]) -> None:
    """Dibuja el encabezado (título + subtítulo) a todo el ancho, arriba."""
    pdf.set_xy(_MARGIN, _MARGIN)
    pdf.set_font(_SANS, "B", 16)
    pdf.set_text_color(*_LYRIC_RGB)
    pdf.cell(0, 9, header[0], new_x="LMARGIN", new_y="NEXT")
    if len(header) > 1:
        pdf.set_font(_SANS, "", 11)
        pdf.set_text_color(*_MUTED_RGB)
        pdf.cell(0, 6, header[1], new_x="LMARGIN", new_y="NEXT")


def _draw_dividers(pdf: FPDF, columns: int, col_w: float,
                   top: float, bottom: float) -> None:
    """Línea vertical tenue en el canalón entre columnas (solo si hay 2+)."""
    if columns < 2:
        return
    pdf.set_draw_color(*_RULE_RGB)
    pdf.set_line_width(0.2)
    for i in range(1, columns):
        x = _MARGIN + i * (col_w + _GUTTER) - _GUTTER / 2
        pdf.line(x, top, x, bottom)


def _draw_block(pdf: FPDF, block: Block, x: float, y: float,
                line_h: float, size: float, col_w: float) -> None:
    """Dibuja un bloque (1+ líneas) en la columna que empieza en ``x, y``."""
    yy = y
    for kind, text in block:
        if kind == "section":
            pdf.set_font(_MONO, "B", size)
            pdf.set_text_color(*_MUTED_RGB)
        elif kind == "chord":
            pdf.set_font(_MONO, "B", size)
            pdf.set_text_color(*_CHORD_RGB)
        else:  # lyric
            pdf.set_font(_MONO, "", size)
            pdf.set_text_color(*_LYRIC_RGB)
        pdf.set_xy(x, yy)
        pdf.cell(col_w, line_h, text)
        yy += line_h


def _build_blocks(song: Song) -> list[Block]:
    """Convierte la canción en bloques inseparables para el flujo por columnas.

    Cada par acorde+letra es un bloque (las líneas de una estrofa pueden repartirse
    entre columnas, pero un acorde nunca se separa de su letra). El encabezado de
    sección se pega a la primera línea de su sección para no quedar huérfano. Las
    líneas en blanco son bloques separadores de altura 1.
    """
    blocks: list[Block] = []
    for section in song.sections:
        label = section.label or SECTION_LABELS.get(section.type, "")
        pending: Block = [("section", f"[{label}]")] if label else []
        for line in section.lines:
            chord_str, lyric_str = line_to_chord_lyric(line)
            if not chord_str and not lyric_str:
                blocks.append([("blank", "")])
                continue
            lines: Block = []
            if chord_str:
                lines.append(("chord", chord_str))
            if lyric_str:
                lines.append(("lyric", lyric_str))
            if pending:                       # pegar el encabezado a la 1ª línea
                blocks.append(pending + lines)
                pending = []
            else:
                blocks.append(lines)
        if pending:                           # sección con etiqueta pero sin líneas
            blocks.append(pending)
        blocks.append([("blank", "")])        # separación entre secciones
    return blocks


def _choose_layout(blocks: list[Block], longest: int,
                   header_h: float) -> tuple[float, int]:
    """Elige ``(tamaño_pt, columnas)`` con la fuente más grande que entra en 1 página.

    Prueba 1 y 2 columnas; se queda con la que permita la fuente mayor, prefiriendo
    1 columna a igualdad. Si nada entra en una página ni con 2 columnas al mínimo,
    devuelve ``(_MIN_PT, 2)`` y el cuerpo fluye a páginas adicionales.
    """
    best_size = -1.0
    best_cols = 2
    for columns in (1, 2):
        size = _largest_fit(blocks, longest, columns, header_h)
        if size is not None and size > best_size + 1e-9:
            best_size = size
            best_cols = columns
    if best_size < 0:
        return _MIN_PT, 2
    return best_size, best_cols


def _largest_fit(blocks: list[Block], longest: int, columns: int,
                 header_h: float) -> float | None:
    """Mayor tamaño en [_MIN_PT, _MAX_PT] que entra en 1 página con ``columns``."""
    size = _MAX_PT
    while size >= _MIN_PT - 1e-9:
        if _width_fits(longest, size, columns) and \
                _packs_one_page(blocks, size, columns, header_h):
            return round(size, 2)
        size -= _STEP
    return None


def _width_fits(longest: int, size: float, columns: int) -> bool:
    """¿La línea más larga entra en el ancho de una columna a ``size`` pt?"""
    return longest * _CHAR_MM_PER_PT * size <= _col_width(columns) + 1e-6


def _packs_one_page(blocks: list[Block], size: float, columns: int,
                    header_h: float) -> bool:
    """Simula el flujo: ¿caben todos los bloques en ``columns`` en una página?"""
    line_h = size * _MM_PER_PT * _LINE_SPACING
    if line_h <= 0:
        return False
    lines_per_col = int((_USABLE_H - header_h) // line_h)
    if lines_per_col <= 0:
        return False
    col = 0
    used = 0
    for block in blocks:
        is_blank = block[0][0] == "blank"
        if used == 0 and is_blank:
            continue  # no abrir columna con una línea en blanco
        h = len(block)
        if h > lines_per_col:
            return False  # un bloque más alto que la columna nunca entra
        if used + h > lines_per_col:
            col += 1
            if col >= columns:
                return False
            used = 0
            if is_blank:
                continue
        used += h
    return True
