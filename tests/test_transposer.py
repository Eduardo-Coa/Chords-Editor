"""Pruebas de transposición de acordes."""

from __future__ import annotations
import pytest

from models.song import Song, Section, Line, Syllable, Chord
from models.transposer import (
    transpose_chord, transpose_song, display_song, bake_transpositions,
    respell_to_key,
)


def _cv(song: Song, sec: int, line: int = 0, syl: int = 0) -> str:
    """Valor del acorde de una sílaba (estrecha el tipo Chord|None para el linter)."""
    chord = song.sections[sec].lines[line].syllables[syl].chord
    assert chord is not None
    return chord.value


def _song_dos_secciones() -> Song:
    """Canción de prueba con dos secciones, cada una con un acorde."""
    song = Song(id=None, title="T", key="C")
    for value in ("C", "G"):
        sec = Section(id=None, position=0, type="verse", label=None)
        line = Line(id=None, position=0)
        line.syllables.append(
            Syllable(id=None, position=0, text="a", chord=Chord(id=None, value=value))
        )
        sec.lines.append(line)
        song.sections.append(sec)
    return song


@pytest.mark.parametrize("chord, semitones, expected", [
    ("Am7", 2, "Bm7"),
    ("C", 1, "C#"),
    ("G", 5, "C"),
    ("Bb", 1, "B"),
    ("F#m", -1, "Fm"),
    ("Dsus4", 0, "Dsus4"),
    ("C", 12, "C"),
])
def test_transpose_chord(chord, semitones, expected):
    assert transpose_chord(chord, semitones) == expected


def test_transpose_song_no_muta_original():
    song = Song(id=None, title="T", key="C")
    sec = Section(id=None, position=0, type="verse", label=None)
    line = Line(id=None, position=0)
    line.syllables.append(
        Syllable(id=None, position=0, text="a", chord=Chord(id=None, value="Am"))
    )
    sec.lines.append(line)
    song.sections.append(sec)

    result = transpose_song(song, 2)

    assert result.key == "D"
    assert _cv(result, 0) == "Bm"
    # El original no cambia
    assert song.key == "C"
    assert _cv(song, 0) == "Am"


@pytest.mark.parametrize("chord, semitones, key, expected", [
    ("A", 1, "E", "Bb"),    # Mi+1 = Fa (bemoles): el IV es Bb, no A#
    ("E", 1, "E", "F"),     # la tónica Mi+1 = Fa
    ("B7", 1, "E", "C7"),   # conserva el sufijo
    ("G#", 2, "A", "A#"),   # La+2 = Si (sostenidos): aquí el pitch 10 sí es A#
    ("C", 1, "C", "Db"),    # Do+1 = Reb (bemoles, menos alteraciones que Do#)
    ("D", 2, "G", "E"),     # Sol+2 = La (sostenidos), D+2 natural = E
    ("F", 2, None, "G"),    # sin tono: comportamiento por defecto (sostenidos)
])
def test_transpose_chord_consciente_del_tono(chord, semitones, key, expected):
    assert transpose_chord(chord, semitones, key) == expected


# --- Ortografía enarmónica: los casos del bug "SiB quedó como A#" ------------

@pytest.mark.parametrize("chord, semitones, key, expected", [
    # El bug reportado: pasar de Fa# a Fa (tono de bemoles) → el IV es Bb, no A#
    ("B", -1, "F#", "Bb"),
    ("A#", -1, "F#", "A"),     # A#7 en Fa# baja a A en Fa (no queda A#)
    # Offset 0 ahora SÍ re-deletrea según el tono (antes devolvía tal cual)
    ("A#", 0, "F", "Bb"),      # un "A#" guardado en Fa se corrige a "Bb"
    ("Bb", 0, "F", "Bb"),      # ya correcto: se queda igual
    ("Bb", 0, "E", "A#"),      # en Mi (sostenidos) el pitch 10 es A#
    # Tonos neutros (Do mayor / La menor): se respeta el acorde de entrada, porque
    # en Do el bVII correcto es Bb (¡no A#!) — el caso de "Grande es Jehová".
    ("Bb", 0, "C", "Bb"),      # NO tocar: Bb es correcto en Do
    ("A#", 0, "C", "A#"),      # en Do se respeta el estilo de entrada
    ("Bb", 12, "C", "Bb"),     # octava en Do: sigue siendo Bb
    ("Bb", 0, "Am", "Bb"),     # La menor también es neutro
    # Sin tono: se conserva el estilo del acorde de entrada (no fuerza sostenidos)
    ("Bb", 3, None, "Db"),     # Bb + 3 = Db, sigue en bemoles
    ("A#", 3, None, "C#"),     # A# + 3 = C#, sigue en sostenidos
    ("Bb", 0, None, "Bb"),     # sin tono y sin mover: se conserva
])
def test_transpose_chord_enarmonia(chord, semitones, key, expected):
    assert transpose_chord(chord, semitones, key) == expected


