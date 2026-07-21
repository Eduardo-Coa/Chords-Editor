"""Panel lateral con la lista de canciones, buscador y botón 'Nueva' (CustomTkinter)."""

from __future__ import annotations
from typing import Callable
import tkinter as tk

import customtkinter as ctk

from database.db import Database
from ui.app import THEME, ctk_button_style

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

        self._selected_id: int | None = None
        self._row_labels: dict[int, ctk.CTkLabel] = {}  # song_id -> label del título
        self._filter_vars: dict[str, tk.StringVar] = {}
        self._filter_menus: dict[str, ctk.CTkOptionMenu] = {}
        self._refreshing = False  # evita recursión al recargar opciones

        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # Construcción de widgets
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Crea el buscador, los filtros, el botón 'Nueva' y la lista con scroll."""
        self._search_var = tk.StringVar()
        ctk.CTkEntry(
            self, textvariable=self._search_var, placeholder_text="Buscar...",
            fg_color=THEME["surface2"], border_width=0, text_color=THEME["text"],
            font=THEME["font_list"],
        ).pack(fill="x", padx=10, pady=(10, 6))

        # Filtros (desplegables) dirigidos por FILTERS
        for spec in FILTERS:
            field, label = spec["field"], spec["label"]
            frame = ctk.CTkFrame(self, fg_color="transparent")
            frame.pack(fill="x", padx=10, pady=(0, 4))
            ctk.CTkLabel(
                frame, text=label, text_color=THEME["text_muted"],
                font=THEME["font_list"], width=44, anchor="w",
            ).pack(side="left")
            var = tk.StringVar(value=FILTER_ALL)
            menu = ctk.CTkOptionMenu(
                frame, variable=var, values=[FILTER_ALL],
                command=lambda _v: self.refresh(),  # solo dispara en selección manual
                fg_color=THEME["surface2"], button_color=THEME["surface2"],
                button_hover_color=THEME["border"], text_color=THEME["text"],
                font=THEME["font_list"], dropdown_font=THEME["font_list"],
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
                    **ctk_button_style("normal", THEME["font_list"]),
                ).pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            self, text="+  Nueva canción", command=self._on_new,
            **ctk_button_style("accent", THEME["font_list"]),
        ).pack(fill="x", padx=10, pady=(6, 8))

        # Área de lista con scroll nativo de CustomTkinter (reemplaza el Canvas)
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=THEME["surface"])
        self._scroll.pack(fill="both", expand=True, padx=(6, 4), pady=(0, 10))

        self._search_var.trace_add("write", lambda *_: self.refresh())

    # ------------------------------------------------------------------
    # Filas
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Recarga la lista aplicando búsqueda y filtros; actualiza los desplegables."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._reload_filter_options()

            query = self._search_var.get().strip()  # placeholder nativo => "" si vacío
            filters = {
                field: var.get()
                for field, var in self._filter_vars.items()
                if var.get() and var.get() != FILTER_ALL
            }

            for child in self._scroll.winfo_children():
                child.destroy()
            self._row_labels.clear()

            for song in self.db.list_songs(query, filters):
                self._make_row(song["id"], song["title"], song.get("key") or "")
        finally:
            self._refreshing = False

    def _open_field_editor(self, field: str) -> None:
        """Abre el editor del campo (por ahora solo autores)."""
        if field == "author":
            from ui.views.author_editor import AuthorEditor
            AuthorEditor(self, self.db, on_changed=self.refresh)

    def _reload_filter_options(self) -> None:
        """Repuebla los desplegables con los valores existentes (preserva selección)."""
        for field, menu in self._filter_menus.items():
            options = [FILTER_ALL] + self.db.distinct_values(field)
            menu.configure(values=options)
            if self._filter_vars[field].get() not in options:
                self._filter_vars[field].set(FILTER_ALL)

    def _make_row(self, song_id: int, title: str, key: str) -> None:
        """Crea una fila clicable con botón de eliminar que aparece en hover."""
        row = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=6)
        row.pack(fill="x", padx=2, pady=1)

        label_text = title + (f"   ·  {key}" if key else "")
        title_lbl = ctk.CTkLabel(
            row, text=label_text, anchor="w", font=THEME["font_list"],
            text_color=THEME["chord"] if song_id == self._selected_id else THEME["text"],
        )
        title_lbl.pack(side="left", fill="x", expand=True, padx=(8, 2), pady=3)
        self._row_labels[song_id] = title_lbl

        # Label transparente: hereda el color de la fila (✕ en rojo), se muestra en hover
        del_btn = ctk.CTkLabel(row, text="✕", text_color=THEME["danger"],
                               font=THEME["font_list"], width=20)

        # Selección
        for w in (row, title_lbl):
            w.bind("<Button-1>", lambda _e, sid=song_id: self._select(sid))
        # Eliminar
        del_btn.bind("<Button-1>", lambda _e, sid=song_id, t=title: self._on_delete(sid, t))

        members = (row, title_lbl, del_btn)

        def show(_e=None) -> None:
            row.configure(fg_color=THEME["surface2"])
            del_btn.pack(side="right", padx=(2, 6))

        def hide(_e=None) -> None:
            x, y = row.winfo_pointerxy()
            under = row.winfo_containing(x, y)
            # Sigue dentro de la fila (o de un hijo): no ocultar todavía
            if under is not None and str(under).startswith(str(row)):
                return
            del_btn.pack_forget()
            row.configure(fg_color="transparent")

        for w in members:
            w.bind("<Enter>", show)
            w.bind("<Leave>", hide)

    def _select(self, song_id: int) -> None:
        """Marca la canción seleccionada y notifica al controlador."""
        self.set_selected(song_id)
        self._on_select(song_id)

    def set_selected(self, song_id: int | None) -> None:
        """Resalta visualmente la canción seleccionada (sin disparar callback)."""
        self._selected_id = song_id
        for sid, lbl in self._row_labels.items():
            lbl.configure(text_color=THEME["chord"] if sid == song_id else THEME["text"])
