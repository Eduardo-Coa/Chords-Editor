"""Fixtures de pytest. Toda operación destructiva se hace SOLO en la base de pruebas."""

from __future__ import annotations
import pytest

from database.config import load_config
from database.db import Database


def _assert_test_db(name: str) -> None:
    """Salvaguarda: aborta si la base no es claramente de pruebas."""
    if "test" not in name.lower():
        raise RuntimeError(
            f"SEGURIDAD: la base '{name}' no parece de pruebas. "
            "Los tests solo se ejecutan contra una base cuyo nombre contenga 'test'. "
            "Revisa DB_NAME_TEST en tu .env."
        )


def _clear_all_songs(db: Database) -> None:
    """Borra todas las canciones (seguro: ya se validó que es la base de pruebas)."""
    for song in db.list_songs():
        db.delete_song(song["id"])


@pytest.fixture
def db() -> Database:
    """Base de datos de pruebas limpia, aislada de los datos reales."""
    config = load_config(test=True)
    _assert_test_db(config.database)  # nunca tocar la base real

    database = Database(config)
    database.init_schema()
    _clear_all_songs(database)
    yield database
    _clear_all_songs(database)
    database.close()
