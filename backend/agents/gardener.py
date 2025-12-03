"""
PG Index Agents - Agente Gardener
https://github.com/686f6c61/pg-index-agents

El agente Gardener mantiene la salud de los indices existentes. Se encarga
del mantenimiento proactivo para evitar degradacion del rendimiento por
bloat, fragmentacion o indices sin uso.

Funciones principales:
1. Monitorear salud de indices (bloat, fragmentacion)
2. Detectar indices sin uso (zombie indexes)
3. Programar tareas de mantenimiento (REINDEX, VACUUM)
4. Adoptar nuevos indices para monitoreo continuo
5. Proponer eliminacion de indices cuando corresponda

El Gardener calcula el bloat de indices usando estadisticas de PostgreSQL
y detecta indices que no han sido utilizados en un periodo configurable.
Las tareas de mantenimiento se priorizan por impacto potencial.

Umbrales configurables:
- BLOAT_THRESHOLD: Ratio minimo para considerar reindex (default: 0.3)
- UNUSED_DAYS: Dias sin uso para considerar un indice zombie (default: 30)

Autor: 686f6c61
Licencia: MIT
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text
import json

from core.database import db_manager
from core.state import state_db
from core.llm import get_llm_for_analysis


class IndexHealth(TypedDict):
    """Health status of an index."""
    index_name: str
    table_name: str
    size_bytes: int
    estimated_bloat_ratio: float
    last_used: Optional[str]
    usage_count: int
    needs_maintenance: bool
    maintenance_reason: Optional[str]


class MaintenanceTask(TypedDict):
    """A maintenance task to be executed."""
    task_type: str  # reindex, vacuum, drop_index
    table_name: str
    index_name: Optional[str]
    sql_command: str
    priority: str  # high, medium, low
    reason: str
    estimated_duration: str


class GardenerState(TypedDict):
    """State for the Gardener agent workflow."""
    database_id: int
    index_health: List[IndexHealth]
    maintenance_tasks: List[MaintenanceTask]
    llm_analysis: Optional[str]
    error: Optional[str]


def calculate_index_bloat(state: GardenerState) -> GardenerState:
    """Calculate bloat ratio for all indexes."""
    if state.get("error"):
        return state

    try:
        with db_manager.read_connection() as conn:
            # Get index statistics and estimate bloat
            # This is a simplified bloat estimation
            result = conn.execute(text("""
                WITH index_stats AS (
                    SELECT
                        schemaname,
                        relname as tablename,
                        indexrelname as indexname,
                        pg_relation_size(indexrelid) as index_size,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes
                    WHERE schemaname = 'public'
                ),
                table_stats AS (
                    SELECT
                        schemaname,
                        relname as tablename,
                        n_live_tup,
                        n_dead_tup
                    FROM pg_stat_user_tables
                    WHERE schemaname = 'public'
                )
                SELECT
                    i.indexname,
                    i.tablename,
                    i.index_size,
                    i.idx_scan,
                    COALESCE(t.n_dead_tup, 0) as dead_tuples,
                    COALESCE(t.n_live_tup, 0) as live_tuples
                FROM index_stats i
                LEFT JOIN table_stats t ON i.tablename = t.tablename
                ORDER BY i.index_size DESC
            """))

            index_health = []
            for row in result:
                index_name = row[0]
                table_name = row[1]
                size_bytes = row[2] or 0
                idx_scan = row[3] or 0
                dead_tuples = row[4] or 0
                live_tuples = row[5] or 0

                # Estimate bloat based on dead tuple ratio
                # This is a simplified heuristic; real bloat detection is more complex
                total_tuples = live_tuples + dead_tuples
                bloat_ratio = dead_tuples / total_tuples if total_tuples > 0 else 0

                # Determine if maintenance is needed
                needs_maintenance = False
                maintenance_reason = None

                if bloat_ratio > 0.2:  # More than 20% bloat
                    needs_maintenance = True
                    maintenance_reason = f"High bloat ratio: {bloat_ratio*100:.1f}%"
                elif idx_scan == 0 and size_bytes > 1024 * 1024:  # Unused and > 1MB
                    needs_maintenance = True
                    maintenance_reason = "Unused index consuming space"

                index_health.append({
                    "index_name": index_name,
                    "table_name": table_name,
                    "size_bytes": size_bytes,
                    "estimated_bloat_ratio": bloat_ratio,
                    "last_used": None,  # Would need more tracking
                    "usage_count": idx_scan,
                    "needs_maintenance": needs_maintenance,
                    "maintenance_reason": maintenance_reason,
                })

            state_db.log("gardener", "INFO",
                        f"Analyzed health of {len(index_health)} indexes",
                        database_id=state["database_id"])

            return {**state, "index_health": index_health}

    except Exception as e:
        state_db.log("gardener", "ERROR", f"Failed to calculate index bloat: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def identify_maintenance_tasks(state: GardenerState) -> GardenerState:
    """Identify maintenance tasks based on index health."""
    if state.get("error"):
        return state

    tasks: List[MaintenanceTask] = []

    for index in state["index_health"]:
        if not index["needs_maintenance"]:
            continue

        # High bloat - suggest REINDEX
        if index["estimated_bloat_ratio"] > 0.2:
            priority = "high" if index["estimated_bloat_ratio"] > 0.4 else "medium"

            tasks.append({
                "task_type": "reindex",
                "table_name": index["table_name"],
                "index_name": index["index_name"],
                "sql_command": f"REINDEX INDEX CONCURRENTLY {index['index_name']}",
                "priority": priority,
                "reason": f"Index bloat at {index['estimated_bloat_ratio']*100:.1f}%. "
                         f"Rebuilding will reclaim space and improve scan performance.",
                "estimated_duration": "varies by index size",
            })

        # Unused index - suggest review/drop
        elif index["usage_count"] == 0 and index["size_bytes"] > 1024 * 1024:
            tasks.append({
                "task_type": "review_index",
                "table_name": index["table_name"],
                "index_name": index["index_name"],
                "sql_command": f"-- Review and potentially: DROP INDEX CONCURRENTLY {index['index_name']}",
                "priority": "low",
                "reason": f"Index has 0 scans but uses {index['size_bytes'] / 1024 / 1024:.1f}MB. "
                         f"Consider dropping if not needed for constraints or rare queries.",
                "estimated_duration": "instant",
            })

    # Check for tables that need VACUUM
    try:
        with db_manager.read_connection() as conn:
            result = conn.execute(text("""
                SELECT
                    relname,
                    n_dead_tup,
                    n_live_tup,
                    last_autovacuum,
                    last_vacuum
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND n_dead_tup > 10000
                AND n_dead_tup > n_live_tup * 0.1
                ORDER BY n_dead_tup DESC
                LIMIT 10
            """))

            for row in result:
                table_name = row[0]
                dead_tuples = row[1]
                live_tuples = row[2]

                tasks.append({
                    "task_type": "vacuum",
                    "table_name": table_name,
                    "index_name": None,
                    "sql_command": f"VACUUM ANALYZE {table_name}",
                    "priority": "medium",
                    "reason": f"Table has {dead_tuples:,} dead tuples ({dead_tuples/(live_tuples+1)*100:.1f}% of live). "
                             f"VACUUM will reclaim space and update statistics.",
                    "estimated_duration": "varies by table size",
                })

    except Exception as e:
        state_db.log("gardener", "WARNING", f"Could not check vacuum needs: {str(e)}",
                    database_id=state["database_id"])

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda x: priority_order.get(x["priority"], 3))

    state_db.log("gardener", "INFO",
                f"Identified {len(tasks)} maintenance tasks",
                database_id=state["database_id"])

    return {**state, "maintenance_tasks": tasks}


def analyze_maintenance_with_llm(state: GardenerState) -> GardenerState:
    """Use LLM to provide maintenance recommendations and priorities."""
    if state.get("error"):
        return state

    try:
        llm = get_llm_for_analysis()

        # Prepare index health summary
        indexes_needing_maintenance = [i for i in state["index_health"] if i["needs_maintenance"]]
        unused_indexes = [i for i in state["index_health"] if i["usage_count"] == 0]

        health_info = []
        for idx in state["index_health"][:20]:
            status = "NEEDS MAINTENANCE" if idx["needs_maintenance"] else "OK"
            health_info.append(
                f"  - {idx['index_name']} on {idx['table_name']}: "
                f"bloat={idx['estimated_bloat_ratio']*100:.1f}%, "
                f"scans={idx['usage_count']}, "
                f"size={idx['size_bytes']/1024/1024:.1f}MB [{status}]"
            )

        tasks_info = []
        for task in state["maintenance_tasks"]:
            tasks_info.append(
                f"  - [{task['priority'].upper()}] {task['task_type']}: {task['table_name']}"
                f"{'.'+task['index_name'] if task['index_name'] else ''}"
            )

        prompt = f"""Analiza el estado de mantenimiento de esta base de datos PostgreSQL y proporciona recomendaciones.

