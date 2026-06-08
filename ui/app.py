"""Ventana principal de HymnChords y constantes de tema visual."""

from __future__ import annotations
import sys
import tkinter as tk
from tkinter import ttk

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
    "danger":       "#c06060",

    # Tipografía
    "font_ui":          ("Segoe UI", 10),
    "font_mono":        ("Consolas", 11),
    "font_stage":       ("Consolas", 22),
    "font_chord_stage": ("Consolas", 18),
    "font_section":     ("Segoe UI", 9),
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
            "font_mono":        ("Menlo", 12),
            "font_stage":       ("Menlo", 24),
            "font_chord_stage": ("Menlo", 20),
            "font_section":     ("Helvetica Neue", 10),
        }
        THEME.update(replacements)


# ----------------------------------------------------------------------
# Aplicación
# ----------------------------------------------------------------------

class App:
    """Controlador principal de la interfaz de HymnChords."""

    def __init__(self, root: tk.Tk, db: Database) -> None:
        self.root = root
        self.db = db

        _apply_platform_fonts()
        _apply_preferences()
        self._configure_root()
        self._configure_styles()
        self._build_layout()

    def _configure_root(self) -> None:
        """Aplica color de fondo y configuración base a la ventana raíz."""
        self.root.configure(bg=THEME["bg"])

    def _configure_styles(self) -> None:
        """Define los estilos ttk usados en toda la aplicación."""
        style = ttk.Style(self.root)
        # 'clam' permite personalizar colores en ttk (default no lo permite bien)
        style.theme_use("clam")

        style.configure(
            "TFrame",
            background=THEME["bg"],
        )
        style.configure(
            "Surface.TFrame",
            background=THEME["surface"],
        )
        style.configure(
            "TLabel",
            background=THEME["bg"],
            foreground=THEME["text"],
            font=THEME["font_ui"],
        )
        style.configure(
            "Muted.TLabel",
            background=THEME["bg"],
            foreground=THEME["text_muted"],
            font=THEME["font_ui"],
        )
        style.configure(
            "TButton",
            background=THEME["surface2"],
            foreground=THEME["text"],
            font=THEME["font_ui"],
            borderwidth=0,
            focuscolor=THEME["accent"],
            padding=(10, 5),
        )
        style.map(
            "TButton",
            background=[("active", THEME["border"])],
        )
        style.configure(
            "Accent.TButton",
            background=THEME["accent"],
            foreground=THEME["bg"],
        )
        style.configure(
            "Danger.TButton",
            background=THEME["surface2"],
            foreground=THEME["danger"],
        )
        style.map(
            "Danger.TButton",
            background=[("active", THEME["danger"])],
            foreground=[("active", THEME["text"])],
        )

    def _build_layout(self) -> None:
        """Monta la vista de edición como contenido principal."""
        # Import diferido para evitar ciclo de importación con las vistas
        from ui.views.edit_view import EditView

        self.container = ttk.Frame(self.root, style="TFrame")
        self.container.pack(fill="both", expand=True)

        self.edit_view = EditView(
            self.container, self.db, on_open_stage=self._open_stage
        )
        self.edit_view.pack(fill="both", expand=True)

    def _open_stage(self, song, offset: int) -> None:
        """Abre la vista escenario para la canción dada."""
        from ui.views.stage_view import StageView

        StageView(self.root, song, offset)
