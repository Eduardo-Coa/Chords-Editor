"""Widget central: renderiza una canción como grilla de sílabas con acordes."""

from __future__ import annotations
from typing import Callable
import tkinter as tk

from models.song import Song, Syllable
from ui.app import THEME
from utils.song_text import line_to_chord_lyric, SECTION_LABELS

# Sílabas que son solo puntuación: no llevan espacio de acorde encima
PUNCTUATION = set(",.;:!¡?¿…")

# Tamaños por defecto de fuente en modo escenario (un poco más pequeños que THEME)
STAGE_LYRIC_SIZE_DEFAULT = 12
STAGE_CHORD_SIZE_DEFAULT = 10

def _is_punctuation(text: str) -> bool:
    """Devuelve True si la sílaba es únicamente signos de puntuación (ignora espacios)."""
    stripped = text.strip()
    return stripped != "" and all(c in PUNCTUATION for c in stripped)


def _is_slot(text: str) -> bool:
    """Devuelve True si la sílaba es una ranura vacía para acorde de paso."""
    return text.strip() == ""


class ChordGrid(tk.Frame):
    """Renderiza una canción en modo edición o escenario."""

    def __init__(
        self,
        parent: tk.Misc,
        song: Song | None = None,
        mode: str = "edit",
        on_chord_click: Callable[[Syllable, tk.Widget], None] | None = None,
        on_add_left: Callable[[Syllable], None] | None = None,
        on_add_right: Callable[[Syllable], None] | None = None,
        on_remove: Callable[[Syllable], None] | None = None,
        on_section_transpose: Callable[[int, int], None] | None = None,
    ) -> None:
        bg = THEME["bg"]
        super().__init__(parent, bg=bg)
        self.song = song
        self.mode = mode
        self._on_chord_click = on_chord_click
        self._on_add_left = on_add_left
        self._on_add_right = on_add_right
        self._on_remove = on_remove
        self._on_section_transpose = on_section_transpose

        # Tamaños de fuente del modo escenario (ajustables en vivo)
        self.stage_lyric_size = STAGE_LYRIC_SIZE_DEFAULT
        self.stage_chord_size = STAGE_CHORD_SIZE_DEFAULT
        # Fondo del modo escenario: override propio (p. ej. negro puro) para no
        # mutar el THEME global, que comparte el modo edición.
        self.stage_bg = THEME["bg"]

        # Mapas reconstruidos en cada render() para anclar el popup y navegar
        self._chord_widgets: dict[int, tk.Widget] = {}
        self._ordered: list[Syllable] = []

        self.render()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_song(self, song: Song | None) -> None:
        """Asigna una nueva canción y vuelve a renderizar."""
        self.song = song
        self.render()

    def set_mode(self, mode: str) -> None:
        """Cambia entre 'edit' y 'stage' y vuelve a renderizar."""
        self.mode = mode
        self.render()

    def set_stage_font_size(self, lyric_size: int) -> None:
        """Ajusta el tamaño de fuente del modo escenario (acorde escala con la letra)."""
        self.stage_lyric_size = max(10, lyric_size)
        self.stage_chord_size = max(8, round(lyric_size * 0.78))
        if self.mode == "stage":
            self.render()

    def set_stage_bg(self, color: str) -> None:
        """Fija el color de fondo del modo escenario (p. ej. negro puro) y re-renderiza."""
        self.stage_bg = color
        if self.mode == "stage":
            self.render()

    def _bg(self) -> str:
        """Color de fondo según el modo: override de escenario o el del tema."""
        return self.stage_bg if self.mode == "stage" else THEME["bg"]

    def render(self) -> None:
        """Reconstruye toda la grilla desde el modelo actual."""
        self.configure(bg=self._bg())
        for child in self.winfo_children():
            child.destroy()
        self._chord_widgets.clear()
        self._ordered.clear()

        if self.song is None:
            return

        for i, section in enumerate(self.song.sections):
            self._render_section(section, i)

    def get_chord_widget(self, syllable: Syllable) -> tk.Widget | None:
        """Devuelve el widget de acorde de una sílaba (para anclar el popup)."""
        return self._chord_widgets.get(id(syllable))

    def editable_syllables(self) -> list[Syllable]:
        """Lista ordenada de sílabas editables (sin puntuación)."""
        return list(self._ordered)

    # ------------------------------------------------------------------
    # Render de secciones y líneas
    # ------------------------------------------------------------------

    def _render_section(self, section, index: int = 0) -> None:
        """Dibuja la etiqueta de la sección, su control de tono y todas sus líneas."""
        label_text = section.label or SECTION_LABELS.get(section.type, "")
        # El control de modulación por bloque solo aparece en edición y de la
        # segunda sección en adelante (la primera es la referencia en tono base).
        show_control = (
            self.mode == "edit" and index >= 1
            and self._on_section_transpose is not None
        )
        if label_text or show_control:
            header = tk.Frame(self, bg=self._bg())
            header.pack(fill="x", padx=12, pady=(12, 2))
            if label_text:
                tk.Label(
                    header, text=label_text.upper(), bg=self._bg(),
                    fg=THEME["section_label"], font=THEME["font_section"], anchor="w",
                ).pack(side="left")
            if show_control:
                self._render_section_control(header, section, index)

        for line in section.lines:
            self._render_line(line)

    def _render_section_control(self, header: tk.Frame, section, index: int) -> None:
        """Mini control [−] tono [+] para modular esta sección respecto al tono base."""
        box = tk.Frame(header, bg=THEME["bg"])
        box.pack(side="right")

        tk.Label(box, text="Tono del bloque", bg=THEME["bg"], fg=THEME["text_muted"],
                 font=THEME["font_section"]).pack(side="left", padx=(0, 4))

        def btn(text: str, delta: int) -> tk.Button:
            return tk.Button(
                box, text=text, width=2, relief="flat",
                bg=THEME["surface2"], fg=THEME["text"],
                activebackground=THEME["border"], font=THEME["font_section"],
                command=lambda: self._on_section_transpose(index, delta),
            )

        btn("−", -1).pack(side="left")
        off = section.transpose
        tk.Label(
            box, text=f"{off:+d}".replace("+0", "0"), bg=THEME["bg"],
            fg=THEME["chord"] if off else THEME["text_muted"],
            font=THEME["font_section"], width=3,
        ).pack(side="left")
        btn("+", 1).pack(side="left")

    def _render_line(self, line) -> None:
        """Dibuja una línea: dos textos apilados en escenario, celdas en edición."""
        if self.mode == "stage":
            self._render_stage_line(line)
            return

        row = tk.Frame(self, bg=THEME["bg"])
        row.pack(fill="x", anchor="w", padx=12, pady=1)

        # Línea vacía: separador visual entre estrofas
        if not line.syllables:
            tk.Frame(row, bg=THEME["bg"], height=12).pack()
            return

        # Línea de solo acordes (intro/interludio/entrada de estrofa)
        is_chord_line = all(_is_slot(s.text) for s in line.syllables)

        # Índice de la última sílaba con texto real: una ranura es "interior"
        # si hay texto después de ella (entre sílabas/palabras)
        last_text_index = -1
        for i, syl in enumerate(line.syllables):
            if not _is_slot(syl.text):
                last_text_index = i

        for i, syllable in enumerate(line.syllables):
            # En una línea de acordes, cada casilla con acorde lleva guión en escenario
            interior_slot = _is_slot(syllable.text) and (i < last_text_index or is_chord_line)
            self._render_syllable(row, syllable, interior_slot)

    def _render_stage_line(self, line) -> None:
        """Dibuja una línea de escenario como dos textos monoespaciados apilados:
        la letra continua (palabras sin partir) y los acordes alineados por columna
        encima de la sílaba a la que corresponden.
        """
        bg = self._bg()
        row = tk.Frame(self, bg=bg)
        row.pack(fill="x", anchor="w", padx=12, pady=0)

        # Línea vacía: separador visual entre estrofas
        if not line.syllables:
            tk.Frame(row, bg=bg, height=12).pack()
            return

        # Fila de acordes (alineada por columnas) y fila de letra. Misma lógica que
        # usa el copiado al portapapeles y el export (utils.song_text): fuente única.
        chord_str, lyric_str = line_to_chord_lyric(line)

        # Línea sin acordes ni letra (p. ej. casillas vacías): no mostrar nada
        if not chord_str and not lyric_str:
            row.destroy()
            return

        family = THEME["font_stage"][0]
        size = self.stage_lyric_size  # mismo tamaño en ambas filas → columnas alineadas
        if chord_str:
            tk.Label(
                row, text=chord_str, bg=bg, fg=THEME["chord"],
                font=(family, size, "bold"), anchor="w", justify="left",
            ).pack(side="top", anchor="w")
        if lyric_str:
            tk.Label(
                row, text=lyric_str, bg=bg, fg=THEME["text"],
                font=(family, size), anchor="w", justify="left",
            ).pack(side="top", anchor="w")

    def _render_syllable(
        self, parent: tk.Frame, syllable: Syllable, interior_slot: bool = False
    ) -> None:
        """Dibuja una sílaba (acorde encima + texto debajo)."""
        is_punct = _is_punctuation(syllable.text)
        is_slot = _is_slot(syllable.text)
        chord_value = syllable.chord.value if syllable.chord else ""

        # En escenario, las ranuras vacías sin acorde no se muestran
        if self.mode == "stage" and is_slot and not chord_value:
            return

        cell = tk.Frame(parent, bg=self._bg())
        # Pequeña separación antes de las ranuras de acordes de paso
        cell.pack(side="left", anchor="n", padx=(3, 0) if is_slot else 0)

        if self.mode == "stage":
            self._render_stage_cell(cell, syllable, chord_value, is_punct, interior_slot)
        else:
            self._render_edit_cell(cell, syllable, chord_value, is_punct, is_slot)

    # ------------------------------------------------------------------
    # Modo edición
    # ------------------------------------------------------------------

    def _render_edit_cell(
        self,
        cell: tk.Frame,
        syllable: Syllable,
        chord_value: str,
        is_punct: bool,
        is_slot: bool = False,
    ) -> None:
        """Celda de edición: Entry de acorde clicable arriba, sílaba abajo."""
        width = max(len(chord_value), len(syllable.text), 2)

        if not is_punct:
            chord_lbl = tk.Label(
                cell,
                text=chord_value or "·",
                width=width,
                bg=THEME["chord_bg"],
                fg=THEME["chord"] if chord_value else THEME["text_muted"],
                font=THEME["font_mono"],
                cursor="hand2",
            )
            chord_lbl.pack(side="top", fill="x")
            chord_lbl.bind(
                "<Button-1>",
                lambda _e, s=syllable, w=chord_lbl: self._handle_chord_click(s, w),
            )
            self._chord_widgets[id(syllable)] = chord_lbl
            self._ordered.append(syllable)
        else:
            # Puntuación: espacio en blanco arriba (sin acorde)
            tk.Frame(cell, bg=THEME["bg"], height=1).pack(side="top", fill="x")

        syl_lbl = tk.Label(
            cell,
            text=syllable.text,
            width=width,
            bg=THEME["surface2"] if is_slot else THEME["surface"],
            fg=THEME["text_muted"] if is_slot else THEME["text"],
            font=THEME["font_mono"],
        )
        syl_lbl.pack(side="top", fill="x")

        # Menú contextual para agregar casillas a izquierda/derecha (en cualquier celda)
        syl_lbl.bind(
            "<Button-3>",
            lambda e, s=syllable: self._show_context_menu(e, s),
        )

    def _handle_chord_click(self, syllable: Syllable, widget: tk.Widget) -> None:
        """Notifica que se hizo clic en el espacio de acorde de una sílaba."""
        if self._on_chord_click is not None:
            self._on_chord_click(syllable, widget)

    def _show_context_menu(self, event: tk.Event, syllable: Syllable) -> None:
        """Muestra opciones para agregar una casilla de acorde a izquierda/derecha."""
        menu = tk.Menu(self, tearoff=0, bg=THEME["surface2"], fg=THEME["text"])
        menu.add_command(
            label="◧  Agregar casilla a la izquierda",
            command=lambda: self._on_add_left(syllable) if self._on_add_left else None,
        )
        menu.add_command(
            label="◨  Agregar casilla a la derecha",
            command=lambda: self._on_add_right(syllable) if self._on_add_right else None,
        )
        # Eliminar solo aplica a casillas (no a sílabas con texto)
        if _is_slot(syllable.text):
            menu.add_separator()
            menu.add_command(
                label="✕  Eliminar casilla",
                command=lambda: self._on_remove(syllable) if self._on_remove else None,
            )
        menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------
    # Modo escenario
    # ------------------------------------------------------------------

    def _render_stage_cell(
        self,
        cell: tk.Frame,
        syllable: Syllable,
        chord_value: str,
        is_punct: bool,
        interior_slot: bool = False,
    ) -> None:
        """Celda de escenario: acorde en color encima, sílaba grande debajo."""
        family = THEME["font_stage"][0]
        chord_font = (family, self.stage_chord_size, "bold")
        lyric_font = (family, self.stage_lyric_size)
        bg = self._bg()

        if chord_value and not is_punct:
            tk.Label(
                cell,
                text=chord_value,
                bg=bg,
                fg=THEME["chord"],
                font=chord_font,
                anchor="w",
            ).pack(side="top", anchor="w")
        else:
            # Sin acorde: espacio vacío encima (no se muestra nada)
            tk.Label(
                cell,
                text=" ",
                bg=bg,
                font=chord_font,
            ).pack(side="top", anchor="w")

        # Una ranura interior con acorde se muestra como guión, para no pegar
        # las palabras y dar apoyo visual al acorde (ej. "coro--nad").
        text = "-" if interior_slot else syllable.text
        tk.Label(
            cell,
            text=text,
            bg=bg,
            fg=THEME["text"],
            font=lyric_font,
            anchor="w",
        ).pack(side="top", anchor="w")