## Estado de Índices
Total: {len(state["index_health"])}
Necesitan mantenimiento: {len(indexes_needing_maintenance)}
Sin uso (0 scans): {len(unused_indexes)}

## Detalle de Índices
{chr(10).join(health_info) if health_info else 'No hay índices'}

## Tareas de Mantenimiento Identificadas
{chr(10).join(tasks_info) if tasks_info else 'No hay tareas pendientes'}

## Tu Análisis
1. **Estado general**: ¿Cómo está la salud de los índices en general?
2. **Prioridades**: ¿Qué tareas son más urgentes y por qué?
3. **Riesgos**: ¿Qué problemas podrían surgir si no se hace mantenimiento?
4. **Plan de acción**: Proporciona un orden específico para ejecutar las tareas
5. **Recomendaciones de programación**: ¿Cuándo ejecutar cada tipo de mantenimiento (horarios de bajo tráfico)?

Responde de forma práctica y orientada a la acción."""

        state_db.log("gardener", "INFO",
                    "Calling LLM for maintenance analysis...",
                    database_id=state["database_id"])

        response = llm.invoke([
            SystemMessage(content="""Eres un DBA especializado en mantenimiento preventivo de PostgreSQL.
Tu experiencia te permite priorizar tareas de mantenimiento segun su impacto real.
Siempre consideras el impacto en produccion y recomiendas horarios apropiados.

