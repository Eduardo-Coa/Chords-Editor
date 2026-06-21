"""Vista principal de edición: integra lista, metadatos, grilla y herramientas."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, filedialog

from database.db import Database
from models.song import Song, Chord, Syllable
from models.transposer import bake_transpositions, display_song
from models.key_chords import chords_for_key
from utils import song_io
from utils.lyrics_parser import parse_lyrics, merge_lyrics, is_chord_line
from ui.app import THEME
from ui.views.song_list import SongList
from ui.widgets.chord_grid import ChordGrid, STAGE_LYRIC_SIZE_DEFAULT
from ui.widgets.chord_popup import ChordPopup


def _reconstruct_lyrics(song: Song) -> str:
    """Reconstruye el texto plano de la letra (con encabezados [Sección])."""
    lines: list[str] = []
    for section in song.sections:
        if section.label:
            lines.append(f"[{section.label}]")
        for line in section.lines:
            if is_chord_line(line):
                continue  # las líneas de acordes no son texto editable
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
        self._stage_lyric_size = STAGE_LYRIC_SIZE_DEFAULT

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

        self._build_file_menu(bar)
        ttk.Button(bar, text="Guardar", command=self._autosave).pack(side="left", padx=2)
        self._stage_btn = ttk.Button(bar, text="Vista Escenario", command=self._toggle_stage)
        self._stage_btn.pack(side="left", padx=2)
        ttk.Button(bar, text="⛶", width=3, command=self._open_stage).pack(side="left")
        ttk.Button(bar, text="A−", width=3,
                   command=lambda: self._change_stage_font(-2)).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="A+", width=3,
                   command=lambda: self._change_stage_font(2)).pack(side="left")
        # Selector de color de acordes (muestra el color actual)
        self._color_swatch = tk.Label(
            bar, text=" ", bg=THEME["chord"], width=2, cursor="hand2",
            relief="raised", borderwidth=1,
        )
        self._color_swatch.pack(side="left", padx=(6, 0))
        self._color_swatch.bind("<Button-1>", lambda _e: self._pick_chord_color())
        ttk.Button(bar, text="−", width=3, command=lambda: self._transpose(-1)).pack(side="left", padx=(12, 0))
        self._offset_lbl = ttk.Label(bar, text="0", style="TLabel", width=3, anchor="center")
        self._offset_lbl.pack(side="left")
        ttk.Button(bar, text="+", width=3, command=lambda: self._transpose(1)).pack(side="left")
        ttk.Button(bar, text="Guardar en este tono", command=self._save_in_key).pack(side="left", padx=2)
        ttk.Button(bar, text="Editar letra", command=self._edit_lyrics).pack(side="left", padx=2)
        ttk.Button(bar, text="Eliminar", style="Danger.TButton",
                   command=self._delete_current).pack(side="left", padx=2)

    def _build_file_menu(self, bar: ttk.Frame) -> None:
        """Mini-menú 'Archivo' con Importar / Exportar canción (.hymnchords)."""
        menubtn = tk.Menubutton(
            bar, text="Archivo ▾",
            bg=THEME["surface2"], fg=THEME["text"],
            activebackground=THEME["border"], activeforeground=THEME["text"],
            relief="flat", font=THEME["font_ui"], padx=10, pady=4, cursor="hand2",
        )
        menu = tk.Menu(
            menubtn, tearoff=0, bg=THEME["surface2"], fg=THEME["text"],
            activebackground=THEME["border"], activeforeground=THEME["text"],
        )
        menu.add_command(label="Importar canción…", command=self._import_song)
        menu.add_command(label="Exportar canción…", command=self._export_song)
        menubtn["menu"] = menu
        menubtn.pack(side="left", padx=(0, 8))

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
            on_add_left=lambda s: self._add_slot(s, before=True),
            on_add_right=lambda s: self._add_slot(s, before=False),
            on_remove=self._remove_slot,
            on_section_transpose=self._change_section_transpose,
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
        self._meta_vars["title"].set(self.song.title)
        self._meta_vars["author"].set(self.song.author or "")
        self._meta_vars["key"].set(self.song.key or "")
        self._meta_vars["rhythm"].set(self.song.rhythm or "")
        self._meta_vars["capo"].set(str(self.song.capo))
        self._show_grid()
        # Vista escenario por defecto al abrir una canción (editar es opt-in
        # con el botón "Volver a editar")
        self._set_view_mode("stage")
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
        # display_song aplica offset global + modulación por bloque. Cuando no hay
        # transposición efectiva devuelve el modelo real (acordes editables).
        display = display_song(self.song, self.transpose_offset)
        self.grid_widget.set_song(display)
        n = len(self.grid_widget.editable_syllables())
        self._set_status(f"{self.song.title} — {n} sílabas")

    # ------------------------------------------------------------------
    # Edición de acordes
    # ------------------------------------------------------------------

    def _on_chord_click(self, syllable, widget) -> None:
        if self.transpose_offset != 0:
            self._set_status(
                "Vuelve a 0, o pulsa «Guardar en este tono» para editar en este tono"
            )
            return
        # Sílaba de una sección modulada: es una copia transpuesta, no el modelo
        # real (no se encuentra por identidad). Para editarla hay que volver el
        # bloque a 0 o fijar la modulación con «Guardar en este tono».
        if self._section_of(syllable) is None:
            self._set_status(
                "Bloque modulado: pulsa «Guardar en este tono» para poder editarlo"
            )
            return
        self._open_popup(syllable, widget)

    def _open_popup(self, syllable, widget) -> None:
        # Casilla con acorde: se edita su valor. Casilla vacía: se ofrece como
        # sugerencia el acorde de la misma posición en una sección previa del
        # mismo tipo (memoria de progresión); si no hay, queda vacía.
        if syllable.chord:
            value = syllable.chord.value
        else:
            value = self._predicted_chord(syllable)
        key = self.song.key if self.song else None
        ChordPopup(
            self, widget, value,
            on_save=lambda v: self._save_chord(syllable, widget, v),
            on_navigate=lambda d: self._navigate(d, syllable),
            suggestions=chords_for_key(key),
            key_label=key or "",
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
    # Memoria de progresión: sugerir acordes por posición
    # ------------------------------------------------------------------

    def _predicted_chord(self, syllable: Syllable) -> str:
        """Sugiere el acorde de una casilla vacía según una sección previa.

        Toma como plantilla la primera sección anterior del mismo tipo que ya
        tenga acordes y devuelve el que ocupa la misma posición (por orden de
        acorde, no de sílaba) que esta casilla. Si no hay plantilla o la
        progresión ya se agotó, devuelve "".
        """
        if self.song is None:
            return ""

        target = self._section_of(syllable)
        if target is None:
            return ""

        reference: list[str] | None = None
        for section in self.song.sections:
            if section is target:
                break  # solo secciones anteriores a la actual
            if section.type == target.type:
                chords = self._section_chords(section)
                if chords:
                    reference = chords
                    break
        if not reference:
            return ""

        k = self._chords_before(target, syllable)
        return reference[k] if k < len(reference) else ""

    def _section_of(self, syllable: Syllable):
        """Devuelve la sección que contiene la sílaba (por identidad)."""
        for section in self.song.sections:
            for line in section.lines:
                if any(s is syllable for s in line.syllables):
                    return section
        return None

    @staticmethod
    def _section_chords(section) -> list[str]:
        """Lista de acordes de la sección en orden de lectura (sin vacíos)."""
        return [
            s.chord.value
            for line in section.lines
            for s in line.syllables
            if s.chord and s.chord.value
        ]

    @staticmethod
    def _chords_before(section, syllable: Syllable) -> int:
        """Cuenta los acordes que preceden a la sílaba dentro de su sección."""
        count = 0
        for line in section.lines:
            for s in line.syllables:
                if s is syllable:
                    return count
                if s.chord and s.chord.value:
                    count += 1
        return count

    # ------------------------------------------------------------------
    # Casillas de acorde manuales
    # ------------------------------------------------------------------

    def _add_slot(self, syllable: Syllable, before: bool) -> None:
        """Inserta una casilla de acorde vacía a la izquierda o derecha de la sílaba."""
        if self.song is None:
            return
        if self.transpose_offset != 0:
            self._set_status("Vuelve al tono original (0) para editar casillas")
            return

        for section in self.song.sections:
            for line in section.lines:
                for i, s in enumerate(line.syllables):
                    if s is syllable:  # identidad, no igualdad (hay slots iguales)
                        insert_at = i if before else i + 1
                        line.syllables.insert(
                            insert_at, Syllable(id=None, position=0, text="")
                        )
                        for pos, syl in enumerate(line.syllables):
                            syl.position = pos
                        self._autosave()
                        self._render_grid()
                        return

    def _remove_slot(self, syllable: Syllable) -> None:
        """Elimina una casilla de acorde (solo si no está asignada a una sílaba)."""
        if self.song is None:
            return
        if self.transpose_offset != 0:
            self._set_status("Vuelve al tono original (0) para editar casillas")
            return
        if syllable.text.strip() != "":
            return  # seguridad: nunca borrar una sílaba con texto

        for section in self.song.sections:
            for line in section.lines:
                for i, s in enumerate(line.syllables):
                    if s is syllable:
                        del line.syllables[i]
                        for pos, syl in enumerate(line.syllables):
                            syl.position = pos
                        self._autosave()
                        self._render_grid()
                        return

    # ------------------------------------------------------------------
    # Transposición
    # ------------------------------------------------------------------

    def _transpose(self, delta: int) -> None:
        if self.song is None:
            return
        self.transpose_offset = (self.transpose_offset + delta)
        self._offset_lbl.config(text=f"{self.transpose_offset:+d}".replace("+0", "0"))
        self._render_grid()

    def _change_section_transpose(self, index: int, delta: int) -> None:
        """Modula una sección concreta (índice en la canción real) y re-renderiza."""
        if self.song is None or not (0 <= index < len(self.song.sections)):
            return
        section = self.song.sections[index]
        section.transpose += delta
        self._autosave()
        self._render_grid()
        label = section.label or f"sección {index + 1}"
        off = section.transpose
        self._set_status(f"{label}: tono del bloque {off:+d}".replace("+0", "0"))

    def _save_in_key(self) -> None:
        if self.song is None:
            return
        # Fijar tanto el offset global como las modulaciones por bloque: hornea lo
        # que se ve en pantalla. Sin nada pendiente, no hay nada que guardar.
        has_section_mod = any(s.transpose != 0 for s in self.song.sections)
        if self.transpose_offset == 0 and not has_section_mod:
            self._set_status("No hay transposición que fijar")
            return
        self.song = bake_transpositions(self.song, self.transpose_offset)
        self.transpose_offset = 0
        self._offset_lbl.config(text="0")
        self._meta_vars["key"].set(self.song.key or "")
        self._autosave()
        self._render_grid()
        self._set_status("Acordes guardados en el nuevo tono")

    # ------------------------------------------------------------------
    # Importar / Exportar canción (.hymnchords)
    # ------------------------------------------------------------------

    def _export_song(self) -> None:
        """Exporta la canción abierta a un archivo .hymnchords (tono original)."""
        if self.song is None:
            self._set_status("No hay canción para exportar")
            return
        ext = song_io.SONG_FILE_EXTENSION
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar canción",
            defaultextension=ext,
            initialfile=song_io.suggested_filename(self.song),
            filetypes=[("Canción HymnChords", f"*{ext}"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            song_io.export_song(self.song, path)
        except song_io.SongIOError as exc:
            messagebox.showerror("Exportar canción", str(exc), parent=self)
            return
        self._set_status(f"Exportada: {self.song.title}")

    def _import_song(self) -> None:
        """Importa una canción desde un .hymnchords como copia nueva."""
        ext = song_io.SONG_FILE_EXTENSION
        path = filedialog.askopenfilename(
            parent=self, title="Importar canción",
            filetypes=[("Canción HymnChords", f"*{ext}"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            song = song_io.import_song(path)
        except song_io.SongIOError as exc:
            messagebox.showerror("Importar canción", str(exc), parent=self)
            return

        # Importar siempre crea una copia nueva: avisar si ya existe ese título.
        if self._title_exists(song.title) and not messagebox.askyesno(
            "Importar canción",
            f"Ya existe una canción titulada «{song.title}».\n"
            "¿Importar de todas formas como copia nueva?",
            parent=self,
        ):
            return

        song.id = None  # asegurar INSERT (no reutilizar ningún id)
        new_id = self.db.save_song(song)
        self.song_list.refresh()
        self.load_song(new_id)
        self.song_list.set_selected(new_id)
        self._set_status(f"Importada: {song.title}")

    def _title_exists(self, title: str) -> bool:
        """True si ya hay una canción con ese título exacto (ignorando mayúsculas)."""
        target = title.strip().casefold()
        return any(
            row["title"].strip().casefold() == target
            for row in self.db.list_songs(title)
        )

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

    def _change_stage_font(self, delta: int) -> None:
        """Ajusta el tamaño de fuente de la vista escenario (inline y pantalla completa)."""
        self._stage_lyric_size = max(10, self._stage_lyric_size + delta)
        self.grid_widget.set_stage_font_size(self._stage_lyric_size)
        if self._view_mode == "stage":
            self._set_status(f"Tamaño de fuente: {self._stage_lyric_size}")

    def _pick_chord_color(self) -> None:
        """Abre el selector de color para los acordes (global y persistente)."""
        from ui.preferences import save_preference

        chosen = colorchooser.askcolor(
            color=THEME["chord"], title="Color de acordes", parent=self
        )
        if not chosen or not chosen[1]:
            return  # cancelado
        THEME["chord"] = chosen[1]
        save_preference("chord_color", chosen[1])
        self._color_swatch.config(bg=chosen[1])
        self._render_grid()  # actualiza los acordes en pantalla
        self.song_list.set_selected(self.song.id if self.song else None)

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
