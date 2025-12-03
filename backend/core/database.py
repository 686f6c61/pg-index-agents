"""
PG Index Agents - Gestion de conexiones a bases de datos
https://github.com/686f6c61/pg-index-agents

Este modulo gestiona las conexiones a la base de datos PostgreSQL objetivo.
Implementa un patron de dos conexiones separadas: una de solo lectura para
analisis seguro y otra de escritura para ejecutar propuestas aprobadas.

El uso de conexiones separadas permite aplicar el principio de minimo privilegio,
donde las operaciones de analisis nunca pueden modificar datos accidentalmente.

Autor: 686f6c61
Licencia: MIT
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from .config import settings


class DatabaseManager:
    """
    Gestor de conexiones a bases de datos PostgreSQL.

    Esta clase implementa el patron lazy initialization para las conexiones,
    creandolas solo cuando se necesitan por primera vez. Mantiene pools de
    conexiones separados para operaciones de lectura y escritura.

    El pool de lectura esta dimensionado para soportar multiples agentes
    ejecutando analisis concurrentes. El pool de escritura es mas pequeno
    ya que las operaciones de modificacion son menos frecuentes y deben
    ser controladas.

    Attributes:
        _read_engine: Motor SQLAlchemy para operaciones de solo lectura.
        _write_engine: Motor SQLAlchemy para operaciones de escritura.
    """

    def __init__(self):
        """Inicializa el gestor sin conexiones activas."""
        self._read_engine: Engine | None = None
        self._write_engine: Engine | None = None

    @property
    def read_engine(self) -> Engine:
        """
        Obtiene o crea el motor de solo lectura.

        El motor se configura con pool_pre_ping para detectar conexiones
        muertas antes de usarlas. El tamano del pool (5 conexiones base,
        hasta 15 con overflow) permite analisis concurrentes.

        Returns:
            Motor SQLAlchemy configurado para lectura.
        """
        if self._read_engine is None:
            self._read_engine = create_engine(
                settings.pg_read_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )
        return self._read_engine

    @property
    def write_engine(self) -> Engine:
        """
        Obtiene o crea el motor de escritura.

        El pool de escritura es intencionalmente pequeno (2 conexiones base,
        hasta 7 con overflow) para limitar las operaciones concurrentes
        que modifican la base de datos.

        Returns:
            Motor SQLAlchemy configurado para escritura.
        """
        if self._write_engine is None:
            self._write_engine = create_engine(
                settings.pg_write_url,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=5
            )
        return self._write_engine

    @contextmanager
    def read_connection(self) -> Generator:
        """
        Context manager para operaciones de solo lectura.

        Proporciona una conexion del pool de lectura que se cierra
        automaticamente al salir del contexto. No realiza commit
        ya que no se esperan modificaciones.

        Yields:
            Conexion SQLAlchemy para ejecutar queries de lectura.

        Example:
            with db_manager.read_connection() as conn:
                result = conn.execute(text("SELECT * FROM pg_tables"))
        """
        conn = self.read_engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write_connection(self) -> Generator:
        """
        Context manager para operaciones de escritura.

        Proporciona una conexion del pool de escritura con manejo
        automatico de transacciones. Realiza commit si la operacion
        es exitosa o rollback si ocurre una excepcion.

        Yields:
            Conexion SQLAlchemy para ejecutar comandos DDL/DML.

        Raises:
            Exception: Cualquier error durante la operacion (despues del rollback).

        Example:
            with db_manager.write_connection() as conn:
                conn.execute(text("CREATE INDEX ..."))
        """
        conn = self.write_engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def test_connection(self) -> dict:
        """
        Verifica la conectividad con la base de datos.

        Intenta conectarse y obtener la version de PostgreSQL para
        confirmar que la configuracion es correcta.

        Returns:
            Diccionario con el estado de la conexion.
            En caso de exito: {"status": "connected", "version": "PostgreSQL ..."}
            En caso de error: {"status": "error", "error": "mensaje de error"}
        """
        try:
            with self.read_connection() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                return {"status": "connected", "version": version}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close(self):
        """
        Cierra todas las conexiones y libera recursos.

        Debe llamarse durante el apagado de la aplicacion para
        liberar correctamente las conexiones del pool.
        """
        if self._read_engine:
            self._read_engine.dispose()
            self._read_engine = None
        if self._write_engine:
            self._write_engine.dispose()
            self._write_engine = None


# Instancia global del gestor de base de datos
# Compartida por todos los modulos que necesitan acceso a PostgreSQL
db_manager = DatabaseManager()
