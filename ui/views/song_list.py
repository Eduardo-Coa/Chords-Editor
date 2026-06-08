"""Panel lateral con la lista de canciones, buscador y botón 'Nueva'."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import ttk

from database.db import Database
from ui.app import THEME

# Ancho inicial del panel (ajustable desde el PanedWindow del edit_view)
PANEL_WIDTH = 240


class SongList(ttk.Frame):
    """Lista de canciones con buscador en vivo, botón nueva y eliminar en hover."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_select: Callable[[int], None],
        on_new: Callable[[], None],
        on_delete: Callable[[int, str], None],
    ) -> None:
        super().__init__(parent, style="Surface.TFrame", width=PANEL_WIDTH)
        self.db = db
        self._on_select = on_select
        self._on_new = on_new
        self._on_delete = on_delete

        self._selected_id: int | None = None
        self._row_labels: dict[int, tk.Label] = {}  # song_id -> label del título

        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # Construcción de widgets
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Crea el buscador, el botón 'Nueva' y el área de lista con scroll."""
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(
            self, textvariable=self._search_var,
            bg=THEME["surface2"], fg=THEME["text"], insertbackground=THEME["text"],
            relief="flat", font=THEME["font_ui"],
        )
        search_entry.pack(fill="x", padx=10, pady=(10, 6), ipady=4)
        self._add_placeholder(search_entry, "Buscar...")

        ttk.Button(
            self, text="+  Nueva canción", style="Accent.TButton", command=self._on_new,
        ).pack(fill="x", padx=10, pady=(0, 8))

        # Área de lista con scroll (Canvas + frame interior)
        container = tk.Frame(self, bg=THEME["surface"])
        container.pack(fill="both", expand=True, padx=(10, 4), pady=(0, 10))

        self._canvas = tk.Canvas(container, bg=THEME["surface"], highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=THEME["surface"])
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        # Que el frame interior ocupe todo el ancho del canvas
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._win, width=e.width),
        )
        self._bind_wheel(self._canvas)

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

    def _bind_wheel(self, widget: tk.Widget) -> None:
        """Scroll con la rueda del mouse (corta la propagación al canvas de edición)."""
        def on_wheel(event: tk.Event) -> str:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"
        widget.bind("<MouseWheel>", on_wheel)

    # ------------------------------------------------------------------
    # Filas
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Recarga la lista desde la base de datos aplicando el filtro actual."""
        query = self._search_var.get().strip()
        if query == "Buscar...":
            query = ""

        for child in self._inner.winfo_children():
            child.destroy()
        self._row_labels.clear()

        for song in self.db.list_songs(query):
            self._make_row(song["id"], song["title"], song.get("key") or "")

    def _make_row(self, song_id: int, title: str, key: str) -> None:
        """Crea una fila clicable con botón de eliminar que aparece en hover."""
        bg = THEME["surface"]
        row = tk.Frame(self._inner, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=2, pady=1)

        label_text = title + (f"   ·  {key}" if key else "")
        title_lbl = tk.Label(
            row, text=label_text, bg=bg,
            fg=THEME["chord"] if song_id == self._selected_id else THEME["text"],
            anchor="w", font=THEME["font_ui"], cursor="hand2",
        )
        title_lbl.pack(side="left", fill="x", expand=True, padx=(6, 2), pady=3)

        del_btn = tk.Label(
            row, text="✕", bg=bg, fg=THEME["danger"],
            cursor="hand2", font=THEME["font_ui"],
        )  # se muestra solo en hover

        self._row_labels[song_id] = title_lbl

        # Selección
        for w in (row, title_lbl):
            w.bind("<Button-1>", lambda _e, sid=song_id: self._select(sid))
        # Eliminar
        del_btn.bind("<Button-1>", lambda _e, sid=song_id, t=title: self._on_delete(sid, t))

        # Hover: resaltar fila y mostrar la X
        members = (row, title_lbl, del_btn)

        def show(_e=None, d=del_btn, ms=members) -> None:
            for w in ms:
                w.config(bg=THEME["surface2"])
            d.pack(side="right", padx=(2, 6))

        def hide(_e=None, r=row, d=del_btn, ms=members) -> None:
            x, y = r.winfo_pointerxy()
            under = r.winfo_containing(x, y)
            # Sigue dentro de la fila: no ocultar todavía
            if under is not None and str(under).startswith(str(r)):
                return
            d.pack_forget()
            for w in ms:
                w.config(bg=THEME["surface"])

        for w in members:
            w.bind("<Enter>", show)
            w.bind("<Leave>", hide)
            self._bind_wheel(w)

    def _select(self, song_id: int) -> None:
        """Marca la canción seleccionada y notifica al controlador."""
        self.set_selected(song_id)
        self._on_select(song_id)

    def set_selected(self, song_id: int | None) -> None:
        """Resalta visualmente la canción seleccionada (sin disparar callback)."""
        self._selected_id = song_id
        for sid, lbl in self._row_labels.items():
            lbl.config(fg=THEME["chord"] if sid == song_id else THEME["text"])
