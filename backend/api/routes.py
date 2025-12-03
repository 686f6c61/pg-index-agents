"""
PG Index Agents - API Routes
https://github.com/686f6c61/pg-index-agents

Este modulo define todos los endpoints REST de la API del sistema. La API
permite gestionar bases de datos registradas, ejecutar agentes de analisis,
aprobar o rechazar propuestas de indices, y configurar niveles de autonomia.

Grupos de endpoints disponibles:

    Gestion de bases de datos:
        - GET/POST /databases - Listar y registrar bases de datos
        - GET /databases/{id} - Obtener detalles de una base de datos
        - GET /databases/{id}/metadata - Obtener metadatos PostgreSQL
        - GET /databases/{id}/queries - Estadisticas de pg_stat_statements
        - DELETE /databases/{id}/results - Limpiar resultados de analisis

    Ejecucion de agentes:
        - POST /databases/{id}/analyze/explorer - Analisis inicial
        - POST /databases/{id}/analyze/observer - Monitoreo continuo
        - POST /databases/{id}/analyze/architect - Generacion de propuestas
        - POST /databases/{id}/analyze/gardener - Mantenimiento de indices
        - POST /databases/{id}/analyze/partitioner - Analisis de particionamiento
        - POST /databases/{id}/analyze/all - Ejecutar todos los agentes

    Gestion de propuestas:
        - GET /databases/{id}/proposals - Listar propuestas pendientes
        - POST /proposals/{id}/approve - Aprobar propuesta
        - POST /proposals/{id}/reject - Rechazar propuesta
        - POST /proposals/{id}/execute - Ejecutar propuesta aprobada

    Configuracion y logs:
        - GET/POST /config/autonomy - Nivel de autonomia
        - GET /logs - Consulta de logs del sistema
        - GET /jobs - Gestion de trabajos en background

Autor: 686f6c61
Licencia: MIT
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import json

from core.database import db_manager
from core.state import state_db
from core.background import job_manager
from services.metadata import metadata_extractor

logger = logging.getLogger(__name__)
router = APIRouter()


class APIError(Exception):
    """Custom API exception with status code and detail."""
    def __init__(self, status_code: int, detail: str, error_type: str = "api_error"):
        self.status_code = status_code
        self.detail = detail
        self.error_type = error_type
        super().__init__(detail)


def handle_db_not_found(db_id: int):
    """Raise consistent 404 for database not found."""
    logger.warning(f"Database not found: {db_id}")
    raise HTTPException(status_code=404, detail=f"Database with id {db_id} not found")


# Request/Response Models
class DatabaseRegister(BaseModel):
    name: str
    host: str = "localhost"
    port: int = 5432
    database_name: str


class DatabaseResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    database_name: str
    status: str
    created_at: str
    last_analysis: Optional[str] = None


# Database Management Endpoints
@router.get("/databases", response_model=List[DatabaseResponse])
async def list_databases():
    """List all registered databases."""
    return state_db.list_databases()


@router.post("/databases", response_model=DatabaseResponse)
async def register_database(db: DatabaseRegister):
    """Register a new database to monitor."""
    existing = state_db.get_database_by_name(db.name)
    if existing:
        raise HTTPException(status_code=400, detail="Database with this name already exists")

    db_id = state_db.register_database(
        name=db.name,
        host=db.host,
        port=db.port,
        database_name=db.database_name
    )

    state_db.log("api", "INFO", f"Registered new database: {db.name}", database_id=db_id)
    return state_db.get_database(db_id)


@router.get("/databases/{db_id}")
async def get_database(db_id: int):
    """Get database details."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")
    return db


