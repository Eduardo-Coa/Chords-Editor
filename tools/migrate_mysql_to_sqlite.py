"""Migración única de datos de MySQL a SQLite para HymnChords.

Lee todas las canciones y listas del servidor MySQL (credenciales del .env) y las
copia a la base SQLite que usa ahora la app. Ejecutar UNA sola vez:

    python tools/migrate_mysql_to_sqlite.py

Es seguro: solo LEE de MySQL, nunca lo modifica ni lo borra. Si la base SQLite ya
tiene canciones, la migración se cancela para no duplicar (usa --force para forzar).
"""

from __future__ import annotations
import sys
from pathlib import Path

# La consola de Windows usa cp1252 por defecto; forzar UTF-8 evita que se caiga
# al imprimir títulos con caracteres especiales.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Permite importar el paquete del proyecto al ejecutar el script directamente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.config import load_config
from database.db import Database
from models.song import Song, Section, Line, Syllable, Chord
from models.setlist import Setlist, SetlistItem


def parse_env(path: Path) -> dict[str, str]:
    """Lee el .env (CLAVE=valor) e ignora comentarios y líneas vacías."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def connect_mysql(env: dict[str, str]):
    """Abre la conexión MySQL de origen con las credenciales del .env."""
    import mysql.connector  # import local: solo se necesita para migrar

    return mysql.connector.connect(
        host=env["DB_HOST"],
        port=int(env.get("DB_PORT", "3306")),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        charset="utf8mb4",
    )


def _has_transpose_column(cur) -> bool:
    """Detecta si el MySQL de origen ya tiene la columna sections.transpose."""
    cur.execute("SHOW COLUMNS FROM sections LIKE 'transpose'")
    return cur.fetchone() is not None


def read_song(cur, song_row: dict, has_transpose: bool) -> Song:
    """Reconstruye un Song completo (secciones, líneas, sílabas, acordes) desde MySQL."""
    song = Song(
        id=None,  # el id lo asigna SQLite al guardar
        title=song_row["title"],
        author=song_row["author"],
        key=song_row["key"],
        rhythm=song_row["rhythm"],
        capo=song_row["capo"] or 0,
        notes=song_row["notes"],
    )

    cols = "id, position, type, label" + (", transpose" if has_transpose else "")
    cur.execute(
        f"SELECT {cols} FROM sections WHERE song_id=%s ORDER BY position",
        (song_row["id"],),
    )
    for sec in cur.fetchall():
        section = Section(
            id=None, position=sec["position"], type=sec["type"],
            label=sec["label"], transpose=sec.get("transpose", 0) or 0,
        )
        cur.execute(
            "SELECT id, position FROM `lines` WHERE section_id=%s ORDER BY position",
            (sec["id"],),
        )
        for line_row in cur.fetchall():
            line = Line(id=None, position=line_row["position"])
            cur.execute(
                "SELECT s.position, s.text, c.value AS chord_value "
                "FROM syllables s LEFT JOIN chords c ON c.syllable_id = s.id "
                "WHERE s.line_id=%s ORDER BY s.position",
                (line_row["id"],),
            )
            for syl in cur.fetchall():
                chord = (
                    Chord(id=None, value=syl["chord_value"])
                    if syl["chord_value"] is not None else None
                )
                line.syllables.append(
                    Syllable(id=None, position=syl["position"],
                             text=syl["text"], chord=chord)
                )
            section.lines.append(line)
        song.sections.append(section)
    return song


def migrate_songs(cur, target: Database) -> dict[int, int]:
    """Copia todas las canciones. Devuelve el mapa id_mysql -> id_sqlite."""
    has_transpose = _has_transpose_column(cur)
    cur.execute(
        "SELECT id, title, author, `key`, rhythm, capo, notes FROM songs ORDER BY id"
    )
    song_rows = cur.fetchall()

    id_map: dict[int, int] = {}
    for row in song_rows:
        song = read_song(cur, row, has_transpose)
        new_id = target.save_song(song)
        id_map[row["id"]] = new_id
        print(f"  - {song.title}")
    return id_map


def migrate_setlists(cur, target: Database, id_map: dict[int, int]) -> int:
    """Copia las listas remapeando los ids de canción. Devuelve cuántas migró."""
    cur.execute("SELECT id, name FROM setlists ORDER BY id")
    setlist_rows = cur.fetchall()

    count = 0
    for srow in setlist_rows:
        cur.execute(
            "SELECT song_id, position, transpose FROM setlist_songs "
            "WHERE setlist_id=%s ORDER BY position",
            (srow["id"],),
        )
        items: list[SetlistItem] = []
        for irow in cur.fetchall():
            new_song_id = id_map.get(irow["song_id"])
            if new_song_id is None:
                continue  # la canción no se migró (no debería pasar)
            items.append(
                SetlistItem(
                    id=None, song_id=new_song_id,
                    position=irow["position"], transpose=irow["transpose"] or 0,
                )
            )
        target.save_setlist(Setlist(id=None, name=srow["name"], items=items))
        count += 1
        print(f"  - lista: {srow['name']} ({len(items)} canciones)")
    return count


def main() -> None:
    force = "--force" in sys.argv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        print("No se encontró el archivo .env con las credenciales de MySQL.")
        return
    env = parse_env(env_path)

    target = Database(load_config())
    target.init_schema()

    existing = target.list_songs()
    if existing and not force:
        print(f"La base SQLite ya contiene {len(existing)} canción(es): "
              f"{load_config().path}")
        print("La migración se canceló para no duplicar datos.")
        print("Si de verdad quieres volver a importar, ejecuta con --force.")
        return

    try:
        mysql_conn = connect_mysql(env)
    except ImportError:
        print("Falta 'mysql-connector-python' para leer de MySQL. Instálalo solo "
              "para migrar:\n    pip install mysql-connector-python")
        return
    except Exception as e:  # noqa: BLE001 — mensaje claro al usuario
        print(f"No se pudo conectar a MySQL: {e}")
        return

    cur = mysql_conn.cursor(dictionary=True)
    print("Migrando canciones...")
    id_map = migrate_songs(cur, target)
    print("Migrando listas...")
    n_lists = migrate_setlists(cur, target, id_map)

    cur.close()
    mysql_conn.close()
    target.close()

    print(f"\nMigración completa: {len(id_map)} canciones y {n_lists} listas.")
    print(f"Base SQLite: {load_config().path}")


if __name__ == "__main__":
    main()