REGLAS DE FORMATO:
- NUNCA uses emojis
- NO uses formato markdown (##, **, -, ```)
- Escribe en parrafos claros
- Usa MAYUSCULAS para titulos de seccion
- Comandos SQL van entre corchetes: [VACUUM ANALYZE tabla]"""),
            HumanMessage(content=prompt)
        ])

        state_db.log("gardener", "INFO",
                    f"LLM maintenance analysis complete: {len(response.content)} chars",
                    database_id=state["database_id"])

        return {**state, "llm_analysis": response.content}

    except Exception as e:
        state_db.log("gardener", "WARNING",
                    f"LLM analysis failed (continuing): {str(e)}",
                    database_id=state["database_id"])
        return {**state, "llm_analysis": None}


def save_health_status(state: GardenerState) -> GardenerState:
    """Save index health status to database."""
    if state.get("error"):
        return state

    # Save as analysis
    result_json = {
        "index_health": state["index_health"],
        "maintenance_tasks": state["maintenance_tasks"],
        "llm_analysis": state.get("llm_analysis"),
        "summary": {
            "total_indexes": len(state["index_health"]),
            "indexes_needing_maintenance": len([i for i in state["index_health"] if i["needs_maintenance"]]),
            "total_tasks": len(state["maintenance_tasks"]),
            "high_priority_tasks": len([t for t in state["maintenance_tasks"] if t["priority"] == "high"]),
        },
        "checked_at": datetime.now().isoformat(),
    }

    # Generate markdown report with LLM analysis
    markdown_report = f"""# Gardener Maintenance Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Total indexes: {len(state["index_health"])}
- Indexes needing maintenance: {len([i for i in state["index_health"] if i["needs_maintenance"]])}
- Maintenance tasks: {len(state["maintenance_tasks"])}
- High priority tasks: {len([t for t in state["maintenance_tasks"] if t["priority"] == "high"])}

## AI Analysis
{state.get("llm_analysis", "No LLM analysis available")}

## Maintenance Tasks
"""
    for task in state["maintenance_tasks"]:
        markdown_report += f"- **[{task['priority'].upper()}]** {task['task_type']}: `{task['sql_command']}`\n"
        markdown_report += f"  - Reason: {task['reason']}\n"

    state_db.save_analysis(
        database_id=state["database_id"],
        agent="gardener",
        analysis_type="health_check",
        result_json=result_json,
        result_markdown=markdown_report,
    )

    # Update index_health table
    conn = state_db._get_connection()
    cursor = conn.cursor()

    for index in state["index_health"]:
        cursor.execute("""
            INSERT INTO index_health (
                database_id, schema_name, table_name, index_name,
                bloat_ratio, usage_count, size_bytes, needs_maintenance
            ) VALUES (?, 'public', ?, ?, ?, ?, ?, ?)
            ON CONFLICT (database_id, schema_name, table_name, index_name)
            DO UPDATE SET
                bloat_ratio = excluded.bloat_ratio,
                usage_count = excluded.usage_count,
                size_bytes = excluded.size_bytes,
                needs_maintenance = excluded.needs_maintenance,
                checked_at = CURRENT_TIMESTAMP
        """, (
            state["database_id"],
            index["table_name"],
            index["index_name"],
            index["estimated_bloat_ratio"],
            index["usage_count"],
            index["size_bytes"],
            1 if index["needs_maintenance"] else 0,
        ))

    conn.commit()
    conn.close()

    state_db.log("gardener", "INFO",
                "Health check complete and saved",
                database_id=state["database_id"])

    return state


def should_continue(state: GardenerState) -> str:
    """Determine if we should continue or end due to error."""
    if state.get("error"):
        return "error"
    return "continue"


def create_gardener_graph():
    """Create the Gardener agent workflow graph."""
    workflow = StateGraph(GardenerState)

    # Add nodes
    workflow.add_node("calculate_index_bloat", calculate_index_bloat)
    workflow.add_node("identify_maintenance_tasks", identify_maintenance_tasks)
    workflow.add_node("analyze_maintenance_with_llm", analyze_maintenance_with_llm)
    workflow.add_node("save_health_status", save_health_status)

    # Set entry point
    workflow.set_entry_point("calculate_index_bloat")

    # Add edges
    workflow.add_conditional_edges(
        "calculate_index_bloat",
        should_continue,
        {"continue": "identify_maintenance_tasks", "error": END}
    )
    workflow.add_edge("identify_maintenance_tasks", "analyze_maintenance_with_llm")
    workflow.add_edge("analyze_maintenance_with_llm", "save_health_status")
    workflow.add_edge("save_health_status", END)

    return workflow.compile()


async def run_gardener_agent(database_id: int) -> Dict[str, Any]:
    """
    Run the Gardener agent on a database.

    Args:
        database_id: ID of the database in the state DB

    Returns:
        Health check results including maintenance tasks
    """
    state_db.log("gardener", "INFO", f"Starting health check for database {database_id}")

    # Create initial state
    initial_state: GardenerState = {
        "database_id": database_id,
        "index_health": [],
        "maintenance_tasks": [],
        "llm_analysis": None,
        "error": None,
    }

    # Create and run the graph
    graph = create_gardener_graph()
    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        return {"error": final_state["error"]}

    return {
        "status": "success",
        "indexes_checked": len(final_state["index_health"]),
        "indexes_needing_maintenance": len([i for i in final_state["index_health"] if i["needs_maintenance"]]),
        "maintenance_tasks": final_state["maintenance_tasks"],
        "tasks_count": len(final_state["maintenance_tasks"]),
    }


async def execute_maintenance_task(database_id: int, task: MaintenanceTask) -> Dict[str, Any]:
    """
    Execute a maintenance task.

    Args:
        database_id: ID of the database
        task: The maintenance task to execute

    Returns:
        Execution result
    """
    if task["task_type"] == "review_index":
        # Review tasks don't execute automatically
        return {
            "status": "skipped",
            "reason": "Review tasks require manual approval",
        }

    try:
        with db_manager.write_connection() as conn:
            start_time = datetime.now()
            conn.execute(text(task["sql_command"]))
            duration = (datetime.now() - start_time).total_seconds()

            state_db.log("gardener", "INFO",
                        f"Executed {task['task_type']} on {task.get('index_name') or task['table_name']} "
                        f"in {duration:.2f}s",
                        database_id=database_id)

            return {
                "status": "success",
                "task_type": task["task_type"],
                "duration_seconds": duration,
            }

    except Exception as e:
        state_db.log("gardener", "ERROR",
                    f"Failed to execute {task['task_type']}: {str(e)}",
                    database_id=database_id)
        return {
            "status": "error",
            "error": str(e),
        }
