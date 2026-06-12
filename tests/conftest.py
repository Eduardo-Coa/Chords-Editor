"""Fixtures de pytest. Cada test usa un archivo SQLite temporal y aislado."""

from __future__ import annotations
import pytest

from database.config import DBConfig
from database.db import Database


@pytest.fixture
def db(tmp_path) -> Database:
    """Base de datos SQLite limpia en un archivo temporal, aislada de los datos reales.

    ``tmp_path`` es único por test y pytest lo elimina al terminar, así que nunca
    se toca la biblioteca real del usuario.
    """
    config = DBConfig(path=tmp_path / "hymnchords_test.db")
    database = Database(config)
    database.init_schema()
    yield database
    database.close()
