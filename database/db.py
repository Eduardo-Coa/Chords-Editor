"""Acceso a la base de datos MySQL para HymnChords."""

from __future__ import annotations
from typing import Any
import mysql.connector

from database.config import DBConfig
from models.song import Song, Section, Line, Syllable, Chord
from models.setlist import Setlist, SetlistItem

# Los type stubs de mysql-connector-python son incompletos (uniones de conexión,
# cursores como context manager, filas dict). Se usa Any en la frontera con la
# librería para evitar falsos positivos del verificador de tipos. El código está
# probado contra MySQL en runtime.


class Database:
    """Maneja todas las operaciones de lectura y escritura contra MySQL."""

    def __init__(self, config: DBConfig) -> None:
        self._config = config
        self._conn: Any = None

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def _connect(self) -> Any:
        """Abre (o reutiliza) la conexión al servidor MySQL."""
        if self._conn is None or not self._conn.is_connected():
            self._conn = mysql.connector.connect(
                host=self._config.host,
                port=self._config.port,
                user=self._config.user,
                password=self._config.password,
                database=self._config.database,
                charset="utf8mb4",
                autocommit=False,
            )
        return self._conn

    def close(self) -> None:
        """Cierra la conexión si está abierta."""
        if self._conn and self._conn.is_connected():
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Inicialización del esquema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """
        Crea la base de datos y las tablas si no existen.
        Debe llamarse una vez al arrancar la aplicación.
        """
        # Conectar sin seleccionar DB para poder crearla
        bootstrap: Any = mysql.connector.connect(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            password=self._config.password,
            charset="utf8mb4",
        )
        try:
            with bootstrap.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self._config.database}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            bootstrap.commit()
        finally:
            bootstrap.close()

        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(f"USE `{self._config.database}`")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    title      VARCHAR(255) NOT NULL,
                    author     VARCHAR(255),
                    `key`      VARCHAR(10),
                    rhythm     VARCHAR(50),
                    capo       INT DEFAULT 0,
                    notes      TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sections (
                    id       INT AUTO_INCREMENT PRIMARY KEY,
                    song_id  INT NOT NULL,
                    position INT NOT NULL,
                    type     ENUM('verse','chorus','bridge','intro','outro') NOT NULL,
                    label    VARCHAR(100),
                    transpose INT DEFAULT 0,
                    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            self._migrate_section_transpose(cur)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS `lines` (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    section_id INT NOT NULL,
                    position   INT NOT NULL,
                    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS syllables (
                    id       INT AUTO_INCREMENT PRIMARY KEY,
                    line_id  INT NOT NULL,
                    position INT NOT NULL,
                    text     VARCHAR(255) NOT NULL,
                    FOREIGN KEY (line_id) REFERENCES `lines`(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chords (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    syllable_id INT NOT NULL UNIQUE,
                    value       VARCHAR(20) NOT NULL,
                    FOREIGN KEY (syllable_id) REFERENCES syllables(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS setlists (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    name       VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS setlist_songs (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    setlist_id INT NOT NULL,
                    song_id    INT NOT NULL,
                    position   INT NOT NULL,
                    transpose  INT DEFAULT 0,
                    FOREIGN KEY (setlist_id) REFERENCES setlists(id) ON DELETE CASCADE,
                    FOREIGN KEY (song_id)    REFERENCES songs(id)    ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()

    def _migrate_section_transpose(self, cur: Any) -> None:
        """Añade la columna ``transpose`` a ``sections`` si una BD antigua no la tiene."""
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sections' "
            "AND COLUMN_NAME='transpose'",
            (self._config.database,),
        )
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE sections ADD COLUMN transpose INT DEFAULT 0")

    # ------------------------------------------------------------------
    # CRUD canciones
    # ------------------------------------------------------------------

    def save_song(self, song: Song) -> int:
        """
        Inserta o actualiza una canción completa (incluyendo secciones, líneas,
        sílabas y acordes). Devuelve el id asignado.
        """
        # Normalización: quitar espacios sobrantes del autor
        if song.author is not None:
            song.author = song.author.strip() or None

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                if song.id is None:
                    cur.execute(
                        "INSERT INTO songs (title, author, `key`, rhythm, capo, notes) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (song.title, song.author, song.key, song.rhythm, song.capo, song.notes),
                    )
                    song.id = cur.lastrowid
                else:
                    cur.execute(
                        "UPDATE songs SET title=%s, author=%s, `key`=%s, rhythm=%s, "
                        "capo=%s, notes=%s WHERE id=%s",
                        (song.title, song.author, song.key, song.rhythm,
                         song.capo, song.notes, song.id),
                    )
                    # Borrar secciones antiguas; el CASCADE elimina líneas/sílabas/acordes
                    cur.execute("DELETE FROM sections WHERE song_id=%s", (song.id,))

                self._save_sections(cur, song)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return song.id  # type: ignore[return-value]

    def _save_sections(self, cur: Any, song: Song) -> None:
        """Inserta secciones, líneas, sílabas y acordes de la canción."""
        for section in song.sections:
            cur.execute(
                "INSERT INTO sections (song_id, position, type, label, transpose) "
                "VALUES (%s, %s, %s, %s, %s)",
                (song.id, section.position, section.type, section.label,
                 section.transpose),
            )
            section.id = cur.lastrowid

            for line in section.lines:
                cur.execute(
                    "INSERT INTO `lines` (section_id, position) VALUES (%s, %s)",
                    (section.id, line.position),
                )
                line.id = cur.lastrowid

                for syllable in line.syllables:
                    cur.execute(
                        "INSERT INTO syllables (line_id, position, text) VALUES (%s, %s, %s)",
                        (line.id, syllable.position, syllable.text),
                    )
                    syllable.id = cur.lastrowid

                    if syllable.chord is not None:
                        cur.execute(
                            "INSERT INTO chords (syllable_id, value) VALUES (%s, %s)",
                            (syllable.id, syllable.chord.value),
                        )
                        syllable.chord.id = cur.lastrowid

    def load_song(self, song_id: int) -> Song:
        """Carga una canción completa desde la base de datos."""
        conn = self._connect()
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id, title, author, `key`, rhythm, capo, notes "
                "FROM songs WHERE id=%s",
                (song_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"No existe la canción con id={song_id}")

            song = Song(
                id=row["id"],
                title=row["title"],
                author=row["author"],
                key=row["key"],
                rhythm=row["rhythm"],
                capo=row["capo"] or 0,
                notes=row["notes"],
            )

            cur.execute(
                "SELECT id, position, type, label, transpose FROM sections "
                "WHERE song_id=%s ORDER BY position",
                (song_id,),
            )
            for sec_row in cur.fetchall():
                section = Section(
                    id=sec_row["id"],
                    position=sec_row["position"],
                    type=sec_row["type"],
                    label=sec_row["label"],
                    transpose=sec_row["transpose"] or 0,
                )
                section.lines = self._load_lines(cur, sec_row["id"])
                song.sections.append(section)

        return song

    def _load_lines(self, cur: Any, section_id: int) -> list[Line]:
        """Carga las líneas de una sección, incluyendo sílabas y acordes."""
        cur.execute(
            "SELECT id, position FROM `lines` WHERE section_id=%s ORDER BY position",
            (section_id,),
        )
        lines: list[Line] = []
        for line_row in cur.fetchall():
            line = Line(id=line_row["id"], position=line_row["position"])

            cur.execute(
                "SELECT s.id, s.position, s.text, c.id AS chord_id, c.value AS chord_value "
                "FROM syllables s "
                "LEFT JOIN chords c ON c.syllable_id = s.id "
                "WHERE s.line_id=%s ORDER BY s.position",
                (line_row["id"],),
            )
            for syl_row in cur.fetchall():
                chord = (
                    Chord(id=syl_row["chord_id"], value=syl_row["chord_value"])
                    if syl_row["chord_value"] is not None
                    else None
                )
                line.syllables.append(
                    Syllable(
                        id=syl_row["id"],
                        position=syl_row["position"],
                        text=syl_row["text"],
                        chord=chord,
                    )
                )
            lines.append(line)
        return lines

    # Campos por los que se puede filtrar. Whitelist de nombre lógico -> columna
    # SQL real (evita inyección). Para agregar un filtro nuevo, basta una línea.
    _FILTER_COLUMNS = {
        "author": "author",
        "rhythm": "rhythm",
        "key": "`key`",
    }

    def list_songs(
        self, query: str = "", filters: dict[str, str] | None = None
    ) -> list[dict]:
        """
        Devuelve lista de canciones como dicts con id, title, author, key.

        ``query`` filtra por título o autor (búsqueda parcial). ``filters`` es un
        dict {campo: valor} para filtros exactos (ej. {"author": "..."}); solo se
        aceptan los campos de ``_FILTER_COLUMNS``. Todos los criterios se combinan
        con AND.
        """
        where: list[str] = []
        params: list[str] = []

        if query:
            pattern = f"%{query}%"
            where.append("(title LIKE %s OR author LIKE %s)")
            params.extend([pattern, pattern])

        for field, value in (filters or {}).items():
            column = self._FILTER_COLUMNS.get(field)
            if column and value:
                where.append(f"{column} = %s")
                params.append(value)

        sql = "SELECT id, title, author, `key` FROM songs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY title"

        conn = self._connect()
        with conn.cursor(dictionary=True) as cur:
            cur.execute(sql, params)
            return cur.fetchall()  # type: ignore[return-value]

    def distinct_values(self, field: str) -> list[str]:
        """Valores distintos no vacíos de un campo filtrable (para los desplegables)."""
        column = self._FILTER_COLUMNS.get(field)
        if column is None:
            raise ValueError(f"Campo no filtrable: {field}")
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT {column} FROM songs "
                f"WHERE {column} IS NOT NULL AND {column} <> '' ORDER BY {column}"
            )
            return [row[0] for row in cur.fetchall()]

    def rename_author(self, old: str, new: str) -> None:
        """
        Renombra un autor en todas sus canciones. Si ``new`` coincide con un autor
        existente, ambos quedan fusionados. Si ``new`` queda vacío, las canciones
        quedan sin autor (NULL).
        """
        new_value = new.strip() or None
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE songs SET author=%s WHERE author=%s", (new_value, old)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def delete_song(self, song_id: int) -> None:
        """Elimina una canción y todos sus datos relacionados."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM songs WHERE id=%s", (song_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------------------------
    # CRUD listas de canciones (setlists)
    # ------------------------------------------------------------------

    def list_setlists(self) -> list[dict]:
        """Devuelve las listas como dicts con id, name y song_count."""
        conn = self._connect()
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT s.id, s.name, COUNT(ss.id) AS song_count "
                "FROM setlists s "
                "LEFT JOIN setlist_songs ss ON ss.setlist_id = s.id "
                "GROUP BY s.id, s.name ORDER BY s.name"
            )
            return cur.fetchall()  # type: ignore[return-value]

    def create_setlist(self, name: str) -> int:
        """Crea una lista vacía y devuelve su id."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO setlists (name) VALUES (%s)", (name,))
                new_id = cur.lastrowid
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return new_id  # type: ignore[return-value]

    def save_setlist(self, setlist: Setlist) -> int:
        """
        Inserta o actualiza una lista completa (nombre + canciones ordenadas con
        su tono). Reemplaza todos los items en una sola transacción. Devuelve el id.
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                if setlist.id is None:
                    cur.execute(
                        "INSERT INTO setlists (name) VALUES (%s)", (setlist.name,)
                    )
                    setlist.id = cur.lastrowid
                else:
                    cur.execute(
                        "UPDATE setlists SET name=%s WHERE id=%s",
                        (setlist.name, setlist.id),
                    )
                    cur.execute(
                        "DELETE FROM setlist_songs WHERE setlist_id=%s", (setlist.id,)
                    )

                for pos, item in enumerate(setlist.items):
                    cur.execute(
                        "INSERT INTO setlist_songs "
                        "(setlist_id, song_id, position, transpose) "
                        "VALUES (%s, %s, %s, %s)",
                        (setlist.id, item.song_id, pos, item.transpose),
                    )
                    item.position = pos
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return setlist.id  # type: ignore[return-value]

    def load_setlist(self, setlist_id: int) -> Setlist:
        """Carga una lista con sus canciones (título y tono de cada una)."""
        conn = self._connect()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT id, name FROM setlists WHERE id=%s", (setlist_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"No existe la lista con id={setlist_id}")

            setlist = Setlist(id=row["id"], name=row["name"])

            cur.execute(
                "SELECT ss.id, ss.song_id, ss.position, ss.transpose, "
                "       so.title, so.`key` "
                "FROM setlist_songs ss "
                "JOIN songs so ON so.id = ss.song_id "
                "WHERE ss.setlist_id=%s ORDER BY ss.position",
                (setlist_id,),
            )
            for item_row in cur.fetchall():
                setlist.items.append(
                    SetlistItem(
                        id=item_row["id"],
                        song_id=item_row["song_id"],
                        position=item_row["position"],
                        transpose=item_row["transpose"] or 0,
                        title=item_row["title"],
                        key=item_row["key"],
                    )
                )
        return setlist

    def delete_setlist(self, setlist_id: int) -> None:
        """Elimina una lista y sus referencias a canciones (las canciones quedan)."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM setlists WHERE id=%s", (setlist_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
