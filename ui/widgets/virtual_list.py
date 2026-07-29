"""Lista virtualizada: solo crea widgets para las filas visibles.

Con cientos de elementos, crear un widget por fila hace que refrescar, hacer
scroll y redimensionar cuesten O(total). Este widget mantiene un *pool* de
filas del tamaño de la ventana visible (~25) y las reutiliza al desplazarse,
dejando esas operaciones en O(visible).

Las filas son tkinter puro por la misma razón que ``chord_grid``: crear widgets
de CustomTkinter es ~5x más lento y su ciclo de redibujado llama a
``update_idletasks()``, lo que dispara relayouts en cascada. La única pieza de
CustomTkinter es el scrollbar (un solo widget, sin coste apreciable), para no
romper el look del panel.
"""

from __future__ import annotations
from typing import Callable
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from ui.app import THEME

# Filas extra que se mantienen fuera de la vista para que el scroll no parpadee
_OVERSCAN = 2

# Filas que avanza cada muesca de la rueda del mouse
_WHEEL_ROWS = 3


class _Row(tk.Frame):
    """Fila reutilizable: título a la izquierda y ✕ (eliminar) visible en hover."""

    def __init__(self, parent: tk.Misc, owner: "VirtualList") -> None:
        super().__init__(parent, bg=THEME["surface"])
        self._owner = owner
        self.item_id: int | None = None

        self.title = tk.Label(
            self, text="", anchor="w", font=owner.font,
            bg=THEME["surface"], fg=THEME["text"],
        )
        self.title.pack(side="left", fill="x", expand=True, padx=(8, 2))

        self.delete = tk.Label(
            self, text="✕", fg=THEME["danger"], bg=THEME["surface"],
            font=owner.font, width=2, cursor="hand2",
        )

        for w in (self, self.title):
            w.bind("<Button-1>", self._on_click)
        self.delete.bind("<Button-1>", self._on_delete)
        for w in (self, self.title, self.delete):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<MouseWheel>", owner._on_wheel)

    # -- contenido -----------------------------------------------------

    def bind_item(self, item_id: int, text: str, selected: bool) -> None:
        """Reapunta esta fila a otro elemento (sin recrear widgets)."""
        self.item_id = item_id
        if self.title.cget("text") != text:
            self.title.configure(text=text)
        self.set_selected(selected)

    def set_selected(self, selected: bool) -> None:
        """Colorea el título según esté seleccionado o no."""
        self.title.configure(fg=THEME["chord"] if selected else THEME["text"])

    def release(self) -> None:
        """Saca la fila de la vista (queda en el pool para reutilizarse)."""
        self.item_id = None
        self.place_forget()

    # -- interacción ---------------------------------------------------

    def _on_click(self, _e: tk.Event) -> None:
        if self.item_id is not None:
            self._owner._select(self.item_id)

    def _on_delete(self, _e: tk.Event) -> str:
        if self.item_id is not None:
            self._owner.on_delete(self.item_id)
        return "break"  # no propagar al click de selección

    def _enter(self, _e: tk.Event) -> None:
        if self.item_id is None:
            return
        self._paint(THEME["surface2"])
        self.delete.pack(side="right", padx=(2, 6))

    def _leave(self, _e: tk.Event) -> None:
        # Moverse entre la fila y sus hijos dispara <Leave>: solo apagar el
        # resaltado si el puntero salió realmente de la fila.
        under = self.winfo_containing(*self.winfo_pointerxy())
        if under is not None and str(under).startswith(str(self)):
            return
        self.delete.pack_forget()
        self._paint(THEME["surface"])

    def _paint(self, color: str) -> None:
        for w in (self, self.title, self.delete):
            w.configure(bg=color)


class VirtualList(tk.Frame):
    """Lista vertical con scroll que solo renderiza las filas visibles."""

    def __init__(
        self,
        parent: tk.Misc,
        on_select: Callable[[int], None],
        on_delete: Callable[[int], None],
        font: tuple | None = None,
    ) -> None:
        super().__init__(parent, bg=THEME["surface"])
        self.on_select = on_select
        self.on_delete = on_delete
        self.font = font or THEME["font_list"]

        self._items: list[tuple[int, str]] = []   # (id, texto a mostrar)
        self._pool: list[_Row] = []
        self._selected_id: int | None = None
        self._offset = 0                          # desplazamiento en píxeles

        # Alto de fila derivado de la fuente, para que siga a font_list
        metrics = tkfont.Font(root=self, font=self.font)
        self._row_h = metrics.metrics("linespace") + 6

        self._scrollbar = ctk.CTkScrollbar(
            self, command=self._on_scrollbar, width=12,
            fg_color=THEME["surface"], button_color=THEME["border"],
            button_hover_color=THEME["text_muted"],
        )
        self._scrollbar.pack(side="right", fill="y", padx=(0, 2), pady=2)

        self._viewport = tk.Frame(self, bg=THEME["surface"])
        self._viewport.pack(side="left", fill="both", expand=True)
        self._viewport.bind("<Configure>", lambda _e: self._render())
        self._viewport.bind("<MouseWheel>", self._on_wheel)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_items(self, items: list[tuple[int, str]]) -> None:
        """Reemplaza el contenido de la lista y vuelve al principio."""
        self._items = items
        self._offset = 0
        self._render()

    def set_selected(self, item_id: int | None) -> None:
        """Resalta el elemento seleccionado (sin disparar ``on_select``)."""
        self._selected_id = item_id
        for row in self._pool:
            if row.item_id is not None:
                row.set_selected(row.item_id == item_id)

    # ------------------------------------------------------------------
    # Renderizado
    # ------------------------------------------------------------------

    def _render(self) -> None:
        """Coloca el pool sobre la ventana visible actual."""
        height = self._viewport.winfo_height()
        if height <= 1:  # todavía sin geometría asignada
            return

        total_px = len(self._items) * self._row_h
        self._offset = max(0, min(self._offset, max(0, total_px - height)))

        needed = height // self._row_h + _OVERSCAN
        while len(self._pool) < needed:
            self._pool.append(_Row(self._viewport, self))

        first = self._offset // self._row_h
        for k, row in enumerate(self._pool):
            index = first + k
            if index < len(self._items):
                item_id, text = self._items[index]
                row.bind_item(item_id, text, item_id == self._selected_id)
                row.place(x=0, y=index * self._row_h - self._offset,
                          relwidth=1, height=self._row_h)
            else:
                row.release()

        if total_px <= height:
            self._scrollbar.set(0.0, 1.0)
        else:
            self._scrollbar.set(self._offset / total_px,
                                (self._offset + height) / total_px)

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------

    def _scroll_to(self, offset: int) -> None:
        """Desplaza a un offset absoluto en píxeles y repinta si cambió."""
        if offset != self._offset:
            self._offset = offset
            self._render()

    def _on_wheel(self, event: tk.Event) -> str:
        step = -int(event.delta / 120) * _WHEEL_ROWS * self._row_h
        self._scroll_to(self._offset + step)
        return "break"

    def _on_scrollbar(self, *args: str) -> None:
        """Atiende al scrollbar (``moveto`` al arrastrar, ``scroll`` al clicar)."""
        total_px = len(self._items) * self._row_h
        if args[0] == "moveto":
            self._scroll_to(int(float(args[1]) * total_px))
        elif args[0] == "scroll":
            amount = int(args[1])
            unit = self._viewport.winfo_height() if args[2] == "pages" else self._row_h
            self._scroll_to(self._offset + amount * unit)

    def _select(self, item_id: int) -> None:
        """Marca la fila y avisa al controlador."""
        self.set_selected(item_id)
        self.on_select(item_id)
