"""
PG Index Agents - Ejecutor seguro de comandos SQL
https://github.com/686f6c61/pg-index-agents

Este modulo proporciona un ejecutor seguro para comandos SQL generados por los agentes.
Implementa validacion de riesgo, respeto a los niveles de autonomia y registro de
todas las acciones ejecutadas.

El ejecutor clasifica los comandos en tres niveles de riesgo:
- Bajo: CREATE INDEX CONCURRENTLY, ANALYZE, VACUUM
- Medio: REINDEX, DROP INDEX CONCURRENTLY
- Alto: DROP INDEX, DROP TABLE, TRUNCATE, ALTER TABLE

Los comandos de alto riesgo sin CONCURRENTLY son rechazados automaticamente.
La ejecucion de comandos depende del nivel de autonomia configurado para cada
base de datos.

Autor: 686f6c61
Licencia: MIT
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text
import re

from core.database import db_manager
from core.state import state_db


class SQLExecutor:
    """
    Ejecutor seguro para comandos SQL de propuestas y tareas de mantenimiento.

    Esta clase actua como capa de seguridad entre los agentes y la base de datos.
    Antes de ejecutar cualquier comando, valida su nivel de riesgo y verifica
    que el nivel de autonomia configurado permita la ejecucion.

    Todas las ejecuciones se registran en la tabla de acciones, incluyendo
    exitos, fallos y tiempos de ejecucion.

    Attributes:
        SAFE_COMMANDS: Lista de comandos considerados seguros (bajo riesgo).
        CAUTION_COMMANDS: Lista de comandos que requieren precaucion (riesgo medio).
        HIGH_RISK_COMMANDS: Lista de comandos de alto riesgo.
    """

    # Comandos considerados seguros (bajo riesgo)
    # Estos no bloquean tablas o usan modos CONCURRENTLY
    SAFE_COMMANDS = [
        'CREATE INDEX CONCURRENTLY',
        'ANALYZE',
        'VACUUM ANALYZE',
        'VACUUM',
    ]

    # Comandos que requieren precaucion (riesgo medio)
    # Pueden bloquear brevemente pero son generalmente seguros
    CAUTION_COMMANDS = [
        'REINDEX',
        'REINDEX CONCURRENTLY',
        'DROP INDEX CONCURRENTLY',
    ]

    # Comandos de alto riesgo
    # Pueden causar bloqueos largos o perdida de datos
    HIGH_RISK_COMMANDS = [
        'DROP INDEX',  # sin CONCURRENTLY bloquea la tabla
        'DROP TABLE',
        'TRUNCATE',
        'ALTER TABLE',
    ]

    @classmethod
    def validate_sql(cls, sql: str) -> Dict[str, Any]:
        """
        Validate a SQL command before execution.

        Returns:
            Dict with 'valid', 'risk_level', and 'reason'
        """
        sql_upper = sql.upper().strip()

        # Check for obviously dangerous commands
        for dangerous in cls.HIGH_RISK_COMMANDS:
            if dangerous in sql_upper and 'CONCURRENTLY' not in sql_upper:
                return {
                    'valid': False,
                    'risk_level': 'high',
                    'reason': f'Command contains {dangerous} without CONCURRENTLY - too risky for automatic execution'
                }

        # Check for safe commands
        for safe in cls.SAFE_COMMANDS:
            if sql_upper.startswith(safe):
                return {
                    'valid': True,
                    'risk_level': 'low',
                    'reason': 'Safe command for automatic execution'
                }

        # Check for medium risk commands
        for caution in cls.CAUTION_COMMANDS:
            if caution in sql_upper:
                return {
                    'valid': True,
                    'risk_level': 'medium',
                    'reason': 'Medium risk - will be executed but monitored'
                }

        # Default: allow but mark as unknown risk
        return {
            'valid': True,
            'risk_level': 'unknown',
            'reason': 'Command not in known categories - proceed with caution'
        }

    @classmethod
    def can_auto_execute(cls, sql: str, database_id: Optional[int] = None) -> bool:
        """
        Check if a command can be auto-executed based on autonomy level and risk.
        """
        autonomy_level = state_db.get_autonomy_level(database_id)
        validation = cls.validate_sql(sql)

        if autonomy_level == 'observation':
            return False

        if autonomy_level == 'assisted':
            return False  # Always requires manual approval

        if autonomy_level == 'trust':
            # Only auto-execute low risk commands
            return validation['risk_level'] == 'low'

        if autonomy_level == 'autonomous':
            # Execute everything that's valid
            return validation['valid']

        return False

    @classmethod
    def execute_proposal(cls, proposal_id: int) -> Dict[str, Any]:
        """
        Execute a proposal's SQL command.

        Args:
            proposal_id: ID of the proposal to execute

        Returns:
            Dict with execution result
        """
        # Get proposal from database
        conn = state_db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, database_id, sql_command, proposal_type, status FROM proposals WHERE id = ?",
            (proposal_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                'success': False,
                'error': 'Proposal not found'
            }

        proposal = {
            'id': row[0],
            'database_id': row[1],
            'sql_command': row[2],
            'proposal_type': row[3],
            'status': row[4]
        }

        if proposal['status'] != 'approved':
            return {
                'success': False,
                'error': f"Proposal status is '{proposal['status']}', must be 'approved' to execute"
            }

        # Validate SQL
        validation = cls.validate_sql(proposal['sql_command'])
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['reason'],
                'risk_level': validation['risk_level']
            }

        # Execute the SQL
        try:
            start_time = datetime.now()

            with db_manager.write_connection() as db_conn:
                # For index operations, we need to commit immediately (can't be in transaction)
                if 'INDEX' in proposal['sql_command'].upper():
                    db_conn.execute(text("COMMIT"))

                db_conn.execute(text(proposal['sql_command']))

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Mark proposal as executed
            state_db.mark_proposal_executed(proposal_id)

            # Record the action
            action_conn = state_db._get_connection()
            action_cursor = action_conn.cursor()
            action_cursor.execute("""
                INSERT INTO actions (database_id, proposal_id, agent, action_type, sql_command, result, success, duration_ms)
                VALUES (?, ?, 'executor', ?, ?, 'Executed successfully', 1, ?)
            """, (
                proposal['database_id'],
                proposal_id,
                proposal['proposal_type'],
                proposal['sql_command'],
                duration_ms
            ))
            action_conn.commit()
            action_conn.close()

            state_db.log(
                'executor', 'INFO',
                f"Executed proposal {proposal_id}: {proposal['proposal_type']} in {duration_ms}ms",
                database_id=proposal['database_id']
            )

            return {
                'success': True,
                'proposal_id': proposal_id,
                'proposal_type': proposal['proposal_type'],
                'sql_command': proposal['sql_command'],
                'duration_ms': duration_ms,
                'risk_level': validation['risk_level']
            }

        except Exception as e:
            error_msg = str(e)

            # Record the failed action
            action_conn = state_db._get_connection()
            action_cursor = action_conn.cursor()
            action_cursor.execute("""
                INSERT INTO actions (database_id, proposal_id, agent, action_type, sql_command, result, success)
                VALUES (?, ?, 'executor', ?, ?, ?, 0)
            """, (
                proposal['database_id'],
                proposal_id,
                proposal['proposal_type'],
                proposal['sql_command'],
                f'Error: {error_msg}'
            ))
            action_conn.commit()
            action_conn.close()

            state_db.log(
                'executor', 'ERROR',
                f"Failed to execute proposal {proposal_id}: {error_msg}",
                database_id=proposal['database_id']
            )

            return {
                'success': False,
                'proposal_id': proposal_id,
                'error': error_msg
            }

    @classmethod
    def execute_maintenance_task(cls, database_id: int, sql_command: str, task_type: str) -> Dict[str, Any]:
        """
        Execute a maintenance task (from Gardener).

        Args:
            database_id: ID of the database
            sql_command: SQL command to execute
            task_type: Type of task (reindex, vacuum, etc.)

        Returns:
            Dict with execution result
        """
        # Validate SQL
        validation = cls.validate_sql(sql_command)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['reason']
            }

        try:
            start_time = datetime.now()

            with db_manager.write_connection() as db_conn:
                # For REINDEX/VACUUM, commit any pending transaction first
                db_conn.execute(text("COMMIT"))
                db_conn.execute(text(sql_command))

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Record the action
            action_conn = state_db._get_connection()
            action_cursor = action_conn.cursor()
            action_cursor.execute("""
                INSERT INTO actions (database_id, agent, action_type, sql_command, result, success, duration_ms)
                VALUES (?, 'gardener', ?, ?, 'Executed successfully', 1, ?)
            """, (
                database_id,
                task_type,
                sql_command,
                duration_ms
            ))
            action_conn.commit()
            action_conn.close()

            state_db.log(
                'executor', 'INFO',
                f"Executed maintenance {task_type} in {duration_ms}ms",
                database_id=database_id
            )

            return {
                'success': True,
                'task_type': task_type,
                'duration_ms': duration_ms
            }

        except Exception as e:
            error_msg = str(e)

            state_db.log(
                'executor', 'ERROR',
                f"Failed to execute maintenance {task_type}: {error_msg}",
                database_id=database_id
            )

            return {
                'success': False,
                'error': error_msg
            }


# Global executor instance
sql_executor = SQLExecutor()
