"""Pruebas del backup automático de la BD y de la configuración de logging."""

from __future__ import annotations
from logging.handlers import RotatingFileHandler

from database.config import DBConfig
from database.db import Database, BACKUP_KEEP
from models.song import Song, Section, Line, Syllable, Chord
from utils.logging_setup import setup_logging


def _song(title: str = "X") -> Song:
    s = Song(id=None, title=title, key="C")
    sec = Section(id=None, position=0, type="verse", label=None)
    ln = Line(id=None, position=0)
    ln.syllables.append(
        Syllable(id=None, position=0, text="a", chord=Chord(id=None, value="C"))
    )
    sec.lines.append(ln)
    s.sections.append(sec)
    return s


def _backups(db_path) -> list:
    return sorted((db_path.parent / "backups").glob("hymnchords-*.db"))


def test_backup_crea_archivo(tmp_path):
    db = Database(DBConfig(path=tmp_path / "t.db"))
    db.init_schema()
    path = db.backup("test")
    assert path is not None and path.exists()
    assert len(_backups(tmp_path / "t.db")) == 1
    db.close()


def test_backup_conserva_contenido(tmp_path):
    """El backup es una copia funcional: se puede abrir y leer la canción."""
    db = Database(DBConfig(path=tmp_path / "t.db"))
    db.init_schema()
    sid = db.save_song(_song("Restaurable"))
    backup_path = db.backup("test")
    db.close()

    assert backup_path is not None
    restored = Database(DBConfig(path=backup_path))
    assert restored.load_song(sid).title == "Restaurable"
    restored.close()


def test_backup_rotacion(tmp_path):
    db = Database(DBConfig(path=tmp_path / "t.db"))
    db.init_schema()
    for _ in range(BACKUP_KEEP + 5):
        db.backup("loop")
    assert len(_backups(tmp_path / "t.db")) == BACKUP_KEEP
    db.close()


def test_delete_song_dispara_backup(tmp_path):
    db = Database(DBConfig(path=tmp_path / "t.db"))
    db.init_schema()
    sid = db.save_song(_song("Borrame"))
    assert _backups(tmp_path / "t.db") == []  # guardar no respalda
    db.delete_song(sid)
    assert len(_backups(tmp_path / "t.db")) == 1  # borrar sí
    db.close()


def test_setup_logging_idempotente(tmp_path):
    logger = setup_logging(log_dir=tmp_path)
    count1 = sum(isinstance(h, RotatingFileHandler) for h in logger.handlers)
    setup_logging(log_dir=tmp_path)
    count2 = sum(isinstance(h, RotatingFileHandler) for h in logger.handlers)
    try:
        assert count2 == count1  # no duplica el handler
        assert (tmp_path / "hymnchords.log").exists()
    finally:
        # Limpiar el handler que apunta al tmp para no contaminar otros tests.
        for h in list(logger.handlers):
            if isinstance(h, RotatingFileHandler) and str(tmp_path) in getattr(
                h, "baseFilename", ""
            ):
                logger.removeHandler(h)
                h.close()
