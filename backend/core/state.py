"""
PG Index Agents - Base de datos de estado SQLite
https://github.com/686f6c61/pg-index-agents

Este modulo gestiona la persistencia del estado del sistema en una base de datos SQLite.
Se utiliza para almacenar analisis, senales, propuestas, logs y configuracion de forma
independiente a la base de datos PostgreSQL que se esta analizando.

El uso de SQLite permite mantener el sistema autocontenido y portable, sin requerir
infraestructura adicional. El esquema incluye las siguientes tablas:

- databases: Bases de datos registradas para monitoreo
- analyses: Resultados de analisis de los agentes
- signals: Senales detectadas por el Observer
- proposals: Propuestas de indices del Architect
- actions: Historial de acciones ejecutadas
- logs: Registro de actividad del sistema
- index_health: Estado de salud de indices (Gardener)
- jobs: Trabajos en segundo plano
- config: Configuracion del sistema

Autor: 686f6c61
Licencia: MIT
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from .config import settings


class StateDatabase:
    """
    Gestor de la base de datos SQLite para persistencia del sistema.

    Esta clase proporciona una interfaz para todas las operaciones de persistencia
    del sistema de agentes. Cada tipo de dato tiene metodos especificos para crear,
    leer, actualizar y eliminar registros.

    La base de datos se crea automaticamente al instanciar la clase si no existe.
    El esquema incluye indices apropiados para optimizar las consultas frecuentes.

    Attributes:
        db_path: Ruta al archivo SQLite.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Inicializa la conexion a la base de datos de estado.

        Args:
            db_path: Ruta al archivo SQLite. Si no se especifica, usa el valor
                    de settings.sqlite_database_path.
        """
        self.db_path = db_path or settings.sqlite_database_path
        self._ensure_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self):
        """Create database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Databases being monitored
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS databases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                database_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_analysis TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)

        # Analysis results from Explorer
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER NOT NULL,
                agent TEXT NOT NULL,
                analysis_type TEXT NOT NULL,
                result_json TEXT NOT NULL,
                result_markdown TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id)
            )
        """)

        # Signals detected by Observer
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER NOT NULL,
                signal_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                details_json TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',
                processed_at TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id)
            )
        """)

        # Proposals from Architect
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER NOT NULL,
                signal_id INTEGER,
                proposal_type TEXT NOT NULL,
                sql_command TEXT NOT NULL,
                justification TEXT NOT NULL,
                estimated_impact_json TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewed_by TEXT,
                executed_at TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id),
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        """)

        # Actions executed by any agent
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER NOT NULL,
                proposal_id INTEGER,
                agent TEXT NOT NULL,
                action_type TEXT NOT NULL,
                sql_command TEXT,
                result TEXT,
                success INTEGER NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER,
                FOREIGN KEY (database_id) REFERENCES databases(id),
                FOREIGN KEY (proposal_id) REFERENCES proposals(id)
            )
        """)

        # General log for all agent activities
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER,
                agent TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                details_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id)
            )
        """)

        # Index health tracking for Gardener
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS index_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER NOT NULL,
                schema_name TEXT NOT NULL,
                table_name TEXT NOT NULL,
                index_name TEXT NOT NULL,
                bloat_ratio REAL,
                last_used TIMESTAMP,
                usage_count INTEGER,
                size_bytes INTEGER,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                needs_maintenance INTEGER DEFAULT 0,
                scheduled_maintenance TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id),
                UNIQUE(database_id, schema_name, table_name, index_name)
            )
        """)

        # Background jobs tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                database_id INTEGER NOT NULL,
                agent TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                current_step TEXT,
                total_steps INTEGER DEFAULT 0,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error TEXT,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id)
            )
        """)

        # Configuration for autonomy levels and thresholds
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                database_id INTEGER,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (database_id) REFERENCES databases(id),
                UNIQUE(database_id, key)
            )
        """)

        conn.commit()
        conn.close()

    # Database management
    def register_database(self, name: str, host: str, port: int, database_name: str) -> int:
        """Register a new database to monitor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO databases (name, host, port, database_name) VALUES (?, ?, ?, ?)",
            (name, host, port, database_name)
        )
        conn.commit()
        db_id = cursor.lastrowid
        conn.close()
        return db_id

    def get_database(self, db_id: int) -> Optional[Dict]:
        """Get database by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM databases WHERE id = ?", (db_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_database_by_name(self, name: str) -> Optional[Dict]:
        """Get database by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM databases WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_databases(self) -> List[Dict]:
        """List all registered databases."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM databases ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Analysis management
    def save_analysis(self, database_id: int, agent: str, analysis_type: str,
                      result_json: Dict, result_markdown: Optional[str] = None) -> int:
        """Save an analysis result."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO analyses (database_id, agent, analysis_type, result_json, result_markdown)
               VALUES (?, ?, ?, ?, ?)""",
            (database_id, agent, analysis_type, json.dumps(result_json), result_markdown)
        )
        # Update last_analysis timestamp
        cursor.execute(
            "UPDATE databases SET last_analysis = CURRENT_TIMESTAMP WHERE id = ?",
            (database_id,)
        )
        conn.commit()
        analysis_id = cursor.lastrowid
        conn.close()
        return analysis_id

    def get_latest_analysis(self, database_id: int, agent: str = None) -> Optional[Dict]:
        """Get the most recent analysis for a database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if agent:
            cursor.execute(
                """SELECT * FROM analyses WHERE database_id = ? AND agent = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (database_id, agent)
            )
        else:
            cursor.execute(
                """SELECT * FROM analyses WHERE database_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (database_id,)
            )
        row = cursor.fetchone()
        conn.close()
        if row:
            result = dict(row)
            result['result_json'] = json.loads(result['result_json'])
            return result
        return None

    # Signal management
    def create_signal(self, database_id: int, signal_type: str, severity: str,
                      description: str, details: Optional[Dict] = None) -> int:
        """Create a new signal."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO signals (database_id, signal_type, severity, description, details_json)
               VALUES (?, ?, ?, ?, ?)""",
            (database_id, signal_type, severity, description,
             json.dumps(details) if details else None)
        )
        conn.commit()
        signal_id = cursor.lastrowid
        conn.close()
        return signal_id

    def get_pending_signals(self, database_id: int) -> List[Dict]:
        """Get unprocessed signals for a database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM signals WHERE database_id = ? AND status = 'new'
               ORDER BY severity DESC, detected_at ASC""",
            (database_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal = dict(row)
            # Parse details_json to extract table and other info
            if signal.get('details_json'):
                try:
                    details = json.loads(signal['details_json'])
                    signal['details'] = details
                    signal['table'] = details.get('table_name')
                except json.JSONDecodeError:
                    signal['details'] = {}
                    signal['table'] = None
            else:
                signal['details'] = {}
                signal['table'] = None
            signals.append(signal)

        return signals

    def get_all_signals(self, database_id: int, limit: int = 100) -> List[Dict]:
        """Get all signals for a database (including processed)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM signals WHERE database_id = ?
               ORDER BY detected_at DESC LIMIT ?""",
            (database_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal = dict(row)
            if signal.get('details_json'):
                try:
                    details = json.loads(signal['details_json'])
                    signal['details'] = details
                    signal['table'] = details.get('table_name')
                except json.JSONDecodeError:
                    signal['details'] = {}
                    signal['table'] = None
            else:
                signal['details'] = {}
                signal['table'] = None
            signals.append(signal)

        return signals

    # Proposal management
    def create_proposal(self, database_id: int, proposal_type: str, sql_command: str,
                        justification: str, estimated_impact: Optional[Dict] = None,
                        signal_id: Optional[int] = None) -> int:
        """Create a new proposal."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO proposals (database_id, signal_id, proposal_type, sql_command,
                                      justification, estimated_impact_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (database_id, signal_id, proposal_type, sql_command, justification,
             json.dumps(estimated_impact) if estimated_impact else None)
        )
        conn.commit()
        proposal_id = cursor.lastrowid
        conn.close()
        return proposal_id

    def get_pending_proposals(self, database_id: int) -> List[Dict]:
        """Get pending proposals for a database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM proposals WHERE database_id = ? AND status = 'pending'
               ORDER BY created_at ASC""",
            (database_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Logging
    def log(self, agent: str, level: str, message: str,
            database_id: Optional[int] = None, details: Optional[Dict] = None):
        """Add a log entry."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO logs (database_id, agent, level, message, details_json)
               VALUES (?, ?, ?, ?, ?)""",
            (database_id, agent, level, message, json.dumps(details) if details else None)
        )
        conn.commit()
        conn.close()

    def get_logs(self, database_id: Optional[int] = None, agent: Optional[str] = None,
                 limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get log entries with optional filters and pagination."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM logs WHERE 1=1"
        params = []

        if database_id:
            query += " AND database_id = ?"
            params.append(database_id)
        if agent:
            query += " AND agent = ?"
            params.append(agent)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Configuration management
    def set_config(self, key: str, value: str, database_id: Optional[int] = None):
        """Set a configuration value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO config (database_id, key, value, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(database_id, key) DO UPDATE SET
               value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
            (database_id, key, value)
        )
        conn.commit()
        conn.close()

    def get_config(self, key: str, database_id: Optional[int] = None, default: str = None) -> Optional[str]:
        """Get a configuration value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if database_id:
            cursor.execute(
                "SELECT value FROM config WHERE database_id = ? AND key = ?",
                (database_id, key)
            )
        else:
            cursor.execute(
                "SELECT value FROM config WHERE database_id IS NULL AND key = ?",
                (key,)
            )
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else default

    def get_all_config(self, database_id: Optional[int] = None) -> Dict[str, str]:
        """Get all configuration values for a database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if database_id:
            cursor.execute(
                "SELECT key, value FROM config WHERE database_id = ? OR database_id IS NULL",
                (database_id,)
            )
        else:
            cursor.execute("SELECT key, value FROM config WHERE database_id IS NULL")
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}

    # Autonomy level management
    def get_autonomy_level(self, database_id: Optional[int] = None) -> str:
        """
        Get the autonomy level for a database.

        Levels:
        - observation: Only observe and report, no actions
        - assisted: Propose actions, require human approval
        - trust: Execute low-risk actions automatically, approve high-risk
        - autonomous: Execute all actions automatically
        """
        return self.get_config('autonomy_level', database_id, default='assisted')

    def set_autonomy_level(self, level: str, database_id: Optional[int] = None):
        """Set the autonomy level for a database."""
        valid_levels = ['observation', 'assisted', 'trust', 'autonomous']
        if level not in valid_levels:
            raise ValueError(f"Invalid autonomy level. Must be one of: {valid_levels}")
        self.set_config('autonomy_level', level, database_id)

    def can_auto_execute(self, action_type: str, database_id: Optional[int] = None) -> bool:
        """
        Check if an action can be auto-executed based on autonomy level.

        Action types and their risk levels:
        - low_risk: SELECT queries, ANALYZE, adding indexes
        - medium_risk: REINDEX CONCURRENTLY, VACUUM
        - high_risk: DROP INDEX, schema changes
        """
        level = self.get_autonomy_level(database_id)

        if level == 'observation':
            return False
        elif level == 'assisted':
            return False
        elif level == 'trust':
            low_risk_actions = ['analyze', 'create_index', 'vacuum', 'reindex_concurrently']
            return action_type in low_risk_actions
        elif level == 'autonomous':
            return True
        return False

    # Proposal status updates
    def approve_proposal(self, proposal_id: int, reviewed_by: str = 'system') -> bool:
        """Approve a proposal."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE proposals SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP,
               reviewed_by = ? WHERE id = ? AND status = 'pending'""",
            (reviewed_by, proposal_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def reject_proposal(self, proposal_id: int, reviewed_by: str = 'system') -> bool:
        """Reject a proposal."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE proposals SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP,
               reviewed_by = ? WHERE id = ? AND status = 'pending'""",
            (reviewed_by, proposal_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def mark_proposal_executed(self, proposal_id: int) -> bool:
        """Mark a proposal as executed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE proposals SET status = 'executed', executed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (proposal_id,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def mark_signal_processed(self, signal_id: int) -> bool:
        """Mark a signal as processed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE signals SET status = 'processed', processed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (signal_id,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0


# Global state database instance
state_db = StateDatabase()
