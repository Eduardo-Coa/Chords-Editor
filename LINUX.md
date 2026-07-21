# Guía: hacer que HymnChords corra en Linux

Guía paso a paso, pensada para seguir sin experiencia previa en el proyecto.
Cada paso dice **qué hacer**, **dónde** y **por qué**.

---

## 0. La idea general (leer esto primero)

HymnChords **ya es casi multiplataforma**. No hay que crear una "versión Linux"
aparte ni borrar lo de Windows. La base de datos, la lógica y la mayor parte de
la interfaz ya funcionan igual en los dos sistemas.

Solo faltan **3 ajustes**, y dos de ellos ya tienen el "enchufe" hecho en el
código (solo hay que agregarles el caso de Linux).

**La regla más importante:** todo lo que hagas es **para sumar**, nunca para
borrar. El objetivo es **un solo código que funcione en Windows y en Linux**, no
dos proyectos separados. Si borrás lo de Windows, el proyecto se parte en dos y
cada mejora futura habría que copiarla a mano para siempre.

### Lo que ya funciona (no tocar)

| Cosa | Estado |
|---|---|
| Base de datos (SQLite) | Ya funciona igual |
| `database/config.py` | Ya guarda los datos en `~/.hymnchords/` en Linux |
| `models/`, `utils/` | Python puro, sin nada de Windows |
| tkinter + CustomTkinter + fpdf2 | Todas corren en Linux |

### Lo que hay que ajustar (los 3 cambios)

1. **Fuentes** — usa fuentes de Windows ("Segoe UI", "Consolas") que en Linux no existen.
2. **Ícono de la ventana** — usa un `.ico`, formato que tkinter no lee en Linux.
3. **Empaquetado** — hay script para hacer el `.exe`; falta el equivalente Linux.

---

## Antes de empezar (esto lo hace Eduardo, el dueño del repo)

**1. Mergear el trabajo a `develop`.** Todo el trabajo estaba en `dev_dcoa37`
(mi rama personal). Antes de que empieces, hago un Pull Request dentro de mi
propio repo: `base: develop` ← `compare: dev_dcoa37`, y lo mergeo. A partir de
ahí, **`develop` es la rama compartida** desde la que vas a trabajar vos —
`dev_dcoa37` queda como mi rama personal, no la toques.

**2. Subir el ícono.** El archivo `assets/Ilahi-iconAPP.png` existe en mi
carpeta pero **no está subido a git** (solo está `icon.ico`). Sin ese PNG el
ícono en Linux no va a funcionar. Lo subo directo a `develop`, después de
mergear lo anterior:

```bash
git checkout develop
git pull origin develop
git add assets/Ilahi-iconAPP.png
git commit -m "Agrega el PNG del icono (necesario para Linux)"
git push origin develop
```

---

## Paso 1 — Preparar la máquina Linux

Abrí una terminal y instalá lo necesario según tu distribución.

**Ubuntu / Debian / Mint:**
```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk git
```

**Fedora:**
```bash
sudo dnf install python3 python3-tkinter git
```

**Arch / Manjaro:**
```bash
sudo pacman -S python tk git
```

> **¿Por qué `python3-tk`?** En Windows tkinter viene incluido con Python, pero
> en Linux se instala aparte. Sin esto la app no abre. Es el error más común.

Verificá que quedó bien (debe decir 3.10 o superior):
```bash
python3 --version
python3 -c "import tkinter; print('tkinter OK')"
```

---

## Paso 2 — Conseguir el código

Vas a trabajar sobre una **copia enlazada** del repo de Eduardo (un *fork*), no
sobre una copia suelta. El fork mantiene el vínculo con el original, que es lo
que después te permite mandarle tus cambios de vuelta con un botón.

> **¿Hay que crear una carpeta a mano antes?** No. El comando para descargar el
> código (`git clone`, más abajo) crea la carpeta él solo, con el nombre del
> proyecto. Lo único que elegís vos es **en qué carpeta más grande** vivir (por
> ejemplo tu Escritorio o tu carpeta Home) — eso se hace con `cd` antes de clonar.

