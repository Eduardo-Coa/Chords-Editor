"""Configuración del logging de HymnChords: archivo rotativo en la carpeta de datos.

El log vive en la carpeta de datos del usuario (la misma que la BD y las
preferencias), no junto al ``.exe``. Se configura una vez al arrancar.
"""

from __future__ import annotations
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from database.config import data_dir

LOGGER_NAME = "hymnchords"
_LOG_FILENAME = "hymnchords.log"


def setup_logging(
    level: int = logging.INFO, log_dir: Path | None = None
) -> logging.Logger:
    """Configura el logger 'hymnchords' con un archivo rotativo. Idempotente.

    Llamarlo más de una vez no duplica el handler. ``log_dir`` permite a los tests
    escribir en una carpeta temporal en vez de la carpeta de datos real.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    log_path = (log_dir or data_dir()) / _LOG_FILENAME
    target = os.path.abspath(str(log_path))

    already = any(getattr(h, "baseFilename", None) == target for h in logger.handlers)
    if not already:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger
