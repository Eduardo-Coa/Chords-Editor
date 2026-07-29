"""Vista principal de edición: integra lista, metadatos, grilla y herramientas."""

from __future__ import annotations
from typing import Callable
import tkinter as tk
from tkinter import messagebox, colorchooser, filedialog

import customtkinter as ctk

from database.db import Database
from models.song import Song, Chord, Syllable
from models.transposer import (bake_transpositions, display_song, key_offset,
                               transpose_chord)
from models.key_chords import chords_for_key
from utils import song_io
from utils.song_text import song_to_text, SECTION_LABELS
from utils.lyrics_parser import (parse_lyrics, merge_lyrics, is_chord_line,
                                 prepend_intro, INTRO_LABEL)
from ui.app import THEME, ctk_button_style
from ui.preferences import load_stage_font_size, save_stage_font_size
from ui.views.song_list import SongList
from ui.views.author_export import AuthorExportDialog
from ui.widgets.chord_grid import ChordGrid, STAGE_LYRIC_SIZE_DEFAULT
from ui.widgets.chord_popup import ChordPopup

# Botones del grupo "Editar": etiqueta en reposo y etiqueta mientras están activos
# (el activo se pinta de dorado y sirve para volver al escenario).
MODE_LABELS = {"chords": "Acordes", "lyrics": "Letra"}
MODE_LABEL_ACTIVE = "Volver"


class _Columns:
    """Contador de columnas para armar la barra de herramientas con ``grid``."""

    def __init__(self) -> None:
        self._next = 0

    def next(self) -> int:
        """Devuelve la columna a usar y avanza a la siguiente."""
        column = self._next
        self._next += 1
        return column

    def peek(self) -> int:
        """Columna que se asignará a continuación (para rotular un grupo)."""
        return self._next


def _chord_row_for_edit(line) -> tuple[str, str]:
    """(fila_de_acordes, fila_de_letra) para la caja editable: acordes alineados por
    columna encima de la letra, SIN insertar guiones en la letra (a diferencia de
    ``line_to_chord_lyric``, que sí lo hace para pantalla/PDF). Así la letra editable
    queda limpia y, al reparsear, cada acorde vuelve a caer sobre su sílaba."""
    chord_str = ""
    lyric_str = ""
    for syl in line.syllables:
        value = syl.chord.value if syl.chord else ""
        if value:
            if len(chord_str) < len(lyric_str):
                chord_str += " " * (len(lyric_str) - len(chord_str))
            elif chord_str:
                chord_str += " "  # separación mínima entre dos acordes
            chord_str += value
        lyric_str += syl.text
    return chord_str.rstrip(), lyric_str.rstrip()


def _reconstruct_lyrics(song: Song) -> str:
    """Reconstruye el texto plano de la letra (con encabezados [Sección]).

    La «Introducción» prependida no se incluye (son casillas; ``merge_lyrics`` la
    conserva aparte). Los interludios sí aparecen como ``[Interludio]``. Las líneas
    de casillas con acordes se muestran como una secuencia con guiones (``G - Bm``).
    Las líneas de letra con acordes traen una fila de acordes alineada encima
    (estilo Cifra Club): así los acordes viajan en el texto y no se pierden al
    editar una línea, y además se pueden editar a mano.
    """
    lines: list[str] = []
    for section in song.sections:
        if section.type == "intro" and section.label == INTRO_LABEL:
            continue
        label = section.label or SECTION_LABELS.get(section.type, "")
        if label:
            lines.append(f"[{label}]")
        for line in section.lines:
            if is_chord_line(line):
                # casillas/interludio → secuencia con guiones (se mantiene igual)
                lines.append(" - ".join(s.chord.value for s in line.syllables if s.chord))
            else:
                # línea de letra: si tiene acordes, su fila de acordes va encima
                chord_row, lyric_row = _chord_row_for_edit(line)
                if chord_row:
                    lines.append(chord_row)
                lines.append(lyric_row)
        lines.append("")
    return "\n".join(lines).strip()


