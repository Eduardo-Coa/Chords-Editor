"""Diálogo para exportar todas las canciones de un autor como un cancionero.

Genera un único archivo ``.hymnchords`` (bundle multi-canción) con todas las
canciones del autor elegido. Reutiliza ``db.distinct_values`` (lista de autores),
``db.list_songs(filters=...)`` (filtro exacto) y ``utils.song_io.export_bundle``.
"""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import messagebox, filedialog

import customtkinter as ctk

from database.db import Database
from utils import song_io
from ui.app import THEME, ctk_button_style


class AuthorExportDialog(ctk.CTkToplevel):
    """Ventana modal: elegir un autor y exportar su cancionero a un archivo."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self._on_status = on_status
        self.title("Exportar por autor")
        self.configure(fg_color=THEME["bg"])
        self.geometry("400x190")
        self.transient(parent.winfo_toplevel())
        self.bind("<Escape>", lambda _e: self.destroy())

        authors = db.distinct_values("author")
        if not authors:
            self._build_empty()
            return
        self._build(authors)

    def _build_empty(self) -> None:
        ctk.CTkLabel(
            self, text="No hay autores con canciones para exportar.",
            text_color=THEME["text"], font=THEME["font_list"], wraplength=340,
        ).pack(padx=20, pady=(34, 12))
        ctk.CTkButton(self, text="Cerrar", command=self.destroy,
                      **ctk_button_style("normal", THEME["font_list"])).pack()

    def _build(self, authors: list[str]) -> None:
        ctk.CTkLabel(
            self, text="Elige un autor para exportar todas sus canciones\n"
                       "en un único archivo (cancionero):",
            text_color=THEME["text"], font=THEME["font_list"], justify="left",
        ).pack(padx=20, pady=(20, 10))

        self._author_var = tk.StringVar(value=authors[0])
        ctk.CTkOptionMenu(
            self, variable=self._author_var, values=authors,
            font=THEME["font_list"], dropdown_font=THEME["font_list"],
        ).pack(padx=20, fill="x")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=18)
        ctk.CTkButton(btns, text="Exportar…", command=self._export,
                      **ctk_button_style("accent", THEME["font_list"])).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancelar", command=self.destroy,
                      **ctk_button_style("normal", THEME["font_list"])).pack(side="left", padx=6)

    def _export(self) -> None:
        author = self._author_var.get()
        rows = self.db.list_songs(filters={"author": author})
        if not rows:
            messagebox.showinfo(
                "Exportar por autor", f"«{author}» no tiene canciones.", parent=self
            )
            return
        songs = [self.db.load_song(row["id"]) for row in rows]

        ext = song_io.SONG_FILE_EXTENSION
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar cancionero", defaultextension=ext,
            initialfile=song_io.bundle_filename(author),
            filetypes=[("Cancionero HymnChords", f"*{ext}"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            song_io.export_bundle(songs, path, author=author)
        except song_io.SongIOError as exc:
            messagebox.showerror("Exportar por autor", str(exc), parent=self)
            return

        msg = f"Exportadas {len(songs)} canciones de «{author}»"
        if self._on_status is not None:
            self._on_status(msg)
        messagebox.showinfo("Exportar por autor", msg + ".", parent=self)
        self.destroy()
