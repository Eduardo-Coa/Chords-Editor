---
name: importar-canciones
description: Genera archivos .hymnchords importables en HymnChords a partir de fuentes externas — himnos del Himnario Adventista (PDF de acordes + nuevohimnario.com) o canciones de sitios de cifrados (Cifra Club, lacuerda.net, texto pegado). Usar cuando el usuario pida extraer, importar o regenerar canciones/himnos con acordes desde una web o documento.
---

# Importar canciones a HymnChords desde fuentes externas

## Principio general

**Nunca escribas en la base de datos SQLite.** El producto de esta tarea es
siempre un archivo `.hymnchords` (JSON, formato de `utils/song_io.py`) que el
usuario importa él mismo desde "Archivo → Importar…" en la app. La importación
siempre crea copias nuevas, así que advierte al usuario si va a re-importar
algo que ya tiene (borraría/duplicaría a mano).

Hay dos herramientas ya construidas y probadas en `C:\Users\USUARIO\Desktop\Himnario\`.
Ambas reutilizan el parser de la propia app (`utils/lyrics_parser.py`), así que
el resultado es idéntico a pegar texto bien alineado en HymnChords. Ejecútalas
con el Python del sistema (necesitan `pdfplumber` solo la primera).

## Herramienta 1: Himnario Adventista (`himnario_pipeline.py`)

Combina la letra limpia de `https://www.nuevohimnario.com/Himno?no=N` con los
acordes del PDF `C:\Users\USUARIO\Documents\ZED\Acordes_para_el_himnario_adventista_2020-2b.pdf`,
alineándolos por coordenadas x y por las anclas de guiones del himnario
(«Se -ñor» = el acorde cambia en «ñor»).

```
python himnario_pipeline.py 97        # un himno  → himno-097-prueba.hymnchords
python himnario_pipeline.py 1-20      # un rango  → himnos-001-020.hymnchords + reporte
```

- Los 613 himnos YA fueron generados e importados (julio 2026). Este script se
  usa para regenerar himnos puntuales tras una corrección.
- Salida en `Desktop\Himnario\`; el reporte `*-reporte.txt` trae advertencias
  y vista previa monoespaciada de cada himno.
- El script ya resuelve las trampas conocidas del PDF: ligaduras tipográficas
  («ti» como un solo char), acordes fusionados («D7G», «Bb7Eb»), sufijos en
  mayúsculas («D7SUS4», «FmaJ7»), pares de paso «G→D» (una casilla por acorde),
  líneas de acordes con etiqueta («Coro G7 C…») o número de estrofa, títulos
  mal tipeados («234 ;Temes…»), estrofas intercaladas y cortes de verso
  distintos entre PDF y web (fusiona hasta 4 líneas del PDF contra 1-3 de la web).
- Si un himno sale mal: inspecciona su bloque con
  `hp.find_hymn_block(hp.pdf_flow(), N)` y revisa qué líneas marca
  `hp._is_chord_pdf_line()`. Casi siempre es un tipeo nuevo del PDF en la línea
  de acordes; amplía la tolerancia en `_word_chords`/`_FILLER_TOKEN_RE`.
- Advertencia `texto PDF≠web`: el emparejado usó similitud; si es ≥80% los
  acordes suelen quedar bien. `línea del PDF sin usar` con pinta de acordes =
  bandera roja (línea de acordes no reconocida): investigar siempre.

## Herramienta 2: sitios de cifrados (`web_a_hymnchords.py`)

Para Cifra Club, lacuerda.net y similares (formato «acordes sobre letra»):

```
python web_a_hymnchords.py URL [--titulo T] [--autor A] [--tono D] [--ritmo 4/4]
python web_a_hymnchords.py archivo.txt --titulo T    # texto ya pegado/limpiado
```

- Extrae el bloque `<pre>` del cifrado (selectores probados para Cifra Club y
  La Cuerda; genérico: el `<pre>` más grande), quita etiquetas sin alterar la
  alineación de columnas y lo pasa por `parse_lyrics` de la app.
- Convierte notación latina (DO RE MI, usada por lacuerda.net) a americana
  columna a columna. El transpositor de la app SOLO entiende americana.
- Si la página trae basura (notas del transcriptor, líneas solapadas), guarda
  el texto extraído en un `.txt`, límpialo, y corre el script sobre el `.txt`.
- Sin `--tono`, adivina el tono con el primer acorde y lo dice: pídele al
  usuario confirmarlo (el último acorde de la canción suele ser mejor pista).
- Verifica siempre la vista previa que imprime: acordes sobre la sílaba
  correcta, secciones bien detectadas ([Coro], [Estrofa]).

## Validación (obligatoria antes de entregar)

1. El propio script valida el round-trip con `load_songs`; si truena, no entregues.
2. Muestra al usuario la vista previa (o el reporte) y señala las advertencias.
3. Con material nuevo, haz SIEMPRE un piloto de 1 canción y pide al usuario
   importarla y validarla en la app antes de correr lotes.

## Convenciones de la biblioteca del himnario

- Título: `NNN - Título` (número con 3 dígitos para que ordene bien).
- Autor: `Himnario Adventista` (agrupa en el exportador por autor).
- Tono: el que se TOCA; si el PDF dice «Tocar en X con capo N», tono = X,
  capo = N y la nota original va en `notes`.
- Cada canción lleva la sección «Introducción» vacía estándar de la app.
- Secuencias de paso «G→D» = casillas consecutivas (una por acorde), nunca un
  solo valor con flecha (rompería la transposición).

## Pendientes conocidos

Himnos con advertencias que quedaron para revisión manual del usuario (detalle
en los reportes de `Desktop\Himnario\`): 22, 41, 68, 70, 82, 92, 111, 149,
178, 180, 213, 224, 228, 257, 262, 278, 281, 282, 353, 364, 390, 399, 431,
443, 445, 448, 460, 465, 498, 516, 552, 569, 572, 593.
