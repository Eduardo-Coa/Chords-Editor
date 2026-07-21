"""Genera los acordes propios de un tono (su 'círculo') para sugerir al editar.

Dado el tono elegido en el panel superior (ej. "C", "G", "Am", "F#m"), produce
una lista ordenada por frecuencia de uso de los acordes que pertenecen a esa
tonalidad: diatónicos + dominantes con séptima + las dominantes secundarias más
comunes. Los acordes se deletrean según la escala del tono (en Fa el IV es "Bb",
no "A#"; en Sol el vii° es "F#").
"""

from __future__ import annotations
import re

# Semitono de cada nota natural (do=0)
_LETTER_PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_LETTERS = ["C", "D", "E", "F", "G", "A", "B"]

# Intervalos (en semitonos desde la tónica) de cada grado de la escala
_MAJOR_STEPS = [0, 2, 4, 5, 7, 9, 11]
_MINOR_STEPS = [0, 2, 3, 5, 7, 8, 10]  # menor natural

# Para cada modo: lista de (grado 0-6 de la escala, sufijo del acorde),
# ORDENADA POR FRECUENCIA DE USO. El grado indexa la escala ya deletreada,
# así que la raíz siempre queda con la alteración correcta del tono.
_MAJOR_CHORDS = [
    (0, ""),     # I
    (4, ""),     # V
    (3, ""),     # IV
    (5, "m"),    # vi
    (1, "m"),    # ii
    (4, "7"),    # V7
    (2, "m"),    # iii
    (2, "7"),    # III7  = V7/vi  (ej. en Do: E7 → Am)
    (5, "7"),    # VI7   = V7/ii  (ej. en Do: A7 → Dm)
    (1, "7"),    # II7   = V7/V   (ej. en Do: D7 → G)
    (6, "°"),    # vii°
]

_MINOR_CHORDS = [
    (0, "m"),    # i
    (4, "7"),    # V7  (dominante de la menor armónica, ej. en Lam: E7)
    (3, "m"),    # iv
    (5, ""),     # VI
    (2, ""),     # III
    (6, ""),     # VII
    (4, ""),     # V   (dominante mayor sin séptima)
    (4, "m"),    # v   (versión menor natural)
    (1, "°"),    # ii°
    (0, "7"),    # i7  = V7/iv  (ej. en Lam: A7 → Dm)
    (3, "7"),    # iv7 = V7/VII (ej. en Lam: D7 → G)
]

_ROOT_RE = re.compile(r"^([A-Ga-g])([#b]{0,2})(.*)$")


def _accidental_str(diff: int) -> str:
    """Convierte un desfase en semitonos (-2..+2) a texto de alteración."""
    return {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}.get(diff, "")


def _build_scale(tonic_letter: str, tonic_accidental: str, steps: list[int]) -> list[str]:
    """Construye los 7 nombres de nota de la escala con el deletreo correcto.

    Usa cada letra A-G una sola vez (partiendo de la tónica) y calcula la
    alteración necesaria para alcanzar la altura de cada grado.
    """
    acc_value = tonic_accidental.count("#") - tonic_accidental.count("b")
    tonic_pitch = (_LETTER_PITCH[tonic_letter] + acc_value) % 12
    start = _LETTERS.index(tonic_letter)

    scale: list[str] = []
    for i, step in enumerate(steps):
        letter = _LETTERS[(start + i) % 7]
        natural = _LETTER_PITCH[letter]
        desired = (tonic_pitch + step) % 12
        diff = (desired - natural) % 12
        if diff > 6:
            diff -= 12  # mapear a rango -..+ (preferir bemoles/sostenidos cercanos)
        scale.append(letter + _accidental_str(diff))
    return scale


def _parse_key(key: str) -> tuple[str, str, bool] | None:
    """Separa el tono en (letra, alteración, es_menor). Devuelve None si no es válido."""
    key = key.strip()
    if not key:
        return None
    is_minor = len(key) > 1 and key.endswith("m") and not key.endswith("dim")
    root = key[:-1] if is_minor else key
    match = _ROOT_RE.match(root)
    if not match or match.group(3):  # sobra texto tras la raíz
        return None
    return match.group(1).upper(), match.group(2), is_minor


def chords_for_key(key: str | None) -> list[str]:
    """Devuelve los acordes propios del tono, ordenados por frecuencia de uso.

    Si el tono está vacío o no se reconoce, devuelve una lista vacía (en ese caso
    el editor simplemente no ofrece sugerencias y se escribe a mano).
    Ejemplo: chords_for_key("C") → ["C","G","F","Am","Dm","G7","Em","E7",...]
    """
    parsed = _parse_key(key or "")
    if parsed is None:
        return []
    letter, accidental, is_minor = parsed
    steps = _MINOR_STEPS if is_minor else _MAJOR_STEPS
    table = _MINOR_CHORDS if is_minor else _MAJOR_CHORDS
    scale = _build_scale(letter, accidental, steps)
    return [scale[degree] + suffix for degree, suffix in table]
