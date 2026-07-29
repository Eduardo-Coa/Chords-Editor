"""Ventana principal de Ilahi y constantes de tema visual."""

from __future__ import annotations
import sys
import tkinter as tk

import customtkinter as ctk

from database.db import Database

# ----------------------------------------------------------------------
# Tema visual
# ----------------------------------------------------------------------

THEME = {
    # Colores base
    "bg":           "#0f0f0f",
    "surface":      "#181818",
    "surface2":     "#222222",
    "border":       "#2e2e2e",
    "divider":      "#3d3d3d",   # líneas separadoras (más visibles que el borde)
    "text":         "#e8e4d8",
    "text_muted":   "#777777",

    # Acento para acordes (verde azulado)
    "chord":        "#7eb8a4",
    "chord_bg":     "#0f1f1c",

    # Secciones
    "verse_bg":     "#1a1a1a",
    "chorus_bg":    "#161e1c",
    "section_label": "#555555",

    # Acento dorado para UI
    "accent":       "#c8a96e",
    # Verde apagado (mismo registro que el dorado y el verde azulado de acordes):
    # marca "hay cambios sin guardar" en el botón Guardar.
    "success":      "#8fb573",
    "danger":       "#c06060",

    # Tipografía
    "font_ui":          ("Segoe UI", 10),
    "font_list":        ("Segoe UI", 10),   # filas de la lista de canciones
    "font_panel":       ("Segoe UI", 12),   # pestañas + buscador/filtros del panel
    "font_toolbar":     ("Segoe UI", 12),   # botones de la barra de herramientas
    "font_meta":        ("Segoe UI", 11),   # barra Título/Autor/Tono/Ritmo/Capo
    "font_mono":        ("Consolas", 11),
    "font_stage":       ("Consolas", 22),
    "font_chord_stage": ("Consolas", 18),
    "font_section":     ("Segoe UI", 11),
}


def _apply_preferences() -> None:
    """Aplica las preferencias guardadas (ej. color de acordes) al THEME."""
    from ui.preferences import load_preferences

    prefs = load_preferences()
    chord_color = prefs.get("chord_color")
    if chord_color:
        THEME["chord"] = chord_color


def _apply_platform_fonts() -> None:
    """Ajusta las fuentes del THEME según el sistema operativo."""
    if sys.platform == "darwin":  # macOS
        replacements = {
            "font_ui":          ("Helvetica Neue", 12),
            "font_list":        ("Helvetica Neue", 14),
            "font_panel":       ("Helvetica Neue", 12),
            "font_toolbar":     ("Helvetica Neue", 12),
            "font_meta":        ("Helvetica Neue", 12),
            "font_mono":        ("Menlo", 12),
            "font_stage":       ("Menlo", 24),
            "font_chord_stage": ("Menlo", 20),
            "font_section":     ("Helvetica Neue", 10),
        }
        THEME.update(replacements)


# ----------------------------------------------------------------------
# Design system CustomTkinter (paleta A: identidad teal/oro actual)
# ----------------------------------------------------------------------

def ctk_button_style(kind: str = "normal", font: tuple | None = None) -> dict:
    """Kwargs de estilo para ``CTkButton`` según la paleta A.

    Reutilizable por todas las vistas migradas para mantener un look coherente.
    ``kind``: 'normal' (gris), 'accent' (dorado), 'success' (verde, cambios sin
    guardar), 'danger' (rojo). ``font`` sobreescribe la tipografía (por defecto
    ``font_ui``).
    """
    base = {"corner_radius": 8, "border_width": 0, "font": font or THEME["font_ui"]}
    if kind == "accent":
        return {**base, "fg_color": THEME["accent"],
                "hover_color": THEME["accent"], "text_color": THEME["bg"]}
    if kind == "success":
        return {**base, "fg_color": THEME["success"],
                "hover_color": THEME["success"], "text_color": THEME["bg"]}
    if kind == "danger":
        return {**base, "fg_color": THEME["surface2"],
                "hover_color": THEME["danger"], "text_color": THEME["danger"]}
    return {**base, "fg_color": THEME["surface2"],
            "hover_color": THEME["border"], "text_color": THEME["text"]}


# ----------------------------------------------------------------------
# Aplicación
# ----------------------------------------------------------------------

class App:
    """Controlador principal de la interfaz de Ilahi."""

    def __init__(self, root: tk.Tk, db: Database) -> None:
        self.root = root
        self.db = db

        _apply_platform_fonts()
        _apply_preferences()
        self._configure_ctk()
        self._configure_root()
        self._build_layout()

    def _configure_ctk(self) -> None:
        """Activa el modo oscuro de CustomTkinter (la paleta A se aplica por widget)."""
        ctk.set_appearance_mode("dark")

    def _configure_root(self) -> None:
        """Aplica color de fondo y configuración base a la ventana raíz."""
        self.root.configure(bg=THEME["bg"])

    def _build_layout(self) -> None:
        """Monta la barra de navegación y las secciones Canciones / Listas."""
        # Import diferido para evitar ciclo de importación con las vistas
        from ui.views.edit_view import EditView

        nav = ctk.CTkFrame(self.root, fg_color=THEME["surface"], corner_radius=0)
        nav.pack(fill="x")
        self._nav_buttons = {
            "songs": ctk.CTkButton(
                nav, text="Canciones", width=110,
                command=lambda: self._show_section("songs"), **ctk_button_style("normal", THEME["font_panel"])),
            "setlists": ctk.CTkButton(
                nav, text="Listas", width=110,
                command=lambda: self._show_section("setlists"), **ctk_button_style("normal", THEME["font_panel"])),
        }
        self._nav_buttons["songs"].pack(side="left", padx=(10, 4), pady=6)
        self._nav_buttons["setlists"].pack(side="left", padx=4, pady=6)

        self.container = ctk.CTkFrame(self.root, fg_color=THEME["bg"], corner_radius=0)
        self.container.pack(fill="both", expand=True)

        self.edit_view = EditView(
            self.container, self.db, on_open_stage=self._open_stage
        )
        self.setlist_view = None  # creada de forma diferida la 1ª vez
        self._section: str | None = None
        self._show_section("songs")

    def _show_section(self, section: str) -> None:
        """Alterna el contenido principal entre 'songs' y 'setlists'."""
        if section == self._section:
            return
        self.edit_view.pack_forget()
        if self.setlist_view is not None:
            self.setlist_view.pack_forget()

        if section == "songs":
            self.edit_view.pack(fill="both", expand=True)
        else:
            if self.setlist_view is None:
                from ui.views.setlist_view import SetlistView
                self.setlist_view = SetlistView(
                    self.container, self.db, on_present=self._open_setlist_stage
                )
            else:
                self.setlist_view.refresh_setlists()
            self.setlist_view.pack(fill="both", expand=True)

        self._section = section
        for name, btn in self._nav_buttons.items():
            active = name == section
            btn.configure(
                fg_color=THEME["accent"] if active else THEME["surface2"],
                text_color=THEME["bg"] if active else THEME["text"],
                hover_color=THEME["accent"] if active else THEME["border"],
            )

    def _open_stage(self, song, offset: int) -> None:
        """Abre la vista escenario para una canción suelta."""
        from ui.views.stage_view import StageView

        self._track_stage_font(StageView(self.root, song, offset))

    def _open_setlist_stage(self, setlist) -> None:
        """Abre la presentación: la lista completa en vista escenario."""
        from ui.views.stage_view import StageView

        playlist = [
            (self.db.load_song(item.song_id), item.transpose)
            for item in setlist.items
        ]
        if playlist:
            self._track_stage_font(StageView(self.root, playlist=playlist))

    def _track_stage_font(self, stage) -> None:
        """Al cerrar el escenario, adopta en el editor el tamaño de fuente elegido allí.

        El tamaño ya quedó persistido en ``preferences.json``; esto solo evita que
        el editor siga mostrando el valor viejo en la misma sesión.
        """
        def _on_destroy(event: tk.Event) -> None:
            if event.widget is stage.top:
                self.edit_view.sync_stage_font_size()

        stage.top.bind("<Destroy>", _on_destroy, add=True)
