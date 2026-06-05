"""Carga la configuración de conexión MySQL desde el archivo .env."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DBConfig:
    """Parámetros de conexión a MySQL leídos del archivo .env."""

    host: str
    port: int
    user: str
    password: str
    database: str


def load_config(env_path: Path | None = None) -> DBConfig:
    """
    Lee el archivo .env y devuelve un DBConfig con las credenciales MySQL.

    Busca el .env en el directorio raíz del proyecto (dos niveles arriba de
    este archivo). Si no existe, lanza FileNotFoundError con instrucciones claras.
    """
    if env_path is None:
        env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        example = env_path.parent / ".env.example"
        raise FileNotFoundError(
            f"No se encontró el archivo de configuración: {env_path}\n"
            f"Copia '{example}' a '.env' y rellena tus credenciales MySQL."
        )

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()

    try:
        return DBConfig(
            host=values["DB_HOST"],
            port=int(values["DB_PORT"]),
            user=values["DB_USER"],
            password=values["DB_PASSWORD"],
            database=values["DB_NAME"],
        )
    except KeyError as e:
        raise KeyError(
            f"Falta la variable {e} en el archivo .env. "
            f"Revisa .env.example para ver todas las variables requeridas."
        ) from e