# Metadata Endpoints
@router.get("/databases/{db_id}/metadata")
async def get_metadata(db_id: int, schema: str = "public"):
    """Get full metadata snapshot for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        snapshot = metadata_extractor.get_full_snapshot(schema)
        state_db.log("api", "INFO", f"Retrieved metadata for database {db_id}", database_id=db_id)
        return snapshot
    except Exception as e:
        state_db.log("api", "ERROR", f"Failed to retrieve metadata: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/databases/{db_id}/queries")
async def get_query_stats(db_id: int, limit: int = 100):
    """Get query statistics from pg_stat_statements."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        stats = metadata_extractor.get_query_statistics(limit)
        if not stats:
            return {"message": "pg_stat_statements not available", "queries": []}
        return {"queries": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Analysis Endpoints
@router.get("/databases/{db_id}/analyses")
async def get_analyses(db_id: int, agent: Optional[str] = None):
    """Get analysis history for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    analysis = state_db.get_latest_analysis(db_id, agent)
    if not analysis:
        return {"message": "No analyses found"}
    return analysis


@router.get("/databases/{db_id}/analyses/history")
async def get_analyses_history(db_id: int, agent: Optional[str] = None, limit: int = 20):
    """Get all historical analyses for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    conn = state_db._get_connection()
    cursor = conn.cursor()

    if agent:
        cursor.execute("""
            SELECT id, database_id, agent, analysis_type, created_at
            FROM analyses WHERE database_id = ? AND agent = ?
            ORDER BY created_at DESC LIMIT ?
        """, (db_id, agent, limit))
    else:
        cursor.execute("""
            SELECT id, database_id, agent, analysis_type, created_at
            FROM analyses WHERE database_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (db_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@router.get("/analyses/{analysis_id}")
async def get_analysis_by_id(analysis_id: int):
    """Get a specific analysis by ID."""
    conn = state_db._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result = dict(row)
    result['result_json'] = json.loads(result['result_json'])
    return result


@router.post("/databases/{db_id}/analyze/explorer")
async def run_explorer(db_id: int, background: bool = False):
    """
    Run the Explorer agent on a database.

    Args:
        db_id: Database ID
        background: If True, run in background and return job_id immediately
    """
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    from agents.explorer import run_explorer_agent

    if background:
        job_id = job_manager.start_agent_job(db_id, 'explorer', run_explorer_agent)
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Explorer agent started in background"
        }

    try:
        result = await run_explorer_agent(db_id)
        return result
    except Exception as e:
        state_db.log("explorer", "ERROR", f"Explorer failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_id}/analyze/observer")
async def run_observer(db_id: int, background: bool = False):
    """
    Run the Observer agent on a database.

    Args:
        db_id: Database ID
        background: If True, run in background and return job_id immediately
    """
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    from agents.observer import run_observer_agent

    if background:
        job_id = job_manager.start_agent_job(db_id, 'observer', run_observer_agent)
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Observer agent started in background"
        }

    try:
        result = await run_observer_agent(db_id)
        return result
    except Exception as e:
        state_db.log("observer", "ERROR", f"Observer failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_id}/analyze/architect")
async def run_architect(db_id: int, background: bool = False):
    """
    Run the Architect agent to process pending signals.

    Args:
        db_id: Database ID
        background: If True, run in background and return job_id immediately
    """
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    from agents.architect import process_pending_signals

    if background:
        job_id = job_manager.start_agent_job(db_id, 'architect', process_pending_signals)
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Architect agent started in background"
        }

    try:
        result = await process_pending_signals(db_id)
        return result
    except Exception as e:
        state_db.log("architect", "ERROR", f"Architect failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_id}/analyze/gardener")
async def run_gardener(db_id: int, background: bool = False):
    """
    Run the Gardener agent for index health check.

    Args:
        db_id: Database ID
        background: If True, run in background and return job_id immediately
    """
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    from agents.gardener import run_gardener_agent

    if background:
        job_id = job_manager.start_agent_job(db_id, 'gardener', run_gardener_agent)
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Gardener agent started in background"
        }

    try:
        result = await run_gardener_agent(db_id)
        return result
    except Exception as e:
        state_db.log("gardener", "ERROR", f"Gardener failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_id}/analyze/partitioner")
async def run_partitioner(db_id: int, background: bool = False):
    """
    Run the Partitioner agent for table partitioning analysis.

    This is a read-only advisory agent that analyzes large tables and
    recommends partitioning strategies. It never executes changes.

    Args:
        db_id: Database ID
        background: If True, run in background and return job_id immediately
    """
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    from agents.partitioner import run_partitioner_agent

    if background:
        job_id = job_manager.start_agent_job(db_id, 'partitioner', run_partitioner_agent)
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Partitioner agent started in background"
        }

    try:
        result = await run_partitioner_agent(db_id)
        return result
    except Exception as e:
        state_db.log("partitioner", "ERROR", f"Partitioner failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


async def _run_all_agents_task(database_id: int) -> dict:
    """Internal function to run all agents sequentially."""
    from agents.explorer import run_explorer_agent
    from agents.observer import run_observer_agent
    from agents.architect import process_pending_signals
    from agents.gardener import run_gardener_agent

    results = {}
    results["explorer"] = await run_explorer_agent(database_id)
    results["observer"] = await run_observer_agent(database_id)
    results["architect"] = await process_pending_signals(database_id)
    results["gardener"] = await run_gardener_agent(database_id)

    return {"status": "success", "results": results}


@router.post("/databases/{db_id}/analyze/all")
async def run_all_agents(db_id: int, background: bool = True):
    """
    Run all agents in sequence: Explorer -> Observer -> Architect -> Gardener.

    Args:
        db_id: Database ID
        background: If True (default), run in background and return job_id immediately
    """
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    if background:
        job_id = job_manager.start_agent_job(db_id, 'all', _run_all_agents_task)
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Full analysis started in background (Explorer -> Observer -> Architect -> Gardener)"
        }

    try:
        result = await _run_all_agents_task(db_id)
        return result
    except Exception as e:
        state_db.log("api", "ERROR", f"Full analysis failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))


# Signal Endpoints
@router.get("/databases/{db_id}/signals")
async def get_signals(db_id: int, include_processed: bool = True):
    """Get signals for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    if include_processed:
        return state_db.get_all_signals(db_id)
    return state_db.get_pending_signals(db_id)


# Proposal Endpoints
@router.get("/databases/{db_id}/proposals")
async def get_proposals(db_id: int):
    """Get pending proposals for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    return state_db.get_pending_proposals(db_id)


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, execute: bool = True):
    """
    Approve a proposal and optionally execute it.

    Args:
        proposal_id: ID of the proposal
        execute: If True, execute the SQL after approving (default True)
    """
    from core.executor import sql_executor

    # First, approve the proposal
    success = state_db.approve_proposal(proposal_id, reviewed_by='user')
    if not success:
        raise HTTPException(status_code=404, detail="Proposal not found or already processed")

    state_db.log("api", "INFO", f"Proposal {proposal_id} approved by user")

    if execute:
        # Execute the proposal
        result = sql_executor.execute_proposal(proposal_id)

        if result['success']:
            return {
                "status": "executed",
                "proposal_id": proposal_id,
                "duration_ms": result.get('duration_ms'),
                "message": f"Proposal executed successfully in {result.get('duration_ms', 0)}ms"
            }
        else:
            return {
                "status": "approved_but_failed",
                "proposal_id": proposal_id,
                "error": result.get('error'),
                "message": "Proposal was approved but execution failed"
            }
    else:
        return {
            "status": "approved",
            "proposal_id": proposal_id,
            "message": "Proposal approved, awaiting execution"
        }


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int):
    """Reject a proposal."""
    success = state_db.reject_proposal(proposal_id, reviewed_by='user')
    if success:
        state_db.log("api", "INFO", f"Proposal {proposal_id} rejected by user")
        return {"status": "rejected", "proposal_id": proposal_id}
    raise HTTPException(status_code=404, detail="Proposal not found or already processed")


@router.post("/proposals/{proposal_id}/execute")
async def execute_proposal(proposal_id: int):
    """Execute an already approved proposal."""
    from core.executor import sql_executor

    result = sql_executor.execute_proposal(proposal_id)

    if result['success']:
        return {
            "status": "executed",
            "proposal_id": proposal_id,
            "duration_ms": result.get('duration_ms'),
            "sql_command": result.get('sql_command'),
            "risk_level": result.get('risk_level')
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Execution failed')
        )


# Autonomy Configuration Endpoints
class AutonomyConfig(BaseModel):
    level: str


@router.get("/config/autonomy")
async def get_autonomy_level(db_id: Optional[int] = None):
    """Get the current autonomy level."""
    level = state_db.get_autonomy_level(db_id)
    return {
        "level": level,
        "database_id": db_id,
        "levels": {
            "observation": "Only observe and report, no actions",
            "assisted": "Propose actions, require human approval",
            "trust": "Execute low-risk actions automatically",
            "autonomous": "Execute all actions automatically"
        }
    }


@router.post("/config/autonomy")
async def set_autonomy_level(config: AutonomyConfig, db_id: Optional[int] = None):
    """Set the autonomy level."""
    try:
        state_db.set_autonomy_level(config.level, db_id)
        state_db.log("api", "INFO", f"Autonomy level set to '{config.level}'", database_id=db_id)
        return {"status": "success", "level": config.level, "database_id": db_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/databases/{db_id}/config")
async def get_database_config(db_id: int):
    """Get all configuration for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    config = state_db.get_all_config(db_id)
    autonomy_level = state_db.get_autonomy_level(db_id)

    return {
        "database_id": db_id,
        "autonomy_level": autonomy_level,
        "config": config
    }


@router.delete("/databases/{db_id}/results")
async def clear_database_results(db_id: int):
    """Clear all analysis results, signals, and proposals for a database."""
    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    conn = state_db._get_connection()
    cursor = conn.cursor()

    # Delete all related data
    cursor.execute("DELETE FROM analyses WHERE database_id = ?", (db_id,))
    analyses_deleted = cursor.rowcount

    cursor.execute("DELETE FROM signals WHERE database_id = ?", (db_id,))
    signals_deleted = cursor.rowcount

    cursor.execute("DELETE FROM proposals WHERE database_id = ?", (db_id,))
    proposals_deleted = cursor.rowcount

    cursor.execute("DELETE FROM index_health WHERE database_id = ?", (db_id,))
    health_deleted = cursor.rowcount

    cursor.execute("DELETE FROM logs WHERE database_id = ?", (db_id,))
    logs_deleted = cursor.rowcount

    # Reset last_analysis timestamp
    cursor.execute("UPDATE databases SET last_analysis = NULL WHERE id = ?", (db_id,))

    conn.commit()
    conn.close()

    state_db.log("api", "INFO", f"Cleared all results for database {db_id}")

    return {
        "status": "success",
        "deleted": {
            "analyses": analyses_deleted,
            "signals": signals_deleted,
            "proposals": proposals_deleted,
            "index_health": health_deleted,
            "logs": logs_deleted
        }
    }


# Log Endpoints
@router.get("/logs")
async def get_logs(
    db_id: Optional[int] = None,
    agent: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get system logs with pagination.

    Args:
        db_id: Filter by database ID
        agent: Filter by agent name
        limit: Maximum results to return (default 100)
        offset: Number of results to skip for pagination
    """
    logs = state_db.get_logs(database_id=db_id, agent=agent, limit=limit, offset=offset)
    return {
        "logs": logs,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(logs),
            "has_more": len(logs) == limit
        }
    }


# Connection Test
@router.get("/test-connection")
async def test_connection():
    """Test database connection."""
    return db_manager.test_connection()


# Job Management Endpoints
@router.get("/jobs")
async def list_jobs(db_id: Optional[int] = None, status: Optional[str] = None, limit: int = 50):
    """
    List background jobs.

    Args:
        db_id: Filter by database ID
        status: Filter by status (pending, running, completed, failed, cancelled)
        limit: Maximum number of jobs to return
    """
    return job_manager.list_jobs(database_id=db_id, status=status, limit=limit)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job status and details."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running or pending job."""
    success = job_manager.cancel_job(job_id)
    if success:
        return {"status": "cancelled", "job_id": job_id}
    raise HTTPException(status_code=400, detail="Job cannot be cancelled (not found or already completed)")


@router.get("/jobs/running/count")
async def get_running_jobs_count():
    """Get count of currently running jobs."""
    return {"running_jobs": job_manager.get_running_jobs_count()}


@router.post("/jobs/cleanup")
async def cleanup_old_jobs(days: int = 7):
    """Remove jobs older than specified days."""
    deleted = job_manager.cleanup_old_jobs(days)
    return {"status": "success", "deleted_jobs": deleted}


# AI Explanation Endpoints
class ExplainRequest(BaseModel):
    type: str  # "anomaly" | "signal" | "maintenance" | "proposal"
    data: dict
    database_id: int


@router.post("/explain")
async def explain_item(request: ExplainRequest):
    """
    Generate an AI-powered technical explanation for an item.

    Args:
        request: Contains type, data, and database_id

    Types:
        - anomaly: Explain a detected anomaly
        - signal: Explain a monitoring signal
        - maintenance: Explain a maintenance task
        - proposal: Explain an index proposal
    """
    from services.ai_explainer import (
        explain_anomaly,
        explain_signal,
        explain_maintenance_task,
        explain_proposal
    )

    # Get database context if available
    db_context = None
    if request.database_id:
        db = state_db.get_database(request.database_id)
        if db:
            db_context = {
                "name": db.get("name"),
                "host": db.get("host"),
                "database_name": db.get("database_name")
            }

    try:
        if request.type == "anomaly":
            explanation = await explain_anomaly(request.data, db_context)
        elif request.type == "signal":
            explanation = await explain_signal(request.data, db_context)
        elif request.type == "maintenance":
            explanation = await explain_maintenance_task(request.data, db_context)
        elif request.type == "proposal":
            explanation = await explain_proposal(request.data, db_context)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown type: {request.type}. Valid types: anomaly, signal, maintenance, proposal"
            )

        state_db.log("api", "INFO", f"Generated AI explanation for {request.type}", database_id=request.database_id)

        return {
            "status": "success",
            "type": request.type,
            "explanation": explanation
        }
    except Exception as e:
        state_db.log("api", "ERROR", f"AI explanation failed: {str(e)}", database_id=request.database_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_id}/report/summary")
async def generate_report_summary(db_id: int):
    """
    Generate an AI-powered executive summary of the database analysis.

    This aggregates all anomalies, signals, proposals, and maintenance tasks
    to produce a comprehensive summary.
    """
    from services.ai_explainer import generate_executive_summary

    db = state_db.get_database(db_id)
    if not db:
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        # Get all data for the summary
        analysis = state_db.get_latest_analysis(db_id, 'explorer')
        anomalies = []
        if analysis and 'result_json' in analysis:
            result = analysis['result_json']
            if isinstance(result, str):
                result = json.loads(result)
            anomalies = result.get('anomalies', [])

        signals = state_db.get_all_signals(db_id)
        proposals = state_db.get_pending_proposals(db_id)

        # Get maintenance tasks from gardener analysis
        gardener_analysis = state_db.get_latest_analysis(db_id, 'gardener')
        maintenance_tasks = []
        if gardener_analysis and 'result_json' in gardener_analysis:
            result = gardener_analysis['result_json']
            if isinstance(result, str):
                result = json.loads(result)
            maintenance_tasks = result.get('maintenance_tasks', [])

        db_context = {
            "name": db.get("name"),
            "host": db.get("host"),
            "database_name": db.get("database_name")
        }

        summary = await generate_executive_summary(
            anomalies=anomalies,
            signals=signals,
            proposals=proposals,
            maintenance_tasks=maintenance_tasks,
            db_context=db_context
        )

        state_db.log("api", "INFO", f"Generated executive summary for database {db_id}", database_id=db_id)

        return {
            "status": "success",
            "database_id": db_id,
            "summary": summary,
            "stats": {
                "anomalies_count": len(anomalies),
                "signals_count": len(signals),
                "proposals_count": len(proposals),
                "maintenance_count": len(maintenance_tasks)
            }
        }
    except Exception as e:
        state_db.log("api", "ERROR", f"Executive summary failed: {str(e)}", database_id=db_id)
        raise HTTPException(status_code=500, detail=str(e))
