"""Vista de gestión de listas de canciones (setlists) para presentaciones."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import ttk, messagebox

from database.db import Database
from models.setlist import Setlist, SetlistItem
from models.transposer import transpose_chord
from ui.app import THEME

PANEL_WIDTH = 240


class SetlistView(ttk.Frame):
    """Pantalla para crear listas, ordenar canciones y lanzar la presentación."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_present: Callable[[Setlist], None] | None = None,
    ) -> None:
        super().__init__(parent, style="TFrame")
        self.db = db
        self._on_present = on_present
        self.setlist: Setlist | None = None
        self._selected_id: int | None = None
        self._row_labels: dict[int, tk.Label] = {}

        self._build()
        self.refresh_setlists()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        paned = tk.PanedWindow(
            self, orient="horizontal", sashwidth=6,
            bg=THEME["border"], bd=0, sashrelief="flat",
        )
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, style="Surface.TFrame", width=PANEL_WIDTH)
        paned.add(left, minsize=180, width=PANEL_WIDTH, stretch="never")
        self._build_left(left)

        right = ttk.Frame(paned, style="TFrame")
        paned.add(right, stretch="always")
        self._build_right(right)

    def _build_left(self, parent: tk.Misc) -> None:
        ttk.Button(
            parent, text="+  Nueva lista", style="Accent.TButton",
            command=self._new_setlist,
        ).pack(fill="x", padx=10, pady=(10, 8))

        container = tk.Frame(parent, bg=THEME["surface"])
        container.pack(fill="both", expand=True, padx=(10, 4), pady=(0, 10))
        self._list_canvas = tk.Canvas(container, bg=THEME["surface"], highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._list_canvas.pack(side="left", fill="both", expand=True)
        self._list_inner = tk.Frame(self._list_canvas, bg=THEME["surface"])
        win = self._list_canvas.create_window((0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind(
            "<Configure>",
            lambda _e: self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all")),
        )
        self._list_canvas.bind(
            "<Configure>", lambda e: self._list_canvas.itemconfig(win, width=e.width)
        )

    def _build_right(self, parent: tk.Misc) -> None:
        # Barra superior: nombre + acciones
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=10, pady=(10, 4))
        self._name_var = tk.StringVar()
        self._name_entry = tk.Entry(
            bar, textvariable=self._name_var, width=30,
            bg=THEME["surface2"], fg=THEME["text"], insertbackground=THEME["text"],
            relief="flat", font=THEME["font_ui"],
        )
        self._name_entry.pack(side="left", ipady=4)
        self._name_entry.bind("<FocusOut>", lambda _e: self._commit_name())
        self._name_entry.bind("<Return>", lambda _e: self._commit_name())

        ttk.Button(bar, text="▶  Presentar", style="Accent.TButton",
                   command=self._present).pack(side="left", padx=(8, 2))
        ttk.Button(bar, text="+  Agregar canción",
                   command=self._open_picker).pack(side="left", padx=2)
        ttk.Button(bar, text="Eliminar lista", style="Danger.TButton",
                   command=self._delete_current).pack(side="left", padx=2)

        # Área de canciones de la lista (scrollable)
        content = ttk.Frame(parent, style="TFrame")
        content.pack(fill="both", expand=True, padx=4, pady=4)
        self._canvas = tk.Canvas(content, bg=THEME["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(content, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=THEME["bg"])
        win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(win, width=e.width))

        self._status = ttk.Label(parent, text="", style="Muted.TLabel", anchor="w")
        self._status.pack(fill="x", side="bottom", padx=10, pady=4)

    # ------------------------------------------------------------------
    # Panel izquierdo: listas
    # ------------------------------------------------------------------

    def refresh_setlists(self) -> None:
        """Recarga el panel de listas desde la base de datos."""
        for child in self._list_inner.winfo_children():
            child.destroy()
        self._row_labels.clear()
        for row in self.db.list_setlists():
            self._make_setlist_row(row["id"], row["name"], row["song_count"])

    def _make_setlist_row(self, sid: int, name: str, count: int) -> None:
        bg = THEME["surface"]
        row = tk.Frame(self._list_inner, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=2, pady=1)
        text = f"{name}   ·  {count}"
        lbl = tk.Label(
            row, text=text, bg=bg,
            fg=THEME["chord"] if sid == self._selected_id else THEME["text"],
            anchor="w", font=THEME["font_ui"], cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True, padx=(6, 2), pady=3)
        self._row_labels[sid] = lbl

        del_btn = tk.Label(row, text="✕", bg=bg, fg=THEME["danger"],
                           cursor="hand2", font=THEME["font_ui"])
        for w in (row, lbl):
            w.bind("<Button-1>", lambda _e, i=sid: self._select_setlist(i))
        del_btn.bind("<Button-1>", lambda _e, i=sid, n=name: self._confirm_delete(i, n))

        members = (row, lbl, del_btn)

        def show(_e=None) -> None:
            for w in members:
                w.config(bg=THEME["surface2"])
            del_btn.pack(side="right", padx=(2, 6))

        def hide(_e=None) -> None:
            x, y = row.winfo_pointerxy()
            under = row.winfo_containing(x, y)
            if under is not None and str(under).startswith(str(row)):
                return
            del_btn.pack_forget()
            for w in members:
                w.config(bg=THEME["surface"])

        for w in members:
            w.bind("<Enter>", show)
            w.bind("<Leave>", hide)

    def _select_setlist(self, sid: int) -> None:
        self.setlist = self.db.load_setlist(sid)
        self._selected_id = sid
        self._name_var.set(self.setlist.name)
        for i, lbl in self._row_labels.items():
            lbl.config(fg=THEME["chord"] if i == sid else THEME["text"])
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
        for child in self._inner.winfo_children():
            child.destroy()
        if self.setlist is None:
            return
        if not self.setlist.items:
            tk.Label(
                self._inner, text="Lista vacía. Pulsa «Agregar canción».",
                bg=THEME["bg"], fg=THEME["text_muted"], font=THEME["font_ui"],
            ).pack(anchor="w", padx=12, pady=12)
        for i, item in enumerate(self.setlist.items):
            self._make_item_row(i, item)
        n = len(self.setlist.items)
        self._status.config(text=f"{n} canción(es)")

    def _make_item_row(self, index: int, item: SetlistItem) -> None:
        row = tk.Frame(self._inner, bg=THEME["surface"])
        row.pack(fill="x", padx=8, pady=2)

        tk.Label(row, text=f"{index + 1}.", bg=THEME["surface"], fg=THEME["text_muted"],
                 font=THEME["font_ui"], width=3, anchor="e").pack(side="left", padx=(6, 4))
        tk.Label(row, text=item.title, bg=THEME["surface"], fg=THEME["text"],
                 font=THEME["font_ui"], anchor="w").pack(side="left", fill="x", expand=True)

        # Control de tono: [−] tono [+]
        tone = tk.Label(row, text=self._tone_text(item), bg=THEME["surface"],
                        fg=THEME["chord"], font=THEME["font_ui"], width=10, anchor="center")

        def btn(text: str, cmd) -> tk.Button:
            return tk.Button(row, text=text, width=2, command=cmd,
                             bg=THEME["surface2"], fg=THEME["text"], relief="flat",
                             activebackground=THEME["border"], font=THEME["font_ui"])

        btn("−", lambda: self._change_transpose(index, -1)).pack(side="left", padx=(6, 0))
        tone.pack(side="left", padx=2)
        btn("+", lambda: self._change_transpose(index, 1)).pack(side="left", padx=(0, 6))

        btn("✕", lambda: self._remove_item(index)).pack(side="right", padx=(2, 6))
        btn("↓", lambda: self._move_item(index, 1)).pack(side="right", padx=1)
        btn("↑", lambda: self._move_item(index, -1)).pack(side="right", padx=1)

    @staticmethod
    def _tone_text(item: SetlistItem) -> str:
        """Texto del tono: 'Do → Re' si transpone, el tono solo, o el offset."""
        offset = item.transpose
        if item.key:
            if offset == 0:
                return item.key
            return f"{item.key}→{transpose_chord(item.key, offset)}"
        return f"{offset:+d}".replace("+0", "0")

    def _change_transpose(self, index: int, delta: int) -> None:
        if self.setlist is None:
            return
        item = self.setlist.items[index]
        item.transpose += delta
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
            self._status.config(text="La lista está vacía")
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
            self._status.config(text="Primero crea o selecciona una lista")
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


class SongPicker(tk.Toplevel):
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
        self.configure(bg=THEME["bg"])
        self.geometry("360x460")
        self.transient(parent.winfo_toplevel())

        self._search_var = tk.StringVar()
        self._entry = tk.Entry(
            self, textvariable=self._search_var, bg=THEME["surface2"], fg=THEME["text"],
            insertbackground=THEME["text"], relief="flat", font=THEME["font_ui"],
        )
        self._entry.pack(fill="x", padx=10, pady=10, ipady=4)
        self._search_var.trace_add("write", lambda *_: self._refresh())
        self._install_placeholder(
            self._entry, "Escriba el nombre de la canción o el autor"
        )

        container = tk.Frame(self, bg=THEME["surface"])
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._canvas = tk.Canvas(container, bg=THEME["surface"], highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=THEME["surface"])
        win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(win, width=e.width))

        ttk.Button(self, text="Listo", command=self.destroy).pack(pady=(0, 10))
        self.bind("<Escape>", lambda _e: self.destroy())
        self._refresh()

    def _install_placeholder(self, entry: tk.Entry, text: str) -> None:
        """Muestra un texto guía atenuado mientras el campo está vacío y sin foco."""
        self._placeholder = text
        self._placeholder_active = False

        def show() -> None:
            self._placeholder_active = True
            entry.config(fg=THEME["text_muted"])
            self._search_var.set(text)

        def clear(_e=None) -> None:
            if self._placeholder_active:
                self._placeholder_active = False
                entry.config(fg=THEME["text"])
                self._search_var.set("")

        def restore(_e=None) -> None:
            if not self._search_var.get():
                show()

        entry.bind("<FocusIn>", clear)
        entry.bind("<FocusOut>", restore)
        show()

    def _query(self) -> str:
        """Texto de búsqueda real (cadena vacía si solo está el placeholder)."""
        if self._placeholder_active:
            return ""
        return self._search_var.get().strip()

    def _refresh(self) -> None:
        for child in self._inner.winfo_children():
            child.destroy()
        for song in self.db.list_songs(self._query()):
            self._make_row(
                song["id"], song["title"], song.get("author"), song.get("key")
            )

    def _make_row(
        self, song_id: int, title: str, author: str | None, key: str | None
    ) -> None:
        bg = THEME["surface"]
        row = tk.Frame(self._inner, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=4, pady=1)

        title_lbl = tk.Label(row, text=title, bg=bg, fg=THEME["text"],
                              anchor="w", font=THEME["font_ui"], cursor="hand2")
        title_lbl.pack(side="left", padx=(6, 0), pady=2)

        widgets = [row, title_lbl]
        if author:
            author_lbl = tk.Label(row, text=f"·  {author}", bg=bg,
                                  fg=THEME["text_muted"], anchor="w",
                                  font=THEME["font_ui"], cursor="hand2")
            author_lbl.pack(side="left", padx=(6, 0), pady=2)
            widgets.append(author_lbl)

        check_lbl = tk.Label(row, text="", bg=bg, fg=THEME["chord"],
                             font=THEME["font_ui"], cursor="hand2")
        check_lbl.pack(side="right", padx=(0, 4))
        if key:
            key_lbl = tk.Label(row, text=key, bg=bg, fg=THEME["chord"],
                               font=THEME["font_ui"], cursor="hand2")
            key_lbl.pack(side="right", padx=(6, 8))
            widgets.append(key_lbl)
        widgets.append(check_lbl)

        def pick(_e=None) -> None:
            self._pick(song_id, title, key, widgets, check_lbl)

        def enter(_e=None) -> None:
            for w in widgets:
                w.config(bg=THEME["surface2"])

        def leave(_e=None) -> None:
            for w in widgets:
                w.config(bg=bg)

        for w in widgets:
            w.bind("<Button-1>", pick)
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)

    def _pick(
        self, song_id: int, title: str, key: str | None,
        widgets: list[tk.Widget], check_lbl: tk.Label,
    ) -> None:
        self._on_pick(song_id, title, key)
        for w in widgets:
            if isinstance(w, tk.Label):
                w.config(fg=THEME["chord"])
        check_lbl.config(text="✓")
