"""Genera assets/icon.ico para HymnChords.

Dibuja una nota musical sobre el fondo oscuro del tema y la guarda como ícono
multitamaño. Pillow es dependencia SOLO de build (ver requirements-build.txt); la
app empaquetada no la necesita. El .ico resultante se commitea, así que solo hay
que correr este script si se quiere rediseñar el ícono.

Uso:
    python tools/make_icon.py
"""

from __future__ import annotations
from pathlib import Path

from PIL import Image, ImageDraw

# Colores del tema (ver THEME en ui/app.py)
BG = (15, 15, 15)          # #0f0f0f
CHORD = (126, 184, 164)    # #7eb8a4 (verde azulado)
ACCENT = (200, 169, 110)   # #c8a96e (dorado)

# Lienzo grande; el .ico se reescala a los tamaños estándar al guardar.
SIZE = 256
ASSETS = Path(__file__).resolve().parent.parent / "assets"
OUT = ASSETS / "icon.ico"


def _draw_note(d: ImageDraw.ImageDraw) -> None:
    """Dibuja una corchea estilizada centrada en el lienzo."""
    # Plica (línea vertical)
    stem_x = 158
    d.line([(stem_x, 60), (stem_x, 176)], fill=CHORD, width=12)
    # Banderola
    d.line([(stem_x, 60), (210, 96)], fill=ACCENT, width=12)
    d.line([(stem_x, 92), (206, 126)], fill=ACCENT, width=12)
    # Cabeza de la nota (elipse rellena, ligeramente inclinada por el offset)
    d.ellipse([(96, 150), (164, 200)], fill=CHORD)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Fondo redondeado con borde dorado tenue.
    d.rounded_rectangle([(8, 8), (SIZE - 8, SIZE - 8)], radius=44, fill=BG,
                        outline=ACCENT, width=4)
    _draw_note(d)

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(OUT, format="ICO", sizes=sizes)
    print(f"Ícono generado: {OUT}")


if __name__ == "__main__":
    main()
