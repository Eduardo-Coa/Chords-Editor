"""Diálogo para renombrar y normalizar autores (CRUD de autores)."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import ttk, messagebox

from database.db import Database
from ui.app import THEME


class AuthorEditor:
    """Ventana modal con la lista de autores para renombrar/fusionar."""

    def __init__(
        self, parent: tk.Misc, db: Database, on_changed: Callable[[], None]
    ) -> None:
        self.db = db
        self._on_changed = on_changed
        self._authors: list[str] = []

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
        tk.Label(
            self.top, text="Autores", bg=THEME["bg"], fg=THEME["text_muted"],
            font=THEME["font_ui"], anchor="w",
        ).pack(fill="x", padx=12, pady=(12, 4))

        list_frame = tk.Frame(self.top, bg=THEME["surface"])
        list_frame.pack(fill="both", expand=True, padx=12)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self._listbox = tk.Listbox(
            list_frame, bg=THEME["surface"], fg=THEME["text"],
            selectbackground=THEME["chord_bg"], selectforeground=THEME["chord"],
            highlightthickness=0, borderwidth=0, activestyle="none",
            font=THEME["font_ui"], yscrollcommand=scrollbar.set,
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # Nuevo nombre + botón renombrar
        tk.Label(
            self.top, text="Nuevo nombre", bg=THEME["bg"], fg=THEME["text_muted"],
            font=THEME["font_ui"], anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        self._name_var = tk.StringVar()
        entry = tk.Entry(
            self.top, textvariable=self._name_var, bg=THEME["surface2"],
            fg=THEME["text"], insertbackground=THEME["text"], relief="flat",
            font=THEME["font_ui"],
        )
        entry.pack(fill="x", padx=12, ipady=4)

        btns = tk.Frame(self.top, bg=THEME["bg"])
        btns.pack(fill="x", padx=12, pady=10)
        ttk.Button(btns, text="Renombrar", style="Accent.TButton",
                   command=self._rename).pack(side="left")
        ttk.Button(btns, text="Cerrar", command=self.top.destroy).pack(side="right")

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        self._authors = self.db.distinct_values("author")
        self._listbox.delete(0, "end")
        for author in self._authors:
            self._listbox.insert("end", author)
        self._name_var.set("")

    def _on_select(self, _e: tk.Event) -> None:
        sel = self._listbox.curselection()
        if sel:
            self._name_var.set(self._authors[sel[0]])

    def _rename(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showinfo("Editar autores", "Selecciona un autor de la lista.",
                                parent=self.top)
            return
        old = self._authors[sel[0]]
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
