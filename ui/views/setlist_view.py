"""Vista de gestión de listas de canciones (setlists) para presentaciones (CustomTkinter)."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from database.db import Database
from models.setlist import Setlist, SetlistItem
from models.transposer import transpose_chord
from ui.app import THEME, ctk_button_style

PANEL_WIDTH = 240


class SetlistView(ctk.CTkFrame):
    """Pantalla para crear listas, ordenar canciones y lanzar la presentación."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_present: Callable[[Setlist], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color=THEME["bg"], corner_radius=0)
        self.db = db
        self._on_present = on_present
        self.setlist: Setlist | None = None
        self._selected_id: int | None = None
        self._row_labels: dict[int, ctk.CTkLabel] = {}

        self._build()
        self.refresh_setlists()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # tk.PanedWindow: CustomTkinter no tiene panel divisible; se conserva tk con
        # CTkFrames dentro (híbrido).
        paned = tk.PanedWindow(
            self, orient="horizontal", sashwidth=6,
            bg=THEME["border"], bd=0, sashrelief="flat",
        )
        paned.pack(fill="both", expand=True)

        left = ctk.CTkFrame(paned, fg_color=THEME["surface"], width=PANEL_WIDTH,
                            corner_radius=0)
        paned.add(left, minsize=180, width=PANEL_WIDTH, stretch="never")
        self._build_left(left)

        right = ctk.CTkFrame(paned, fg_color=THEME["bg"], corner_radius=0)
        paned.add(right, stretch="always")
        self._build_right(right)

    def _build_left(self, parent: tk.Misc) -> None:
        ctk.CTkButton(
            parent, text="+  Nueva lista", command=self._new_setlist,
            **ctk_button_style("accent", THEME["font_list"]),
        ).pack(fill="x", padx=10, pady=(10, 8))

        self._list_scroll = ctk.CTkScrollableFrame(parent, fg_color=THEME["surface"])
        self._list_scroll.pack(fill="both", expand=True, padx=(10, 4), pady=(0, 10))

    def _build_right(self, parent: tk.Misc) -> None:
        # Barra superior: nombre + acciones
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(10, 4))
        self._name_var = tk.StringVar()
        self._name_entry = ctk.CTkEntry(
            bar, textvariable=self._name_var, width=240,
            fg_color=THEME["surface2"], border_width=0, text_color=THEME["text"],
            font=THEME["font_list"],
        )
        self._name_entry.pack(side="left")
        self._name_entry.bind("<FocusOut>", lambda _e: self._commit_name())
        self._name_entry.bind("<Return>", lambda _e: self._commit_name())

        ctk.CTkButton(bar, text="▶  Presentar", command=self._present,
                      **ctk_button_style("accent", THEME["font_list"])).pack(side="left", padx=(8, 2))
        ctk.CTkButton(bar, text="+  Agregar canción", command=self._open_picker,
                      **ctk_button_style("normal", THEME["font_list"])).pack(side="left", padx=2)
        ctk.CTkButton(bar, text="Eliminar lista", command=self._delete_current,
                      **ctk_button_style("danger", THEME["font_list"])).pack(side="left", padx=2)

        # Área de canciones de la lista (scrollable)
        self._scroll = ctk.CTkScrollableFrame(parent, fg_color=THEME["bg"])
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self._status = ctk.CTkLabel(parent, text="", text_color=THEME["text_muted"],
                                    font=THEME["font_list"], anchor="w")
        self._status.pack(fill="x", side="bottom", padx=10, pady=4)

    # ------------------------------------------------------------------
    # Panel izquierdo: listas
    # ------------------------------------------------------------------

    def refresh_setlists(self) -> None:
        """Recarga el panel de listas desde la base de datos."""
        for child in self._list_scroll.winfo_children():
            child.destroy()
        self._row_labels.clear()
        for row in self.db.list_setlists():
            self._make_setlist_row(row["id"], row["name"], row["song_count"])

    def _make_setlist_row(self, sid: int, name: str, count: int) -> None:
        row = ctk.CTkFrame(self._list_scroll, fg_color="transparent", corner_radius=6)
        row.pack(fill="x", padx=2, pady=1)
        lbl = ctk.CTkLabel(
            row, text=f"{name}   ·  {count}", anchor="w", font=THEME["font_list"],
            text_color=THEME["chord"] if sid == self._selected_id else THEME["text"],
        )
        lbl.pack(side="left", fill="x", expand=True, padx=(8, 2), pady=3)
        self._row_labels[sid] = lbl

        del_btn = ctk.CTkLabel(row, text="✕", text_color=THEME["danger"],
                               font=THEME["font_list"], width=20)
        for w in (row, lbl):
            w.bind("<Button-1>", lambda _e, i=sid: self._select_setlist(i))
        del_btn.bind("<Button-1>", lambda _e, i=sid, n=name: self._confirm_delete(i, n))

        members = (row, lbl, del_btn)

        def show(_e=None) -> None:
            row.configure(fg_color=THEME["surface2"])
            del_btn.pack(side="right", padx=(2, 6))

        def hide(_e=None) -> None:
            x, y = row.winfo_pointerxy()
            under = row.winfo_containing(x, y)
            if under is not None and str(under).startswith(str(row)):
                return
            del_btn.pack_forget()
            row.configure(fg_color="transparent")

        for w in members:
            w.bind("<Enter>", show)
            w.bind("<Leave>", hide)

    def _select_setlist(self, sid: int) -> None:
        self.setlist = self.db.load_setlist(sid)
        self._selected_id = sid
        self._name_var.set(self.setlist.name)
        for i, lbl in self._row_labels.items():
            lbl.configure(text_color=THEME["chord"] if i == sid else THEME["text"])
        self._render_detail()

    def _new_setlist(self) -> None:
        sid = self.db.create_setlist("Lista sin título")
        self.refresh_setlists()
        self._select_setlist(sid)
        self._name_entry.focus_set()
        self._name_entry.select_range(0, "end")

    # ------------------------------------------------------------------
    # Panel derecho: detalle de la lista
    # ------------------------------------------------------------------

    def _render_detail(self) -> None:
        for child in self._scroll.winfo_children():
            child.destroy()
        if self.setlist is None:
            return
        if not self.setlist.items:
            ctk.CTkLabel(
                self._scroll, text="Lista vacía. Pulsa «Agregar canción».",
                text_color=THEME["text_muted"], font=THEME["font_list"],
            ).pack(anchor="w", padx=12, pady=12)
        for i, item in enumerate(self.setlist.items):
            self._make_item_row(i, item)
        n = len(self.setlist.items)
        self._status.configure(text=f"{n} canción(es)")

    def _make_item_row(self, index: int, item: SetlistItem) -> None:
        row = ctk.CTkFrame(self._scroll, fg_color=THEME["surface"], corner_radius=6)
        row.pack(fill="x", padx=8, pady=2)

        ctk.CTkLabel(row, text=f"{index + 1}.", text_color=THEME["text_muted"],
                     font=THEME["font_list"], width=28, anchor="e").pack(side="left", padx=(6, 4))
        ctk.CTkLabel(row, text=item.title, text_color=THEME["text"], font=THEME["font_list"],
                     anchor="w").pack(side="left", fill="x", expand=True)

        tone = ctk.CTkLabel(row, text=self._tone_text(item), text_color=THEME["chord"],
                            font=THEME["font_list"], width=80)

        def mbtn(text: str, cmd) -> ctk.CTkButton:
            return ctk.CTkButton(row, text=text, width=28, command=cmd, **ctk_button_style("normal", THEME["font_list"]))

        mbtn("−", lambda: self._change_transpose(index, -1)).pack(side="left", padx=(6, 0))
        tone.pack(side="left", padx=2)
        mbtn("+", lambda: self._change_transpose(index, 1)).pack(side="left", padx=(0, 6))

        mbtn("✕", lambda: self._remove_item(index)).pack(side="right", padx=(2, 6))
        mbtn("↓", lambda: self._move_item(index, 1)).pack(side="right", padx=1)
        mbtn("↑", lambda: self._move_item(index, -1)).pack(side="right", padx=1)

    @staticmethod
    def _tone_text(item: SetlistItem) -> str:
        """Texto del tono: 'Do→Re' si transpone, el tono solo, o el offset."""
        offset = item.transpose
        if item.key:
            if offset == 0:
                return item.key
            return f"{item.key}→{transpose_chord(item.key, offset, item.key)}"
        return f"{offset:+d}".replace("+0", "0")

    def _change_transpose(self, index: int, delta: int) -> None:
        if self.setlist is None:
            return
        self.setlist.items[index].transpose += delta
        self._autosave()
        self._render_detail()

    def _move_item(self, index: int, delta: int) -> None:
        if self.setlist is None:
            return
        j = index + delta
        if not (0 <= j < len(self.setlist.items)):
            return
        items = self.setlist.items
        items[index], items[j] = items[j], items[index]
        self._autosave()
        self._render_detail()

    def _remove_item(self, index: int) -> None:
        if self.setlist is None:
            return
        del self.setlist.items[index]
        self._autosave()
        self._render_detail()

    # ------------------------------------------------------------------
    # Nombre, presentar, borrar
    # ------------------------------------------------------------------

    def _commit_name(self) -> None:
        if self.setlist is None:
            return
        name = self._name_var.get().strip() or "Lista sin título"
        if name != self.setlist.name:
            self.setlist.name = name
            self._autosave()

    def _present(self) -> None:
        if self.setlist is None or not self.setlist.items:
            self._status.configure(text="La lista está vacía")
            return
        if self._on_present is not None:
            self._on_present(self.setlist)

    def _delete_current(self) -> None:
        if self.setlist is None or self.setlist.id is None:
            return
        self._confirm_delete(self.setlist.id, self.setlist.name)

    def _confirm_delete(self, sid: int, name: str) -> None:
        if not messagebox.askyesno(
            "Eliminar lista",
            f"¿Eliminar la lista «{name}»?\nLas canciones no se borran, solo la lista.",
            icon="warning", parent=self,
        ):
            return
        self.db.delete_setlist(sid)
        if self.setlist is not None and self.setlist.id == sid:
            self.setlist = None
            self._selected_id = None
            self._name_var.set("")
            self._render_detail()
        self.refresh_setlists()

    def _autosave(self) -> None:
        if self.setlist is None:
            return
        self.db.save_setlist(self.setlist)
        self.refresh_setlists()

    # ------------------------------------------------------------------
    # Selector de canciones para agregar
    # ------------------------------------------------------------------

    def _open_picker(self) -> None:
        if self.setlist is None:
            self._status.configure(text="Primero crea o selecciona una lista")
            return
        SongPicker(self, self.db, on_pick=self._add_song)

    def _add_song(self, song_id: int, title: str, key: str | None) -> None:
        if self.setlist is None:
            return
        self.setlist.items.append(
            SetlistItem(
                id=None, song_id=song_id, position=len(self.setlist.items),
                transpose=0, title=title, key=key,
            )
        )
        self._autosave()
        self._render_detail()


