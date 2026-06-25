"""Smoke tests de UI: cada vista y widget se construye sin lanzar excepción.

NO verifican comportamiento (que el scroll scrollee, que el hover resalte); solo
que la CONSTRUCCIÓN no falla — la regresión más común al migrar a CustomTkinter.
El comportamiento se valida a mano (checklist por vista; ver ROADMAP.md).

Necesitan un display real (Windows local lo tiene). Si tkinter no puede abrir
ventana (entorno headless/CI sin display), los tests se saltan automáticamente.

Reutiliza el fixture ``db`` de conftest.py (SQLite temporal, aislado).
"""

from __future__ import annotations
import tkinter as tk

import pytest

from models.song import Song, Section, Line, Syllable, Chord


@pytest.fixture(scope="module")
def _root():
    """Una sola raíz Tk para todo el módulo (oculta).

    Crear/destruir muchos ``tk.Tk()`` en un mismo proceso es frágil (falla
    transitoria), así que se comparte una única raíz. Si no hay display, se
    saltan todos los tests del módulo.
    """
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("sin display disponible para pruebas de UI")
    r.withdraw()  # nunca mostrar la ventana raíz
    try:
        yield r
    finally:
        r.destroy()


@pytest.fixture
def root(_root):
    """Raíz compartida; destruye los widgets creados tras cada test (aislamiento)."""
    yield _root
    for child in _root.winfo_children():
        child.destroy()


def _sample_song() -> Song:
    """Canción mínima (una sección, una línea, un acorde) para construir vistas."""
    song = Song(id=None, title="Prueba", author="Autor", key="C")
    sec = Section(id=None, position=0, type="verse", label="Estrofa")
    line = Line(id=None, position=0)
    line.syllables.append(
        Syllable(id=None, position=0, text="Glo", chord=Chord(id=None, value="C"))
    )
    line.syllables.append(Syllable(id=None, position=1, text="ria", chord=None))
    sec.lines.append(line)
    song.sections.append(sec)
    return song


def _noop(*_args, **_kwargs) -> None:
    """Callback vacío para las vistas que requieren handlers."""


# --- Vistas tipo Frame (el grueso de la migración) -------------------------

def test_app_se_construye(root, db):
    from ui.app import App
    App(root, db)
    root.update_idletasks()


def test_song_list(root, db):
    from ui.views.song_list import SongList
    SongList(root, db, on_select=_noop, on_new=_noop, on_delete=_noop)
    root.update_idletasks()


def test_edit_view_vacia(root, db):
    from ui.views.edit_view import EditView
    EditView(root, db)
    root.update_idletasks()


def test_edit_view_carga_cancion(root, db):
    from ui.views.edit_view import EditView
    song_id = db.save_song(_sample_song())
    ev = EditView(root, db)
    ev.load_song(song_id)  # ejercita el render del chord_grid (modo escenario)
    root.update_idletasks()


def test_setlist_view(root, db):
    from ui.views.setlist_view import SetlistView
    SetlistView(root, db)
    root.update_idletasks()


# --- Widget central chord_grid (se queda en tk; igual lo cubrimos) ---------

def test_chord_grid_modo_edicion(root):
    from ui.widgets.chord_grid import ChordGrid
    ChordGrid(root, _sample_song(), mode="edit")
    root.update_idletasks()


def test_chord_grid_modo_escenario(root):
    from ui.widgets.chord_grid import ChordGrid
    ChordGrid(root, _sample_song(), mode="stage")
    root.update_idletasks()


def test_chord_grid_override_fondo_escenario(root):
    """set_stage_bg cambia el fondo del modo escenario sin tocar el THEME global."""
    from ui.widgets.chord_grid import ChordGrid
    from ui.app import THEME
    grid = ChordGrid(root, _sample_song(), mode="stage")
    grid.set_stage_bg("#000000")
    root.update_idletasks()
    assert grid.stage_bg == "#000000"
    assert str(grid.cget("bg")) == "#000000"
    assert THEME["bg"] != "#000000"  # el tema global queda intacto


# --- Diálogos / Toplevels (se construyen y se cierran de inmediato) --------

def test_chord_popup(root):
    from ui.widgets.chord_popup import ChordPopup
    anchor = tk.Label(root, text="la")
    anchor.pack()
    root.update_idletasks()
    popup = ChordPopup(root, anchor, "C", on_save=_noop)
    try:
        root.update_idletasks()
    finally:
        popup.close()


def test_author_editor(root, db):
    from ui.views.author_editor import AuthorEditor
    db.save_song(_sample_song())
    editor = AuthorEditor(root, db, on_changed=_noop)
    try:
        root.update_idletasks()
    finally:
        editor.top.destroy()


def test_song_picker(root, db):
    from ui.views.setlist_view import SongPicker
    db.save_song(_sample_song())
    picker = SongPicker(root, db, on_pick=_noop)
    try:
        root.update_idletasks()
    finally:
        picker.destroy()


def test_stage_view(root):
    from ui.views.stage_view import StageView
    stage = StageView(root, _sample_song())
    try:
        stage.top.withdraw()  # evita el flash de pantalla completa durante el test
        root.update_idletasks()
    finally:
        stage.close()


def test_stage_view_playlist(root):
    """Cubre la rama de navegación (panel de controles con « n/total »)."""
    from ui.views.stage_view import StageView
    stage = StageView(root, playlist=[(_sample_song(), 0), (_sample_song(), 2)])
    try:
        stage.top.withdraw()
        root.update_idletasks()
    finally:
        stage.close()


def test_stage_view_toggle_negro_puro(root):
    """La tecla N alterna a negro puro y propaga el fondo al canvas y al grid."""
    from ui.views.stage_view import StageView
    from ui.app import THEME
    stage = StageView(root, _sample_song())
    try:
        stage.top.withdraw()
        stage._toggle_black()
        root.update_idletasks()
        assert stage._pure_black is True
        assert str(stage._canvas.cget("bg")) == "#000000"
        assert stage._grid.stage_bg == "#000000"
        stage._toggle_black()  # vuelve al fondo del tema
        assert stage._pure_black is False
        assert stage._grid.stage_bg == THEME["bg"]
    finally:
        stage.close()
