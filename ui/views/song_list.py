"""Panel lateral con la lista de canciones, buscador y botón 'Nueva'."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import ttk

from database.db import Database
from ui.app import THEME

# Ancho fijo del panel según el layout del CLAUDE.md
PANEL_WIDTH = 240


class SongList(ttk.Frame):
    """Lista de canciones con buscador en vivo y botón de nueva canción."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_select: Callable[[int], None],
        on_new: Callable[[], None],
    ) -> None:
        super().__init__(parent, style="Surface.TFrame", width=PANEL_WIDTH)
        self.db = db
        self._on_select = on_select
        self._on_new = on_new

        # Mapea el índice del Listbox al id de la canción
        self._index_to_id: list[int] = []

        # Mantener el ancho fijo aunque los hijos sean más angostos
        self.pack_propagate(False)

        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # Construcción de widgets
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Crea el buscador, el botón 'Nueva' y la lista."""
        # --- Buscador ---
        self._search_var = tk.StringVar()

        search_entry = tk.Entry(
            self,
            textvariable=self._search_var,
            bg=THEME["surface2"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="flat",
            font=THEME["font_ui"],
        )
        search_entry.pack(fill="x", padx=10, pady=(10, 6), ipady=4)
        self._add_placeholder(search_entry, "Buscar...")

        # --- Botón Nueva ---
        new_btn = ttk.Button(
            self,
            text="+  Nueva canción",
            style="Accent.TButton",
            command=self._on_new,
        )
        new_btn.pack(fill="x", padx=10, pady=(0, 8))

        # --- Lista de canciones ---
        list_frame = tk.Frame(self, bg=THEME["surface"])
        list_frame.pack(fill="both", expand=True, padx=(10, 4), pady=(0, 10))

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            list_frame,
            bg=THEME["surface"],
            fg=THEME["text"],
            selectbackground=THEME["chord_bg"],
            selectforeground=THEME["chord"],
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            font=THEME["font_ui"],
            yscrollcommand=scrollbar.set,
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox.yview)

        self._listbox.bind("<<ListboxSelect>>", self._handle_select)

        # Registrar el filtro en vivo ahora que el listbox ya existe
        self._search_var.trace_add("write", lambda *_: self.refresh())

    def _add_placeholder(self, entry: tk.Entry, text: str) -> None:
        """Muestra un texto guía cuando el Entry está vacío y sin foco."""
        def on_focus_in(_: tk.Event) -> None:
            if entry.get() == text:
                entry.delete(0, "end")
                entry.config(fg=THEME["text"])

        def on_focus_out(_: tk.Event) -> None:
            if not entry.get():
                entry.insert(0, text)
                entry.config(fg=THEME["text_muted"])

        entry.insert(0, text)
        entry.config(fg=THEME["text_muted"])
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Recarga la lista desde la base de datos aplicando el filtro actual."""
        query = self._search_var.get().strip()
        if query == "Buscar...":
            query = ""

        self._listbox.delete(0, "end")
        self._index_to_id.clear()

        for song in self.db.list_songs(query):
            key = song.get("key") or ""
            label = f"{song['title']}" + (f"   ·  {key}" if key else "")
            self._listbox.insert("end", label)
            self._index_to_id.append(song["id"])

    def _handle_select(self, _: tk.Event) -> None:
        """Notifica la selección de una canción al controlador."""
        selection = self._listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self._index_to_id):
            self._on_select(self._index_to_id[index])
