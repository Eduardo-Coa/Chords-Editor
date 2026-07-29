"""Panel lateral con la lista de canciones, buscador y botón 'Nueva' (CustomTkinter)."""

from __future__ import annotations
from typing import Callable
import tkinter as tk

import customtkinter as ctk

from database.db import Database
from ui.app import THEME, ctk_button_style
from ui.widgets.virtual_list import VirtualList

# Ancho inicial del panel (ajustable desde el PanedWindow del edit_view)
PANEL_WIDTH = 240

# Filtros del panel, dirigidos por datos. Para agregar un filtro nuevo, añade
# una entrada aquí (y la columna correspondiente en Database._FILTER_COLUMNS).
FILTERS = [
    {"field": "author", "label": "Autor", "editable": True},
    # {"field": "rhythm", "label": "Ritmo"},
    # {"field": "key",    "label": "Tono"},
]

# Texto del desplegable que significa "sin filtro"
FILTER_ALL = "Todos"


class SongList(ctk.CTkFrame):
    """Lista de canciones con buscador en vivo, botón nueva y eliminar en hover."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_select: Callable[[int], None],
        on_new: Callable[[], None],
        on_delete: Callable[[int, str], None],
    ) -> None:
        super().__init__(
            parent, fg_color=THEME["surface"], width=PANEL_WIDTH, corner_radius=0
        )
        self.db = db
        self._on_select = on_select
        self._on_new = on_new
        self._on_delete = on_delete

        self._titles: dict[int, str] = {}  # song_id -> título (para el diálogo de borrado)
        self._filter_vars: dict[str, tk.StringVar] = {}
        self._filter_menus: dict[str, ctk.CTkOptionMenu] = {}
        self._refreshing = False  # evita recursión al recargar opciones
        self._search_after_id: str | None = None

        self._build()
        self._reload_filter_options()
        self.refresh()

    # ------------------------------------------------------------------
    # Construcción de widgets
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Crea el buscador, los filtros, el botón 'Nueva' y la lista con scroll.

        El encabezado usa ``font_panel``; las filas usan ``font_list`` (ver
        ``_make_row``), para poder ajustar cada uno por separado.
        """
        font = THEME["font_panel"]
        self._search_var = tk.StringVar()
        ctk.CTkEntry(
            self, textvariable=self._search_var, placeholder_text="Buscar...",
            fg_color=THEME["surface2"], border_width=0, text_color=THEME["text"],
            font=font,
        ).pack(fill="x", padx=10, pady=(10, 6))

        # Filtros (desplegables) dirigidos por FILTERS
        for spec in FILTERS:
            field, label = spec["field"], spec["label"]
            frame = ctk.CTkFrame(self, fg_color="transparent")
            frame.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(
                frame, text=label, text_color=THEME["text_muted"],
                font=font, width=44, anchor="w",
            ).pack(side="left")
            var = tk.StringVar(value=FILTER_ALL)
            menu = ctk.CTkOptionMenu(
                frame, variable=var, values=[FILTER_ALL],
                command=lambda _v: self.refresh(),  # solo dispara en selección manual
                fg_color=THEME["surface2"], button_color=THEME["surface2"],
                button_hover_color=THEME["border"], text_color=THEME["text"],
                font=font, dropdown_font=font,
                dropdown_fg_color=THEME["surface2"],
                dropdown_text_color=THEME["text"], dropdown_hover_color=THEME["border"],
            )
            menu.pack(side="left", fill="x", expand=True)
            self._filter_vars[field] = var
            self._filter_menus[field] = menu

            # Botón de edición (✎) para filtros editables (ej. autores)
            if spec.get("editable"):
                ctk.CTkButton(
                    frame, text="✎", width=28,
                    command=lambda f=field: self._open_field_editor(f),
                    **ctk_button_style("normal", font),
                ).pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            self, text="+  Nueva canción", command=self._on_new,
            **ctk_button_style("accent", font),
        ).pack(fill="x", padx=10, pady=(6, 8))

        # Lista virtualizada: renderiza solo las filas visibles (ver VirtualList)
        self._list = VirtualList(
            self, on_select=self._select, on_delete=self._delete,
            font=THEME["font_list"],
        )
        self._list.pack(fill="both", expand=True, padx=(6, 4), pady=(0, 10))

        self._search_var.trace_add("write", lambda *_: self._schedule_refresh())

    # ------------------------------------------------------------------
    # Filas
    # ------------------------------------------------------------------

    # Espera tras la última tecla antes de buscar. Con la lista virtualizada el
    # refresh cuesta ~8 ms, así que basta con agrupar las pulsaciones rápidas.
    _SEARCH_DELAY_MS = 120

    def _schedule_refresh(self) -> None:
        """Agrupa las pulsaciones seguidas en una sola búsqueda."""
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(self._SEARCH_DELAY_MS, self.refresh)

    def refresh(self, reload_filters: bool = False) -> None:
        """Recarga la lista aplicando búsqueda y filtros.

        ``reload_filters`` repuebla los desplegables (ej. autores); solo hace
        falta tras agregar/editar/borrar una canción, no en cada tecla del buscador.
        """
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._search_after_id = None
            if reload_filters:
                self._reload_filter_options()

            query = self._search_var.get().strip()  # placeholder nativo => "" si vacío
            filters = {
                field: var.get()
                for field, var in self._filter_vars.items()
                if var.get() and var.get() != FILTER_ALL
            }

            songs = self.db.list_songs(query, filters)
            self._titles = {s["id"]: s["title"] for s in songs}
            self._list.set_items([
                (s["id"], s["title"] + (f"   ·  {s['key']}" if s.get("key") else ""))
                for s in songs
            ])
        finally:
            self._refreshing = False

    def _open_field_editor(self, field: str) -> None:
        """Abre el editor del campo (por ahora solo autores)."""
        if field == "author":
            from ui.views.author_editor import AuthorEditor
            AuthorEditor(self, self.db, on_changed=lambda: self.refresh(reload_filters=True))

    def _reload_filter_options(self) -> None:
        """Repuebla los desplegables con los valores existentes (preserva selección)."""
        for field, menu in self._filter_menus.items():
            options = [FILTER_ALL] + self.db.distinct_values(field)
            menu.configure(values=options)
            if self._filter_vars[field].get() not in options:
                self._filter_vars[field].set(FILTER_ALL)

    def _select(self, song_id: int) -> None:
        """Notifica al controlador que se eligió una canción."""
        self._on_select(song_id)

    def _delete(self, song_id: int) -> None:
        """Pide el borrado al controlador, con el título para el diálogo."""
        self._on_delete(song_id, self._titles.get(song_id, ""))

    def set_selected(self, song_id: int | None) -> None:
        """Resalta visualmente la canción seleccionada (sin disparar callback)."""
        self._list.set_selected(song_id)
