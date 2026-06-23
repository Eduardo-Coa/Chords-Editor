# ROADMAP — HymnChords

> Resultado de la **auditoría (EPIC 0)**. Fecha: 2026-06-21.
> Árbol leído completo: **4.357 líneas** de código fuente + tests.
> Escala de esfuerzo: **S** < 2 h · **M** 2–5 h · **L** 5–10 h · **XL** > 10 h.

---

## 1. Estado actual (verificado)

| Métrica | Valor |
|---|---|
| Python | 3.14.4 (objetivo de compatibilidad: 3.10+) |
| UI | tkinter + ttk (tema `clam`, dict `THEME` en `ui/app.py`) |
| Dependencia de runtime | `customtkinter` (declarada; el código aún corre en tk puro) |
| Persistencia | SQLite, conexión única viva (`database/db.py`) |
| Tests | 57 funciones / 81 casos pytest — **100 % lógica, 0 % UI** |
| Líneas de código (fuente) | 4.357 |

**Lo que está sano:** `models/`, `utils/` y `database/` no importan tkinter — la
lógica está limpiamente desacoplada y bien testeada. `conftest.py` aísla cada test
en un SQLite temporal (nunca toca la base real).

## 2. Ya implementado — NO rehacer

| Objetivo original | Estado real |
|---|---|
| 3b Autoscroll con slider | ✅ Hecho (`stage_view.py:113-117`, `_auto_tick`) |
| 3f Atajos (espacio/flechas) | ✅ Mayormente (`stage_view.py:133-149`) |
| 3a Transposición en vivo | 🟡 Funciona por re-render; falta optimizar a in-place |
| 3e Escenario oscuro | 🟡 Fondo `#0f0f0f`; falta toggle a negro puro |

## 3. Deuda técnica encontrada

| ID | Deuda | Evidencia | Severidad |
|---|---|---|---|
| **D1** | Patrón `Canvas + frame + create_window + scrollregion` duplicado **5 veces** | `edit_view`, `song_list`, `setlist_view` (×2), `stage_view` | 🔴 Alta (lo colapsa `CTkScrollableFrame`) |
| **D2** | Lógica de fila con hover (show/hide + click) duplicada **3 veces** | `song_list._make_row`, `setlist_view._make_setlist_row`, `SongPicker._make_row` | 🟠 Media |
| **D3** | Placeholder de Entry implementado **2 veces** distinto | `song_list._add_placeholder`, `SongPicker._install_placeholder` | 🟡 Baja |
| **D4** | Archivos sobre el límite de ~300 líneas de CLAUDE.md | `edit_view` 690, `setlist_view` 470, `db` 462, `lyrics_parser` 456 | 🟠 Media |
| **D5** | `THEME` es estado global mutable (lo muta `_pick_chord_color`) — viola la propia regla "no variables globales mutables" | `ui/app.py:14`, `edit_view.py:571` | 🟡 Baja (pragmático) |
| **D6** | Sin capa controlador: las vistas tienen `self.db` y llaman a la BD directo → no testeables sin Tk+DB | `edit_view`, `song_list`, `setlist_view`, `author_editor` | 🟠 Media |
| **D7** | `save_song` hace `DELETE FROM sections` + re-INSERT completo en **cada** autosave (cada acorde) | `db.py:159` | 🟡 Baja (funciona; pierde ids y reescribe todo) |
| **D8** | **Cero verificación de UI** — los 81 tests son de lógica | `tests/` | 🔴 Alta (bloquea migración segura) |
| **D9** | Sin logging ni backup en `db.py` (`except Exception: raise` a secas) | `db.py:163,343` | 🟠 Media |

### Trazabilidad: deuda → tarea (ningún ítem queda huérfano)

| Deuda | Se resuelve en | Cómo |
|---|---|---|
| 🔴 **D1** Canvas-scroll ×5 | T7, T8, T9, T10 | **4/5 eliminado** (song_list, setlist ×2, edit_view → `CTkScrollableFrame`). El de **stage_view se CONSERVA a propósito**: centra + auto-scroll por fracción, que `CTkScrollableFrame` no soporta (como `chord_grid`). |
| 🔴 **D8** Cero tests UI | **T1 (primero)** | `test_ui_smoke.py` (construcción) + checklist manual (comportamiento) |
| 🟠 D2 Filas hover ×3 | T7, T8 | ✅ las 3 vistas usan el mismo patrón simplificado (label transparente + `fg_color` de fila) |
| 🟡 D3 Placeholder ×2 | T7, T8 | ✅ resuelto — song_list y SongPicker usan `placeholder_text` nativo (helpers eliminados) |
| 🟠 D4 Archivos largos | T8 (`setlist_view`), T9 (`edit_view`) | setlist_view 470→383 (mejoró, sigue >300; extraer `SongPicker` pendiente); edit_view en T9 |
| 🟡 D5 `THEME` global | T6 | se acota en el design system; **se conserva** (lo usa `chord_grid` en tk) |
| 🟠 D6 Sin controlador | — | **aceptada** para el tamaño actual; revisitar solo si la app crece |
| 🟡 D7 `save_song` reescribe todo | — | deuda aparte; optimización opcional fuera de este plan |
| 🟠 D9 Sin logging/backup | T2 | logging + backup antes de escrituras |

## 4. Acoplamiento UI ↔ lógica

```
models/ utils/ database/   → SIN tkinter (núcleo limpio, testeable) ✅
        │
        ▼
ui/app.py  ──►  THEME (dict global, mutable)  ──►  importado por TODAS las vistas
ui/views/* ──►  reciben `db` y lo llaman directo (no hay controlador)  ⚠️ D6
ui/widgets/chord_grid ──► tk puro, autocontenido (se QUEDA en tk)
```

