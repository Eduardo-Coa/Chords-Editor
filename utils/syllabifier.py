"""Silabificación de palabras en español sin dependencias externas."""

from __future__ import annotations

VOWELS = set("aeiouáéíóúüAEIOUÁÉÍÓÚÜ")

DIPHTHONGS = {
    "ia", "ie", "io", "ua", "ue", "ui", "uo",
    "ai", "ei", "oi", "au", "eu", "ou",
}

# Grupos consonánticos que nunca se separan (van siempre con la vocal siguiente)
INSEPARABLE = {
    "bl", "br", "cl", "cr", "dr",
    "fl", "fr", "gl", "gr", "pl", "pr", "tr",
}

# Dígrafos que actúan como consonante única
DIGRAPHS = {"ch", "ll", "rr"}


def _is_vowel(c: str) -> bool:
    return c in VOWELS


def _normalize_vowel(c: str) -> str:
    """Quita tilde para comparar pares de vocales en diptongos."""
    return c.lower().translate(str.maketrans("áéíóúü", "aeiouu"))


def _is_diphthong(a: str, b: str) -> bool:
    """Devuelve True si las vocales a y b forman diptongo en español."""
    pair = _normalize_vowel(a) + _normalize_vowel(b)
    return pair in DIPHTHONGS


def _tokenize(word: str) -> list[str]:
    """
    Divide la palabra en tokens tratando ch, ll, rr como unidad consonántica única.
    Preserva mayúsculas/minúsculas del original.
    """
    tokens: list[str] = []
    i = 0
    while i < len(word):
        if i + 1 < len(word) and word[i : i + 2].lower() in DIGRAPHS:
            tokens.append(word[i : i + 2])
            i += 2
        else:
            tokens.append(word[i])
            i += 1
    return tokens


def _build_nuclei(tokens: list[str]) -> list[tuple[int, int]]:
    """
    Agrupa los índices de tokens vocálicos en núcleos silábicos.
    Las vocales contiguas que forman diptongo quedan como un solo núcleo (start, end).
    Vocales contiguas que forman hiato generan núcleos separados.
    """
    vowel_pos = [i for i, t in enumerate(tokens) if _is_vowel(t[0])]
    nuclei: list[tuple[int, int]] = []
    vi = 0
    while vi < len(vowel_pos):
        start = vowel_pos[vi]
        if (
            vi + 1 < len(vowel_pos)
            and vowel_pos[vi + 1] == start + 1
            and _is_diphthong(tokens[start], tokens[start + 1])
        ):
            nuclei.append((start, start + 1))
            vi += 2
        else:
            nuclei.append((start, start))
            vi += 1
    return nuclei


def syllabify(word: str) -> list[str]:
    """
    Divide una palabra española en sílabas.

    Devuelve lista de strings. Ej: syllabify("guitarra") → ["gui", "ta", "rra"]
    """
    if not word:
        return []
    if len(word) == 1:
        return [word]

    tokens = _tokenize(word)
    nuclei = _build_nuclei(tokens)

    # Sin vocales o solo un núcleo: la palabra es una única sílaba
    if len(nuclei) <= 1:
        return [word]

    syllables: list[str] = []
    start = 0

    for ni in range(len(nuclei) - 1):
        n_end = nuclei[ni][1]
        next_n_start = nuclei[ni + 1][0]
        cons = list(range(n_end + 1, next_n_start))

        if not cons:
            # Hiato: cerrar sílaba en la vocal actual
            syllables.append("".join(tokens[start : n_end + 1]))
            start = next_n_start

        elif len(cons) == 1:
            # Consonante única: va con la sílaba siguiente
            syllables.append("".join(tokens[start : n_end + 1]))
            start = cons[0]

        elif len(cons) == 2:
            c1, c2 = cons
            pair = (tokens[c1] + tokens[c2]).lower()
            if pair in INSEPARABLE:
                # Grupo inseparable: ambas consonantes abren la siguiente sílaba
                syllables.append("".join(tokens[start : n_end + 1]))
                start = c1
            else:
                # Primera cierra, segunda abre
                syllables.append("".join(tokens[start : c1 + 1]))
                start = c2

        else:
            # 3+ consonantes: si las dos últimas son inseparables van juntas con la siguiente vocal;
            # si no, solo la última va con la siguiente vocal
            last_two = (tokens[cons[-2]] + tokens[cons[-1]]).lower()
            split_point = cons[-2] if last_two in INSEPARABLE else cons[-1]
            syllables.append("".join(tokens[start:split_point]))
            start = split_point

    # Resto final (última sílaba)
    syllables.append("".join(tokens[start:]))

    return [s for s in syllables if s]