def test_respell_to_key_corrige_sostenido_en_tono_de_bemoles():
    """En Fa, un acorde guardado como A# se re-deletrea a Bb sin cambiar la altura."""
    song = Song(id=None, title="T", key="F")
    sec = Section(id=None, position=0, type="verse", label=None)
    line = Line(id=None, position=0)
    line.syllables.append(
        Syllable(id=None, position=0, text="a", chord=Chord(id=None, value="A#"))
    )
    line.syllables.append(
        Syllable(id=None, position=1, text="b", chord=Chord(id=None, value="C"))
    )
    sec.lines.append(line)
    song.sections.append(sec)

    fixed = respell_to_key(song)

    assert _cv(fixed, 0, syl=0) == "Bb"   # corregido
    assert _cv(fixed, 0, syl=1) == "C"    # intacto
    assert _cv(song, 0, syl=0) == "A#"    # no muta el original


def test_respell_to_key_respeta_tono_neutro():
    """En Do, respell_to_key NO cambia un Bb a A# (Bb es el bVII correcto)."""
    song = Song(id=None, title="Grande es Jehová", key="C")
    sec = Section(id=None, position=0, type="verse", label=None)
    line = Line(id=None, position=0)
    line.syllables.append(
        Syllable(id=None, position=0, text="a", chord=Chord(id=None, value="Bb"))
    )
    sec.lines.append(line)
    song.sections.append(sec)

    assert _cv(respell_to_key(song), 0) == "Bb"  # se respeta, no se corrompe


def test_respell_to_key_sin_tono_conserva_estilo():
    """Sin tono, respell_to_key no fuerza un estilo: deja el acorde como está."""
    song = Song(id=None, title="T", key=None)
    sec = Section(id=None, position=0, type="verse", label=None)
    line = Line(id=None, position=0)
    line.syllables.append(
        Syllable(id=None, position=0, text="a", chord=Chord(id=None, value="Bb"))
    )
    sec.lines.append(line)
    song.sections.append(sec)

    assert _cv(respell_to_key(song), 0) == "Bb"


def test_display_song_sin_offsets_devuelve_el_modelo_real():
    """Sin transposición efectiva, display_song devuelve la misma instancia."""
    song = _song_dos_secciones()
    assert display_song(song, 0) is song


def test_display_song_modula_solo_el_bloque():
    """La modulación de una sección solo afecta a esa sección, no a las demás."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2  # subir 2 semitonos solo el segundo bloque

    shown = display_song(song, 0)

    assert _cv(shown, 0) == "C"  # intacto
    assert _cv(shown, 1) == "A"  # G + 2
    # No es destructivo: el modelo original conserva su acorde
    assert _cv(song, 1) == "G"
    # La sección sin modular se devuelve por referencia (editable)
    assert shown.sections[0] is song.sections[0]


def test_display_song_suma_offset_global_y_de_bloque():
    """El total por sección es global + section.transpose."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2

    shown = display_song(song, 1)  # global +1

    # C+1 = Db (tono de bemoles): el deletreo sigue al tono de destino
    assert shown.key == "Db"
    assert _cv(shown, 0) == "Db"  # C + 1
    assert _cv(shown, 1) == "Bb"  # G + 3 (tono Eb)


def test_bake_solo_modulacion_de_bloque():
    """Hornear con offset global 0 fija la modulación del bloque y la deja en 0."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2  # solo el segundo bloque +2

    baked = bake_transpositions(song, 0)

    assert _cv(baked, 0) == "C"           # bloque sin modular: intacto
    assert _cv(baked, 1) == "A"           # G + 2 horneado
    assert baked.sections[1].transpose == 0  # ya no hay modulación pendiente
    assert baked.key == "C"               # sin offset global, el tono no cambia
    # No es destructivo: el original conserva su acorde y su modulación
    assert _cv(song, 1) == "G"
    assert song.sections[1].transpose == 2


def test_bake_combina_offset_global_y_de_bloque():
    """Hornear suma offset global + section.transpose y resetea todo a 0."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 2

    baked = bake_transpositions(song, 1)  # global +1

    assert baked.key == "Db"              # C + 1
    assert _cv(baked, 0) == "Db"          # C + 1
    assert _cv(baked, 1) == "Bb"          # G + 3
    assert all(s.transpose == 0 for s in baked.sections)


def test_bake_coincide_con_display():
    """Lo horneado debe coincidir con lo que display_song muestra en pantalla."""
    song = _song_dos_secciones()
    song.sections[1].transpose = 3

    shown = display_song(song, 2)
    baked = bake_transpositions(song, 2)

    assert _cv(baked, 0) == _cv(shown, 0)
    assert _cv(baked, 1) == _cv(shown, 1)
    assert baked.key == shown.key


# ---------------------------------------------------------------------------
# Acordes con bajo (slash): transponen las dos partes
# ---------------------------------------------------------------------------

def test_slash_transpone_acorde_y_bajo():
    assert transpose_chord("G/F#", 2) == "A/G#"
    assert transpose_chord("G/F#", -2) == "F/E"
    assert transpose_chord("G/B", 1) == "G#/C"      # el bajo cruza la octava


def test_slash_conserva_calidad_del_acorde():
    assert transpose_chord("Am7/G", 2) == "Bm7/A"


def test_slash_deletrea_ambas_partes_segun_el_tono():
    # Re +1 = Mib (tono de bemoles): acorde y bajo en bemoles
    assert transpose_chord("D/F#", 1, key="D") == "Eb/G"


def test_slash_respell_sin_cambiar_altura():
    assert transpose_chord("C/E", 0) == "C/E"
