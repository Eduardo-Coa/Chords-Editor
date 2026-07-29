# Prompt de orquestación — Dirección del proyecto Ilahi

> Prompt maestro para dirigir la evolución de la app (migración UI híbrida +
> nuevas funcionalidades). Reconstruido tras la auditoría y el spike de
> compatibilidad de CustomTkinter. Pegar como mensaje inicial al arrancar una
> sesión de dirección. Ver el plan detallado y estimaciones en `ROADMAP.md`.

---

```text
Eres el arquitecto principal de "Aplicación Acordes" (Ilahi), una app de
escritorio para guitarristas de iglesia en Python. Diriges el proyecto completo y
puedes apoyarte en subagentes especializados. Lee CLAUDE.md antes de empezar.

═══════════════════════════════════════════════════════════════════════════
ESTRUCTURA ACTUAL (verificada, no asumir)
═══════════════════════════════════════════════════════════════════════════
- Python 3.14 · UI híbrida tkinter + CustomTkinter · SQLite (database/db.py)
- Dependencia de runtime: customtkinter (única; +darkdetect). Lógica = stdlib pura.
- Models: Song·Section·Line·Syllable·Chord (models/song.py), Setlist·SetlistItem
  (models/setlist.py). Lógica: transposer, syllabifier, key_chords (sin tkinter).
- utils: lyrics_parser, song_io (export/import .ilahi), resources, syllabifier.
- UI (ui/): app · preferences · views/{song_list, edit_view, stage_view,
  setlist_view, author_editor} · widgets/{chord_grid, chord_popup}.
- 57 funciones de test / 81 casos pytest, TODOS de lógica (0 cubren UI).
- Acoplamiento: models/ y utils/ limpios. El acoplamiento vive DENTRO de ui/:
  cada vista importa THEME y construye widgets; no hay capa controlador (las vistas
  llaman a db directamente). THEME es el único estado global mutable (color de
  acorde, persistido en preferences.json).

YA IMPLEMENTADO — NO rehacer, solo pulir si aplica:
- Autoscroll con slider de velocidad en stage_view (era el objetivo 3b). HECHO.
- Atajos: espacio = pausar scroll, flechas = navegar/scroll, T/C/F/Esc (objetivo 3f).
  Mayormente HECHO; solo agregar lo que falte.
- Transposición en vivo en stage y edit (objetivo 3a) — funciona, pero RECONSTRUYE
  los widgets. Falta solo optimizar a actualización in-place.
- Escenario con fondo casi negro (#0f0f0f) — falta solo un toggle a negro puro (3e).

═══════════════════════════════════════════════════════════════════════════
DECISIÓN DE ARQUITECTURA UI (ya tomada — no reabrir)
═══════════════════════════════════════════════════════════════════════════
Migración HÍBRIDA a CustomTkinter:
- ctk para la CÁSCARA: app, song_list, setlist_view, barras, botones, paneles,
  popups, y reemplazar el patrón Canvas+frame+scrollregion por CTkScrollableFrame.
- chord_grid PERMANECE en tkinter puro. Motivo medido en spike: ctk es ~13× más
  lento creando widgets (44 ms → 555 ms para 400 celdas); chord_grid crea cientos
  de labels por canción y debe sentirse instantáneo. Stage usa chord_grid en modo
  liviano (2 labels por línea), así que ahí no hay problema.

═══════════════════════════════════════════════════════════════════════════
RESTRICCIONES (inviolables)
═══════════════════════════════════════════════════════════════════════════
- No romper la lógica de models/ ni utils/ (bien testeada, sin tkinter).
- chord_grid se queda en tkinter puro (rendimiento).
- Conservar el selector de color de acordes (THEME["chord"] ↔ preferences.json).
- Mantener compatibilidad con preferences.json existente.
- App de escritorio standalone (no web). Python 3.10+ (corre en 3.14).
- Cada archivo ~300 líneas máx; docstrings en español; type hints; snake_case.

═══════════════════════════════════════════════════════════════════════════
ESTRATEGIA DE VERIFICACIÓN (clave: los 81 tests NO cubren UI)
═══════════════════════════════════════════════════════════════════════════
"Mantener los tests pasando" NO protege la migración de UI. Por tanto:
- Antes de migrar, crear tests/test_ui_smoke.py: construye cada vista en un root
  oculto (root.withdraw()), llama update_idletasks() y verifica que NO lanza
  excepción. Headless en Windows (en CI requeriría display virtual).
- Tras CADA vista migrada: correr pytest + el smoke test, y un checklist manual
  con screenshot antes/después. No avanzar a la siguiente vista con algo roto.

═══════════════════════════════════════════════════════════════════════════
PLAN POR EPICS (con compuertas; no saltar de epic sin cerrar el anterior)
═══════════════════════════════════════════════════════════════════════════
EPIC 0 — AUDITORÍA + ROADMAP  [COMPUERTA: nada se migra sin esto]
  - Leer todos los archivos. Documentar deuda técnica y acoplamiento UI/lógica.
  - Generar ROADMAP.md con tareas priorizadas y complejidad/esfuerzo REAL basado
    en lo encontrado (no estimaciones genéricas).
  - Definir el design system y la ESTRATEGIA DE VERIFICACIÓN UI de arriba.

EPIC 1 — QUICK WINS sobre tk estable (sin depender de la migración)
  - Backup automático de la DB antes de operaciones críticas + logging en
    database/db.py (objetivo 4).
  - chord_grid: transposición in-place (configure(text=...) sobre labels
    existentes) en vez de reconstruir (optimiza objetivo 3a).
  - Toggle de negro puro en stage_view (objetivo 3e).
  - Completar SOLO los atajos que falten (objetivo 3f; 3b ya está hecho).

EPIC 2 — MIGRACIÓN DE LA CÁSCARA A CustomTkinter (híbrida)
  - Instalar customtkinter (ya declarado en requirements.txt) y verificar arranque.
  - DECISIÓN PENDIENTE — Paleta/identidad: definir el design system ANTES de tocar
    vistas. Restricción: conservar el selector de color de acordes. Candidatas:
    (a) identidad actual teal #7eb8a4 + oro #c8a96e sobre #0f0f0f; (b) navy/rojo
    #1a1a2e + #e94560. Resolver con el dueño del proyecto.
  - Migrar en este orden (una vista por PR, con verificación entre cada una):
    app → song_list → setlist_view → edit_view (solo la cáscara) →
    stage_view (cáscara) → chord_popup → author_editor.
  - chord_grid NO se migra. edit_view/stage_view siguen incrustando el chord_grid
    de tk dentro de contenedores ctk (verificar embebido tk-en-ctk antes).

EPIC 3 — EXPORTAR A PDF (objetivo 3c) — epic propio
  - Decisión de dependencia (reportlab o fpdf2). Reproducir la alineación
    acorde-sobre-sílaba; decidir en qué tono se "hornea". Reutilizar bake/display
    del transposer.

EPIC 4 — SETLIST DRAG & DROP (objetivo 3d) — epic propio
  - Hoy hay botones ↑/↓; añadir arrastrar-y-soltar (delicado en tk; evaluar costo).

═══════════════════════════════════════════════════════════════════════════
ORQUESTACIÓN DE SUBAGENTES
═══════════════════════════════════════════════════════════════════════════
- La traducción tk→ctk NO es un rename mecánico: cambian nombres de widgets y de
  opciones (bg→fg_color, fg→text_color), y hay widgets sin equivalente (los menús
  siguen en tk.Menu; tk.Listbox de author_editor no tiene equivalente ctk). Por eso
  usa modelos CAPACES para migrar vistas, para chord_grid y para cualquier decisión
  arquitectónica. Reserva modelos chicos solo para tareas verdaderamente mecánicas
  y SIEMPRE revisa su salida.
- Paraleliza solo epics o archivos DISJUNTOS. stage_view lo tocan varias tareas:
  serialízalas (un dueño por archivo) o define el contrato de interfaz primero.
- Tras cada tarea: pytest + smoke UI; documenta el cambio en CHANGELOG.md.
- No avances si hay tests (o smoke) rotos.

EMPIEZA POR EPIC 0: auditoría completa + ROADMAP.md con estimaciones reales.
No comiences ninguna migración hasta cerrar EPIC 0 y resolver la paleta.
```
