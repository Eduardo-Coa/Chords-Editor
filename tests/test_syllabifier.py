"""Pruebas del silabificador en español."""

from __future__ import annotations
import pytest

from utils.syllabifier import syllabify


@pytest.mark.parametrize("word, expected", [
    ("guitarra", ["gui", "ta", "rra"]),
    ("amor", ["a", "mor"]),
    ("gloria", ["glo", "ria"]),
    ("gracia", ["gra", "cia"]),
    ("corazon", ["co", "ra", "zon"]),
    ("alabanza", ["a", "la", "ban", "za"]),
    ("precioso", ["pre", "cio", "so"]),
    ("construir", ["cons", "truir"]),
    ("tranquilo", ["tran", "qui", "lo"]),
    ("pueblo", ["pue", "blo"]),
    ("noche", ["no", "che"]),
    ("lluvia", ["llu", "via"]),
    ("aleluya", ["a", "le", "lu", "ya"]),
])
def test_syllabify(word, expected):
    assert syllabify(word) == expected


def test_syllabify_vacio():
    assert syllabify("") == []


def test_syllabify_una_letra():
    assert syllabify("a") == ["a"]
