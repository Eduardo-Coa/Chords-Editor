"""Diálogo para renombrar y normalizar autores (CRUD de autores) — CustomTkinter.

El ``tk.Listbox`` original no tiene equivalente en CustomTkinter, así que la lista
de autores se reconstruye como filas seleccionables dentro de un
``CTkScrollableFrame``. La ventana sigue siendo ``tk.Toplevel`` por la fiabilidad
del ``grab_set`` modal.
"""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from database.db import Database
from ui.app import THEME, ctk_button_style


class AuthorEditor:
    """Ventana modal con la lista de autores para renombrar/fusionar."""

    def __init__(
        self, parent: tk.Misc, db: Database, on_changed: Callable[[], None]
    ) -> None:
        self.db = db
        self._on_changed = on_changed
        self._authors: list[str] = []
        self._selected: str | None = None
        self._row_labels: dict[str, ctk.CTkLabel] = {}

        self.top = tk.Toplevel(parent)
        self.top.title("Editar autores")
        self.top.configure(bg=THEME["bg"])
        self.top.geometry("420x360")
        self.top.transient(parent)  # type: ignore[arg-type]
        self.top.grab_set()

        self._build()
        self._reload()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build(self) -> None:
        ctk.CTkLabel(self.top, text="Autores", text_color=THEME["text_muted"],
                     font=THEME["font_list"], anchor="w").pack(fill="x", padx=12, pady=(12, 4))

        self._list = ctk.CTkScrollableFrame(self.top, fg_color=THEME["surface"])
        self._list.pack(fill="both", expand=True, padx=12)

        ctk.CTkLabel(self.top, text="Nuevo nombre", text_color=THEME["text_muted"],
                     font=THEME["font_list"], anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        self._name_var = tk.StringVar()
        ctk.CTkEntry(
            self.top, textvariable=self._name_var, fg_color=THEME["surface2"],
            border_width=0, text_color=THEME["text"], font=THEME["font_list"],
        ).pack(fill="x", padx=12)

        btns = ctk.CTkFrame(self.top, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(btns, text="Renombrar", command=self._rename,
                      **ctk_button_style("accent", THEME["font_list"])).pack(side="left")
        ctk.CTkButton(btns, text="Cerrar", command=self.top.destroy,
                      **ctk_button_style("normal", THEME["font_list"])).pack(side="right")

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        self._authors = self.db.distinct_values("author")
        self._selected = None
        self._name_var.set("")
        for child in self._list.winfo_children():
            child.destroy()
        self._row_labels.clear()
        for author in self._authors:
            self._make_row(author)

    def _make_row(self, author: str) -> None:
        """Fila seleccionable de un autor (reemplaza un item del Listbox)."""
        row = ctk.CTkFrame(self._list, fg_color="transparent", corner_radius=6)
        row.pack(fill="x", padx=2, pady=1)
        lbl = ctk.CTkLabel(row, text=author, anchor="w", font=THEME["font_list"],
                           text_color=THEME["text"])
        lbl.pack(side="left", fill="x", expand=True, padx=(8, 2), pady=3)
        self._row_labels[author] = lbl
        for w in (row, lbl):
            w.bind("<Button-1>", lambda _e, a=author: self._select_author(a))

    def _select_author(self, author: str) -> None:
        self._selected = author
        self._name_var.set(author)
        for a, lbl in self._row_labels.items():
            lbl.configure(text_color=THEME["chord"] if a == author else THEME["text"])

    def _rename(self) -> None:
        old = self._selected
        if not old:
            messagebox.showinfo("Editar autores", "Selecciona un autor de la lista.",
                                parent=self.top)
            return
        new = self._name_var.get().strip()
        if not new or new == old:
            return

        if new in self._authors:
            if not messagebox.askyesno(
                "Fusionar autores",
                f"«{new}» ya existe. ¿Fusionar «{old}» con «{new}»?\n"
                f"Las canciones de «{old}» pasarán a «{new}».",
                parent=self.top,
            ):
                return

        self.db.rename_author(old, new)
        self._on_changed()
        self._reload()