class SongPicker(ctk.CTkToplevel):
    """Diálogo flotante para elegir canciones de la biblioteca y agregarlas."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_pick: Callable[[int, str, str | None], None],
    ) -> None:
        super().__init__(parent)
        self.db = db
        self._on_pick = on_pick
        self.title("Agregar canción")
        self.configure(fg_color=THEME["bg"])
        self.geometry("360x460")
        self.transient(parent.winfo_toplevel())

        self._search_var = tk.StringVar()
        ctk.CTkEntry(
            self, textvariable=self._search_var,
            placeholder_text="Escriba el nombre de la canción o el autor",
            fg_color=THEME["surface2"], border_width=0, text_color=THEME["text"],
            font=THEME["font_list"],
        ).pack(fill="x", padx=10, pady=10)
        self._search_var.trace_add("write", lambda *_: self._refresh())

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=THEME["surface"])
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ctk.CTkButton(self, text="Listo", command=self.destroy,
                      **ctk_button_style("normal", THEME["font_list"])).pack(pady=(0, 10))
        self.bind("<Escape>", lambda _e: self.destroy())
        self._refresh()

    def _refresh(self) -> None:
        for child in self._scroll.winfo_children():
            child.destroy()
        for song in self.db.list_songs(self._search_var.get().strip()):
            self._make_row(song["id"], song["title"], song.get("author"), song.get("key"))

    def _make_row(
        self, song_id: int, title: str, author: str | None, key: str | None
    ) -> None:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=6)
        row.pack(fill="x", padx=2, pady=1)

        title_lbl = ctk.CTkLabel(row, text=title, anchor="w", font=THEME["font_list"])
        title_lbl.pack(side="left", padx=(8, 0), pady=2)

        widgets = [row, title_lbl]
        if author:
            author_lbl = ctk.CTkLabel(row, text=f"·  {author}", anchor="w",
                                      text_color=THEME["text_muted"], font=THEME["font_list"])
            author_lbl.pack(side="left", padx=(6, 0), pady=2)
            widgets.append(author_lbl)

        check_lbl = ctk.CTkLabel(row, text="", text_color=THEME["chord"],
                                 font=THEME["font_list"], width=16)
        check_lbl.pack(side="right", padx=(0, 4))
        if key:
            key_lbl = ctk.CTkLabel(row, text=key, text_color=THEME["chord"],
                                   font=THEME["font_list"])
            key_lbl.pack(side="right", padx=(6, 8))
            widgets.append(key_lbl)
        widgets.append(check_lbl)

        def pick(_e=None) -> None:
            self._on_pick(song_id, title, key)
            title_lbl.configure(text_color=THEME["chord"])
            check_lbl.configure(text="✓")

        def enter(_e=None) -> None:
            row.configure(fg_color=THEME["surface2"])

        def leave(_e=None) -> None:
            row.configure(fg_color="transparent")

        for w in widgets:
            w.bind("<Button-1>", pick)
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
