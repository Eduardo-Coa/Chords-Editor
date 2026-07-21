"""Pruebas del parser de letra pegada."""

from __future__ import annotations

from models.song import Chord, Song
from utils.lyrics_parser import (
    parse_lyrics, merge_lyrics, is_chord_line, CHORD_LINE_SLOTS,
    is_section_header, parse_section_header, detect_header,
    is_chord_line_text, is_chord_token, prepend_intro, INTRO_LABEL,
)


def _chords_of(line):
    """Valores de acorde de una línea, en orden."""
    return [s.chord.value for s in line.syllables if s.chord]


def _lyric_lines(song, sec=0):
    """Líneas de letra de una sección (omite la línea de acordes inicial)."""
    return [l for l in song.sections[sec].lines if not is_chord_line(l)]


def _chord_line(song, sec=0):
    """Devuelve la línea de acordes de una sección."""
    return next(l for l in song.sections[sec].lines if is_chord_line(l))


def _first_chord(line):
    """(texto_silaba, acorde) de la primera sílaba con acorde de una línea."""
    for s in line.syllables:
        if s.chord:
            return s.text.strip(), s.chord.value
    return None


# ---------------------------------------------------------------------------
# Parseo básico
# ---------------------------------------------------------------------------

def test_sin_casillas_automaticas_en_letra():
    # Las casillas en las líneas de letra son manuales: el parser no agrega ninguna
    song = parse_lyrics("Cristo vive", title="Test")
    assert song.title == "Test"
    line = _lyric_lines(song)[0]
    assert [s for s in line.syllables if s.text == ""] == []


def test_lineas_vacias_se_conservan():
    song = parse_lyrics("Linea uno\n\nLinea dos")
    lyric = _lyric_lines(song)
    assert len(lyric) == 3
    assert lyric[1].syllables == []  # separador en medio


def test_silabas_reconstruyen_texto():
    song = parse_lyrics("gloria a Dios")
    line = _lyric_lines(song)[0]
    texto = "".join(s.text for s in line.syllables).strip()
    assert texto == "gloria a Dios"


# ---------------------------------------------------------------------------
# Línea de acordes por sección
# ---------------------------------------------------------------------------

def test_cada_seccion_tiene_linea_de_acordes():
    song = parse_lyrics("[Estrofa 1]\nGracias te doy\n[Coro]\nJesús te ama")
    for section in song.sections:
        chord_line = section.lines[0]
        assert is_chord_line(chord_line)
        assert len(chord_line.syllables) == CHORD_LINE_SLOTS


def test_linea_de_acordes_va_primero():
    song = parse_lyrics("Gracias te doy")
    assert is_chord_line(song.sections[0].lines[0])
    assert not is_chord_line(song.sections[0].lines[1])


# ---------------------------------------------------------------------------
# Secciones con corchetes
# ---------------------------------------------------------------------------

def test_detecta_encabezado_seccion():
    assert is_section_header("[Coro]")
    assert is_section_header("  [Estrofa 1]  ")
    assert not is_section_header("Cristo vive")
    assert not is_section_header("vive [en mi]")


def test_tipo_seccion_por_palabra_clave():
    assert parse_section_header("[Coro]") == ("Coro", "chorus")
    assert parse_section_header("[Estrofa 1]") == ("Estrofa 1", "verse")
    assert parse_section_header("[Puente]") == ("Puente", "bridge")
    # intro/interludio → sección de casillas (tipo 'intro'), con etiqueta canónica
    assert parse_section_header("[Intro]") == ("Introducción", "intro")
    assert parse_section_header("[Interludio]") == ("Interludio", "intro")
    assert parse_section_header("[Inter]") == ("Interludio", "intro")
    assert parse_section_header("[Instrumental]") == ("Instrumental", "verse")


def test_parse_con_secciones():
    song = parse_lyrics("[Estrofa 1]\nGracias te doy\n[Coro]\nJesús te ama")
    assert len(song.sections) == 2
    assert song.sections[0].label == "Estrofa 1"
    assert song.sections[0].type == "verse"
    assert song.sections[1].label == "Coro"
    assert song.sections[1].type == "chorus"
    assert _lyric_lines(song, 0)[0].syllables[0].text.startswith("Gra")


def test_letra_antes_de_encabezado_va_en_seccion_por_defecto():
    song = parse_lyrics("Línea suelta\n[Coro]\nletra del coro")
    assert song.sections[0].label is None
    assert song.sections[1].label == "Coro"


# ---------------------------------------------------------------------------
# Encabezados implícitos: números y palabras clave sin corchetes
# ---------------------------------------------------------------------------

