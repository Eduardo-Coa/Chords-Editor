"""Vista escenario: pantalla limpia y grande para tocar en vivo."""

from __future__ import annotations
import tkinter as tk

from models.song import Song
from models.transposer import transpose_song
from ui.app import THEME
from ui.widgets.chord_grid import ChordGrid


class StageView:
    """Ventana de pantalla completa con la canción para el escenario."""

    def __init__(self, parent: tk.Misc, song: Song, offset: int = 0) -> None:
        self._base = song
        self._offset = offset

        self.top = tk.Toplevel(parent)
        self.top.title(song.title)
        self.top.configure(bg=THEME["bg"])
        self._fullscreen = True
        self.top.attributes("-fullscreen", True)

        self._build_canvas()
        self._build_transpose_panel()
        self._bind_keys()
        self._render()

        self.top.focus_force()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build_canvas(self) -> None:
        self._canvas = tk.Canvas(self.top, bg=THEME["bg"], highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=THEME["bg"])
        self._window = self._canvas.create_window(
            (40, 30), window=self._inner, anchor="nw"
        )
        self._inner.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )

        self._grid = ChordGrid(self._inner, None, mode="stage")
        self._grid.pack(fill="both", expand=True, anchor="nw")

    def _build_transpose_panel(self) -> None:
        """Mini panel de transposición, oculto por defecto (se muestra con T)."""
        self._panel = tk.Frame(self.top, bg=THEME["surface2"])
        self._panel_visible = False

        tk.Button(
            self._panel, text="−", width=3, command=lambda: self._transpose(-1),
            bg=THEME["surface2"], fg=THEME["text"], relief="flat",
            activebackground=THEME["border"], font=THEME["font_ui"],
        ).pack(side="left", padx=2, pady=2)

        self._offset_lbl = tk.Label(
            self._panel, text="0", width=4, bg=THEME["surface2"],
            fg=THEME["accent"], font=THEME["font_ui"],
        )
        self._offset_lbl.pack(side="left")

        tk.Button(
            self._panel, text="+", width=3, command=lambda: self._transpose(1),
            bg=THEME["surface2"], fg=THEME["text"], relief="flat",
            activebackground=THEME["border"], font=THEME["font_ui"],
        ).pack(side="left", padx=2, pady=2)

    def _bind_keys(self) -> None:
        self.top.bind("<Escape>", lambda _e: self.close())
        self.top.bind("<f>", lambda _e: self._toggle_fullscreen())
        self.top.bind("<F>", lambda _e: self._toggle_fullscreen())
        self.top.bind("<t>", lambda _e: self._toggle_panel())
        self.top.bind("<T>", lambda _e: self._toggle_panel())
        self.top.bind("<Up>", lambda _e: self._canvas.yview_scroll(-1, "units"))
        self.top.bind("<Down>", lambda _e: self._canvas.yview_scroll(1, "units"))
        self.top.bind("<MouseWheel>", self._on_mousewheel)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if self._offset == 0:
            display = self._base
        else:
            display = transpose_song(self._base, self._offset)
        self._grid.set_song(display)
        self._offset_lbl.config(text=f"{self._offset:+d}".replace("+0", "0"))

    def _transpose(self, delta: int) -> None:
        self._offset += delta
        self._render()

    def _toggle_panel(self) -> None:
        if self._panel_visible:
            self._panel.place_forget()
        else:
            self._panel.place(relx=1.0, y=10, x=-10, anchor="ne")
        self._panel_visible = not self._panel_visible

    def _toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        self.top.attributes("-fullscreen", self._fullscreen)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def close(self) -> None:
        self.top.destroy()
