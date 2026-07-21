"""Genera assets/icon.ico a partir del ícono de la marca (assets/Ilahi-iconAPP.png).

Antes este script DIBUJABA una nota musical con Pillow; ahora solo convierte el
ícono oficial de Ilahi al formato multitamaño que necesita Windows (la ventana y
el .exe). El PNG fuente se commitea junto al .ico.

Pillow es dependencia SOLO de build (ver requirements-build.txt); la app
empaquetada no la necesita. El .ico resultante se commitea, así que solo hay que
correr este script si cambia el ícono de la marca.

Uso:
    python tools/make_icon.py
"""

from __future__ import annotations
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SRC = ASSETS / "Ilahi-iconAPP.png"
OUT = ASSETS / "icon.ico"

# Tamaños estándar de Windows: el explorador y la barra de tareas eligen el que
# necesitan. 256 es el máximo que admite el formato .ico.
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    """Convierte el PNG de la marca en un .ico multitamaño."""
    if not SRC.exists():
        raise SystemExit(f"Falta el ícono de la marca: {SRC}")
    # RGBA conserva la transparencia si el PNG la trae; Windows la respeta.
    img = Image.open(SRC).convert("RGBA")
    img.save(OUT, format="ICO", sizes=SIZES)
    print(f"Ícono generado: {OUT}  ({img.width}×{img.height} → {len(SIZES)} tamaños)")


if __name__ == "__main__":
    main()