def test_detect_header_numero_es_estrofa():
    assert detect_header("1") == ("Estrofa 1", "verse")
    assert detect_header("2") == ("Estrofa 2", "verse")
    assert detect_header("3.") == ("Estrofa 3", "verse")


def test_detect_header_palabra_clave():
    assert detect_header("Coro:") == ("Coro", "chorus")
    assert detect_header("coro") == ("Coro", "chorus")
    assert detect_header("Puente") == ("Puente", "bridge")
    assert detect_header("Estrofa 2") == ("Estrofa 2", "verse")


def test_detect_header_linea_normal_no_es_encabezado():
    assert detect_header("Vivo por Cristo, confiando en su amor,") is None
    assert detect_header("es de mi senda Jesús guía fiel.") is None
    assert detect_header("") is None


def test_parse_con_numeros_y_coro_implicitos():
    texto = (
        "1\nVivo por Cristo\nvida me imparte\n"
        "Coro:\n\n¡Oh, Salvador bendito!\n"
        "2\nVivo por Cristo, murió por mí"
    )
    song = parse_lyrics(texto)
    labels = [(s.label, s.type) for s in song.sections]
    assert labels == [
        ("Estrofa 1", "verse"),
        ("Coro", "chorus"),
        ("Estrofa 2", "verse"),
    ]
    # La línea en blanco tras "Coro:" no deja un separador al inicio del coro
    coro_lyric = [l for l in song.sections[1].lines if not is_chord_line(l)]
    primera = "".join(s.text for s in coro_lyric[0].syllables).strip()
    assert primera == "¡Oh, Salvador bendito!"


# ---------------------------------------------------------------------------
# merge_lyrics: editar letra conservando acordes
# ---------------------------------------------------------------------------

def _song_con_acordes() -> Song:
    """Canción con id, acordes en las líneas de letra y en la línea de acordes."""
    song = parse_lyrics("Gracias te doy\nque pronto volverás")
    song.id = 42
    lyric = _lyric_lines(song)
    lyric[0].syllables[0].chord = Chord(id=None, value="D")
    lyric[1].syllables[0].chord = Chord(id=None, value="G")
    # Acorde en la línea de acordes (intro de la sección)
    _chord_line(song).syllables[0].chord = Chord(id=None, value="A")
    return song


def test_merge_conserva_id():
    merged = merge_lyrics(_song_con_acordes(), "Gracias te doy\nque pronto volverás")
    assert merged.id == 42


def test_merge_agregar_linea_conserva_acordes_previos():
    nuevo = "Gracias te doy\nque pronto volverás\nuna línea nueva"
    merged = merge_lyrics(_song_con_acordes(), nuevo)
    lyric = _lyric_lines(merged)
    assert _first_chord(lyric[0]) == ("Gra", "D")
    assert _first_chord(lyric[1]) == ("que", "G")
    assert _first_chord(lyric[2]) is None  # línea nueva sin acordes


def test_merge_linea_editada_pierde_sus_acordes_pero_otras_no():
    nuevo = "Gracias te doy\nque muy pronto volverás"
    merged = merge_lyrics(_song_con_acordes(), nuevo)
    lyric = _lyric_lines(merged)
    assert _first_chord(lyric[0]) == ("Gra", "D")  # intacta
    assert _first_chord(lyric[1]) is None          # editada, sin acordes


def test_merge_conserva_linea_de_acordes_por_seccion():
    # Al editar la letra, la línea de acordes (intro) conserva su acorde
    merged = merge_lyrics(_song_con_acordes(), "Gracias te doy\nque pronto volverás")
    assert _first_chord(_chord_line(merged)) == ("", "A")


# ---------------------------------------------------------------------------
# Acordes sueltos separados por guiones (secuencias instrumentales)
# ---------------------------------------------------------------------------

def test_linea_de_acordes_con_guiones_se_reconoce():
    assert is_chord_line_text("G - Bm - A - D - A")
    assert is_chord_line_text("A - G - Bm - A - D - A - G")
    assert not is_chord_line_text("solo - texto suelto")  # no son acordes
    assert not is_chord_line_text("- - -")                # solo guiones


def test_bloque_de_acordes_al_inicio_es_introduccion():
    song = parse_lyrics("G - Bm - A - D - A\n\n[Estrofa]\nTodos mis tesoros")
    assert song.sections[0].label == INTRO_LABEL
    assert song.sections[0].type == "intro"
    chord_lines = [l for l in song.sections[0].lines if is_chord_line(l)]
    assert len(chord_lines) == 1
    assert _chords_of(chord_lines[0]) == ["G", "Bm", "A", "D", "A"]
    assert song.sections[1].type == "verse"


