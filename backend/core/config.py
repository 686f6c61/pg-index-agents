"""
PG Index Agents - Configuracion centralizada
https://github.com/686f6c61/pg-index-agents

Este modulo gestiona la configuracion de la aplicacion mediante variables de entorno.
Utiliza Pydantic Settings para la validacion y carga automatica desde archivos .env.
La configuracion incluye credenciales de API, conexiones a bases de datos y parametros
del servidor.

Autor: 686f6c61
Licencia: MIT
"""

import sys
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    """
    Configuracion de la aplicacion cargada desde variables de entorno.

    Esta clase define todos los parametros configurables del sistema. Los valores
    se cargan automaticamente desde variables de entorno o desde un archivo .env
    ubicado en el directorio de trabajo.

    La configuracion se divide en cuatro secciones principales:
    - API de OpenRouter para acceso a modelos de lenguaje
    - Conexion de solo lectura a PostgreSQL (para analisis)
    - Conexion de escritura a PostgreSQL (para ejecutar propuestas)
    - Base de datos SQLite para estado interno

    Attributes:
        openrouter_api_key: Clave de API para OpenRouter. Requerida para funciones de IA.
        openrouter_base_url: URL base del servicio OpenRouter.
        llm_model: Identificador del modelo de lenguaje a utilizar.
        pg_target_host: Host de PostgreSQL. Puede ser ruta de socket Unix o direccion IP.
        pg_target_port: Puerto de PostgreSQL.
        pg_target_database: Nombre de la base de datos a analizar.
        pg_target_user: Usuario para conexion de solo lectura.
        pg_target_password: Contrasena para conexion de solo lectura.
        pg_target_write_user: Usuario para conexion de escritura (opcional).
        pg_target_write_password: Contrasena para conexion de escritura (opcional).
        sqlite_database_path: Ruta al archivo SQLite para estado interno.
        api_host: Direccion de escucha del servidor API.
        api_port: Puerto del servidor API.
    """

    # Configuracion de OpenRouter API
    # OpenRouter actua como gateway para acceder a diferentes modelos de lenguaje
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "moonshotai/kimi-k2"

    @field_validator('openrouter_api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """
        Valida que la clave de API este configurada.

        Si la clave esta vacia, emite una advertencia pero permite continuar.
        Esto permite ejecutar la aplicacion sin funciones de IA para pruebas.
        """
        if not v or v.strip() == "":
            print("WARNING: OPENROUTER_API_KEY not set. LLM features will not work.", file=sys.stderr)
        return v

    # Configuracion de PostgreSQL - Conexion de solo lectura
    # Estas credenciales se usan para analizar la estructura de la base de datos
    # sin riesgo de modificar datos accidentalmente
    pg_target_host: str = "/var/run/postgresql"
    pg_target_port: int = 5433
    pg_target_database: str = "stackexchange"
    pg_target_user: str = "r"
    pg_target_password: str = ""

    # Configuracion de PostgreSQL - Conexion de escritura
    # Credenciales opcionales para ejecutar comandos que modifican la base de datos
    # como CREATE INDEX o REINDEX. Si no se especifican, se usan las credenciales
    # de lectura (requiere que el usuario tenga permisos de escritura)
    pg_target_write_user: Optional[str] = None
    pg_target_write_password: Optional[str] = None

    # Base de datos SQLite para estado interno
    # Almacena analisis, propuestas, logs y configuracion de la aplicacion
    sqlite_database_path: str = "./state.db"

    # Configuracion del servidor API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        """Configuracion de Pydantic Settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def pg_read_url(self) -> str:
        """
        Construye la URL de conexion de solo lectura a PostgreSQL.

        Soporta tanto conexiones TCP/IP como sockets Unix. Las conexiones por socket
        se detectan automaticamente cuando pg_target_host comienza con '/'.

        Returns:
            URL de conexion en formato SQLAlchemy.
        """
        password_part = f":{self.pg_target_password}" if self.pg_target_password else ""
        # Las conexiones por socket Unix requieren un formato especial de URL
        if self.pg_target_host.startswith("/"):
            return (
                f"postgresql://{self.pg_target_user}{password_part}"
                f"@/{self.pg_target_database}?host={self.pg_target_host}&port={self.pg_target_port}"
            )
        return (
            f"postgresql://{self.pg_target_user}{password_part}"
            f"@{self.pg_target_host}:{self.pg_target_port}/{self.pg_target_database}"
        )

    @property
    def pg_write_url(self) -> str:
        """
        Construye la URL de conexion de escritura a PostgreSQL.

        Si no se han configurado credenciales de escritura especificas,
        utiliza las mismas credenciales que la conexion de lectura.

        Returns:
            URL de conexion en formato SQLAlchemy.
        """
        user = self.pg_target_write_user or self.pg_target_user
        password = self.pg_target_write_password or self.pg_target_password
        password_part = f":{password}" if password else ""
        if self.pg_target_host.startswith("/"):
            return (
                f"postgresql://{user}{password_part}"
                f"@/{self.pg_target_database}?host={self.pg_target_host}&port={self.pg_target_port}"
            )
        return (
            f"postgresql://{user}{password_part}"
            f"@{self.pg_target_host}:{self.pg_target_port}/{self.pg_target_database}"
        )


# Instancia global de configuracion
# Se carga automaticamente al importar el modulo
settings = Settings()


def validate_settings() -> list[str]:
    """
    Valida la configuracion critica durante el arranque de la aplicacion.

    Esta funcion verifica que los parametros esenciales esten configurados
    y devuelve una lista de advertencias para parametros faltantes o invalidos.
    No lanza excepciones, solo informa de problemas potenciales.

    Returns:
        Lista de mensajes de advertencia. Lista vacia si todo esta correcto.
    """
    warnings = []

    if not settings.openrouter_api_key:
        warnings.append("OPENROUTER_API_KEY not set - LLM features disabled")

    if not settings.pg_target_database:
        warnings.append("PG_TARGET_DATABASE not set - database connection will fail")

    return warnings