### 2.1 — Tener cuenta de GitHub

Si no tenés una, creála gratis en **github.com** (botón *Sign up*). Es la misma
cuenta con la que vas a hacer todo lo que sigue.

### 2.2 — Entrar al repositorio de Eduardo

Eduardo te va a pasar este link:

```
https://github.com/Eduardo-Coa/Chords-Editor
```

Abrilo en el navegador, **con tu cuenta ya iniciada**.

### 2.3 — Hacer tu Fork

Arriba a la derecha de la página vas a ver un botón que dice **Fork**. Hacé
clic ahí (podés dejar las opciones por defecto y confirmar).

Esto crea una **copia del repositorio dentro de tu propia cuenta**. Vas a
terminar en una página con una URL parecida a esta (con tu usuario, no el de
Eduardo):

```
https://github.com/TU-USUARIO/Chords-Editor
```

**A partir de acá trabajás sobre ESA página (la tuya), no sobre la de Eduardo.**
Guardate esa URL: es la que vas a usar en el paso siguiente.

> Si ya habías creado un repositorio vacío por tu cuenta antes de esta guía,
> **no lo uses**: borralo y hacé el fork. Un repo suelto (sin el vínculo del
> fork) no puede mandarle los cambios de vuelta a Eduardo con un Pull Request.

### 2.4 — Copiar la URL para descargar

Ya parado en **tu** fork (`github.com/TU-USUARIO/Chords-Editor`), buscá el
botón verde que dice **Code**, hacé clic, y copiá la URL que aparece bajo
**HTTPS** (con el ícono de copiar al lado).

### 2.5 — Elegir dónde va a vivir el proyecto

Abrí la terminal y movete a la carpeta donde querés que aparezca el proyecto.
Por ejemplo, tu Escritorio:

```bash
cd ~/Escritorio
```

(en algunos sistemas en inglés es `cd ~/Desktop`; si no sabés cuál es, hacé
`cd ~` para ir a tu carpeta personal y descargarlo ahí).

### 2.6 — Descargar el código (clonar)

Ahora sí, el comando que **crea la carpeta automáticamente**:

```bash
git clone <PEGÁ-ACÁ-LA-URL-QUE-COPIASTE-EN-2.4>
```

Esto va a crear una carpeta nueva llamada `Chords-Editor` (el nombre del
repositorio) con todo el código adentro. Entrá a esa carpeta:

```bash
cd Chords-Editor
```

> ⚠️ **Importante — leer esto antes de seguir.** El repositorio tiene tres
> ramas: `main`, `develop` y `dev_dcoa37`. `main` es casi un cascarón vacío
> (un solo archivo) y `dev_dcoa37` es la rama personal de Eduardo — ninguna
> de las dos es para vos. **Trabajá siempre desde `develop`**, que es donde
> Eduardo dejó el proyecto completo. Cuando clonás, `git` te deja parado en
> `main` por defecto. Si seguís de largo sin hacer el paso 2.7, no vas a
> encontrar la mayoría de los archivos que mencionamos más abajo.

### 2.7 — Pararte sobre el código real y crear tu rama de trabajo

Primero, movete a la rama donde está todo el trabajo:

```bash
git checkout develop
```

Ahora sí, creá tu rama de trabajo **a partir de esta**:

```bash
git checkout -b linux
```

Esto crea una rama nueva llamada `linux`, partiendo de `develop` (no de
`main` ni de la personal de Eduardo), y te para sobre ella. Trabajar en una
rama aparte es lo que te permite mandar tus cambios prolijos con un Pull
Request al final (Paso 7).

Confirmá que quedaste en el lugar correcto:

```bash
git branch
```

Debe mostrar `linux` con un asterisco (`*`) al lado, y en la carpeta ya deberías
ver `models/`, `ui/`, `database/`, `utils/`, `tests/`, etc. (no solo `main.py`).

✅ **En este punto ya tenés el código real en tu máquina.** Seguí con el Paso 3.

