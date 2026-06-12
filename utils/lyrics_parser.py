"""Convierte texto de letra pegado en un modelo Song con sílabas."""

from __future__ import annotations
import re
from collections import defaultdict, deque

from models.song import Song, Section, Line, Syllable, Chord
from utils.syllabifier import syllabify

PUNCTUATION = set(",.;:!¡?¿…\"'()-—«»")

# Casillas que trae por defecto la línea de acordes al inicio de cada sección
# (para intros, interludios y la entrada de cada estrofa).
CHORD_LINE_SLOTS = 4

# Encabezado de sección: una línea que es solo [texto], ej. [Coro], [Estrofa 1]
SECTION_RE = re.compile(r"^\[(.+)\]$")

# Reconoce un acorde en notación americana (A–G), única que entiende el
# transpositor. La calidad/extensiones se limitan a un whitelist para que una
# palabra de la letra como "Gloria" no matchee como "G + loria".
CHORD_RE = re.compile(
    r"^[A-G][#b]?"                                          # raíz
    r"(?:maj|min|sus|dim|aug|add|m|M|°|\+|-|#|b|\d|\(|\))*"  # calidad/extensiones
    r"(?:/[A-G][#b]?)?$"                                     # bajo opcional
)


def is_chord_token(tok: str) -> bool:
    """True si el token aislado parece un acorde (notación americana)."""
    return bool(CHORD_RE.match(tok))


def is_chord_line_text(line: str) -> bool:
    """True si la línea de texto es de solo acordes (todos sus tokens lo son)."""
    tokens = line.split()
    return bool(tokens) and all(is_chord_token(t) for t in tokens)

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


# Encabezados "implícitos" sin corchetes que se reconocen al pegar la letra:
# una palabra clave sola (opcionalmente con ":") = encabezado de sección.
_IMPLICIT_SECTION_KEYWORDS = {
    "coro": ("Coro", "chorus"),
    "estribillo": ("Estribillo", "chorus"),
    "puente": ("Puente", "bridge"),
    "interludio": ("Interludio", "bridge"),
    "intro": ("Intro", "intro"),
    "introduccion": ("Intro", "intro"),
    "final": ("Final", "outro"),
    "outro": ("Final", "outro"),
    "coda": ("Coda", "outro"),
}

# "Estrofa 2" / "Verso 2" escrito como texto (con o sin número)
_VERSE_WORD_RE = re.compile(r"^(?:estrofa|verso)\s*(\d+)?$")


def detect_header(line: str) -> tuple[str, str] | None:
    """
    Detecta un encabezado de sección y devuelve (etiqueta, tipo), o None.

    Reconoce tres formas:
      - Explícita con corchetes:  ``[Coro]``, ``[Estrofa 1]``
      - Un número solo:           ``1`` → ("Estrofa 1", "verse")
      - Una palabra clave sola:   ``Coro:``, ``coro`` → ("Coro", "chorus")
    """
    stripped = line.strip()
    if not stripped:
        return None

    # Explícito: [texto]
    if is_section_header(stripped):
        return parse_section_header(stripped)

    # Quitar marcadores finales típicos: "Coro:", "1.", "2)"
    core = stripped.rstrip(".:)-").strip()
    if not core:
        return None

    # Número solo → Estrofa N
    if core.isdigit():
        return f"Estrofa {core}", "verse"

    normalized = _strip_accents(core.lower())

    # "Estrofa 2" / "Verso" escrito como texto
    verse_match = _VERSE_WORD_RE.match(normalized)
    if verse_match:
        num = verse_match.group(1)
        return (f"Estrofa {num}" if num else "Estrofa"), "verse"

    # Palabra clave conocida (coro, puente, intro, final, ...)
    if normalized in _IMPLICIT_SECTION_KEYWORDS:
        return _IMPLICIT_SECTION_KEYWORDS[normalized]

    return None


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


# ----------------------------------------------------------------------
# Alineación de acordes por columna (formato Cifra Club)
# ----------------------------------------------------------------------


def _runs(raw: str) -> list[tuple[int, str]]:
    """Devuelve las corridas de no-espacio como (columna_inicial, texto)."""
    result: list[tuple[int, str]] = []
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == " ":
            i += 1
            continue
        start = i
        while i < n and raw[i] != " ":
            i += 1
        result.append((start, raw[start:i]))
    return result


def _is_assignable(text: str) -> bool:
    """True si a la sílaba se le puede poner un acorde (tiene letra real)."""
    stripped = text.strip()
    return stripped != "" and any(c not in PUNCTUATION for c in stripped)


def _build_line_with_columns(raw: str, position: int) -> tuple[Line, list[int]]:
    """
    Como _parse_line pero conserva la columna inicial de cada sílaba en el
    texto crudo (sin descartar los espacios de sangría), para alinear acordes.
    """
    line = Line(id=None, position=position)
    cols: list[int] = []
    words = _runs(raw)
    pos = 0
    for wi, (start_col, word) in enumerate(words):
        parts = _split_word(word)
        if not parts:
            continue
        # Columna de cada parte dentro de la palabra (syllabify preserva caracteres)
        off = 0
        part_cols: list[int] = []
        for part in parts:
            part_cols.append(start_col + off)
            off += len(part)
        # Espacio de separación al final de la última parte (salvo última palabra)
        if wi < len(words) - 1:
            parts[-1] = parts[-1] + " "
        for part, col in zip(parts, part_cols):
            line.syllables.append(Syllable(id=None, position=pos, text=part))
            cols.append(col)
            pos += 1
    return line, cols


