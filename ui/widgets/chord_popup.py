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
        suggestions: list[str] | None = None,
        key_label: str = "",
    ) -> None:
        self._on_save = on_save
        self._on_navigate = on_navigate
        self._closed = False

        # Acordes del tono para recorrer con ↑↓ (vacío = solo escritura manual)
        self._suggestions = suggestions or []
        # Evita que el trace reinicie el índice al fijar una sugerencia por código
        self._programmatic = False
        # Si el valor inicial (acorde existente o sugerido) está en la lista del
        # tono, arrancamos la navegación posicionados en él; el "tope" del ciclo
        # (al que se vuelve dando la vuelta) queda vacío. Si no, el valor es el
        # texto tecleado y ocupa ese tope.
        if value and value in self._suggestions:
            self._sugg_index: int | None = self._suggestions.index(value)
            self._typed = ""
        else:
            self._sugg_index = None
            self._typed = value

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

        # Pista discreta: tono actual + recordatorio de las flechas
        if self._suggestions:
            hint = f"↑↓ {key_label}".strip()
            tk.Label(
                self.top,
                text=hint,
                bg=THEME["accent"],
                fg=THEME["bg"],
                font=THEME["font_section"],
            ).pack(fill="x", pady=(0, 1))

        self._bind_keys()
        self._position_over(anchor)

        self._entry.focus_force()
        self._entry.select_range(0, "end")
        self._var.trace_add("write", lambda *_: self._on_text_changed())
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
        # Flechas: recorrer los acordes del tono (estilo historial de terminal)
        self._entry.bind("<Down>", lambda _e: self._cycle_suggestion(1))
        self._entry.bind("<Up>", lambda _e: self._cycle_suggestion(-1))
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

    def _on_text_changed(self) -> None:
        """Si el usuario teclea, abandona la lista y recuerda lo escrito."""
        if not self._programmatic:
            self._sugg_index = None
            self._typed = self._var.get()
        self._update_validity()

    # ------------------------------------------------------------------
    # Navegación por los acordes del tono
    # ------------------------------------------------------------------

    def _cycle_suggestion(self, direction: int) -> str:
        """Recorre los acordes del tono dentro del Entry, en ciclo.

        El ciclo incluye el texto tecleado por el usuario como posición "tope":
        ``texto → 1º → 2º → … → último → texto`` con ↓ (ascendente) y al revés
        con ↑ (descendente). Ambas flechas entran a la lista desde el primer
        toque y dan la vuelta hasta el texto, como el historial de la terminal.
        """
        if not self._suggestions:
            return "break"

        n = len(self._suggestions)
        cur = self._sugg_index

        if direction > 0:  # ↓ : avanzar (ascendente)
            if cur is None:
                new_index: int | None = 0
            elif cur == n - 1:
                new_index = None  # vuelta al texto tecleado
            else:
                new_index = cur + 1
        else:  # ↑ : retroceder (descendente)
            if cur is None:
                new_index = n - 1
            elif cur == 0:
                new_index = None  # vuelta al texto tecleado
            else:
                new_index = cur - 1

        self._sugg_index = new_index
        text = self._typed if new_index is None else self._suggestions[new_index]
        self._set_text(text)
        return "break"

    def _set_text(self, text: str) -> None:
        """Fija el texto del Entry sin que el trace lo trate como escritura manual."""
        self._programmatic = True
        self._var.set(text)
        self._programmatic = False
        self._entry.icursor("end")
        self._entry.select_range(0, "end")
        self._update_validity()

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
