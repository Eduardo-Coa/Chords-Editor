"""Convierte texto de letra pegado en un modelo Song con sílabas."""

from __future__ import annotations
import re
from collections import defaultdict, deque

from models.song import Song, Section, Line, Syllable
from utils.syllabifier import syllabify

PUNCTUATION = set(",.;:!¡?¿…\"'()-—«»")

# Ranuras vacías al final de cada línea para acordes de paso/enlace
# (notas entre líneas que no van sobre ninguna sílaba, ej: (D7) antes de G).
TRAILING_NOTE_SLOTS = 4

# Encabezado de sección: una línea que es solo [texto], ej. [Coro], [Estrofa 1]
SECTION_RE = re.compile(r"^\[(.+)\]$")

# Palabras clave para inferir el tipo de sección a partir de su etiqueta.
# El primer tipo cuya palabra clave aparezca en la etiqueta gana.
SECTION_TYPE_KEYWORDS = [
    ("chorus", ("coro", "chorus", "estribillo")),
    ("bridge", ("puente", "bridge")),
    ("intro", ("intro",)),
    ("outro", ("final", "outro", "coda")),
    ("verse", ("estrofa", "verso", "verse")),
]


def _strip_accents(text: str) -> str:
    """Quita tildes para comparar palabras clave de sección."""
    return text.translate(str.maketrans("áéíóúü", "aeiouu"))


def is_section_header(line: str) -> bool:
    """Devuelve True si la línea es un encabezado de sección tipo [Coro]."""
    return bool(SECTION_RE.match(line.strip()))


def parse_section_header(line: str) -> tuple[str, str]:
    """
    Extrae (etiqueta, tipo) de un encabezado [texto].
    El tipo se infiere por palabras clave; por defecto 'verse'.
    """
    match = SECTION_RE.match(line.strip())
    label = match.group(1).strip() if match else line.strip()
    normalized = _strip_accents(label.lower())
    for section_type, keywords in SECTION_TYPE_KEYWORDS:
        if any(k in normalized for k in keywords):
            return label, section_type
    return label, "verse"


def _split_word(word: str) -> list[str]:
    """
    Separa un 'word' en partes: puntuación inicial, sílabas del núcleo y
    puntuación final, cada una como string independiente.
    """
    leading = ""
    while word and word[0] in PUNCTUATION:
        leading += word[0]
        word = word[1:]

    trailing = ""
    while word and word[-1] in PUNCTUATION:
        trailing = word[-1] + trailing
        word = word[:-1]

    parts: list[str] = []
    if leading:
        parts.append(leading)
    if word:
        parts.extend(syllabify(word))
    if trailing:
        parts.append(trailing)
    return parts


def _parse_line(text: str, position: int) -> Line:
    """Convierte una línea de texto en un Line con sus sílabas."""
    line = Line(id=None, position=position)

    words = [w for w in text.split(" ") if w != ""]
    pos = 0
    for wi, word in enumerate(words):
        parts = _split_word(word)
        if not parts:
            continue
        # Separar palabras con un espacio al final de la última parte
        if wi < len(words) - 1:
            parts[-1] = parts[-1] + " "
        for part in parts:
            line.syllables.append(Syllable(id=None, position=pos, text=part))
            pos += 1

    # Ranuras de acordes de paso al final de la línea (solo si hay contenido)
    if line.syllables:
        for _ in range(TRAILING_NOTE_SLOTS):
            line.syllables.append(Syllable(id=None, position=pos, text=""))
            pos += 1
    return line


def parse_lyrics(text: str, title: str = "Sin título") -> Song:
    """
    Construye una Song a partir del texto pegado.

    Los encabezados [Coro], [Estrofa 1], etc. abren nuevas secciones. La letra
    anterior al primer encabezado va en una sección por defecto (verse, sin
    etiqueta). Las líneas vacías se conservan como separadores (Line sin sílabas).
    """
    song = Song(id=None, title=title)
    current: Section | None = None
    section_pos = 0
    line_pos = 0

    for raw_line in text.split("\n"):
        stripped = raw_line.strip()

        if is_section_header(stripped):
            label, section_type = parse_section_header(stripped)
            current = Section(id=None, position=section_pos, type=section_type, label=label)
            song.sections.append(current)
            section_pos += 1
            line_pos = 0
            continue

        if current is None:
            # Letra antes de cualquier encabezado: sección por defecto sin etiqueta
            current = Section(id=None, position=section_pos, type="verse", label=None)
            song.sections.append(current)
            section_pos += 1
            line_pos = 0

        current.lines.append(_parse_line(stripped, line_pos))
        line_pos += 1

    if not song.sections:
        song.sections.append(Section(id=None, position=0, type="verse", label=None))

    return song


def _line_text(line: Line) -> str:
    """Texto plano de una línea (une las sílabas, sin espacios sobrantes)."""
    return "".join(s.text for s in line.syllables).strip()


def merge_lyrics(existing: Song, new_text: str) -> Song:
    """
    Reprocesa la letra conservando los acordes de las líneas que no cambiaron.

    Devuelve una Song con el mismo id y metadatos de ``existing`` pero con la
    estructura de ``new_text``. Las líneas cuyo texto coincide reutilizan sus
    sílabas (con acordes); las nuevas o modificadas se silabifican sin acordes.
    El emparejado es por orden, así las líneas repetidas (ej. un coro) se asignan
    una a una en secuencia.
    """
    old_by_text: dict[str, deque[Line]] = defaultdict(deque)
    for section in existing.sections:
        for line in section.lines:
            text = _line_text(line)
            if text:
                old_by_text[text].append(line)

    merged = parse_lyrics(new_text, title=existing.title)
    merged.id = existing.id
    merged.author = existing.author
    merged.key = existing.key
    merged.rhythm = existing.rhythm
    merged.capo = existing.capo
    merged.notes = existing.notes

    for section in merged.sections:
        for line in section.lines:
            text = _line_text(line)
            if text and old_by_text.get(text):
                old_line = old_by_text[text].popleft()
                line.syllables = old_line.syllables  # conserva acordes

    return merged