---

## Paso 3 — Crear el entorno e instalar las librerías

El *entorno virtual* (`venv`) es una carpeta donde se instalan las librerías del
proyecto sin ensuciar el Python del sistema.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Después de activarlo vas a ver `(.venv)` al principio de la línea de la
terminal. **Cada vez que abras una terminal nueva tenés que volver a correr
`source .venv/bin/activate`.**

> `requirements-dev.txt` instala las librerías de la app (customtkinter, fpdf2)
> **más** pytest, que te va a servir para verificar que no rompiste nada.

---

## Paso 4 — Primera corrida (ver qué pasa)

```bash
python main.py
```

**Lo esperable:** la app abre y funciona, pero se ve fea — las letras salen con
una fuente rara y los acordes quedan desalineados. Eso es justamente lo que
arreglan los cambios que siguen.

Si la app **no abre** y el error dice `ModuleNotFoundError: No module named
'tkinter'`, volvé al Paso 1: falta `python3-tk`.

---

## Paso 5 — Los 3 cambios

### Cambio 1: las fuentes (el más importante)

**Archivo:** `ui/app.py`
**Buscá** la función `_apply_platform_fonts()`. Se ve así:

```python
def _apply_platform_fonts() -> None:
    """Ajusta las fuentes del THEME según el sistema operativo."""
    if sys.platform == "darwin":  # macOS
        replacements = {
            "font_ui":          ("Helvetica Neue", 12),
            ...
        }
        THEME.update(replacements)
```

**Qué hacer:** agregá un bloque `elif` para Linux, justo después del bloque de
macOS (respetando la indentación: el `elif` va alineado con el `if`).

```python
    elif sys.platform.startswith("linux"):
        THEME.update({
            "font_ui":          ("DejaVu Sans", 10),
            "font_list":        ("DejaVu Sans", 12),
            "font_mono":        ("DejaVu Sans Mono", 11),
            "font_stage":       ("DejaVu Sans Mono", 22),
            "font_chord_stage": ("DejaVu Sans Mono", 18),
            "font_section":     ("DejaVu Sans", 9),
        })
```

> **¿Por qué DejaVu?** Viene instalada en prácticamente toda distribución Linux.
> Y **DejaVu Sans Mono es monoespaciada**, que es imprescindible: los acordes se
> alinean sobre las sílabas contando caracteres. Con una fuente que no sea
> monoespaciada, los acordes quedan corridos.

---

### Cambio 2: el ícono de la ventana

**Archivo:** `main.py`

Primero, arriba del todo, agregá `import sys` junto a los otros imports:

```python
from __future__ import annotations
import sys
import tkinter as tk
```

Después buscá este bloque (está cerca de la línea 25):

```python
    try:
        root.iconbitmap(str(resource_path("assets/icon.ico")))
    except tk.TclError:
        pass  # sin ícono no es fatal
```

**Reemplazalo por:**

```python
    try:
        if sys.platform.startswith("linux"):
            # tkinter en Linux no lee .ico: se usa un PNG con iconphoto.
            root.iconphoto(
                True,
                tk.PhotoImage(file=str(resource_path("assets/Ilahi-iconAPP.png"))))
        else:
            root.iconbitmap(str(resource_path("assets/icon.ico")))
    except (tk.TclError, OSError):
        pass  # sin ícono no es fatal
```

> Fijate que **no borramos** la línea de Windows: la dejamos en el `else`. Ese es
> el patrón de todos los cambios.

---

### Cambio 3: el empaquetado (dejalo para el final)

Windows arma un `.exe` con `build.ps1` + `HymnChords.spec`. **No los toques ni
los borres.**

Para Linux, lo más simple que ya sirve es un script de arranque. Creá un archivo
nuevo llamado `run.sh` en la raíz del proyecto:

```bash
#!/usr/bin/env bash
# Arranca HymnChords en Linux (crea el entorno la primera vez).
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python main.py
```

Y dale permiso de ejecución:

