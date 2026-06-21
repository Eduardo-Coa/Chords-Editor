"""Exportar e importar canciones como archivos .hymnchords (JSON).

Formato de intercambio para pasar una canción entre usuarios de la app. La fuente
de verdad sigue siendo SQLite; esto es solo una capa de transporte por encima.

El JSON NO incluye los ``id`` de base de datos ni las ``position`` (el orden de las
listas las reconstruye), de modo que al importar la canción entra siempre como
nueva (``id`` en None → INSERT). Se exporta el tono ORIGINAL guardado: la
transposición de la UI es solo visual y no afecta al archivo.
"""

from __future__ import annotations
import json
import re
from pathlib import Path

from models.song import Song, Section, Line, Syllable, Chord

# Identificador y versión del formato (subir la versión al cambiar el esquema).
FORMAT_NAME = "hymnchords-song"
FORMAT_VERSION = 1

# Extensión de los archivos de canción exportados.
SONG_FILE_EXTENSION = ".hymnchords"

# Tipos de sección válidos: deben coincidir con el CHECK de la tabla `sections`.
_VALID_SECTION_TYPES = {"verse", "chorus", "bridge", "intro", "outro"}

# Caracteres no permitidos en nombres de archivo en Windows.
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


class SongIOError(Exception):
    """Error al exportar o importar una canción (formato inválido, archivo dañado…)."""


# ----------------------------------------------------------------------
# Modelo <-> dict
# ----------------------------------------------------------------------

def song_to_dict(song: Song) -> dict:
    """Serializa una canción a un dict portable (sin ``id`` ni ``position``)."""
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "title": song.title,
        "author": song.author,
        "key": song.key,
        "rhythm": song.rhythm,
        "capo": song.capo,
        "notes": song.notes,
        "sections": [
            {
                "type": section.type,
                "label": section.label,
                "transpose": section.transpose,
                "lines": [
                    {
                        "syllables": [
                            {
                                "text": syl.text,
                                "chord": syl.chord.value if syl.chord else None,
                            }
                            for syl in line.syllables
                        ],
                    }
                    for line in section.lines
                ],
            }
            for section in song.sections
        ],
    }


def dict_to_song(data: dict) -> Song:
    """Reconstruye una canción desde un dict, con todos los ``id`` en None.

    Valida el formato, la versión y los tipos de sección. Lanza ``SongIOError``
    con un mensaje legible si algo no encaja.
    """
    if not isinstance(data, dict):
        raise SongIOError("El archivo no contiene una canción válida.")
    if data.get("format") != FORMAT_NAME:
        raise SongIOError("El archivo no es una canción de HymnChords.")

    version = data.get("version")
    if not isinstance(version, int) or version > FORMAT_VERSION:
        raise SongIOError(
            f"Versión de archivo no compatible (v{version}). "
            "Actualiza HymnChords para abrir esta canción."
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SongIOError("La canción no tiene título.")

    song = Song(
        id=None,
        title=title.strip(),
        author=_opt_str(data.get("author")),
        key=_opt_str(data.get("key")),
        rhythm=_opt_str(data.get("rhythm")),
        capo=_as_int(data.get("capo"), default=0),
        notes=_opt_str(data.get("notes")),
    )

    for position, sec_data in enumerate(data.get("sections", [])):
        song.sections.append(_section_from_dict(sec_data, position))
    return song


def _section_from_dict(data: dict, position: int) -> Section:
    """Reconstruye una sección validando su tipo contra el enum permitido."""
    if not isinstance(data, dict):
        raise SongIOError("Sección con formato inválido.")
    sec_type = data.get("type")
    if sec_type not in _VALID_SECTION_TYPES:
        raise SongIOError(f"Tipo de sección desconocido: {sec_type!r}.")

    section = Section(
        id=None,
        position=position,
        type=sec_type,
        label=_opt_str(data.get("label")),
        transpose=_as_int(data.get("transpose"), default=0),
    )
    for line_pos, line_data in enumerate(data.get("lines", [])):
        line = Line(id=None, position=line_pos)
        for syl_pos, syl_data in enumerate(line_data.get("syllables", [])):
            chord_value = syl_data.get("chord")
            chord = Chord(id=None, value=chord_value) if chord_value else None
            line.syllables.append(
                Syllable(
                    id=None,
                    position=syl_pos,
                    text=str(syl_data.get("text", "")),
                    chord=chord,
                )
            )
        section.lines.append(line)
    return section


def _opt_str(value: object) -> str | None:
    """Normaliza a ``str | None``: cadenas vacías o espacios → None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: object, default: int = 0) -> int:
    """Convierte a int de forma tolerante; usa ``default`` si no es un número."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------
# Archivo <-> disco
# ----------------------------------------------------------------------

def export_song(song: Song, path: str | Path) -> None:
    """Escribe la canción como JSON UTF-8 (acentos legibles) en ``path``."""
    data = song_to_dict(song)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        raise SongIOError(f"No se pudo guardar el archivo: {exc}") from exc


def import_song(path: str | Path) -> Song:
    """Lee y reconstruye una canción desde un archivo ``.hymnchords``."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except OSError as exc:
        raise SongIOError(f"No se pudo abrir el archivo: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SongIOError("El archivo está dañado o no es un JSON válido.") from exc
    return dict_to_song(raw)


def suggested_filename(song: Song) -> str:
    """Nombre de archivo sugerido al exportar (título saneado + extensión)."""
    base = _INVALID_FILENAME_CHARS.sub("_", song.title).strip() or "cancion"
    return base + SONG_FILE_EXTENSION