def test_bloque_de_acordes_entre_estrofas_es_interludio():
    song = parse_lyrics(
        "[Estrofa 1]\nlínea uno\nG - Bm - A\n[Estrofa 2]\nlínea dos")
    labels = [(s.label, s.type) for s in song.sections]
    assert labels == [
        ("Estrofa 1", "verse"),
        ("Interludio", "intro"),
        ("Estrofa 2", "verse"),
    ]
    inter = [l for l in song.sections[1].lines if is_chord_line(l)][0]
    assert _chords_of(inter) == ["G", "Bm", "A"]


def test_acordes_con_guiones_no_se_pegan_a_la_letra_de_abajo():
    # Una secuencia con guiones es instrumental: la letra siguiente abre estrofa
    song = parse_lyrics("G - Bm - A\nMi letra aquí")
    assert song.sections[0].label == INTRO_LABEL
    assert not any(
        "".join(s.text for s in l.syllables).strip() for l in song.sections[0].lines)
    assert song.sections[1].type == "verse"
    ultima = song.sections[1].lines[-1]
    assert "".join(s.text for s in ultima.syllables).strip() == "Mi letra aquí"


def test_dos_lineas_de_acordes_bajo_encabezado_son_casillas():
    song = parse_lyrics(
        "[Final]\nG - Bm - A - D - A\nA - G - Bm - A - D - A - G\n\nEn mi caminar")
    final = song.sections[0]
    assert (final.label, final.type) == ("Final", "outro")
    chord_lines = [l for l in final.lines if is_chord_line(l)]
    assert len(chord_lines) == 2
    assert _chords_of(chord_lines[0]) == ["G", "Bm", "A", "D", "A"]
    assert _chords_of(chord_lines[1]) == ["A", "G", "Bm", "A", "D", "A", "G"]
    lyric = [l for l in final.lines
             if "".join(s.text for s in l.syllables).strip()]
    assert len(lyric) == 1


def test_prepend_intro_no_duplica_si_ya_empieza_con_introduccion():
    song = parse_lyrics("G - Bm - A - D - A\n\n[Estrofa]\nletra")
    n_antes = len(song.sections)
    prepend_intro(song)
    assert len(song.sections) == n_antes
    assert song.sections[0].label == INTRO_LABEL


def test_prepend_intro_agrega_cuando_no_hay_intro():
    song = parse_lyrics("[Estrofa]\nCristo vive hoy")
    prepend_intro(song)
    assert song.sections[0].label == INTRO_LABEL
    assert song.sections[0].type == "intro"


def test_intro_con_guiones_no_absorbe_la_letra_de_cifra_club():
    # Bloque de acordes con guiones al inicio + acordes-sobre-letra (Cifra Club):
    # la intro se queda solo con el bloque; la letra abre una estrofa (no se pierde).
    texto = (
        "G - Bm - A - D - A\n"
        "\n"
        "G                         Bm\n"
        " Todos mis tesoros pueden desaparecer\n"
        "G                       D              A\n"
        " lo que amo hoy tal vez mañana ya no esté"
    )
    song = parse_lyrics(texto)
    assert song.sections[0].label == INTRO_LABEL
    assert not any(
        "".join(s.text for s in l.syllables).strip() for l in song.sections[0].lines
    ), "la intro no debe contener letra"
    verse = song.sections[1]
    assert verse.type == "verse"
    lyric = [ "".join(s.text for s in l.syllables).strip()
              for l in verse.lines
              if "".join(s.text for s in l.syllables).strip() ]
    assert lyric == [
        "Todos mis tesoros pueden desaparecer",
        "lo que amo hoy tal vez mañana ya no esté",
    ]
    # los acordes de Cifra Club quedaron pegados a la letra
    primera = next(l for l in verse.lines
                   if "".join(s.text for s in l.syllables).strip().startswith("Todos"))
    assert "G" in _chords_of(primera) and "Bm" in _chords_of(primera)


def test_acordes_antes_de_encabezado_van_en_la_estrofa_no_interludio():
    # Cifra Club: una línea de acordes (alineados por columna) justo antes de un
    # encabezado [Estrofa] es la entrada de esa estrofa: se pega a su 1ª línea de
    # letra, NO forma interludio. El interludio solo es una línea de acordes SIN
    # letra asociada.
    song = parse_lyrics(
        "[Coro]\nB F#\nlínea del coro\n"
        "F# C# D#m C#\n[Estrofa]\ntu amor es mi esperanza\nB F#\npor eso regresar")
    assert not any(s.type == "intro" for s in song.sections), "no debe haber interludio"
    estrofa = next(s for s in song.sections if s.label == "Estrofa")
    primera = estrofa.lines[0]
    assert "".join(x.text for x in primera.syllables).strip().startswith("tu amor")
    assert _chords_of(primera) == ["F#", "C#", "D#m", "C#"]


