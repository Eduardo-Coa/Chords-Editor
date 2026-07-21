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

# Sección de introducción que se antepone a cada canción nueva: dos líneas de
# CINCO casillas vacías (se muestran como guiones) para anotar los acordes de la
# entrada. Se llama «Introducción» y es de tipo 'intro'.
INTRO_LABEL = "Introducción"
INTRO_LINES = 2
INTRO_SLOTS = 5


def make_intro_section(position: int = 0) -> Section:
    """Crea la sección «Introducción»: 2 líneas de 5 casillas vacías (guiones)."""
    intro = Section(id=None, position=position, type="intro",
                    label=INTRO_LABEL, transpose=0)
    for line_pos in range(INTRO_LINES):
        line = Line(id=None, position=line_pos)
        for slot in range(INTRO_SLOTS):
            line.syllables.append(Syllable(id=None, position=slot, text="", chord=None))
        intro.lines.append(line)
    return intro


def prepend_intro(song: Song) -> Song:
    """Antepone la «Introducción» a la canción y renumera las posiciones. Muta ``song``.

    Si la canción ya empieza con una «Introducción» (p. ej. porque el texto traía
    un bloque de acordes al inicio), no se antepone otra.
    """
    first = song.sections[0] if song.sections else None
    already = (first is not None
               and first.type == "intro" and first.label == INTRO_LABEL)
    if not already:
        song.sections.insert(0, make_intro_section())
    for pos, section in enumerate(song.sections):
        section.position = pos
    return song

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


# Un token que es solo guiones («-», «–», «—») se usa como separador entre
# acordes de una secuencia («G - Bm - A»); no es un acorde ni letra.
_SEPARATOR_RE = re.compile(r"^[-–—]+$")


# Acorde ENVUELTO en paréntesis: «(G)», convención habitual para un acorde opcional
# o de paso. Ojo: no confundir con los paréntesis INTERNOS de «C(add9)», que CHORD_RE
# ya acepta y este patrón no toca (no empiezan con «(»).
_PAREN_CHORD_RE = re.compile(r"^\((.+)\)$")


def bare_chord(tok: str) -> str:
    """Quita los paréntesis que envuelven a un acorde opcional: «(G)» → «G».

    Se guarda SIN paréntesis a propósito: ``transpose_chord("(G)")`` devuelve el
    acorde igual, así que con ellos se quedaría sin transponer mientras el resto de
    la canción sí cambia de tono.
    """
    m = _PAREN_CHORD_RE.match(tok)
    return m.group(1) if m else tok


def is_chord_token(tok: str) -> bool:
    """True si el token aislado parece un acorde (notación americana), aceptándolo
    también entre paréntesis («(G)»)."""
    return bool(CHORD_RE.match(bare_chord(tok)))


def _is_separator_token(tok: str) -> bool:
    """True si el token es solo guiones (separador de una secuencia de acordes)."""
    return bool(_SEPARATOR_RE.match(tok))


def is_chord_line_text(line: str) -> bool:
    """True si la línea es de solo acordes (ignorando guiones separadores).

    Reconoce tanto acordes alineados por columna («G      Bm») como secuencias
    separadas por guiones («G - Bm - A - D - A»); en ambos casos todos los tokens
    que no son separadores deben parecer acordes.
    """
    tokens = [t for t in line.split() if not _is_separator_token(t)]
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


def _repair_unmatched_brackets(line: str) -> str:
    """Completa un corchete sin pareja: «Intro]» o «[Intro» → «[Intro]».

    Perder un corchete al copiar de una web es un accidente muy común, y sin pareja el
    encabezado no se reconocía: la línea entraba como LETRA, lo que abría una estrofa
    sin etiqueta Y desviaba el bloque de acordes siguiente a un «Interludio».

    Solo actúa cuando hay EXACTAMENTE uno de los dos corchetes; con ambos (o con
    ninguno) la línea ya se interpreta bien y se devuelve intacta.
    """
    abre, cierra = line.startswith("["), line.endswith("]")
    if abre == cierra:
        return line
    nucleo = (line[1:] if abre else line[:-1]).strip()
    return f"[{nucleo}]" if nucleo else line


# Secciones de «casillas» (solo acordes, sin letra): introducción e interludio.
# Ambas son de tipo 'intro' y se muestran con guiones; el label las distingue.
# La primera palabra de la etiqueta decide (así «Interludio 2» también cuenta).
_SLOT_SECTION = {
    "intro": ("Introducción", "intro"),
    "introduccion": ("Introducción", "intro"),
    "inter": ("Interludio", "intro"),
    "interludio": ("Interludio", "intro"),
}


