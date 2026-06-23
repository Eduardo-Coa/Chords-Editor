"""Representación de una canción como texto monoespaciado (acordes sobre la letra).

Fuente única de verdad para: el render de la vista escenario, copiar al
portapapeles, y (a futuro) el export a HTML/PDF. La fila de acordes se alinea por
columnas con la fila de letra — el formato estándar de cifrado (Cifra Club,
Ultimate Guitar) y reimportable por ``utils.lyrics_parser``.
"""

from __future__ import annotations

from models.song import Song, Line

# Etiquetas legibles para cada tipo de sección (encabezados [Sección]).
SECTION_LABELS = {
    "verse": "Estrofa",
    "chorus": "Coro",
    "bridge": "Puente",
    "intro": "Intro",
    "outro": "Final",
}


def line_to_chord_lyric(line: Line) -> tuple[str, str]:
    """Devuelve (fila_de_acordes, fila_de_letra) alineadas por columnas.

    Cada acorde queda justo encima del inicio de su sílaba: la columna donde
    empieza una sílaba en la letra unida es ``len(lyric_str)``.
    """
    chord_str = ""
    lyric_str = ""
    for syllable in line.syllables:
        value = syllable.chord.value if syllable.chord else ""
        if value:
            if len(chord_str) < len(lyric_str):
                chord_str += " " * (len(lyric_str) - len(chord_str))
            elif chord_str:
                chord_str += " "  # evita que dos acordes se peguen
            chord_str += value
        lyric_str += syllable.text
    return chord_str.rstrip(), lyric_str.rstrip()


def song_header_lines(song: Song) -> list[str]:
    """Encabezado de la canción: ``[título, "autor · Tono · Ritmo · Capo"]``.

    Cada campo aparece solo si está disponible (autor, tono, ritmo; capo solo si
    es distinto de 0). Reutilizado por el copiado al portapapeles y el export a PDF.
    """
    lines = [song.title]
    info: list[str] = []
    if song.author:
        info.append(song.author)
    if song.key:
        info.append(f"Tono: {song.key}")
    if song.rhythm:
        info.append(f"Ritmo: {song.rhythm}")
    if song.capo:  # solo si usa capo (capo != 0)
        info.append(f"Capo: traste {song.capo}")
    if info:
        lines.append(" · ".join(info))
    return lines


def song_to_text(song: Song, metadata: bool = False) -> str:
    """Canción completa como texto monoespaciado, con encabezados ``[Sección]``.

    Preserva las líneas vacías como separadores entre estrofas. Las líneas de solo
    acordes (intro/interludio) salen como una sola fila de acordes. Si ``metadata``
    es True, antepone un encabezado con título, autor, tono y —si usa capo— el traste.
    """
    out: list[str] = []
    if metadata:
        out.extend(song_header_lines(song))
        out.append("")  # línea en blanco entre el encabezado y la letra
    for section in song.sections:
        label = section.label or SECTION_LABELS.get(section.type, "")
        if label:
            out.append(f"[{label}]")
        for line in section.lines:
            chord_str, lyric_str = line_to_chord_lyric(line)
            if not chord_str and not lyric_str:
                out.append("")  # línea vacía: separador entre estrofas
                continue
            if chord_str:
                out.append(chord_str)
            if lyric_str:
                out.append(lyric_str)
        out.append("")  # separación entre secciones
    return "\n".join(out).strip() + "\n"
