"""
PG Index Agents - Gestor de trabajos en segundo plano
https://github.com/686f6c61/pg-index-agents

Este modulo gestiona la ejecucion de agentes como trabajos en segundo plano.
Permite ejecutar analisis de larga duracion sin bloquear la API, proporcionando
seguimiento de progreso en tiempo real y almacenamiento de resultados.

El sistema de trabajos soporta:
- Creacion y seguimiento de trabajos por ID unico (UUID)
- Actualizacion de progreso por pasos del agente
- Cancelacion de trabajos en ejecucion
- Almacenamiento de resultados en SQLite
- Limpieza automatica de trabajos antiguos

Cada agente tiene definidos sus pasos de ejecucion para mostrar progreso
granular en la interfaz de usuario.

Autor: 686f6c61
Licencia: MIT
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import json

from core.state import state_db


class JobManager:
    """
    Gestor de trabajos en segundo plano para ejecucion de agentes.

    Esta clase coordina la ejecucion asincrona de agentes, permitiendo que
    multiples analisis se ejecuten en paralelo sin bloquear la API REST.
    Cada trabajo se identifica por un UUID unico y su estado se persiste
    en SQLite.

    El gestor mantiene un diccionario de tareas asyncio activas para permitir
    cancelacion y monitoreo de trabajos en ejecucion.

    Attributes:
        AGENT_STEPS: Diccionario con los pasos de cada agente para tracking.
        _running_jobs: Diccionario de tareas asyncio activas por job_id.
    """

    # Configuracion de pasos por agente para seguimiento de progreso
    # Estos pasos corresponden a las fases de ejecucion de cada agente
    AGENT_STEPS = {
        'explorer': [
            'extract_metadata',        # Extraccion de metadatos de PostgreSQL
            'build_dependency_graph',  # Construccion del grafo de dependencias
            'classify_tables',         # Clasificacion de tablas por criticidad
            'detect_anomalias',        # Deteccion de anomalias en indices
            'analyze_with_llm',        # Analisis con modelo de lenguaje
            'generate_work_plan',      # Generacion del plan de trabajo
            'generate_report',         # Generacion del reporte final
            'save_results'             # Guardado de resultados
        ],
        'observer': [
            'collect_query_metrics',   # Recoleccion de metricas de queries
            'collect_table_metrics',   # Recoleccion de metricas de tablas
            'collect_index_metrics',   # Recoleccion de metricas de indices
            'load_previous_metrics',   # Carga de metricas anteriores
            'analyze_metrics_with_llm', # Analisis de metricas con LLM
            'detect_signals',          # Deteccion de senales
            'save_results'             # Guardado de resultados
        ],
        'architect': [
            'analyze_query',           # Analisis de query problematica
            'get_existing_indexes',    # Obtencion de indices existentes
            'get_table_columns',       # Obtencion de columnas de tabla
            'analyze_with_llm',        # Analisis con LLM
            'generate_proposals',      # Generacion de propuestas
            'save_proposals'           # Guardado de propuestas
        ],
        'gardener': [
            'calculate_index_bloat',   # Calculo de bloat en indices
            'identify_maintenance_tasks', # Identificacion de tareas
            'analyze_maintenance_with_llm', # Analisis con LLM
            'save_health_status'       # Guardado de estado de salud
        ],
        'all': [
            'run_explorer',            # Ejecucion del Explorer
            'run_observer',            # Ejecucion del Observer
            'run_architect',           # Ejecucion del Architect
            'run_gardener',            # Ejecucion del Gardener
            'finalize_results'         # Finalizacion de resultados
        ]
    }

    def __init__(self):
        self._running_jobs: Dict[str, asyncio.Task] = {}

    def create_job(self, database_id: int, agent: str) -> str:
        """
        Create a new job record.

        Args:
            database_id: ID of the database
            agent: Name of the agent to run

        Returns:
            Job ID (UUID)
        """
        job_id = str(uuid.uuid4())
        steps = self.AGENT_STEPS.get(agent, [])

        conn = state_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (id, database_id, agent, status, progress, total_steps, created_at)
            VALUES (?, ?, ?, 'pending', 0, ?, CURRENT_TIMESTAMP)
        """, (job_id, database_id, agent, len(steps)))
        conn.commit()
        conn.close()

        state_db.log('jobs', 'INFO', f'Created job {job_id} for {agent}', database_id=database_id)

        return job_id

    def update_job(self, job_id: str, **kwargs):
        """
        Update job status.

        Possible kwargs:
        - status: 'pending', 'running', 'completed', 'failed', 'cancelled'
        - progress: 0-100
        - current_step: name of current step
        - error: error message if failed
        - result_json: JSON string of results
        """
        conn = state_db._get_connection()
        cursor = conn.cursor()

        updates = []
        values = []

        if 'status' in kwargs:
            updates.append('status = ?')
            values.append(kwargs['status'])

            if kwargs['status'] == 'running' and 'started_at' not in kwargs:
                updates.append('started_at = CURRENT_TIMESTAMP')
            elif kwargs['status'] in ('completed', 'failed', 'cancelled'):
                updates.append('completed_at = CURRENT_TIMESTAMP')

        if 'progress' in kwargs:
            updates.append('progress = ?')
            values.append(kwargs['progress'])

        if 'current_step' in kwargs:
            updates.append('current_step = ?')
            values.append(kwargs['current_step'])

        if 'error' in kwargs:
            updates.append('error = ?')
            values.append(kwargs['error'])

        if 'result_json' in kwargs:
            updates.append('result_json = ?')
            values.append(kwargs['result_json'])

        if updates:
            values.append(job_id)
            cursor.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

        conn.close()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status by ID."""
        conn = state_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'database_id': row[1],
            'agent': row[2],
            'status': row[3],
            'progress': row[4],
            'current_step': row[5],
            'total_steps': row[6],
            'started_at': row[7],
            'completed_at': row[8],
            'error': row[9],
            'result_json': json.loads(row[10]) if row[10] else None,
            'created_at': row[11]
        }

    def list_jobs(self, database_id: Optional[int] = None, status: Optional[str] = None,
                  limit: int = 50) -> list:
        """List jobs with optional filters."""
        conn = state_db._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if database_id:
            query += " AND database_id = ?"
            params.append(database_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        jobs = []
        for row in rows:
            jobs.append({
                'id': row[0],
                'database_id': row[1],
                'agent': row[2],
                'status': row[3],
                'progress': row[4],
                'current_step': row[5],
                'total_steps': row[6],
                'started_at': row[7],
                'completed_at': row[8],
                'error': row[9],
                'created_at': row[11]
            })

        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id in self._running_jobs:
            task = self._running_jobs[job_id]
            task.cancel()
            del self._running_jobs[job_id]
            self.update_job(job_id, status='cancelled')
            return True

        # Check if job exists and is pending
        job = self.get_job(job_id)
        if job and job['status'] == 'pending':
            self.update_job(job_id, status='cancelled')
            return True

        return False

    async def run_agent_job(self, job_id: str, agent_func: Callable[..., Awaitable[Dict[str, Any]]],
                           database_id: int, agent: str, **kwargs):
        """
        Run an agent as a background job.

        Args:
            job_id: Job ID to track
            agent_func: Async function to run
            database_id: Database ID
            agent: Agent name
            **kwargs: Additional arguments for the agent
        """
        self.update_job(job_id, status='running', current_step='initializing')

        try:
            # Run the agent
            result = await agent_func(database_id, **kwargs)

            # Store result
            self.update_job(
                job_id,
                status='completed',
                progress=100,
                current_step='done',
                result_json=json.dumps(result)
            )

            state_db.log('jobs', 'INFO', f'Job {job_id} completed successfully', database_id=database_id)

        except asyncio.CancelledError:
            self.update_job(job_id, status='cancelled', error='Job was cancelled')
            state_db.log('jobs', 'WARNING', f'Job {job_id} was cancelled', database_id=database_id)

        except Exception as e:
            error_msg = str(e)
            self.update_job(job_id, status='failed', error=error_msg)
            state_db.log('jobs', 'ERROR', f'Job {job_id} failed: {error_msg}', database_id=database_id)

        finally:
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]

    def start_agent_job(self, database_id: int, agent: str,
                       agent_func: Callable[..., Awaitable[Dict[str, Any]]],
                       **kwargs) -> str:
        """
        Start an agent as a background job.

        Args:
            database_id: Database ID
            agent: Agent name
            agent_func: Async function to run
            **kwargs: Additional arguments for the agent

        Returns:
            Job ID
        """
        job_id = self.create_job(database_id, agent)

        # Create and store the task
        task = asyncio.create_task(
            self.run_agent_job(job_id, agent_func, database_id, agent, **kwargs)
        )
        self._running_jobs[job_id] = task

        return job_id

    def get_running_jobs_count(self) -> int:
        """Get count of currently running jobs."""
        return len(self._running_jobs)

    def cleanup_old_jobs(self, days: int = 7):
        """Remove jobs older than specified days."""
        conn = state_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM jobs
            WHERE created_at < datetime('now', ? || ' days')
            AND status IN ('completed', 'failed', 'cancelled')
        """, (f'-{days}',))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            state_db.log('jobs', 'INFO', f'Cleaned up {deleted} old jobs')

        return deleted


# Global job manager instance
job_manager = JobManager()
