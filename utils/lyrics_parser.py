"""Convierte texto de letra pegado en un modelo Song con sílabas."""

from __future__ import annotations
import re
from collections import defaultdict, deque

from models.song import Song, Section, Line, Syllable
from utils.syllabifier import syllabify

PUNCTUATION = set(",.;:!¡?¿…\"'()-—«»")

# Casillas que trae por defecto la línea de acordes al inicio de cada sección
# (para intros, interludios y la entrada de cada estrofa).
CHORD_LINE_SLOTS = 4

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


def is_chord_line(line: Line) -> bool:
    """True si la línea es de solo acordes (todas sus casillas vacías, sin letra)."""
    return bool(line.syllables) and all(s.text.strip() == "" for s in line.syllables)


def _make_chord_line(position: int) -> Line:
    """Crea una línea de acordes con CHORD_LINE_SLOTS casillas vacías."""
    line = Line(id=None, position=position)
    for i in range(CHORD_LINE_SLOTS):
        line.syllables.append(Syllable(id=None, position=i, text=""))
    return line


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
    counters = {"section": 0, "line": 0}

    def start_section(label: str | None, section_type: str) -> Section:
        section = Section(
            id=None, position=counters["section"], type=section_type, label=label
        )
        # Cada sección arranca con una línea de acordes (intro/interludio/entrada)
        section.lines.append(_make_chord_line(0))
        song.sections.append(section)
        counters["section"] += 1
        counters["line"] = 1  # las líneas de letra van después de la de acordes
        return section

    for raw_line in text.split("\n"):
        stripped = raw_line.strip()

        if is_section_header(stripped):
            label, section_type = parse_section_header(stripped)
            current = start_section(label, section_type)
            continue

        if current is None:
            # Letra antes de cualquier encabezado: sección por defecto sin etiqueta
            current = start_section(None, "verse")

        current.lines.append(_parse_line(stripped, counters["line"]))
        counters["line"] += 1

    if not song.sections:
        start_section(None, "verse")

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

    # Las líneas de acordes (sin texto) se emparejan por sección, no por texto
    for idx, new_section in enumerate(merged.sections):
        if idx >= len(existing.sections):
            break
        old_chord_line = next(
            (l for l in existing.sections[idx].lines if is_chord_line(l)), None
        )
        if old_chord_line is None:
            continue
        for i, line in enumerate(new_section.lines):
            if is_chord_line(line):
                new_section.lines[i] = old_chord_line  # conserva sus acordes
                break

    return merged
