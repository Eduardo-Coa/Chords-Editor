"""Popup flotante para editar el acorde de una sílaba."""

from __future__ import annotations
from typing import Callable
import re
import tkinter as tk

from ui.app import THEME

# Validación suave: raíz A-G con alteración opcional y sufijo de calidad.
# No bloquea el guardado; solo sirve para advertir visualmente.
_CHORD_RE = re.compile(r"^[A-G][#b]?[A-Za-z0-9#b°ø+\-/]*$")


def is_valid_chord(value: str) -> bool:
    """Devuelve True si el texto parece un acorde válido (o está vacío)."""
    value = value.strip()
    if value == "":
        return True
    return bool(_CHORD_RE.match(value))


class ChordPopup:
    """Ventana flotante con un Entry para escribir el acorde de una sílaba."""

    def __init__(
        self,
        parent: tk.Misc,
        anchor: tk.Widget,
        value: str,
        on_save: Callable[[str], None],
        on_navigate: Callable[[int], None] | None = None,
    ) -> None:
        self._on_save = on_save
        self._on_navigate = on_navigate
        self._closed = False

        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)  # sin barra de título
        self.top.configure(bg=THEME["accent"])  # borde fino vía padding

        self._var = tk.StringVar(value=value)
        self._entry = tk.Entry(
            self.top,
            textvariable=self._var,
            width=6,
            justify="center",
            bg=THEME["surface2"],
            fg=THEME["chord"],
            insertbackground=THEME["chord"],
            relief="flat",
            font=THEME["font_mono"],
        )
        self._entry.pack(padx=1, pady=1, ipady=3, ipadx=2)

        self._bind_keys()
        self._position_over(anchor)

        self._entry.focus_force()
        self._entry.select_range(0, "end")
        self._var.trace_add("write", lambda *_: self._update_validity())
        self._update_validity()

    # ------------------------------------------------------------------
    # Posicionamiento
    # ------------------------------------------------------------------

    def _position_over(self, anchor: tk.Widget) -> None:
        """Coloca el popup justo encima de la sílaba clickeada."""
        anchor.update_idletasks()
        self.top.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() - self.top.winfo_reqheight() - 2
        self.top.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Teclas
    # ------------------------------------------------------------------

    def _bind_keys(self) -> None:
        self._entry.bind("<Return>", lambda _e: self._save_and_close())
        self._entry.bind("<Escape>", lambda _e: self.cancel())
        self._entry.bind("<Tab>", lambda _e: self._save_and_navigate(1))
        self._entry.bind("<Shift-Tab>", lambda _e: self._save_and_navigate(-1))
        # Clic fuera del popup: cerrar sin guardar
        self._entry.bind("<FocusOut>", lambda _e: self.cancel())

    # ------------------------------------------------------------------
    # Validación visual
    # ------------------------------------------------------------------

    def _update_validity(self) -> None:
        """Cambia el color del texto si el acorde no parece válido."""
        if is_valid_chord(self._var.get()):
            self._entry.config(fg=THEME["chord"])
        else:
            self._entry.config(fg=THEME["danger"])

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persiste el valor actual a través del callback."""
        self._on_save(self._var.get().strip())

    def _save_and_close(self) -> str:
        self._save()
        self.close()
        return "break"

    def _save_and_navigate(self, direction: int) -> str:
        """Guarda y pide al controlador moverse a la sílaba adyacente."""
        self._save()
        self.close()
        if self._on_navigate is not None:
            self._on_navigate(direction)
        return "break"

    def cancel(self) -> str:
        """Cierra sin guardar."""
        self.close()
        return "break"

    def close(self) -> None:
        """Destruye la ventana del popup (una sola vez)."""
        if self._closed:
            return
        self._closed = True
        self.top.destroy()