El acoplamiento problemático está **dentro de `ui/`**, no entre UI y lógica. Eso es
buena noticia para la migración: tocar la cáscara no arriesga la lógica.

## 5. Estrategia de verificación UI (def. EPIC 0 — bloquea EPIC 2)

1. **`tests/test_ui_smoke.py`**: por cada vista, crear un `tk.Tk()` (o `ctk.CTk()`)
   con `root.withdraw()`, instanciar la vista con un `db` de `conftest`, llamar
   `update_idletasks()` y afirmar que **no lanza**. Cubre regresiones de construcción
   (imports, widgets, opciones inválidas) — el fallo más común al migrar a ctk.
2. **Checklist manual + screenshot** antes/después por vista migrada.
3. **Compuerta**: `pytest` (81 lógica) **+** smoke **+** checklist en verde antes de
   pasar a la siguiente vista.

## 6. Design system (def. EPIC 0)

- **Tokens** (mapear `THEME` → API ctk): `bg→fg_color` de ventana, `surface/surface2→
  fg_color` de frames, `text→text_color`, `accent→` color de botón, `danger→`.
- `chord_grid` **conserva `THEME` de tk** (no se migra) → mantener los tokens vivos.
- **Selector de color de acordes**: sigue escribiendo `THEME["chord"]` y
  `preferences.json`; el design system debe respetarlo.
- 🔲 **DECISIÓN PENDIENTE — paleta**: (a) identidad actual teal+oro sobre near-black;
  (b) navy `#1a1a2e` + rojo `#e94560`. **Resolver antes de migrar `app.py`.**

## 7. Plan por epics con estimaciones reales

| # | Tarea | Epic | Esfuerzo | Riesgo | Archivos / notas |
|---|---|---|---|---|---|
| T0 | Auditoría + este ROADMAP | 0 | — | — | ✅ hecho |
| T1 | `test_ui_smoke.py` (red de seguridad UI) | 0→1 | S | bajo | ✅ hecho — 11 smoke tests, raíz Tk compartida |
| T2 | Logging + backup de DB antes de escrituras | 1 | M | bajo | ✅ hecho — `backup()`+rotación en `db.py`, `utils/logging_setup.py`, 5 tests |
| T3 | Transposición in-place en `chord_grid` | 1 | M | medio | ⏸️ **defer** — el rebuild en tk ya es ~44 ms (instantáneo); valor bajo al quedarse `chord_grid` en tk |
| T4 | Toggle negro puro en escenario | 1 | S | bajo | pendiente (opcional) — `stage_view` ya es ctk; requiere override de color en `chord_grid` |
| T5 | Completar atajos faltantes | 1 | S | bajo | `stage_view` (revisar qué falta) |
| T6 | `app.py` → ctk + design system | 2 | M | medio | ✅ hecho — paleta A, `ctk_button_style()`, nav migrada; raíz sigue tk |
| T7 | `song_list` → ctk | 2 | M | medio | ✅ hecho — CTkScrollableFrame, CTkOptionMenu, placeholder nativo |
| T8 | `setlist_view` → ctk | 2 | L | medio | ✅ hecho — 2× D1 + SongPicker; 470→383 líneas |
| T9 | `edit_view` (cáscara) → ctk | 2 | L | **alto** | ✅ hecho — chord_grid tk embebido en CTkScrollableFrame; menú sigue tk.Menu |
| T10 | `stage_view` (cáscara) → ctk | 2 | M | medio | ✅ hecho — paneles + `CTkSlider`; canvas tk se conserva (centrado + auto-scroll) |
| T11 | `chord_popup` → ctk | 2 | M | medio | ✅ hecho — CTkEntry/CTkLabel; Toplevel borderless se conserva |
| T12 | `author_editor` → ctk | 2 | S–M | medio | ✅ hecho — Listbox → CTkScrollableFrame de filas seleccionables |
| T13 | Exportar a PDF | 3 | L | medio | ✅ hecho — `fpdf2` (1 clic), Courier monoespaciada embebida, auto-ajuste de fuente, claro; menú Archivo |
| T14 | Setlist drag & drop | 4 | M–L | medio | ✅ hecho — agarre `≡` por fila, línea de inserción al arrastrar, sin re-render durante el drag (no rompe el grab); `compute_drop_index` pura + 6 tests. ↑/↓ se conservan como respaldo |

**EPIC 1 ≈ S+M+M+S+S → ~1.5–2 días. EPIC 2 ≈ M+M+L+L+M+M+S → ~1 semana.**

## 8. Riesgos principales

1. **Embebido tk-en-ctk** (T9/T10): `chord_grid` (tk) debe vivir dentro de
   contenedores ctk. Hacer un mini-spike de embebido + color de fondo **antes** de T9.
2. **Rendimiento `chord_grid`** (ya mitigado por diseño): se queda en tk; vigilar que
   T3 lo deje instantáneo.
3. **`tk.Listbox` sin equivalente ctk** (T12): replantear como lista scrollable.
4. **`stage_view` compartido** por T4/T5/T10: un solo dueño, serializar.
5. **Paleta sin decidir**: bloquea T6. Resolver primero.

## 9. Orden de ejecución sugerido

```
EPIC 0  ✅ (T0)  →  ✅ T1 (smoke)         ← compuerta de seguridad UI (lista)
EPIC 1  ✅ T2 → T3 (defer) → T4 → T5      ← valor inmediato, sin dependencia nueva
        [decidir paleta]                  ← compuerta de EPIC 2
EPIC 2  ✅ T6 → ✅ T7 → ✅ T8 → ✅ T9 → ✅ T10 → ✅ T11 → ✅ T12  ← COMPLETA
EPIC 3  ✅ T13 (PDF)     EPIC 4  ✅ T14 (d&d)  ← independientes
```
