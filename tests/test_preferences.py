"""Pruebas del módulo de preferencias."""

from __future__ import annotations

from ui.preferences import load_preferences, save_preference


def test_load_sin_archivo_devuelve_vacio(tmp_path):
    assert load_preferences(tmp_path / "no_existe.json") == {}


def test_guardar_y_leer(tmp_path):
    path = tmp_path / "prefs.json"
    save_preference("chord_color", "#ff8800", path)
    assert load_preferences(path) == {"chord_color": "#ff8800"}


def test_guardar_conserva_otras_claves(tmp_path):
    path = tmp_path / "prefs.json"
    save_preference("chord_color", "#ff8800", path)
    save_preference("otra", 42, path)
    prefs = load_preferences(path)
    assert prefs["chord_color"] == "#ff8800"
    assert prefs["otra"] == 42


def test_archivo_corrupto_devuelve_vacio(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text("esto no es json", encoding="utf-8")
    assert load_preferences(path) == {}