def _slot_section_header(normalized_label: str) -> tuple[str, str] | None:
    """(label canónico, 'intro') si la etiqueta es intro/interludio; si no, None."""
    parts = normalized_label.split()
    return _SLOT_SECTION.get(parts[0]) if parts else None


def parse_section_header(line: str) -> tuple[str, str]:
    """
    Extrae (etiqueta, tipo) de un encabezado [texto].
    El tipo se infiere por palabras clave; por defecto 'verse'.
    """
    match = SECTION_RE.match(line.strip())
    label = match.group(1).strip() if match else line.strip()
    normalized = _strip_accents(label.lower())
    slot = _slot_section_header(normalized)
    if slot is not None:
        return slot
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
    # intro/interludio → sección de casillas (tipo 'intro', se muestran con guiones)
    "interludio": ("Interludio", "intro"),
    "inter": ("Interludio", "intro"),
    "intro": ("Introducción", "intro"),
    "introduccion": ("Introducción", "intro"),
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
    # Un corchete sin pareja se completa antes de nada: casi siempre es un encabezado
    # copiado a medias, no letra (ver _repair_unmatched_brackets).
    stripped = _repair_unmatched_brackets(stripped)

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


def _chord_tokens(raw: str) -> list[str]:
    """Acordes de una línea suelta, en orden, descartando guiones separadores."""
    return [t for _, t in _runs(raw) if not _is_separator_token(t)]


def _has_lyric(section: Section) -> bool:
    """True si la sección ya tiene alguna línea de letra real (no casillas/blancos)."""
    return any(l.syllables and not is_chord_line(l) for l in section.lines)