def _target_index(cols: list[int], syllables: list[Syllable], col: int) -> int | None:
    """
    Elige la sílaba (índice) a la que asignar un acorde ubicado en la columna
    ``col``: la que contiene esa columna; si cae en un espacio, la más cercana a
    la derecha; si está más allá de la última, la última sílaba asignable.
    """
    candidates: list[tuple[int, int, int]] = []  # (idx, start, end)
    for idx, syl in enumerate(syllables):
        if not _is_assignable(syl.text):
            continue
        start = cols[idx]
        end = start + len(syl.text.strip())
        candidates.append((idx, start, end))
    if not candidates:
        return None
    for idx, start, end in candidates:
        if start <= col < end:
            return idx
    right = [c for c in candidates if c[1] >= col]
    if right:
        return min(right, key=lambda c: c[1])[0]
    return candidates[-1][0]


def _attach_chords(chord_raw: str, lyric_raw: str, position: int) -> Line:
    """Construye una línea de letra con los acordes de ``chord_raw`` alineados."""
    line, cols = _build_line_with_columns(lyric_raw, position)
    chords = _runs(chord_raw)
    if not line.syllables:
        return _filled_chord_line([t for _, t in chords], position)

    for col, token in chords:
        idx = _target_index(cols, line.syllables, col)
        if idx is None:
            continue
        if line.syllables[idx].chord is not None:
            # Colisión: dos acordes sobre la misma sílaba → casilla intercalada
            slot = Syllable(id=None, position=0, text="")
            line.syllables.insert(idx + 1, slot)
            cols.insert(idx + 1, col)
            slot.chord = Chord(id=None, value=token)
        else:
            line.syllables[idx].chord = Chord(id=None, value=token)

    for pos, syl in enumerate(line.syllables):
        syl.position = pos
    return line


def _filled_chord_line(tokens: list[str], position: int) -> Line:
    """Línea de solo acordes (slots vacíos) con los acordes en orden."""
    line = Line(id=None, position=position)
    n = max(len(tokens), CHORD_LINE_SLOTS)
    for i in range(n):
        syl = Syllable(id=None, position=i, text="")
        if i < len(tokens):
            syl.chord = Chord(id=None, value=tokens[i])
        line.syllables.append(syl)
    return line


def parse_lyrics(text: str, title: str = "Sin título") -> Song:
    """
    Construye una Song a partir del texto pegado.

    Los encabezados [Coro], [Estrofa 1], etc. abren nuevas secciones. La letra
    anterior al primer encabezado va en una sección por defecto (verse, sin
    etiqueta). Las líneas vacías se conservan como separadores (Line sin sílabas).

    Si el texto trae líneas de acordes alineadas por columna encima de la letra
    (formato Cifra Club), los acordes se asignan automáticamente a la sílaba
    correspondiente. Una línea de acordes sin letra debajo se trata como pasaje
    instrumental (línea de casillas). Cuando no hay acordes en el texto, cada
    sección arranca con una línea de casillas vacías para llenar a mano.
    """
    raw_lines = text.split("\n")
    has_chords = any(
        detect_header(rl) is None and is_chord_line_text(rl)
        for rl in raw_lines
    )

    song = Song(id=None, title=title)
    current: Section | None = None
    counters = {"section": 0, "line": 0}

    def start_section(label: str | None, section_type: str) -> Section:
        section = Section(
            id=None, position=counters["section"], type=section_type, label=label
        )
        if not has_chords:
            # Sin acordes en el texto: casillas vacías al inicio (flujo clásico)
            section.lines.append(_make_chord_line(0))
            counters["line"] = 1
        else:
            counters["line"] = 0
        song.sections.append(section)
        counters["section"] += 1
        return section

    i, n = 0, len(raw_lines)
    while i < n:
        raw = raw_lines[i]
        stripped = raw.strip()

        header = detect_header(stripped)
        if header is not None:
            current = start_section(header[0], header[1])
            i += 1
            continue

        if has_chords and stripped and is_chord_line_text(raw):
            # Buscar la línea de letra debajo, saltando líneas en blanco
            # intermedias (algunas exportaciones dejan un espacio entre la fila
            # de acordes y su letra).
            j = i + 1
            while j < n and raw_lines[j].strip() == "":
                j += 1
            cand_raw = raw_lines[j] if j < n else ""
            cand_stripped = cand_raw.strip()
            is_lyric_below = (
                cand_stripped != ""
                and not is_section_header(cand_stripped)
                and not is_chord_line_text(cand_raw)
            )
            if current is None:
                current = start_section(None, "verse")
            if is_lyric_below:
                current.lines.append(_attach_chords(raw, cand_raw, counters["line"]))
                counters["line"] += 1
                i = j + 1  # consume acordes, blancos intermedios y la letra
            else:
                tokens = [t for _, t in _runs(raw)]
                current.lines.append(_filled_chord_line(tokens, counters["line"]))
                counters["line"] += 1
                i += 1
            continue

        if current is None:
            # Letra antes de cualquier encabezado: sección por defecto sin etiqueta
            current = start_section(None, "verse")

        # Omitir líneas en blanco al inicio de una sección (justo tras su encabezado)
        only_chord_line = (
            len(current.lines) == 1 and is_chord_line(current.lines[0])
        )
        if not stripped and (only_chord_line or not current.lines):
            i += 1
            continue

        current.lines.append(_parse_line(stripped, counters["line"]))
        counters["line"] += 1
        i += 1

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
