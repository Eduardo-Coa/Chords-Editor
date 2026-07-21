# Compilar HymnChords como `.exe`

HymnChords se distribuye como un **único ejecutable portable** para Windows. El
usuario final **no necesita Python**: solo copia `HymnChords.exe` y lo abre con
doble clic.

## Requisitos para compilar

- Python 3.10+ en Windows
- Las herramientas de build (PyInstaller y Pillow):

```powershell
pip install -r requirements-build.txt
```

## Compilar

Desde la raíz del proyecto:

```powershell
./build.ps1
```

El script instala las dependencias de build, genera el ícono si falta y corre
PyInstaller. El resultado queda en:

```
dist\HymnChords.exe
```

(Equivale a `pyinstaller HymnChords.spec --clean --noconfirm`.)

## Dónde guarda sus datos

El `.exe` es portable y **no guarda nada junto a sí mismo**. La biblioteca de
canciones y las preferencias viven en la carpeta de datos del usuario:

```
%APPDATA%\HymnChords\
├── hymnchords.db        ← base SQLite con las canciones
└── preferences.json     ← preferencias (color de acordes, etc.)
```

Así cada usuario tiene su propia biblioteca y puede mover o reinstalar el `.exe`
sin perder sus canciones.

## Notas

- **SmartScreen:** al ser un ejecutable sin firma digital, la primera vez Windows
  puede mostrar "Windows protegió tu PC / editor desconocido". Es normal; basta con
  *Más información → Ejecutar de todas formas*. Firmar el binario está fuera del
  alcance actual.
- **Rediseñar el ícono:** editar `tools/make_icon.py` y correr
  `python tools/make_icon.py` para regenerar `assets/icon.ico`.
