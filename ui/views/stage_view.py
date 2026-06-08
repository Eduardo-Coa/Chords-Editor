"""Vista escenario: pantalla limpia y grande para tocar en vivo."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk

from models.song import Song
from models.transposer import transpose_song
from ui.app import THEME
from ui.widgets.chord_grid import ChordGrid, STAGE_LYRIC_SIZE_DEFAULT

# Velocidad de scroll automático: píxeles por segundo, independiente del largo
# de la canción. El slider (1-10) multiplica estos píxeles por segundo.
_SCROLL_TICK_MS = 40
_SCROLL_PX_PER_SPEED = 6.0  # px/s por cada unidad del slider (vel. 5 ≈ 30 px/s)


class StageView:
    """Ventana de pantalla completa con la canción para el escenario."""

    def __init__(self, parent: tk.Misc, song: Song, offset: int = 0) -> None:
        self._base = song
        self._offset = offset
        self._lyric_size = STAGE_LYRIC_SIZE_DEFAULT

        self._scrolling = False
        self._scroll_after: str | None = None
        self._scroll_frac = 0.0  # posición acumulada (float), evita redondeo sub-pixel

        self.top = tk.Toplevel(parent)
        self.top.title(song.title)
        self.top.configure(bg=THEME["bg"])
        self._fullscreen = True
        self.top.attributes("-fullscreen", True)

        self._build_canvas()
        self._build_transpose_panel()
        self._build_controls_panel()
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
        self._window = self._canvas.create_window((40, 30), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", lambda _e: self._center())

        self._grid = ChordGrid(self._inner, None, mode="stage")
        self._grid.set_stage_font_size(self._lyric_size)
        self._grid.pack(fill="both", expand=True, anchor="nw")

    def _build_transpose_panel(self) -> None:
        """Mini panel de transposición, oculto por defecto (tecla T)."""
        self._panel = tk.Frame(self.top, bg=THEME["surface2"])
        self._panel_visible = False

        tk.Button(self._panel, text="−", width=3, command=lambda: self._transpose(-1),
                  bg=THEME["surface2"], fg=THEME["text"], relief="flat",
                  activebackground=THEME["border"], font=THEME["font_ui"]).pack(side="left", padx=2, pady=2)
        self._offset_lbl = tk.Label(self._panel, text="0", width=4, bg=THEME["surface2"],
                                    fg=THEME["accent"], font=THEME["font_ui"])
        self._offset_lbl.pack(side="left")
        tk.Button(self._panel, text="+", width=3, command=lambda: self._transpose(1),
                  bg=THEME["surface2"], fg=THEME["text"], relief="flat",
                  activebackground=THEME["border"], font=THEME["font_ui"]).pack(side="left", padx=2, pady=2)

    def _build_controls_panel(self) -> None:
        """Panel de controles (fuente, scroll, velocidad), oculto por defecto (tecla C)."""
        self._controls = tk.Frame(self.top, bg=THEME["surface2"])
        self._controls_visible = False

        def boton(text, cmd, w=3):
            return tk.Button(self._controls, text=text, width=w, command=cmd,
                             bg=THEME["surface2"], fg=THEME["text"], relief="flat",
                             activebackground=THEME["border"], font=THEME["font_ui"])

        boton("A−", lambda: self._change_font(-2)).pack(side="left", padx=2, pady=4)
        boton("A+", lambda: self._change_font(2)).pack(side="left", padx=2, pady=4)

        self._play_btn = boton("▶", self._toggle_scroll)
        self._play_btn.pack(side="left", padx=(12, 2), pady=4)

        tk.Label(self._controls, text="Vel.", bg=THEME["surface2"],
                 fg=THEME["text_muted"], font=THEME["font_ui"]).pack(side="left", padx=(8, 2))
        self._speed_var = tk.DoubleVar(value=5.0)
        ttk.Scale(self._controls, from_=1, to=10, variable=self._speed_var,
                  orient="horizontal", length=120).pack(side="left", padx=(0, 8), pady=4)

    def _bind_keys(self) -> None:
        self.top.bind("<Escape>", lambda _e: self.close())
        self.top.bind("<f>", lambda _e: self._toggle_fullscreen())
        self.top.bind("<F>", lambda _e: self._toggle_fullscreen())
        self.top.bind("<t>", lambda _e: self._toggle_panel())
        self.top.bind("<T>", lambda _e: self._toggle_panel())
        self.top.bind("<c>", lambda _e: self._toggle_controls())
        self.top.bind("<C>", lambda _e: self._toggle_controls())
        self.top.bind("<space>", lambda _e: self._toggle_scroll())
        self.top.bind("<Up>", lambda _e: self._canvas.yview_scroll(-1, "units"))
        self.top.bind("<Down>", lambda _e: self._canvas.yview_scroll(1, "units"))
        self.top.bind("<MouseWheel>", self._on_mousewheel)

    # ------------------------------------------------------------------
    # Centrado
    # ------------------------------------------------------------------

    def _on_inner_configure(self, _e: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._center()

    def _center(self) -> None:
        """Centra horizontalmente el bloque de la canción en la pantalla."""
        cw = self._canvas.winfo_width()
        content_w = self._inner.winfo_reqwidth()
        x = max((cw - content_w) // 2, 20)
        self._canvas.coords(self._window, x, 30)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _render(self) -> None:
        display = self._base if self._offset == 0 else transpose_song(self._base, self._offset)
        self._grid.set_song(display)
        self._offset_lbl.config(text=f"{self._offset:+d}".replace("+0", "0"))
        self.top.after_idle(self._center)

    def _transpose(self, delta: int) -> None:
        self._offset += delta
        self._render()

    def _change_font(self, delta: int) -> None:
        self._lyric_size = max(10, self._lyric_size + delta)
        self._grid.set_stage_font_size(self._lyric_size)
        self.top.after_idle(self._center)

    def _toggle_panel(self) -> None:
        if self._panel_visible:
            self._panel.place_forget()
        else:
            self._panel.place(relx=1.0, y=10, x=-10, anchor="ne")
        self._panel_visible = not self._panel_visible

    def _toggle_controls(self) -> None:
        if self._controls_visible:
            self._controls.place_forget()
        else:
            self._controls.place(relx=0.5, rely=1.0, y=-12, anchor="s")
        self._controls_visible = not self._controls_visible

    def _toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        self.top.attributes("-fullscreen", self._fullscreen)

    # ------------------------------------------------------------------
    # Scroll automático
    # ------------------------------------------------------------------

    def _toggle_scroll(self) -> None:
        self._scrolling = not self._scrolling
        self._play_btn.config(text="⏸" if self._scrolling else "▶")
        if self._scrolling:
            # Sincronizar el acumulador con la posición visible actual al arrancar.
            self._scroll_frac = self._canvas.yview()[0]
            self._auto_tick()
        elif self._scroll_after is not None:
            self.top.after_cancel(self._scroll_after)
            self._scroll_after = None

    def _auto_tick(self) -> None:
        if not self._scrolling:
            return
        _, bottom = self._canvas.yview()
        if bottom >= 1.0:  # llegó al final: detener
            self._scrolling = False
            self._play_btn.config(text="▶")
            return
        # Convertir píxeles/segundo a fracción de la canción para este tick, usando
        # la altura total del contenido: misma velocidad visual sin importar el largo.
        # Acumulamos en self._scroll_frac (float) para no perder los avances
        # sub-pixel que el canvas redondearía a cero a velocidades bajas.
        bbox = self._canvas.bbox("all")
        total_px = (bbox[3] - bbox[1]) if bbox else 0
        if total_px > 0:
            px_this_tick = self._speed_var.get() * _SCROLL_PX_PER_SPEED * (_SCROLL_TICK_MS / 1000)
            self._scroll_frac += px_this_tick / total_px
            self._canvas.yview_moveto(self._scroll_frac)
        self._scroll_after = self.top.after(_SCROLL_TICK_MS, self._auto_tick)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def close(self) -> None:
        self._scrolling = False
        if self._scroll_after is not None:
            self.top.after_cancel(self._scroll_after)
        self.top.destroy()