def test_acorde_entre_parentesis_se_reconoce_y_se_guarda_sin_ellos():
    """«(G)» es la convención de acorde opcional/de paso. Se acepta como acorde, pero se
    guarda SIN paréntesis: con ellos ``transpose_chord`` lo dejaría igual y se quedaría
    sin transponer mientras el resto de la canción sí cambia de tono."""
    assert is_chord_token("(G)") is True
    assert is_chord_token("(Am7)") is True
    assert is_chord_token("(hola)") is False      # letra entre paréntesis, no acorde
    assert is_chord_token("C(add9)") is True      # paréntesis INTERNOS: ya se aceptaban


def test_una_linea_con_acorde_entre_parentesis_sigue_siendo_de_acordes():
    """Regresión: bastaba un «(G)» para que la línea entera dejara de contar como
    acordes y se procesara como letra, dejando el verso de abajo SIN acordes."""
    assert is_chord_line_text("        Am7          G7     (G)") is True
    song = parse_lyrics("        Am7          G7     (G)\nand try harder to be true?")
    linea = [l for l in song.sections[0].lines
             if "".join(s.text for s in l.syllables).strip()][0]
    assert _chords_of(linea) == ["Am7", "G7", "G"]     # el (G) entró, ya sin paréntesis


def test_acorde_pasado_el_final_recibe_casilla_sin_partir_la_puntuacion():
    """Un acorde que cae más allá del verso no se pega a la última palabra ni parte el
    signo: recibe su propia casilla AL FINAL del renglón."""
    song = parse_lyrics("        Am7          G7     (G)\nand try harder to be true?")
    linea = [l for l in song.sections[0].lines
             if "".join(s.text for s in l.syllables).strip()][0]
    textos = [s.text for s in linea.syllables]
    assert textos[-2:] == ["?", ""]          # el signo queda antes de la casilla
    assert linea.syllables[-1].chord.value == "G"


def test_lineas_en_blanco_al_inicio_no_inventan_seccion():
    """Regresión: una línea en blanco arriba abría una «Estrofa» fantasma vacía, porque
    el parser aún no tenía sección y creaba una para colgarla. Cuenta también la línea
    de solo espacios, fácil de arrastrar al copiar de una web."""
    cuerpo = "[Intro]\nG   C   Am   D\n\n[Verse 1]\nCristo vive hoy\n"
    esperado = [("Introducción", "intro"), ("Verse 1", "verse")]
    for delante in ("", "\n", "   \n", "\n  \n\n"):
        song = parse_lyrics(delante + cuerpo)
        assert [(s.label, s.type) for s in song.sections] == esperado, repr(delante)


def test_lineas_en_blanco_del_medio_siguen_separando():
    """El descarte es SOLO al inicio: en el medio la línea vacía sigue separando."""
    song = parse_lyrics("[Verse 1]\nuno\n\n[Verse 2]\ndos\n")
    assert [s.label for s in song.sections] == ["Verse 1", "Verse 2"]


def test_encabezado_con_un_corchete_suelto_se_reconoce_igual():
    """Al copiar de una web es fácil perder un corchete. Sin pareja, «Intro]» no se
    reconocía y entraba como LETRA."""
    assert detect_header("Intro]") == ("Introducción", "intro")
    assert detect_header("[Intro") == ("Introducción", "intro")
    assert detect_header("Verse 1]") == ("Verse 1", "verse")
    assert detect_header("[Intro]") == ("Introducción", "intro")   # completo, igual
    assert detect_header("Intro") == ("Introducción", "intro")     # sin corchetes, igual


def test_un_corchete_suelto_no_inventa_secciones():
    """Regresión: «Intro]» abría una estrofa sin etiqueta (con «Intro]» de letra) y
    además empujaba el bloque de acordes de la entrada a un «Interludio»."""
    song = parse_lyrics("Intro]\nG   C   Am   D\n\n[Verse 1]\nCristo vive hoy")
    assert [(s.label, s.type) for s in song.sections] == [
        ("Introducción", "intro"),
        ("Verse 1", "verse"),
    ]


def test_reparar_corchetes_no_toca_lineas_normales():
    """Una línea sin corchetes, o con corchetes internos, se deja como está."""
    assert detect_header("Cristo vive hoy") is None
    assert detect_header("y el sol [de la mañana] salió") is None
