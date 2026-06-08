"""Vista principal de edición: integra lista, metadatos, grilla y herramientas."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import ttk, messagebox

from database.db import Database
from models.song import Song, Chord
from models.transposer import transpose_song
from utils.lyrics_parser import parse_lyrics, merge_lyrics
from ui.app import THEME
from ui.views.song_list import SongList
from ui.widgets.chord_grid import ChordGrid
from ui.widgets.chord_popup import ChordPopup


def _reconstruct_lyrics(song: Song) -> str:
    """Reconstruye el texto plano de la letra (con encabezados [Sección])."""
    lines: list[str] = []
    for section in song.sections:
        if section.label:
            lines.append(f"[{section.label}]")
        for line in section.lines:
            lines.append("".join(s.text for s in line.syllables).strip())
    return "\n".join(lines)


class EditView(ttk.Frame):
    """Pantalla de edición de canciones."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_open_stage: Callable[[Song, int], None] | None = None,
    ) -> None:
        super().__init__(parent, style="TFrame")
        self.db = db
        self._on_open_stage = on_open_stage

        self.song: Song | None = None
        self.transpose_offset = 0
        self._view_mode = "edit"  # 'edit' o 'stage' (escenario inline)

        self._build()

    # ------------------------------------------------------------------
    # Construcción del layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # PanedWindow clásico: ancho inicial 240, mínimo 180, ajustable arrastrando
        paned = tk.PanedWindow(
            self, orient="horizontal", sashwidth=6,
            bg=THEME["border"], bd=0, sashrelief="flat",
        )
        paned.pack(fill="both", expand=True)

        self.song_list = SongList(
            paned, self.db, on_select=self.load_song,
            on_new=self._new_song, on_delete=self._confirm_delete,
        )
        paned.add(self.song_list, minsize=180, width=240, stretch="never")

        right = ttk.Frame(paned, style="TFrame")
        paned.add(right, stretch="always")

        self._build_metadata_bar(right)
        self._build_toolbar(right)
        self._build_content(right)
        self._build_status_bar(right)

    def _build_metadata_bar(self, parent: tk.Misc) -> None:
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=10, pady=(8, 4))

        self._meta_vars: dict[str, tk.StringVar] = {}
        fields = [("title", "Título", 28), ("author", "Autor", 18),
                  ("key", "Tono", 5), ("rhythm", "Ritmo", 10), ("capo", "Capo", 4)]
        for name, label, width in fields:
            ttk.Label(bar, text=label, style="Muted.TLabel").pack(side="left", padx=(6, 2))
            var = tk.StringVar()
            entry = tk.Entry(
                bar, textvariable=var, width=width,
                bg=THEME["surface2"], fg=THEME["text"],
                insertbackground=THEME["text"], relief="flat", font=THEME["font_ui"],
            )
            entry.pack(side="left", ipady=3)
            entry.bind("<FocusOut>", lambda _e: self._commit_metadata())
            self._meta_vars[name] = var

    def _build_toolbar(self, parent: tk.Misc) -> None:
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", padx=10, pady=4)

        ttk.Button(bar, text="Guardar", command=self._autosave).pack(side="left", padx=2)
        self._stage_btn = ttk.Button(bar, text="Vista Escenario", command=self._toggle_stage)
        self._stage_btn.pack(side="left", padx=2)
        ttk.Button(bar, text="⛶", width=3, command=self._open_stage).pack(side="left")
        ttk.Button(bar, text="−", width=3, command=lambda: self._transpose(-1)).pack(side="left", padx=(12, 0))
        self._offset_lbl = ttk.Label(bar, text="0", style="TLabel", width=3, anchor="center")
        self._offset_lbl.pack(side="left")
        ttk.Button(bar, text="+", width=3, command=lambda: self._transpose(1)).pack(side="left")
        ttk.Button(bar, text="Guardar en este tono", command=self._save_in_key).pack(side="left", padx=2)
        ttk.Button(bar, text="Editar letra", command=self._edit_lyrics).pack(side="left", padx=2)
        ttk.Button(bar, text="Eliminar", style="Danger.TButton",
                   command=self._delete_current).pack(side="left", padx=2)

    def _build_content(self, parent: tk.Misc) -> None:
        """Área central que alterna entre la grilla y el editor de letra."""
        self._content = ttk.Frame(parent, style="TFrame")
        self._content.pack(fill="both", expand=True, padx=4, pady=4)

        # Canvas con scroll que contiene la grilla
        self._canvas = tk.Canvas(self._content, bg=THEME["bg"], highlightthickness=0)
        self._vsb = ttk.Scrollbar(self._content, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        self._inner = tk.Frame(self._canvas, bg=THEME["bg"])
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.grid_widget = ChordGrid(
            self._inner, None, mode="edit",
            on_chord_click=self._on_chord_click,
            on_split=self._split_syllable,
            on_merge=self._merge_syllable,
        )
        self.grid_widget.pack(fill="both", expand=True, anchor="nw")

        # Editor de letra (oculto al inicio)
        self._paste_frame = ttk.Frame(self._content, style="TFrame")
        self._paste_text = tk.Text(
            self._paste_frame, bg=THEME["surface"], fg=THEME["text"],
            insertbackground=THEME["text"], relief="flat",
            font=THEME["font_mono"], wrap="word", height=20,
        )
        self._paste_text.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Button(
            self._paste_frame, text="Procesar letra", style="Accent.TButton",
            command=self._process_lyrics,
        ).pack(pady=6)

        self._show_grid()

    def _build_status_bar(self, parent: tk.Misc) -> None:
        bar = ttk.Frame(parent, style="TFrame")
        bar.pack(fill="x", side="bottom")
        self._status = ttk.Label(bar, text="Listo", style="Muted.TLabel", anchor="w")
        self._status.pack(side="left", padx=10, pady=4)

    # ------------------------------------------------------------------
    # Alternar contenido central
    # ------------------------------------------------------------------

    def _show_grid(self) -> None:
        self._paste_frame.pack_forget()
        self._canvas.pack(side="left", fill="both", expand=True)
        self._vsb.pack(side="right", fill="y")

    def _show_paste(self, initial_text: str = "") -> None:
        self._canvas.pack_forget()
        self._vsb.pack_forget()
        self._paste_text.delete("1.0", "end")
        if initial_text:
            self._paste_text.insert("1.0", initial_text)
        else:
            self._paste_text.insert("1.0", "Pega la letra aquí...")
        self._paste_frame.pack(fill="both", expand=True)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    # ------------------------------------------------------------------
    # Flujo de nueva canción / edición de letra
    # ------------------------------------------------------------------

    def _new_song(self) -> None:
        self.song = None
        self.transpose_offset = 0
        self._reset_to_edit_mode()
        for var in self._meta_vars.values():
            var.set("")
        self.grid_widget.set_song(None)
        self._show_paste()
        self._set_status("Pega la letra y pulsa 'Procesar letra'")

    def _edit_lyrics(self) -> None:
        if self.song is None:
            self._new_song()
            return
        self._show_paste(_reconstruct_lyrics(self.song))

    def _process_lyrics(self) -> None:
        text = self._paste_text.get("1.0", "end").strip()
        if not text or text == "Pega la letra aquí...":
            self._set_status("No hay texto para procesar")
            return
        title = self._meta_vars["title"].get().strip() or "Sin título"

        if self.song is not None and self.song.id is not None:
            # Editando una canción existente: misma entrada, conservar acordes
            self.song = merge_lyrics(self.song, text)
        else:
            self.song = parse_lyrics(text, title=title)

        self._apply_metadata_to_song()
        self.transpose_offset = 0
        self._offset_lbl.config(text="0")
        self._autosave()
        self._render_grid()
        self._show_grid()

    # ------------------------------------------------------------------
    # Carga y metadatos
    # ------------------------------------------------------------------

    def load_song(self, song_id: int) -> None:
        self.song = self.db.load_song(song_id)
        self.transpose_offset = 0
        self._offset_lbl.config(text="0")
        self._reset_to_edit_mode()
        self._meta_vars["title"].set(self.song.title)
        self._meta_vars["author"].set(self.song.author or "")
        self._meta_vars["key"].set(self.song.key or "")
        self._meta_vars["rhythm"].set(self.song.rhythm or "")
        self._meta_vars["capo"].set(str(self.song.capo))
        self._render_grid()
        self._show_grid()
        self._set_status(f"Cargada: {self.song.title}")

    def _apply_metadata_to_song(self) -> None:
        if self.song is None:
            return
        self.song.title = self._meta_vars["title"].get().strip() or "Sin título"
        self.song.author = self._meta_vars["author"].get().strip() or None
        self.song.key = self._meta_vars["key"].get().strip() or None
        self.song.rhythm = self._meta_vars["rhythm"].get().strip() or None
        try:
            self.song.capo = int(self._meta_vars["capo"].get())
        except ValueError:
            self.song.capo = 0

    def _commit_metadata(self) -> None:
        if self.song is None:
            return
        self._apply_metadata_to_song()
        self._autosave()

    # ------------------------------------------------------------------
    # Renderizado de la grilla (con transposición visual)
    # ------------------------------------------------------------------

    def _render_grid(self) -> None:
        if self.song is None:
            self.grid_widget.set_song(None)
            return
        if self.transpose_offset == 0:
            display = self.song
        else:
            display = transpose_song(self.song, self.transpose_offset)
        self.grid_widget.set_song(display)
        n = len(self.grid_widget.editable_syllables())
        self._set_status(f"{self.song.title} — {n} sílabas")

    # ------------------------------------------------------------------
    # Edición de acordes
    # ------------------------------------------------------------------

    def _on_chord_click(self, syllable, widget) -> None:
        if self.transpose_offset != 0:
            self._set_status("Vuelve al tono original (0) para editar acordes")
            return
        self._open_popup(syllable, widget)

    def _open_popup(self, syllable, widget) -> None:
        value = syllable.chord.value if syllable.chord else ""
        ChordPopup(
            self, widget, value,
            on_save=lambda v: self._save_chord(syllable, widget, v),
            on_navigate=lambda d: self._navigate(d, syllable),
        )

    def _save_chord(self, syllable, widget, value: str) -> None:
        value = value.strip()
        if value:
            if syllable.chord:
                syllable.chord.value = value
            else:
                syllable.chord = Chord(id=None, value=value)
        else:
            syllable.chord = None
        widget.config(
            text=value or "·",
            fg=THEME["chord"] if value else THEME["text_muted"],
        )
        self._autosave()

    def _navigate(self, direction: int, current) -> None:
        syls = self.grid_widget.editable_syllables()
        try:
            idx = syls.index(current) + direction
        except ValueError:
            return
        if 0 <= idx < len(syls):
            nxt = syls[idx]
            widget = self.grid_widget.get_chord_widget(nxt)
            if widget is not None:
                self._open_popup(nxt, widget)

    # ------------------------------------------------------------------
    # Dividir / unir sílabas
    # ------------------------------------------------------------------

    def _split_syllable(self, syllable) -> None:
        self._set_status("Dividir sílaba: pendiente de implementar")

    def _merge_syllable(self, syllable) -> None:
        self._set_status("Unir sílaba: pendiente de implementar")

    # ------------------------------------------------------------------
    # Transposición
    # ------------------------------------------------------------------

    def _transpose(self, delta: int) -> None:
        if self.song is None:
            return
        self.transpose_offset = (self.transpose_offset + delta)
        self._offset_lbl.config(text=f"{self.transpose_offset:+d}".replace("+0", "0"))
        self._render_grid()

    def _save_in_key(self) -> None:
        if self.song is None or self.transpose_offset == 0:
            self._set_status("No hay transposición que fijar")
            return
        self.song = transpose_song(self.song, self.transpose_offset)
        self.transpose_offset = 0
        self._offset_lbl.config(text="0")
        self._meta_vars["key"].set(self.song.key or "")
        self._autosave()
        self._render_grid()
        self._set_status("Acordes guardados en el nuevo tono")

    # ------------------------------------------------------------------
    # Guardado y escenario
    # ------------------------------------------------------------------

    def _autosave(self) -> None:
        if self.song is None:
            return
        self.db.save_song(self.song)
        self.song_list.refresh()
        if self.song.id is not None:
            self.song_list.set_selected(self.song.id)
        self._set_status("Guardado")

    # ------------------------------------------------------------------
    # Eliminar canción (CRUD Delete)
    # ------------------------------------------------------------------

    def _delete_current(self) -> None:
        """Elimina la canción abierta en el panel de edición."""
        if self.song is None or self.song.id is None:
            self._set_status("No hay canción para eliminar")
            return
        self._confirm_delete(self.song.id, self.song.title)

    def _confirm_delete(self, song_id: int, title: str) -> None:
        """Pide confirmación y elimina la canción de la base de datos."""
        if not messagebox.askyesno(
            "Eliminar canción",
            f"¿Seguro que quieres eliminar «{title}»?\nEsta acción no se puede deshacer.",
            icon="warning", parent=self,
        ):
            return

        self.db.delete_song(song_id)

        # Si se borró la canción abierta, limpiar el panel derecho
        if self.song is not None and self.song.id == song_id:
            self.song = None
            self.transpose_offset = 0
            self._offset_lbl.config(text="0")
            for var in self._meta_vars.values():
                var.set("")
            self.grid_widget.set_song(None)
            self._show_grid()

        self.song_list.refresh()
        self.song_list.set_selected(self.song.id if self.song else None)
        self._set_status(f"Eliminada: {title}")

    def _reset_to_edit_mode(self) -> None:
        """Vuelve a modo edición sin renderizar (lo hará quien llame después)."""
        self._view_mode = "edit"
        self.grid_widget.mode = "edit"
        self._stage_btn.config(text="Vista Escenario")

    def _toggle_stage(self) -> None:
        """Alterna el panel derecho entre edición y vista escenario (inline)."""
        if self.song is None:
            self._set_status("No hay canción para mostrar")
            return
        self._set_view_mode("edit" if self._view_mode == "stage" else "stage")

    def _set_view_mode(self, mode: str) -> None:
        """Aplica el modo de vista (edit/stage) al grid y actualiza el botón."""
        self._view_mode = mode
        self.grid_widget.mode = mode  # se renderiza con _render_grid
        self._stage_btn.config(
            text="Volver a editar" if mode == "stage" else "Vista Escenario"
        )
        self._render_grid()

    def _open_stage(self) -> None:
        """Abre la vista escenario en pantalla completa (ícono ⛶)."""
        if self.song is None:
            return
        if self._on_open_stage is not None:
            # Se pasa la canción original + offset; el escenario transpone por su cuenta
            self._on_open_stage(self.song, self.transpose_offset)
        else:
            self._set_status("Vista escenario aún no disponible")

    def _set_status(self, msg: str) -> None:
        self._status.config(text=msg)