def _is_dash_sequence(raw: str) -> bool:
    """True si la línea de acordes usa guiones («G - Bm - A»): es instrumental."""
    return any(_is_separator_token(t) for t in raw.split())


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
    chords = [(c, t) for c, t in _runs(chord_raw) if not _is_separator_token(t)]
    if not line.syllables:
        return _filled_chord_line([t for _, t in chords], position)

    # Un acorde que empieza más allá del último carácter del verso NO tiene letra
    # debajo: es un acorde suelto (final de frase). Se le da su propia casilla AL
    # FINAL del renglón, en orden. Antes caían sobre la última sílaba *asignable*, lo
    # que los pegaba a la última palabra o —si chocaban— metía la casilla ANTES del
    # signo de puntuación, partiendo «true?» en «true» + casilla + «?».
    fin_letra = len(lyric_raw.rstrip())
    sueltos = [t for c, t in chords if c >= fin_letra]

    for col, token in chords:
        if col >= fin_letra:
            continue                     # se agrega al final, después del bucle
        idx = _target_index(cols, line.syllables, col)
        if idx is None:
            continue
        if line.syllables[idx].chord is not None:
            # Colisión: dos acordes sobre la misma sílaba → casilla intercalada
            slot = Syllable(id=None, position=0, text="")
            line.syllables.insert(idx + 1, slot)
            cols.insert(idx + 1, col)
            slot.chord = Chord(id=None, value=bare_chord(token))
        else:
            line.syllables[idx].chord = Chord(id=None, value=bare_chord(token))

    for token in sueltos:
        slot = Syllable(id=None, position=0, text="")
        slot.chord = Chord(id=None, value=bare_chord(token))
        line.syllables.append(slot)

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
            syl.chord = Chord(id=None, value=bare_chord(tokens[i]))
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
    # Las líneas en blanco de ARRIBA se descartan: como todavía no hay sección abierta,
    # la primera hacía que el parser creara una «Estrofa» sin etiqueta para colgarla y,
    # aunque después la línea se descartaba, la sección fantasma quedaba. Cuenta también
    # la línea de solo espacios (muy fácil de arrastrar al copiar de una web). En el
    # MEDIO del texto no se tocan: ahí separan estrofas.
    while raw_lines and not raw_lines[0].strip():
        raw_lines.pop(0)
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
        if section_type == "intro" and not has_chords:
            # Sección de casillas (intro/interludio) sin acordes en el texto:
            # 2 líneas de 5 casillas vacías para llenar a mano.
            for line_pos in range(INTRO_LINES):
                line = Line(id=None, position=line_pos)
                for slot in range(INTRO_SLOTS):
                    line.syllables.append(Syllable(id=None, position=slot, text=""))
                section.lines.append(line)
            counters["line"] = INTRO_LINES
        elif section_type != "intro" and not has_chords:
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
            # Una secuencia con guiones («G - Bm - A») es siempre instrumental: no se
            # pega a ninguna letra. Los acordes alineados por columna (Cifra Club)
            # buscan su letra: directamente debajo, o —si primero viene un encabezado—
            # la primera línea de letra de esa sección.
            if not _is_dash_sequence(raw):
                j = i + 1
                while j < n and raw_lines[j].strip() == "":
                    j += 1
                cand_raw = raw_lines[j] if j < n else ""
                cand = cand_raw.strip()

                # 1) Letra directamente debajo → pegar los acordes ahí (nunca dentro
                #    de una sección de casillas, que solo llevan acordes).
                if cand and detect_header(cand) is None and not is_chord_line_text(cand_raw):
                    if current is None or current.type == "intro":
                        current = start_section(None, "verse")
                    current.lines.append(_attach_chords(raw, cand_raw, counters["line"]))
                    counters["line"] += 1
                    i = j + 1
                    continue

                # 2) Un encabezado y, tras él, una línea de letra → los acordes son la
                #    entrada de esa sección: se abre y se pegan a su primera letra. NO
                #    forman interludio (el interludio es una línea de acordes SIN letra).
                header = detect_header(cand) if cand else None
                if header is not None and header[1] != "intro":
                    k = j + 1
                    while k < n and raw_lines[k].strip() == "":
                        k += 1
                    after_raw = raw_lines[k] if k < n else ""
                    after = after_raw.strip()
                    if (after and detect_header(after) is None
                            and not is_chord_line_text(after_raw)):
                        current = start_section(header[0], header[1])
                        current.lines.append(
                            _attach_chords(raw, after_raw, counters["line"]))
                        counters["line"] += 1
                        i = k + 1
                        continue

            # 3) Bloque de acordes suelto, sin letra asociada: se clasifica por
            #    posición. Al inicio de la canción → Introducción; entre estrofas (ya
            #    hay letra antes) → Interludio; justo bajo un encabezado que aún no
            #    tiene letra ([Final], [Intro parte 2]) → llena esa sección.
            if current is None:
                current = start_section(INTRO_LABEL, "intro")
            elif _has_lyric(current):
                current = start_section("Interludio", "intro")
            current.lines.append(
                _filled_chord_line(_chord_tokens(raw), counters["line"]))
            counters["line"] += 1
            i += 1
            continue

        if current is None:
            # Letra antes de cualquier encabezado: sección por defecto sin etiqueta
            current = start_section(None, "verse")
        elif current.type == "intro" and stripped:
            # Las secciones de casillas (intro/interludio) no llevan letra: una
            # línea de letra que sigue a un bloque de acordes abre una estrofa.
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
    merged.original_key = existing.original_key
    merged.rhythm = existing.rhythm
    merged.capo = existing.capo
    merged.notes = existing.notes

    for section in merged.sections:
        for line in section.lines:
            text = _line_text(line)
            if text and old_by_text.get(text):
                old_line = old_by_text[text].popleft()
                line.syllables = old_line.syllables  # conserva acordes

    # La «Introducción» prependida no aparece en el texto editable: se separa para
    # que la alineación por índice con el resto de secciones cuadre, y se repone al
    # frente al final (con sus acordes intactos).
    intro = next((s for s in existing.sections
                  if s.type == "intro" and s.label == INTRO_LABEL), None)
    existing_body = [s for s in existing.sections if s is not intro]

    # Recuperar acordes de las casillas que quedaron VACÍAS (p. ej. la entrada de
    # una sección, que no viaja en el texto), emparejando por índice de sección.
    # Los acordes que ya vienen del texto (interludios que el usuario ve/edita) NO
    # se tocan: solo se consideran casillas viejas que tenían acordes.
    for idx, new_section in enumerate(merged.sections):
        if idx >= len(existing_body):
            break
        old_chord_lines = deque(
            l for l in existing_body[idx].lines
            if is_chord_line(l) and any(s.chord for s in l.syllables))
        for i, line in enumerate(new_section.lines):
            already = any(s.chord for s in line.syllables)
            if is_chord_line(line) and not already and old_chord_lines:
                new_section.lines[i] = old_chord_lines.popleft()

    if intro is not None:
        merged.sections = [intro] + [
            s for s in merged.sections
            if not (s.type == "intro" and s.label == INTRO_LABEL)
        ]
    for pos, section in enumerate(merged.sections):
        section.position = pos

    return merged