class EditView(ctk.CTkFrame):
    """Pantalla de edición de canciones."""

    def __init__(
        self,
        parent: tk.Misc,
        db: Database,
        on_open_stage: Callable[[Song, int], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color=THEME["bg"], corner_radius=0)
        self.db = db
        self._on_open_stage = on_open_stage

        self.song: Song | None = None
        self.transpose_offset = 0
        self._view_mode = "edit"  # 'edit' o 'stage' (escenario inline)
        self._content_view = "grid"  # 'grid' o 'lyrics' (qué ocupa el área central)
        # Tamaño de fuente del escenario: preferencia global y persistente, así
        # que se aplica igual a todas las canciones que se abran.
        self._stage_lyric_size = load_stage_font_size(STAGE_LYRIC_SIZE_DEFAULT)

        self._build()

    # ------------------------------------------------------------------
    # Construcción del layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # PanedWindow clásico: ancho inicial 240, mínimo 180, ajustable arrastrando.
        # opaqueresize=False: durante el arrastre solo se dibuja una línea guía y el
        # relayout ocurre al soltar. Con la lista llena, el relayout continuo cuesta
        # ~886 ms por movimiento (cascada de redibujado de CustomTkinter) frente a
        # ~50 ms así: 18x más fluido.
        paned = tk.PanedWindow(
            self, orient="horizontal", sashwidth=6, opaqueresize=False,
            bg=THEME["border"], bd=0, sashrelief="flat",
        )
        paned.pack(fill="both", expand=True)

        self.song_list = SongList(
            paned, self.db, on_select=self.load_song,
            on_new=self._new_song, on_delete=self._confirm_delete,
        )
        paned.add(self.song_list, minsize=180, width=240, stretch="never")

        right = ctk.CTkFrame(paned, fg_color=THEME["bg"], corner_radius=0)
        paned.add(right, stretch="always")

        self._build_metadata_bar(right)
        self._build_divider(right)
        self._build_toolbar(right)
        self._build_content(right)
        self._build_status_bar(right)
        self._bind_focus_release()

    def _build_metadata_bar(self, parent: tk.Misc) -> None:
        bar = self._centered_row(parent, pady=(8, 4))

        self._meta_vars: dict[str, tk.StringVar] = {}
        # ancho en píxeles (ctk), aproximando los antiguos anchos en caracteres
        fields = [("title", "Título", 180), ("author", "Autor", 120),
                  ("key", "Círculo", 56), ("original_key", "Tono orig.", 60),
                  ("rhythm", "Ritmo", 80), ("capo", "Capo", 48)]
        font = THEME["font_meta"]
        for name, label, width in fields:
            ctk.CTkLabel(bar, text=label, text_color=THEME["text_muted"],
                         font=font).pack(side="left", padx=(6, 2))
            var = tk.StringVar()
            entry = ctk.CTkEntry(
                bar, textvariable=var, width=width,
                fg_color=THEME["surface2"], border_width=0,
                text_color=THEME["text"], font=font,
            )
            entry.pack(side="left")
            if name == "key":
                # "Círculo" no es un metadato más: muestra el tono que suena ahora
                # y, al escribir uno, transpone la canción hasta él.
                entry.bind("<FocusOut>", lambda _e: self._apply_circle_key())
                entry.bind("<Return>", lambda _e: self._release_focus())
            else:
                entry.bind("<FocusOut>", lambda _e: self._commit_metadata())
                # Enter confirma y suelta el foco; Escape descarta lo tecleado.
                entry.bind("<Return>", lambda _e: self._release_focus())
            entry.bind("<Escape>", lambda _e, n=name: self._revert_meta_field(n))
            # Cada tecla repinta "Guardar": lo tecleado aún no está en la BD.
            var.trace_add("write", lambda *_a: self._refresh_save_state())
            self._meta_vars[name] = var

    def _bind_focus_release(self) -> None:
        """Suelta el foco de las casillas de texto al hacer clic fuera de ellas.

        Los botones del toolbar y los frames no toman foco, así que sin esto el
        cursor se quedaba parpadeando en un campo de metadatos hasta cerrar la
        ventana: cualquier tecleo accidental cambiaba la canción sin avisar.
        El binding va en el *toplevel*, que forma parte de los ``bindtags`` de
        todos sus descendientes, así que ve los clics en cualquier hijo.
        """
        self.winfo_toplevel().bind("<Button-1>", self._on_click_anywhere, add="+")

    def _on_click_anywhere(self, event: tk.Event) -> None:
        """Si el clic no cayó en una casilla de texto, quita el foco de la activa."""
        if isinstance(event.widget, (tk.Entry, tk.Text, tk.Spinbox)):
            return
        self._release_focus()

    def _release_focus(self) -> None:
        """Mueve el foco a la vista (dispara ``FocusOut`` → guardar) si estaba en un campo."""
        try:
            focused = self.focus_get()
        except KeyError:                      # foco en otro intérprete/ventana
            return
        if not isinstance(focused, (tk.Entry, tk.Text, tk.Spinbox)):
            return
        # Nunca robar el foco a otra ventana (el popup de acordes se cancela al
        # perderlo): solo soltamos campos de esta misma ventana.
        if focused.winfo_toplevel() is not self.winfo_toplevel():
            return
        self.focus_set()

    def _meta_value(self, name: str) -> str:
        """Valor guardado del campo ``name`` (vacío si no hay canción abierta)."""
        if self.song is None:
            return ""
        if name == "capo":
            return str(self.song.capo)
        if name == "key":
            return self._circle_key()
        return getattr(self.song, name, "") or ""

    def _revert_meta_field(self, name: str) -> None:
        """Descarta la edición en curso del campo y suelta el foco (Escape)."""
        self._meta_vars[name].set(self._meta_value(name))
        self._release_focus()

    def _centered_row(self, parent: tk.Misc, pady: tuple[int, int] | int) -> ctk.CTkFrame:
        """Crea una fila centrada horizontalmente que se re-centra al redimensionar.

        Devuelve el frame donde empaquetar los controles (con ``side="left"``).
        El contenedor externo ocupa todo el ancho y el interno, al no rellenarlo,
        queda centrado; ``pack`` lo recoloca solo con cada cambio de tamaño. Si la
        ventana se estrecha más que el contenido, se alinea a la izquierda: centrar
        recortaría por ambos lados y escondería el primer control.
        """
        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.pack(fill="x", pady=pady)
        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack(padx=10)

        def realign(_event: tk.Event | None = None) -> None:
            anchor = "center" if row.winfo_reqwidth() <= outer.winfo_width() else "w"
            if row.pack_info().get("anchor") != anchor:
                row.pack_configure(anchor=anchor)

        outer.bind("<Configure>", realign)
        return row

    def _build_divider(self, parent: tk.Misc) -> None:
        """Línea fina que separa la barra de metadatos de la de herramientas."""
        line = tk.Frame(parent, height=1, bg=THEME["divider"])
        line.pack(fill="x", padx=10, pady=(4, 2))

    def _build_toolbar(self, parent: tk.Misc) -> None:
        """Barra de herramientas en dos filas: rótulos de grupo arriba, controles abajo.

        Se usa ``grid`` (y no ``pack``) precisamente por eso: la fila 0 reserva la
        altura del rótulo para TODAS las columnas, así que los botones sin rótulo
        bajan lo mismo que los rotulados y todos quedan a la misma altura.
        """
        bar = self._centered_row(parent, pady=(0, 4))

        font = THEME["font_toolbar"]
        col = _Columns()   # lleva la cuenta de la columna actual

        self._build_file_menu(bar, col.next())
        # "Guardar" también fija la transposición visible (ver _save) y se pinta
        # de verde mientras haya cambios sin guardar (ver _refresh_save_state).
        self._save_btn = ctk.CTkButton(bar, text="Guardar", width=80, command=self._save,
                                       **ctk_button_style("normal", font))
        self._save_btn.grid(row=1, column=col.next(), padx=2)

        # Bajo el rótulo "Editar": alternar la edición de acordes y editar la letra.
        # Se guardan en _mode_btns porque el que está en uso se pinta de dorado y
        # pasa a decir "Volver" mientras se trabaja en esa vista (_refresh_mode_buttons).
        self._group_separator(bar, col.next())
        editar_col = col.peek()
        self._mode_btns = {
            "chords": ctk.CTkButton(bar, text=MODE_LABELS["chords"], width=100,
                                    command=lambda: self._on_mode_button("chords"),
                                    **ctk_button_style("normal", font)),
            "lyrics": ctk.CTkButton(bar, text=MODE_LABELS["lyrics"], width=80,
                                    command=lambda: self._on_mode_button("lyrics"),
                                    **ctk_button_style("normal", font)),
        }
        self._mode_btns["chords"].grid(row=1, column=col.next(), padx=2)
        self._mode_btns["lyrics"].grid(row=1, column=col.next(), padx=2)
        self._group_label(bar, "Editar", editar_col, span=2)

        # Tamaño de letra del escenario y color de los acordes.
        self._group_separator(bar, col.next())
        apariencia_col = col.peek()
        ctk.CTkButton(bar, text="A−", width=36, command=lambda: self._change_stage_font(-2),
                      **ctk_button_style("normal", font)
                      ).grid(row=1, column=col.next())
        ctk.CTkButton(bar, text="A+", width=36, command=lambda: self._change_stage_font(2),
                      **ctk_button_style("normal", font)
                      ).grid(row=1, column=col.next(), padx=(2, 0))
        # Selector de color de acordes (tk.Label: muestra el color actual como fondo)
        self._color_swatch = tk.Label(
            bar, text=" ", bg=THEME["chord"], width=2, cursor="hand2",
            relief="raised", borderwidth=1,
        )
        self._color_swatch.grid(row=1, column=col.next(), padx=(6, 0))
        self._color_swatch.bind("<Button-1>", lambda _e: self._pick_chord_color())
        self._group_label(bar, "Apariencia", apariencia_col, span=3)

        self._group_separator(bar, col.next())
        transponer_col = col.peek()
        ctk.CTkButton(bar, text="−", width=36, command=lambda: self._transpose(-1),
                      **ctk_button_style("normal", font)
                      ).grid(row=1, column=col.next())
        self._offset_lbl = tk.Label(bar, text="0", bg=THEME["bg"], fg=THEME["text"],
                                    width=3, font=font)
        self._offset_lbl.grid(row=1, column=col.next())
        ctk.CTkButton(bar, text="+", width=36, command=lambda: self._transpose(1),
                      **ctk_button_style("normal", font)
                      ).grid(row=1, column=col.next())
        self._group_label(bar, "Transponer", transponer_col, span=3)

        self._group_separator(bar, col.next())
        ctk.CTkButton(bar, text="Eliminar", command=self._delete_current,
                      **ctk_button_style("danger", font)
                      ).grid(row=1, column=col.next(), padx=(0, 2))

    def _group_label(self, bar: tk.Misc, text: str, column: int, span: int = 1) -> None:
        """Rótulo (fila 0) centrado sobre las columnas de un grupo de botones."""
        ctk.CTkLabel(bar, text=text, text_color=THEME["text_muted"],
                     font=THEME["font_meta"]
                     ).grid(row=0, column=column, columnspan=span, pady=(0, 1))

    def _group_separator(self, bar: tk.Misc, column: int) -> None:
        """Línea vertical entre grupos de la barra, del mismo color que el divisor."""
        line = tk.Frame(bar, width=1, bg=THEME["divider"])
        line.grid(row=1, column=column, sticky="ns", padx=10, pady=1)

    def _build_file_menu(self, bar: tk.Misc, column: int) -> None:
        """Botón 'Archivo': importar/exportar (.ilahi), PDF y copiar.

        Es un ``CTkButton`` como el resto del toolbar (un ``tk.Menubutton`` no
        toma el estilo del tema); el menú se despliega a mano bajo el botón.
        """
        menu = tk.Menu(
            bar, tearoff=0, bg=THEME["surface2"], fg=THEME["text"],
            activebackground=THEME["border"], activeforeground=THEME["text"],
            font=THEME["font_toolbar"],
        )
        menu.add_command(label="Importar canción o cancionero…", command=self._import_song)
        menu.add_command(label="Exportar canción…", command=self._export_song)
        menu.add_command(label="Exportar por autor…", command=self._export_by_author)
        menu.add_separator()
        menu.add_command(label="Exportar a PDF…", command=self._export_pdf)
        menu.add_separator()
        menu.add_command(label="Copiar al portapapeles", command=self._copy_text)

        btn = ctk.CTkButton(bar, text="Archivo ▾", width=90,
                            **ctk_button_style("normal", THEME["font_toolbar"]))
        btn.configure(command=lambda: self._popup_menu(menu, btn))
        btn.grid(row=1, column=column, padx=2)

    @staticmethod
    def _popup_menu(menu: tk.Menu, anchor: tk.Misc) -> None:
        """Despliega ``menu`` justo debajo del widget ``anchor``."""
        try:
            menu.tk_popup(anchor.winfo_rootx(),
                          anchor.winfo_rooty() + anchor.winfo_height())
        finally:
            menu.grab_release()

    def _build_content(self, parent: tk.Misc) -> None:
        """Área central que alterna entre la grilla y el editor de letra."""
        self._content = ctk.CTkFrame(parent, fg_color=THEME["bg"])
        self._content.pack(fill="both", expand=True, padx=4, pady=4)

        # Área con scroll nativo de ctk que contiene la grilla (chord_grid = tk puro)
        self._scroll = ctk.CTkScrollableFrame(self._content, fg_color=THEME["bg"])

        self.grid_widget = ChordGrid(
            self._scroll, None, mode="edit",
            on_chord_click=self._on_chord_click,
            on_add_left=lambda s: self._add_slot(s, before=True),
            on_add_right=lambda s: self._add_slot(s, before=False),
            on_remove=self._remove_slot,
            on_section_transpose=self._change_section_transpose,
        )
        self.grid_widget.set_stage_font_size(self._stage_lyric_size)
        self.grid_widget.pack(fill="both", expand=True, anchor="nw")

        # Editor de letra (oculto al inicio)
        self._paste_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        self._paste_text = ctk.CTkTextbox(
            self._paste_frame, fg_color=THEME["surface"], text_color=THEME["text"],
            font=(THEME["font_mono"][0], 16), wrap="word",  # mono, algo mayor para editar
        )
        self._paste_text.pack(fill="both", expand=True, padx=4, pady=4)
        # El rótulo cambia según el contexto (ver _show_paste): "Procesar" al crear
        # una canción nueva, "Guardar cambios" al editar la letra de una existente.
        self._process_btn = ctk.CTkButton(
            self._paste_frame, text="Procesar", command=self._process_lyrics,
            **ctk_button_style("accent", THEME["font_toolbar"]),
        )
        self._process_btn.pack(pady=6)

        self._build_stage_fab()
        self._show_grid()

    def _build_stage_fab(self) -> None:
        """Botón flotante de pantalla completa, en la esquina inferior derecha.

        Va con ``place`` sobre el área de contenido (no en la barra) para que
        quede siempre a la vista sin ocupar sitio en el toolbar. Se crea al final
        para quedar por encima de la grilla en el orden de apilado, y el margen
        derecho deja libre la barra de scroll.
        """
        ctk.CTkButton(
            self._content, text="⛶", width=54, height=54, command=self._open_stage,
            **{**ctk_button_style("normal", (THEME["font_ui"][0], 22)),
               "corner_radius": 27},
        ).place(relx=1.0, rely=1.0, anchor="se", x=-28, y=-16)

    def _build_status_bar(self, parent: tk.Misc) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", side="bottom")
        self._status = ctk.CTkLabel(bar, text="Listo", text_color=THEME["text_muted"],
                                    font=THEME["font_list"], anchor="w")
        self._status.pack(side="left", padx=10, pady=4)

    # ------------------------------------------------------------------
    # Alternar contenido central
    # ------------------------------------------------------------------

    def _show_grid(self) -> None:
        self._paste_frame.pack_forget()
        self._scroll.pack(fill="both", expand=True)
        self._content_view = "grid"
        self._refresh_mode_buttons()

    def _show_paste(self, initial_text: str = "") -> None:
        self._scroll.pack_forget()
        self._paste_text.delete("1.0", "end")
        if initial_text:
            self._paste_text.insert("1.0", initial_text)
        else:
            self._paste_text.insert("1.0", "Pega la letra aquí...")
        self._process_btn.configure(
            text="Guardar cambios" if self.song is not None else "Procesar"
        )
        self._paste_frame.pack(fill="both", expand=True)
        self._content_view = "lyrics"
        self._refresh_mode_buttons()

    def _active_edit_mode(self) -> str | None:
        """Cuál de los botones de «Editar» corresponde a lo que se ve ahora.

        ``None`` cuando no se está editando: escenario inline o sin canción.
        """
        if self._content_view == "lyrics":
            return "lyrics"
        if self.song is not None and self._view_mode == "edit":
            return "chords"
        return None

    def _refresh_mode_buttons(self) -> None:
        """Pinta de dorado el botón de la vista en uso y lo convierte en «Volver».

        El color de activo es el mismo de la barra de navegación; el cambio de
        texto deja claro que ese botón ahora sale de la vista, no entra a ella.
        """
        active = self._active_edit_mode()
        for name, btn in self._mode_btns.items():
            is_active = name == active
            style = ctk_button_style("accent" if is_active else "normal",
                                     THEME["font_toolbar"])
            btn.configure(
                text=MODE_LABEL_ACTIVE if is_active else MODE_LABELS[name],
                fg_color=style["fg_color"], hover_color=style["hover_color"],
                text_color=style["text_color"],
            )

    def _on_mode_button(self, name: str) -> None:
        """Entra a la vista del botón, o vuelve al escenario si ya está activa."""
        if self._active_edit_mode() == name:
            self._back_to_stage()
        elif name == "chords":
            self._edit_chords()
        else:
            self._edit_lyrics()

    def _back_to_stage(self) -> None:
        """Vuelve a la vista escenario inline desde cualquiera de los dos editores."""
        self._show_grid()
        if self.song is None:
            self._set_status("Listo")
            return
        self._set_view_mode("stage")

    # ------------------------------------------------------------------
    # Flujo de nueva canción / edición de letra
    # ------------------------------------------------------------------

    def _new_song(self) -> None:
        self.song = None
        self._set_offset(0)
        self._reset_to_edit_mode()
        for var in self._meta_vars.values():
            var.set("")
        self.grid_widget.set_song(None)
        self._show_paste()
        self._set_status("Pega la letra y pulsa 'Procesar'")

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
            prepend_intro(self.song)   # toda canción nueva empieza con «Introducción»

        self._apply_metadata_to_song()
        self._set_offset(0)
        self._autosave()
        self._render_grid()
        self._show_grid()

    # ------------------------------------------------------------------
    # Carga y metadatos
    # ------------------------------------------------------------------

    def load_song(self, song_id: int) -> None:
        self.song = self.db.load_song(song_id)
        self._set_offset(0)                      # refresca 'Círculo' con el tono real
        self._meta_vars["title"].set(self.song.title)
        self._meta_vars["author"].set(self.song.author or "")
        self._meta_vars["original_key"].set(self.song.original_key or "")
        self._meta_vars["rhythm"].set(self.song.rhythm or "")
        self._meta_vars["capo"].set(str(self.song.capo))
        self._refresh_save_state()               # canción recién cargada: limpia
        self._show_grid()
        # Vista escenario por defecto al abrir una canción (editar es opt-in
        # con el botón "Editar acordes")
        self._set_view_mode("stage")
        self._set_status(f"Cargada: {self.song.title}")

    def _metadata_from_fields(self) -> dict[str, object]:
        """Valores de la barra de metadatos ya normalizados para el modelo.

        Fuente única para volcarlos a la canción y para detectar si difieren de
        lo guardado (botón «Guardar» en verde), de modo que ambas rutas apliquen
        exactamente los mismos valores por defecto.
        """
        def field(name: str) -> str:
            return self._meta_vars[name].get().strip()

        try:
            capo = int(field("capo"))
        except ValueError:
            capo = 0
        return {
            "title": field("title") or "Sin título",
            "author": field("author") or None,
            "original_key": field("original_key") or None,
            "rhythm": field("rhythm") or None,
            "capo": capo,
        }

    def _apply_metadata_to_song(self) -> None:
        if self.song is None:
            return
        for name, value in self._metadata_from_fields().items():
            setattr(self.song, name, value)
        # 'Círculo' muestra el tono TRANSPUESTO: no se vuelca al modelo (lo maneja
        # _apply_circle_key). Solo sirve de tono base si la canción aún no tiene.
        if not self.song.key:
            self.song.key = self._meta_vars["key"].get().strip() or None

    def _commit_metadata(self) -> None:
        if self.song is None:
            return
        self._apply_metadata_to_song()
        self._autosave()

    # ------------------------------------------------------------------
    # Estado "sin guardar" (botón Guardar en verde)
    # ------------------------------------------------------------------

    def _is_dirty(self) -> bool:
        """True si hay algo que la base de datos todavía no tiene.

        Dos fuentes reales: la transposición global (siempre es solo visual) y el
        texto tecleado en un campo de metadatos que aún no se ha confirmado. Los
        acordes, la letra y los metadatos confirmados se autoguardan, así que no
        cuentan como pendientes. La modulación por bloque tampoco: se persiste en
        ``sections.transpose`` en cuanto se cambia.
        """
        if self.song is None:
            return False
        if self.transpose_offset != 0:
            return True
        if any(getattr(self.song, name) != value
               for name, value in self._metadata_from_fields().items()):
            return True
        return self._meta_vars["key"].get().strip() != self._circle_key()

    def _refresh_save_state(self) -> None:
        """Pinta «Guardar» de verde mientras haya cambios sin guardar."""
        btn = getattr(self, "_save_btn", None)
        if btn is None:                     # aún construyendo la barra
            return
        style = ctk_button_style("success" if self._is_dirty() else "normal",
                                 THEME["font_toolbar"])
        btn.configure(fg_color=style["fg_color"], hover_color=style["hover_color"],
                      text_color=style["text_color"])

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
                "Vuelve a 0, o pulsa «Guardar» para fijar este tono y poder editarlo"
            )
            return
        # Sílaba de una sección modulada: es una copia transpuesta, no el modelo
        # real (no se encuentra por identidad). Para editarla hay que volver el
        # bloque a 0 o fijar la modulación con «Guardar».
        if self._section_of(syllable) is None:
            self._set_status(
                "Bloque modulado: pulsa «Guardar» para fijarlo y poder editarlo"
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
        self._set_offset(self.transpose_offset + delta)
        self._render_grid()

    def _set_offset(self, offset: int) -> None:
        """Fija la transposición visual y refresca el contador y la casilla 'Círculo'."""
        self.transpose_offset = offset
        self._offset_lbl.config(text=f"{offset:+d}".replace("+0", "0"))
        self._refresh_circle_key()
        self._refresh_save_state()

    def _circle_key(self) -> str:
        """Tono que suena ahora: el de la canción más la transposición visual."""
        if self.song is None or not self.song.key:
            return ""
        return transpose_chord(self.song.key, self.transpose_offset, self.song.key)

    def _refresh_circle_key(self) -> None:
        """Escribe en la casilla 'Círculo' el tono actual (sin tocar el modelo)."""
        self._meta_vars["key"].set(self._circle_key())

    def _apply_circle_key(self) -> None:
        """Interpreta lo escrito en 'Círculo': transpone la canción hasta ese tono.

        La transposición sigue siendo visual (el tono guardado no cambia): para
        fijarla está el botón «Guardar». Si la canción aún no tiene tono, la
        casilla simplemente se lo asigna, porque no hay origen desde el cual
        transponer.
        """
        if self.song is None:
            return
        typed = self._meta_vars["key"].get().strip()
        if not self.song.key:
            self.song.key = typed or None
            self._autosave()
            self._render_grid()
            return
        if not typed:
            self._refresh_circle_key()      # vacío: no hay destino, restaurar
            return
        offset = key_offset(self.song.key, typed)
        if offset is None:
            self._set_status(f"Tono no reconocido: {typed}")
            self._refresh_circle_key()
            return
        if offset == self.transpose_offset:
            self._refresh_circle_key()      # ya estamos ahí: normalizar ortografía
            return
        self._set_offset(offset)
        self._render_grid()
        self._set_status(f"Transpuesto a {self._circle_key()}")

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

    def _has_pending_transpose(self) -> bool:
        """True si hay transposición sin fijar: offset global o modulación de bloque."""
        if self.song is None:
            return False
        return (self.transpose_offset != 0
                or any(s.transpose != 0 for s in self.song.sections))

    def _save(self) -> None:
        """Guarda la canción y, de paso, fija la transposición que esté a la vista.

        Un solo botón «Guardar»: lo que se ve en pantalla (offset global +
        modulación por bloque) es lo que queda en la base de datos. Antes de
        reescribir los acordes se hace un respaldo, porque es la única operación
        de guardado que altera valores ya existentes.
        """
        if self.song is None:
            self._set_status("No hay canción para guardar")
            return
        if not self._has_pending_transpose():
            self._autosave()
            return
        self.db.backup("save_in_key")  # respaldo antes de reescribir los acordes
        self.song = bake_transpositions(self.song, self.transpose_offset)
        self._set_offset(0)                      # 'Círculo' ya muestra el tono fijado
        self._autosave()
        self._render_grid()
        key = self._circle_key()
        self._set_status(f"Guardado en {key}" if key else "Guardado en el nuevo tono")

    # ------------------------------------------------------------------
    # Importar / Exportar canción (.ilahi)
    # ------------------------------------------------------------------

    def _export_song(self) -> None:
        """Exporta la canción abierta a un archivo .ilahi (tono original)."""
        if self.song is None:
            self._set_status("No hay canción para exportar")
            return
        ext = song_io.SONG_FILE_EXTENSION
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar canción",
            defaultextension=ext,
            initialfile=song_io.suggested_filename(self.song),
            filetypes=[("Canción Ilahi", f"*{ext}"), ("Todos", "*.*")],
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
        """Importa desde un .ilahi: una canción suelta o un cancionero completo.

        El filtro incluye la extensión heredada .hymnchords para que los archivos
        exportados con el nombre anterior sigan apareciendo en el diálogo.
        """
        ext = song_io.SONG_FILE_EXTENSION
        legacy = song_io.LEGACY_FILE_EXTENSION
        path = filedialog.askopenfilename(
            parent=self, title="Importar canción o cancionero",
            filetypes=[("Ilahi", f"*{ext} *{legacy}"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            songs = song_io.load_songs(path)
        except song_io.SongIOError as exc:
            messagebox.showerror("Importar", str(exc), parent=self)
            return

        if not songs:
            messagebox.showinfo("Importar", "El archivo no contiene canciones.", parent=self)
        elif len(songs) == 1:
            self._import_one(songs[0])
        else:
            self._import_many(songs)

    def _import_one(self, song: Song) -> None:
        """Importa una única canción como copia nueva (avisa si el título ya existe)."""
        if self._title_exists(song.title) and not messagebox.askyesno(
            "Importar canción",
            f"Ya existe una canción titulada «{song.title}».\n"
            "¿Importar de todas formas como copia nueva?",
            parent=self,
        ):
            return
        song.id = None  # asegurar INSERT (no reutilizar ningún id)
        new_id = self.db.save_song(song)
        self.song_list.refresh(reload_filters=True)
        self.load_song(new_id)
        self.song_list.set_selected(new_id)
        self._set_status(f"Importada: {song.title}")

    def _import_many(self, songs: list[Song]) -> None:
        """Importa un cancionero: todas las canciones entran como copias nuevas."""
        if not messagebox.askyesno(
            "Importar cancionero",
            f"El archivo contiene {len(songs)} canciones.\n"
            "¿Importarlas todas como copias nuevas?",
            parent=self,
        ):
            return
        duplicates = 0
        last_id: int | None = None
        for song in songs:
            if self._title_exists(song.title):
                duplicates += 1
            song.id = None  # asegurar INSERT
            last_id = self.db.save_song(song)
        self.song_list.refresh(reload_filters=True)
        if last_id is not None:
            self.load_song(last_id)
            self.song_list.set_selected(last_id)
        msg = f"Importadas {len(songs)} canciones"
        if duplicates:
            msg += f" ({duplicates} con título ya existente)"
        self._set_status(msg)

    def _export_by_author(self) -> None:
        """Abre el diálogo para exportar todas las canciones de un autor (cancionero)."""
        AuthorExportDialog(self, self.db, on_status=self._set_status)

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
        self.song_list.refresh(reload_filters=True)
        if self.song.id is not None:
            self.song_list.set_selected(self.song.id)
        self._refresh_save_state()   # ya no hay nada pendiente: vuelve a gris
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
            self._set_offset(0)
            for var in self._meta_vars.values():
                var.set("")
            self.grid_widget.set_song(None)
            self._show_grid()

        self.song_list.refresh(reload_filters=True)
        self.song_list.set_selected(self.song.id if self.song else None)
        self._set_status(f"Eliminada: {title}")

    def _reset_to_edit_mode(self) -> None:
        """Vuelve a modo edición sin renderizar (lo hará quien llame después)."""
        self._view_mode = "edit"
        self.grid_widget.mode = "edit"
        self._refresh_mode_buttons()

    def _edit_chords(self) -> None:
        """Muestra la grilla en modo edición de acordes (salir es «Volver»)."""
        if self.song is None:
            self._set_status("No hay canción para editar")
            return
        self._show_grid()   # por si se venía del editor de letra
        self._set_view_mode("edit")

    def _change_stage_font(self, delta: int) -> None:
        """Ajusta el tamaño de fuente de la vista escenario (inline y pantalla completa)."""
        self._stage_lyric_size = max(10, self._stage_lyric_size + delta)
        self.grid_widget.set_stage_font_size(self._stage_lyric_size)
        save_stage_font_size(self._stage_lyric_size)
        if self._view_mode == "stage":
            self._set_status(f"Tamaño de fuente: {self._stage_lyric_size}")

    def sync_stage_font_size(self) -> None:
        """Relee el tamaño de fuente guardado (lo pudo cambiar la vista escenario)."""
        size = load_stage_font_size(self._stage_lyric_size)
        if size == self._stage_lyric_size:
            return
        self._stage_lyric_size = size
        self.grid_widget.set_stage_font_size(size)

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
        """Aplica el modo de vista (edit/stage) al grid y lo re-renderiza.

        El botón "Acordes" es un alternador de texto fijo: no cambia de etiqueta,
        pero sí de color mientras la edición de acordes esté activa.
        """
        self._view_mode = mode
        self.grid_widget.mode = mode  # se renderiza con _render_grid
        self._refresh_mode_buttons()
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

    def _export_pdf(self) -> None:
        """Exporta la canción a PDF (cifrado monoespaciado) en el tono visible."""
        if self.song is None:
            self._set_status("No hay canción para exportar")
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar a PDF", defaultextension=".pdf",
            initialfile=song_io.safe_filename(self.song.title) + ".pdf",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            from utils import pdf_export  # import diferido: fpdf es pesado
            pdf_export.song_to_pdf(
                display_song(self.song, self.transpose_offset), path
            )
        except Exception as exc:
            messagebox.showerror(
                "Exportar a PDF", f"No se pudo crear el PDF:\n{exc}", parent=self
            )
            return
        self._set_status(f"PDF exportado: {self.song.title}")

    def _copy_text(self) -> None:
        """Copia la canción (acordes sobre la letra) al portapapeles, en el tono visible."""
        if self.song is None:
            self._set_status("No hay canción para copiar")
            return
        text = song_to_text(display_song(self.song, self.transpose_offset), metadata=True)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Copiado al portapapeles (acordes + letra)")

    def _set_status(self, msg: str) -> None:
        self._status.configure(text=msg)