```bash
chmod +x run.sh
```

Con eso cualquiera en Linux corre la app con `./run.sh`. Un ejecutable único
(AppImage o `.deb`) es un paso siguiente, opcional — conviene dejarlo para
después de que lo básico funcione bien.

---

## Paso 6 — Probar que todo anda

**1. Las pruebas automáticas** (verifican que no rompiste la lógica):

```bash
pytest
```

Todas deben pasar. Si alguna falla, algo de lo que tocaste rompió algo:
revisá el cambio antes de seguir.

**2. La app a mano:**

```bash
python main.py
```

Revisá esta lista:

- [ ] Abre la ventana y se ve el ícono
- [ ] Las letras se ven bien (no con fuente rara)
- [ ] **Los acordes quedan alineados sobre las sílabas** ← lo más importante
- [ ] Se puede crear una canción y pegarle letra
- [ ] Se pueden asignar acordes haciendo clic
- [ ] La vista de escenario abre y se ve bien
- [ ] Transponer (+/-) funciona
- [ ] Exportar a PDF funciona
- [ ] Al cerrar y volver a abrir, las canciones siguen ahí

**3. Dónde quedaron los datos** (para confirmar que guarda bien):

```bash
ls -la ~/.hymnchords/
```

Deberías ver `hymnchords.db` y `preferences.json`.

---

## Paso 7 — Mandarle los cambios a Eduardo

```bash
git add -A
git commit -m "Soporte para Linux: fuentes, icono y script de arranque"
git push -u origin linux
```

Después:

1. Entrá a tu fork en GitHub.
2. Va a aparecer un cartel que dice **Compare & pull request**. Clic ahí.
3. ⚠️ **Muy importante:** arriba de la página vas a ver dos menús desplegables
   que dicen algo como `base: main` ← `compare: linux`. Cambiá **`base`** de
   `main` a **`develop`**. Si dejás `main`, GitHub va a mostrar un diff
   gigante con TODO el trabajo previo de Eduardo, no solo tus cambios de Linux.
4. Escribí brevemente qué cambiaste y en qué distribución lo probaste.
5. Clic en **Create pull request**.

Eduardo lo revisa y lo integra. A partir de ahí queda **un solo proyecto** que
funciona en los dos sistemas.

---

## Reglas de oro (para no romper nada)

✅ **Sí:**
- Agregar ramas `elif sys.platform.startswith("linux"):` junto a las que ya existen.
- Dejar intacto todo lo de Windows.
- Correr `pytest` antes de cada commit.

❌ **No:**
- Borrar `build.ps1`, `HymnChords.spec`, `assets/icon.ico` ni `tools/make_icon.py`.
- Subir la carpeta `.venv` (es pesada y es de tu máquina; ya está ignorada).
- Cambiar cosas de `models/`, `database/` o `utils/`: ahí no hay nada de Windows.
  Si algo falla ahí, es un bug de verdad — avisale a Eduardo antes de tocarlo.
- Reescribir la interfaz con otra librería (Qt, GTK). No hace falta: CustomTkinter
  ya corre en Linux.

---

## Problemas comunes

**`ModuleNotFoundError: No module named 'tkinter'`**
Falta el paquete del sistema. Volvé al Paso 1 (`sudo apt install python3-tk`).

**Los acordes salen desalineados**
La fuente monoespaciada no se está aplicando. Revisá el Cambio 1: que sea
`DejaVu Sans Mono` (no `DejaVu Sans`) en `font_mono`, `font_stage` y
`font_chord_stage`. Verificá que la tengas: `fc-list | grep "DejaVu Sans Mono"`.

**La ventana abre sin ícono**
No es grave (el código lo ignora a propósito). Casi seguro falta el archivo
`assets/Ilahi-iconAPP.png`: pedile a Eduardo que lo suba (ver "Antes de empezar").

**`pip install` falla**
Confirmá que el entorno esté activado: tenés que ver `(.venv)` al principio de
la línea. Si no, corré `source .venv/bin/activate`.
