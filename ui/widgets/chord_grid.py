"""Widget central: renderiza una canción como grilla de sílabas con acordes."""

from __future__ import annotations
from typing import Callable
import tkinter as tk

from models.song import Song, Syllable
from ui.app import THEME

# Sílabas que son solo puntuación: no llevan espacio de acorde encima
PUNCTUATION = set(",.;:!¡?¿…")

# Etiquetas legibles para cada tipo de sección
SECTION_LABELS = {
    "verse": "Estrofa",
    "chorus": "Coro",
    "bridge": "Puente",
    "intro": "Intro",
    "outro": "Final",
}


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
        on_split: Callable[[Syllable], None] | None = None,
        on_merge: Callable[[Syllable], None] | None = None,
    ) -> None:
        bg = THEME["bg"]
        super().__init__(parent, bg=bg)
        self.song = song
        self.mode = mode
        self._on_chord_click = on_chord_click
        self._on_split = on_split
        self._on_merge = on_merge

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

    def render(self) -> None:
        """Reconstruye toda la grilla desde el modelo actual."""
        for child in self.winfo_children():
            child.destroy()
        self._chord_widgets.clear()
        self._ordered.clear()

        if self.song is None:
            return

        for section in self.song.sections:
            self._render_section(section)

    def get_chord_widget(self, syllable: Syllable) -> tk.Widget | None:
        """Devuelve el widget de acorde de una sílaba (para anclar el popup)."""
        return self._chord_widgets.get(id(syllable))

    def editable_syllables(self) -> list[Syllable]:
        """Lista ordenada de sílabas editables (sin puntuación)."""
        return list(self._ordered)

    # ------------------------------------------------------------------
    # Render de secciones y líneas
    # ------------------------------------------------------------------

    def _render_section(self, section) -> None:
        """Dibuja la etiqueta de la sección y todas sus líneas."""
        label_text = section.label or SECTION_LABELS.get(section.type, "")
        if label_text:
            label = tk.Label(
                self,
                text=label_text.upper(),
                bg=THEME["bg"],
                fg=THEME["section_label"],
                font=THEME["font_section"],
                anchor="w",
            )
            label.pack(fill="x", padx=12, pady=(12, 2))

        for line in section.lines:
            self._render_line(line)

    def _render_line(self, line) -> None:
        """Dibuja una línea como una fila horizontal de sílabas."""
        row = tk.Frame(self, bg=THEME["bg"])
        row.pack(fill="x", anchor="w", padx=12, pady=1)

        # Línea vacía: separador visual entre estrofas
        if not line.syllables:
            tk.Frame(row, bg=THEME["bg"], height=12).pack()
            return

        for syllable in line.syllables:
            self._render_syllable(row, syllable)

    def _render_syllable(self, parent: tk.Frame, syllable: Syllable) -> None:
        """Dibuja una sílaba (acorde encima + texto debajo)."""
        is_punct = _is_punctuation(syllable.text)
        is_slot = _is_slot(syllable.text)
        chord_value = syllable.chord.value if syllable.chord else ""

        # En escenario, las ranuras vacías sin acorde no se muestran
        if self.mode == "stage" and is_slot and not chord_value:
            return

        cell = tk.Frame(parent, bg=THEME["bg"])
        # Pequeña separación antes de las ranuras de acordes de paso
        cell.pack(side="left", anchor="n", padx=(3, 0) if is_slot else 0)

        if self.mode == "stage":
            self._render_stage_cell(cell, syllable, chord_value, is_punct)
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

        # Menú contextual para dividir / unir sílabas (no aplica a ranuras)
        if not is_punct and not is_slot:
            syl_lbl.bind(
                "<Button-3>",
                lambda e, s=syllable: self._show_context_menu(e, s),
            )

    def _handle_chord_click(self, syllable: Syllable, widget: tk.Widget) -> None:
        """Notifica que se hizo clic en el espacio de acorde de una sílaba."""
        if self._on_chord_click is not None:
            self._on_chord_click(syllable, widget)

    def _show_context_menu(self, event: tk.Event, syllable: Syllable) -> None:
        """Muestra opciones de dividir/unir sílaba con clic derecho."""
        menu = tk.Menu(self, tearoff=0, bg=THEME["surface2"], fg=THEME["text"])
        menu.add_command(
            label="÷  Dividir sílaba",
            command=lambda: self._on_split(syllable) if self._on_split else None,
        )
        menu.add_command(
            label="+  Unir con siguiente",
            command=lambda: self._on_merge(syllable) if self._on_merge else None,
        )
        menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------
    # Modo escenario
    # ------------------------------------------------------------------

    def _render_stage_cell(
        self, cell: tk.Frame, syllable: Syllable, chord_value: str, is_punct: bool
    ) -> None:
        """Celda de escenario: acorde en color encima, sílaba grande debajo."""
        if chord_value and not is_punct:
            tk.Label(
                cell,
                text=chord_value,
                bg=THEME["bg"],
                fg=THEME["chord"],
                font=THEME["font_chord_stage"] + ("bold",),
                anchor="w",
            ).pack(side="top", anchor="w")
        else:
            # Sin acorde: espacio vacío encima (no se muestra nada)
            tk.Label(
                cell,
                text=" ",
                bg=THEME["bg"],
                font=THEME["font_chord_stage"],
            ).pack(side="top", anchor="w")

        tk.Label(
            cell,
            text=syllable.text,
            bg=THEME["bg"],
            fg=THEME["text"],
            font=THEME["font_stage"],
            anchor="w",
        ).pack(side="top", anchor="w")
