"""Vista escenario: pantalla limpia y grande para tocar en vivo."""

from __future__ import annotations
import tkinter as tk

import customtkinter as ctk

from models.song import Song
from models.transposer import display_song
from ui.app import THEME, ctk_button_style
from ui.widgets.chord_grid import ChordGrid, STAGE_LYRIC_SIZE_DEFAULT

# Velocidad de scroll automático: píxeles por segundo, independiente del largo
# de la canción. El slider (1-10) multiplica estos píxeles por segundo.
_SCROLL_TICK_MS = 40
_SCROLL_PX_PER_SPEED = 6.0  # px/s por cada unidad del slider (vel. 5 ≈ 30 px/s)


class StageView:
    """Ventana de pantalla completa con la canción para el escenario."""

    def __init__(
        self,
        parent: tk.Misc,
        song: Song | None = None,
        offset: int = 0,
        *,
        playlist: list[tuple[Song, int]] | None = None,
        index: int = 0,
    ) -> None:
        # playlist: lista de (Song, offset) para una presentación. Si no viene,
        # se envuelve la canción suelta para reusar el mismo flujo.
        if playlist:
            self._items: list[tuple[Song, int]] = list(playlist)
        else:
            assert song is not None, "StageView requiere song o playlist"
            self._items = [(song, offset)]
        self._index = max(0, min(index, len(self._items) - 1))
        self._base, self._offset = self._items[self._index]
        self._lyric_size = STAGE_LYRIC_SIZE_DEFAULT

        self._scrolling = False
        self._scroll_after: str | None = None
        self._scroll_frac = 0.0  # posición acumulada (float), evita redondeo sub-pixel

        self.top = tk.Toplevel(parent)
        self.top.title(self._base.title)
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

        self._title_lbl = tk.Label(
            self._inner, text="", bg=THEME["bg"], fg=THEME["chord"], anchor="center",
        )
        self._title_lbl.pack(fill="x", pady=(0, 14))

        self._grid = ChordGrid(self._inner, None, mode="stage")
        self._grid.set_stage_font_size(self._lyric_size)
        self._grid.pack(fill="both", expand=True, anchor="nw")
        self._update_title()

    def _build_transpose_panel(self) -> None:
        """Mini panel de transposición, oculto por defecto (tecla T)."""
        self._panel = ctk.CTkFrame(self.top, fg_color=THEME["surface2"])
        self._panel_visible = False

        ctk.CTkButton(self._panel, text="−", width=36, command=lambda: self._transpose(-1),
                      **ctk_button_style("normal", THEME["font_list"])).pack(side="left", padx=2, pady=2)
        self._offset_lbl = ctk.CTkLabel(self._panel, text="0", width=40,
                                        text_color=THEME["accent"], font=THEME["font_list"])
        self._offset_lbl.pack(side="left")
        ctk.CTkButton(self._panel, text="+", width=36, command=lambda: self._transpose(1),
                      **ctk_button_style("normal", THEME["font_list"])).pack(side="left", padx=2, pady=2)

        self._make_draggable(self._panel, self._offset_lbl)

    def _build_controls_panel(self) -> None:
        """Panel de controles (fuente, scroll, velocidad), oculto por defecto (tecla C)."""
        self._controls = ctk.CTkFrame(self.top, fg_color=THEME["surface2"])
        self._controls_visible = False

        def boton(text, cmd, w=36):
            return ctk.CTkButton(self._controls, text=text, width=w, command=cmd,
                                 **ctk_button_style("normal", THEME["font_list"]))

        boton("A−", lambda: self._change_font(-2)).pack(side="left", padx=2, pady=4)
        boton("A+", lambda: self._change_font(2)).pack(side="left", padx=2, pady=4)

        self._play_btn = boton("▶", self._toggle_scroll)
        self._play_btn.pack(side="left", padx=(12, 2), pady=4)

        vel_lbl = ctk.CTkLabel(self._controls, text="Vel.", text_color=THEME["text_muted"],
                               font=THEME["font_list"])
        vel_lbl.pack(side="left", padx=(8, 2))
        self._speed_var = tk.DoubleVar(value=5.0)
        ctk.CTkSlider(self._controls, from_=1, to=10, variable=self._speed_var,
                      width=120).pack(side="left", padx=(0, 8), pady=4)

        # Navegación entre canciones de la lista (solo si hay más de una)
        self._nav_lbl: ctk.CTkLabel | None = None
        if len(self._items) > 1:
            self._prev_btn = boton("«", lambda: self._goto(-1))
            self._prev_btn.pack(side="left", padx=(12, 2), pady=4)
            self._nav_lbl = ctk.CTkLabel(
                self._controls, text="", text_color=THEME["accent"], font=THEME["font_list"],
            )
            self._nav_lbl.pack(side="left", padx=2)
            self._next_btn = boton("»", lambda: self._goto(1))
            self._next_btn.pack(side="left", padx=2, pady=4)
            self._update_nav_label()

        self._make_draggable(self._controls, vel_lbl)

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
        # Navegación entre canciones de la lista
        self.top.bind("<Right>", lambda _e: self._goto(1))
        self.top.bind("<Next>", lambda _e: self._goto(1))     # Av Pág
        self.top.bind("<Left>", lambda _e: self._goto(-1))
        self.top.bind("<Prior>", lambda _e: self._goto(-1))   # Re Pág

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

    def _update_title(self) -> None:
        """Actualiza el título de la canción en escenario (color y tamaño de acorde, algo mayor)."""
        family = THEME["font_stage"][0]
        size = round(self._grid.stage_chord_size * 1.4)
        self._title_lbl.config(text=self._base.title, font=(family, size, "bold"))

    def _render(self) -> None:
        display = display_song(self._base, self._offset)
        self._grid.set_song(display)
        self._update_title()
        self._offset_lbl.configure(text=f"{self._offset:+d}".replace("+0", "0"))
        self.top.after_idle(self._center)

    def _transpose(self, delta: int) -> None:
        self._offset += delta
        self._render()

    def _goto(self, delta: int) -> None:
        """Pasa a la siguiente/anterior canción de la lista (con tope en los extremos)."""
        new_index = self._index + delta
        if not (0 <= new_index < len(self._items)) or new_index == self._index:
            return
        # Conservar la transposición en vivo de la canción actual al movernos
        self._items[self._index] = (self._base, self._offset)
        self._index = new_index
        self._base, self._offset = self._items[self._index]

        # Detener auto-scroll y volver al inicio de la nueva canción
        if self._scrolling:
            self._toggle_scroll()
        self._scroll_frac = 0.0
        self._canvas.yview_moveto(0.0)

        self.top.title(self._base.title)
        self._update_nav_label()
        self._render()

    def _update_nav_label(self) -> None:
        """Actualiza el indicador 'n/total — Título' del panel de navegación."""
        if self._nav_lbl is not None:
            self._nav_lbl.configure(
                text=f"{self._index + 1}/{len(self._items)}  ·  {self._base.title}"
            )

    def _change_font(self, delta: int) -> None:
        self._lyric_size = max(10, self._lyric_size + delta)
        self._grid.set_stage_font_size(self._lyric_size)
        self._update_title()
        self.top.after_idle(self._center)

    def _make_draggable(self, panel: tk.Misc, *grips: tk.Misc) -> None:
        """Permite mover ``panel`` arrastrándolo por su fondo o por los ``grips``.

        Los botones y el slider conservan su función (no se les enlaza el arrastre).
        La posición se recuerda (``panel._pos``) para re-mostrarlo donde se dejó.
        """
        def start(event: tk.Event) -> None:
            self._drag_dx = event.x_root - panel.winfo_rootx()
            self._drag_dy = event.y_root - panel.winfo_rooty()

        def move(event: tk.Event) -> None:
            parent = panel.master
            x = event.x_root - self._drag_dx - parent.winfo_rootx()
            y = event.y_root - self._drag_dy - parent.winfo_rooty()
            panel.place_configure(x=x, y=y, relx=0, rely=0, anchor="nw")
            panel._pos = (x, y)  # type: ignore[attr-defined]

        for widget in (panel, *grips):
            widget.bind("<Button-1>", start, add="+")
            widget.bind("<B1-Motion>", move, add="+")

    def _place_panel(self, panel: tk.Misc, default: dict) -> None:
        """Muestra el panel en su última posición arrastrada, o en la de por defecto."""
        pos = getattr(panel, "_pos", None)
        if pos is not None:
            panel.place(x=pos[0], y=pos[1], anchor="nw")
        else:
            panel.place(**default)

    def _toggle_panel(self) -> None:
        if self._panel_visible:
            self._panel.place_forget()
        else:
            self._place_panel(self._panel, dict(relx=1.0, y=10, x=-10, anchor="ne"))
        self._panel_visible = not self._panel_visible

    def _toggle_controls(self) -> None:
        if self._controls_visible:
            self._controls.place_forget()
        else:
            self._place_panel(self._controls, dict(relx=0.5, rely=1.0, y=-12, anchor="s"))
        self._controls_visible = not self._controls_visible

    def _toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        self.top.attributes("-fullscreen", self._fullscreen)

    # ------------------------------------------------------------------
    # Scroll automático
    # ------------------------------------------------------------------

    def _toggle_scroll(self) -> None:
        self._scrolling = not self._scrolling
        self._play_btn.configure(text="⏸" if self._scrolling else "▶")
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
            self._play_btn.configure(text="▶")
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
