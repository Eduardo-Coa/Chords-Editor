"""Pruebas de la migración de la carpeta de datos HymnChords -> Ilahi.

Todas usan carpetas temporales explícitas: nunca tocan %APPDATA% real.
"""

from __future__ import annotations

from database.config import migrate_legacy_data_dir


def _carpeta_vieja(tmp_path, con_respaldos: bool = True):
    """Crea una carpeta de datos al estilo HymnChords con contenido de ejemplo."""
    old = tmp_path / "HymnChords"
    old.mkdir()
    (old / "hymnchords.db").write_text("base", encoding="utf-8")
    (old / "hymnchords.log").write_text("log", encoding="utf-8")
    (old / "preferences.json").write_text('{"chord_color": "#ff8800"}', encoding="utf-8")
    if con_respaldos:
        backups = old / "backups"
        backups.mkdir()
        (backups / "hymnchords-20260101-120000.db").write_text("r1", encoding="utf-8")
        (backups / "hymnchords-20260102-120000.db").write_text("r2", encoding="utf-8")
    return old


def test_migra_y_renombra_archivos(tmp_path):
    old = _carpeta_vieja(tmp_path)
    new = tmp_path / "Ilahi"

    assert migrate_legacy_data_dir(new, old) is True
    assert not old.exists()
    assert (new / "ilahi.db").read_text(encoding="utf-8") == "base"
    assert (new / "ilahi.log").exists()
    assert not (new / "hymnchords.db").exists()


def test_migra_las_preferencias_sin_tocarlas(tmp_path):
    old = _carpeta_vieja(tmp_path)
    new = tmp_path / "Ilahi"
    migrate_legacy_data_dir(new, old)
    assert (new / "preferences.json").read_text(encoding="utf-8") == \
        '{"chord_color": "#ff8800"}'


def test_migra_los_respaldos_con_prefijo_nuevo(tmp_path):
    old = _carpeta_vieja(tmp_path)
    new = tmp_path / "Ilahi"
    migrate_legacy_data_dir(new, old)

    backups = sorted(p.name for p in (new / "backups").glob("*.db"))
    assert backups == ["ilahi-20260101-120000.db", "ilahi-20260102-120000.db"]


def test_no_pisa_una_carpeta_nueva_existente(tmp_path):
    """Si ya hay datos con el nombre nuevo, la migración no hace nada."""
    old = _carpeta_vieja(tmp_path)
    new = tmp_path / "Ilahi"
    new.mkdir()
    (new / "ilahi.db").write_text("base nueva", encoding="utf-8")

    assert migrate_legacy_data_dir(new, old) is False
    assert (new / "ilahi.db").read_text(encoding="utf-8") == "base nueva"
    assert old.exists()  # la vieja queda intacta


def test_sin_carpeta_vieja_no_hace_nada(tmp_path):
    new = tmp_path / "Ilahi"
    assert migrate_legacy_data_dir(new, tmp_path / "HymnChords") is False
    assert not new.exists()


def test_es_idempotente(tmp_path):
    """Llamarla dos veces no rompe ni vuelve a mover nada."""
    old = _carpeta_vieja(tmp_path)
    new = tmp_path / "Ilahi"

    assert migrate_legacy_data_dir(new, old) is True
    assert migrate_legacy_data_dir(new, old) is False
    assert (new / "ilahi.db").exists()


def test_migra_carpeta_sin_respaldos(tmp_path):
    old = _carpeta_vieja(tmp_path, con_respaldos=False)
    new = tmp_path / "Ilahi"
    assert migrate_legacy_data_dir(new, old) is True
    assert (new / "ilahi.db").exists()
