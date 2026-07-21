"""Pruebas de la lógica pura de reordenamiento por arrastre (drag & drop)."""

from __future__ import annotations

from ui.views.setlist_view import compute_drop_index


# Cuatro filas con centros verticales en 10, 20, 30, 40.
CENTERS = [10.0, 20.0, 30.0, 40.0]


def _reorder(items: list[str], dragged: int, drop: int) -> list[str]:
    """Aplica pop+insert como hace la vista, para comprobar el orden final."""
    out = list(items)
    out.insert(drop, out.pop(dragged))
    return out


def test_arrastrar_primera_al_fondo():
    # Cursor por debajo de todas las filas → cae al final.
    t = compute_drop_index(100.0, CENTERS, dragged_index=0)
    assert t == 3
    assert _reorder(["A", "B", "C", "D"], 0, t) == ["B", "C", "D", "A"]


def test_arrastrar_ultima_al_inicio():
    # Cursor por encima de todas → cae primero.
    t = compute_drop_index(5.0, CENTERS, dragged_index=3)
    assert t == 0
    assert _reorder(["A", "B", "C", "D"], 3, t) == ["D", "A", "B", "C"]


def test_quedarse_en_su_lugar_es_noop():
    # Cursor sobre el centro de su propia fila → mismo índice (sin cambio).
    t = compute_drop_index(20.0, CENTERS, dragged_index=1)
    assert t == 1
    assert _reorder(["A", "B", "C", "D"], 1, t) == ["A", "B", "C", "D"]


def test_mover_al_medio():
    # Arrastrar la fila 0 hasta entre la 1 (c=20) y la 2 (c=30).
    t = compute_drop_index(25.0, CENTERS, dragged_index=0)
    assert t == 1
    assert _reorder(["A", "B", "C", "D"], 0, t) == ["B", "A", "C", "D"]


def test_mover_fila_intermedia_hacia_arriba():
    t = compute_drop_index(15.0, CENTERS, dragged_index=2)
    assert t == 1
    assert _reorder(["A", "B", "C", "D"], 2, t) == ["A", "C", "B", "D"]


def test_dos_filas():
    centers = [10.0, 20.0]
    assert compute_drop_index(100.0, centers, dragged_index=0) == 1
    assert compute_drop_index(5.0, centers, dragged_index=1) == 0
