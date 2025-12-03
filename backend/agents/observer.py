"""
PG Index Agents - Agente Observer
https://github.com/686f6c61/pg-index-agents

El agente Observer monitorea continuamente las metricas de rendimiento de
PostgreSQL y detecta senales que requieren atencion. Actua como el sistema
de alerta temprana del proyecto.

Funciones principales:
1. Recolectar metricas de pg_stat_statements, pg_stat_user_tables, pg_stat_user_indexes
2. Normalizar y agrupar queries por fingerprint (patron de query)
3. Calcular scores de impacto (frecuencia × tiempo medio de ejecucion)
4. Detectar tendencias y anomalias (degradacion, nuevas queries de alto impacto)
5. Generar senales priorizadas para el agente Architect

El Observer puede ejecutarse periodicamente para mantener un monitoreo continuo.
Las senales generadas incluyen informacion detallada sobre la query problematica,
las tablas involucradas y metricas de rendimiento.

Requisitos:
- Extension pg_stat_statements habilitada para metricas de queries
- Estadisticas de tablas e indices actualizadas (ANALYZE reciente)

Autor: 686f6c61
Licencia: MIT
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import re
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text
import json

from core.database import db_manager
from core.state import state_db
from core.llm import get_llm_for_analysis


class QueryMetrics(TypedDict):
    """Metrics for a single query fingerprint."""
    query_id: str
    fingerprint: str
    query_sample: str
    calls: int
    total_time_ms: float
    mean_time_ms: float
    rows: int
    impact_score: float
    tables: List[str]


class TableMetrics(TypedDict):
    """Metrics for a table."""
    table_name: str
    row_count: int
    dead_rows: int
    seq_scan: int
    idx_scan: int
    inserts: int
    updates: int
    deletes: int
    size_bytes: int


class IndexMetrics(TypedDict):
    """Metrics for an index."""
    index_name: str
    table_name: str
    idx_scan: int
    idx_tup_read: int
    idx_tup_fetch: int
    size_bytes: int


class Signal(TypedDict):
    """A detected signal that may require attention."""
    signal_type: str
    severity: str  # high, medium, low
    description: str
    details: Dict[str, Any]
    table: Optional[str]
    query_id: Optional[str]


class ObserverState(TypedDict):
    """State for the Observer agent workflow."""
    database_id: int
    query_metrics: List[QueryMetrics]
    table_metrics: List[TableMetrics]
    index_metrics: List[IndexMetrics]
    previous_metrics: Optional[Dict[str, Any]]
    signals: List[Signal]
    llm_analysis: Optional[str]
    error: Optional[str]


def normalize_query(query: str) -> str:
    """
    Normalize a query by removing literals to create a fingerprint.
    This groups queries like:
    - SELECT * FROM users WHERE id = 5
    - SELECT * FROM users WHERE id = 100
    Into the same fingerprint.
    """
    if not query:
        return ""

    # Remove string literals
    normalized = re.sub(r"'[^']*'", "'?'", query)
    # Remove numeric literals
    normalized = re.sub(r'\b\d+\b', '?', normalized)
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    # Lowercase
    normalized = normalized.lower()

    return normalized


def extract_tables_from_query(query: str) -> List[str]:
    """Extract table names from a SQL query (simple extraction)."""
    tables = []

    # FROM clause
    from_match = re.findall(r'\bfrom\s+([a-z_][a-z0-9_]*)', query.lower())
    tables.extend(from_match)

    # JOIN clauses
    join_match = re.findall(r'\bjoin\s+([a-z_][a-z0-9_]*)', query.lower())
    tables.extend(join_match)

    # UPDATE/INSERT/DELETE
    update_match = re.findall(r'\bupdate\s+([a-z_][a-z0-9_]*)', query.lower())
    tables.extend(update_match)

    insert_match = re.findall(r'\binsert\s+into\s+([a-z_][a-z0-9_]*)', query.lower())
    tables.extend(insert_match)

    delete_match = re.findall(r'\bdelete\s+from\s+([a-z_][a-z0-9_]*)', query.lower())
    tables.extend(delete_match)

    return list(set(tables))


def collect_query_metrics(state: ObserverState) -> ObserverState:
    """Collect query metrics from pg_stat_statements."""
    if state.get("error"):
        return state

    try:
        with db_manager.read_connection() as conn:
            # Check if pg_stat_statements is available
            check = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                )
            """))
            if not check.scalar():
                state_db.log("observer", "WARNING",
                           "pg_stat_statements not available",
                           database_id=state["database_id"])
                return {**state, "query_metrics": []}

            # Get query statistics
            result = conn.execute(text("""
                SELECT
                    queryid::text,
                    query,
                    calls,
                    total_exec_time as total_time_ms,
                    mean_exec_time as mean_time_ms,
                    rows
                FROM pg_stat_statements
                WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                AND query NOT LIKE '%pg_stat%'
                AND query NOT LIKE '%pg_catalog%'
                AND calls > 0
                ORDER BY total_exec_time DESC
                LIMIT 200
            """))

            metrics = []
            for row in result:
                query_id = row[0]
                query = row[1] or ""
                calls = row[2] or 0
                total_time = row[3] or 0
                mean_time = row[4] or 0
                rows = row[5] or 0

                fingerprint = normalize_query(query)
                tables = extract_tables_from_query(query)

                # Impact score: frequency × mean time (higher = more impact)
                impact_score = calls * mean_time

                metrics.append({
                    "query_id": query_id,
                    "fingerprint": hashlib.md5(fingerprint.encode()).hexdigest()[:12],
                    "query_sample": query[:500] if query else "",
                    "calls": calls,
                    "total_time_ms": total_time,
                    "mean_time_ms": mean_time,
                    "rows": rows,
                    "impact_score": impact_score,
                    "tables": tables,
                })

            state_db.log("observer", "INFO",
                        f"Collected metrics for {len(metrics)} queries",
                        database_id=state["database_id"])

            return {**state, "query_metrics": metrics}

    except Exception as e:
        state_db.log("observer", "ERROR", f"Failed to collect query metrics: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def collect_table_metrics(state: ObserverState) -> ObserverState:
    """Collect table metrics from pg_stat_user_tables."""
    if state.get("error"):
        return state

    try:
        with db_manager.read_connection() as conn:
            result = conn.execute(text("""
                SELECT
                    relname as table_name,
                    n_live_tup as row_count,
                    n_dead_tup as dead_rows,
                    seq_scan,
                    idx_scan,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) as size_bytes
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
            """))

            metrics = []
            for row in result:
                metrics.append({
                    "table_name": row[0],
                    "row_count": row[1] or 0,
                    "dead_rows": row[2] or 0,
                    "seq_scan": row[3] or 0,
                    "idx_scan": row[4] or 0,
                    "inserts": row[5] or 0,
                    "updates": row[6] or 0,
                    "deletes": row[7] or 0,
                    "size_bytes": row[8] or 0,
                })

            return {**state, "table_metrics": metrics}

    except Exception as e:
        state_db.log("observer", "ERROR", f"Failed to collect table metrics: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def collect_index_metrics(state: ObserverState) -> ObserverState:
    """Collect index metrics from pg_stat_user_indexes."""
    if state.get("error"):
        return state

    try:
        with db_manager.read_connection() as conn:
            result = conn.execute(text("""
                SELECT
                    indexrelname as index_name,
                    relname as table_name,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch,
                    pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(indexrelname)) as size_bytes
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
            """))

            metrics = []
            for row in result:
                metrics.append({
                    "index_name": row[0],
                    "table_name": row[1],
                    "idx_scan": row[2] or 0,
                    "idx_tup_read": row[3] or 0,
                    "idx_tup_fetch": row[4] or 0,
                    "size_bytes": row[5] or 0,
                })

            return {**state, "index_metrics": metrics}

    except Exception as e:
        state_db.log("observer", "ERROR", f"Failed to collect index metrics: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def load_previous_metrics(state: ObserverState) -> ObserverState:
    """Load previous metrics for comparison."""
    if state.get("error"):
        return state

    # Get the last analysis from the observer
    analysis = state_db.get_latest_analysis(state["database_id"], "observer")

    if analysis:
        return {**state, "previous_metrics": analysis.get("result_json", {})}

    return {**state, "previous_metrics": None}


def analyze_metrics_with_llm(state: ObserverState) -> ObserverState:
    """Use LLM to analyze metrics and identify patterns."""
    if state.get("error"):
        return state

    try:
        llm = get_llm_for_analysis()

        # Prepare top queries for analysis
        top_queries = sorted(state["query_metrics"], key=lambda x: x["impact_score"], reverse=True)[:10]
        queries_info = []
        for q in top_queries:
            queries_info.append(
                f"  - Impact: {q['impact_score']:.0f} | Calls: {q['calls']} | "
                f"Avg: {q['mean_time_ms']:.2f}ms | Tables: {', '.join(q['tables'])}"
            )

        # Prepare table metrics
        tables_info = []
        for t in state["table_metrics"][:15]:
            seq_ratio = t["seq_scan"] / (t["seq_scan"] + t["idx_scan"] + 1) * 100
            tables_info.append(
                f"  - {t['table_name']}: {t['row_count']:,} rows, "
                f"seq_scan={t['seq_scan']}, idx_scan={t['idx_scan']} ({seq_ratio:.0f}% seq), "
                f"dead_rows={t['dead_rows']}"
            )

        # Prepare unused indexes
        unused_indexes = [i for i in state["index_metrics"] if i["idx_scan"] == 0]
        unused_info = [f"  - {i['index_name']} on {i['table_name']} ({i['size_bytes']/1024/1024:.1f}MB)"
                      for i in unused_indexes[:10]]

        prompt = f"""Analiza estas métricas de rendimiento de PostgreSQL y proporciona un diagnóstico.

## Queries de Mayor Impacto (Top 10)
{chr(10).join(queries_info) if queries_info else 'No hay datos de queries'}

## Estadísticas de Tablas
{chr(10).join(tables_info) if tables_info else 'No hay datos'}

## Índices No Utilizados
{chr(10).join(unused_info) if unused_info else 'Todos los índices están en uso'}

## Tu Análisis
1. **Resumen ejecutivo**: En 2-3 frases, describe el estado general del rendimiento
2. **Patrones detectados**: Identifica patrones preocupantes en las queries o tablas
3. **Problemas prioritarios**: Lista los 3 problemas más urgentes a resolver
4. **Recomendaciones inmediatas**: Qué acciones tomar primero

Responde de forma clara y accionable, priorizando por impacto."""

        state_db.log("observer", "INFO",
                    "Calling LLM for metrics analysis...",
                    database_id=state["database_id"])

        response = llm.invoke([
            SystemMessage(content="""Eres un experto en monitoreo de rendimiento de PostgreSQL.
Analizas métricas para identificar problemas de rendimiento antes de que afecten a producción.
Das recomendaciones claras y priorizadas basadas en el impacto real."""),
            HumanMessage(content=prompt)
        ])

        state_db.log("observer", "INFO",
                    f"LLM metrics analysis complete: {len(response.content)} chars",
                    database_id=state["database_id"])

        return {**state, "llm_analysis": response.content}

    except Exception as e:
        state_db.log("observer", "WARNING",
                    f"LLM analysis failed (continuing): {str(e)}",
                    database_id=state["database_id"])
        return {**state, "llm_analysis": None}


def detect_signals(state: ObserverState) -> ObserverState:
    """Detect signals from collected metrics."""
    if state.get("error"):
        return state

    signals: List[Signal] = []

    # Signal 1: High-impact queries (top queries by impact score)
    high_impact_queries = sorted(
        state["query_metrics"],
        key=lambda x: x["impact_score"],
        reverse=True
    )[:10]

    for query in high_impact_queries:
        if query["impact_score"] > 100000:  # Threshold: 100 seconds total
            signals.append({
                "signal_type": "high_impact_query",
                "severity": "high" if query["impact_score"] > 1000000 else "medium",
                "description": f"High-impact query detected: {query['calls']} calls, {query['mean_time_ms']:.2f}ms avg",
                "details": {
                    "query_sample": query["query_sample"][:200],
                    "fingerprint": query["fingerprint"],
                    "calls": query["calls"],
                    "mean_time_ms": query["mean_time_ms"],
                    "total_time_ms": query["total_time_ms"],
                    "impact_score": query["impact_score"],
                },
                "table": query["tables"][0] if query["tables"] else None,
                "query_id": query["query_id"],
            })

    # Signal 2: Sequential scans on large tables
    for table in state["table_metrics"]:
        if table["row_count"] > 10000 and table["seq_scan"] > 100:
            # High seq_scan ratio
            total_scans = table["seq_scan"] + (table["idx_scan"] or 1)
            seq_ratio = table["seq_scan"] / total_scans

            if seq_ratio > 0.5:  # More than 50% sequential scans
                signals.append({
                    "signal_type": "high_sequential_scans",
                    "severity": "medium" if seq_ratio > 0.8 else "low",
                    "description": f"Table '{table['table_name']}' has {seq_ratio*100:.0f}% sequential scans ({table['seq_scan']} seq vs {table['idx_scan']} idx)",
                    "details": {
                        "row_count": table["row_count"],
                        "seq_scan": table["seq_scan"],
                        "idx_scan": table["idx_scan"],
                        "seq_ratio": seq_ratio,
                    },
                    "table": table["table_name"],
                    "query_id": None,
                })

    # Signal 3: Unused indexes (expensive to maintain)
    for index in state["index_metrics"]:
        if index["idx_scan"] == 0 and index["size_bytes"] > 1024 * 1024:  # > 1MB
            signals.append({
                "signal_type": "unused_index",
                "severity": "low",
                "description": f"Index '{index['index_name']}' on '{index['table_name']}' has 0 scans but uses {index['size_bytes'] / 1024 / 1024:.1f}MB",
                "details": {
                    "index_name": index["index_name"],
                    "table_name": index["table_name"],
                    "size_bytes": index["size_bytes"],
                },
                "table": index["table_name"],
                "query_id": None,
            })

    # Signal 4: Tables with high dead row ratio (need VACUUM)
    for table in state["table_metrics"]:
        if table["row_count"] > 1000:
            dead_ratio = table["dead_rows"] / (table["row_count"] + table["dead_rows"] + 1)
            if dead_ratio > 0.1:  # More than 10% dead rows
                signals.append({
                    "signal_type": "high_dead_rows",
                    "severity": "medium" if dead_ratio > 0.3 else "low",
                    "description": f"Table '{table['table_name']}' has {dead_ratio*100:.0f}% dead rows ({table['dead_rows']:,} dead / {table['row_count']:,} live)",
                    "details": {
                        "row_count": table["row_count"],
                        "dead_rows": table["dead_rows"],
                        "dead_ratio": dead_ratio,
                    },
                    "table": table["table_name"],
                    "query_id": None,
                })

    # Signal 5: Compare with previous metrics (trend detection)
    if state["previous_metrics"]:
        prev_queries = {q["fingerprint"]: q for q in state["previous_metrics"].get("query_metrics", [])}

        for query in state["query_metrics"]:
            prev = prev_queries.get(query["fingerprint"])
            if prev and prev["mean_time_ms"] > 0:
                # Check for degradation (mean time increased by more than 50%)
                degradation = (query["mean_time_ms"] - prev["mean_time_ms"]) / prev["mean_time_ms"]
                if degradation > 0.5 and query["mean_time_ms"] > 10:  # > 50% slower and > 10ms
                    signals.append({
                        "signal_type": "query_degradation",
                        "severity": "high" if degradation > 1.0 else "medium",
                        "description": f"Query degraded by {degradation*100:.0f}%: {prev['mean_time_ms']:.2f}ms → {query['mean_time_ms']:.2f}ms",
                        "details": {
                            "fingerprint": query["fingerprint"],
                            "query_sample": query["query_sample"][:200],
                            "previous_mean_ms": prev["mean_time_ms"],
                            "current_mean_ms": query["mean_time_ms"],
                            "degradation_percent": degradation * 100,
                        },
                        "table": query["tables"][0] if query["tables"] else None,
                        "query_id": query["query_id"],
                    })

    # Sort signals by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda x: severity_order.get(x["severity"], 3))

    state_db.log("observer", "INFO",
                f"Detected {len(signals)} signals",
                database_id=state["database_id"])

    return {**state, "signals": signals}


def save_results(state: ObserverState) -> ObserverState:
    """Save observation results and signals."""
    if state.get("error"):
        return state

    # Save metrics as analysis
    result_json = {
        "query_metrics": state["query_metrics"],
        "table_metrics": state["table_metrics"],
        "index_metrics": state["index_metrics"],
        "llm_analysis": state.get("llm_analysis"),
        "signals_summary": {
            "total": len(state["signals"]),
            "high": len([s for s in state["signals"] if s["severity"] == "high"]),
            "medium": len([s for s in state["signals"] if s["severity"] == "medium"]),
            "low": len([s for s in state["signals"] if s["severity"] == "low"]),
        },
        "collected_at": datetime.now().isoformat(),
    }

    # Generate markdown report with LLM analysis
    markdown_report = f"""# Observer Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Metrics Summary
- Queries analyzed: {len(state["query_metrics"])}
- Tables monitored: {len(state["table_metrics"])}
- Indexes tracked: {len(state["index_metrics"])}
- Signals detected: {len(state["signals"])}

## AI Analysis
{state.get("llm_analysis", "No LLM analysis available")}

## Detected Signals
"""
    for signal in state["signals"][:10]:
        markdown_report += f"- **[{signal['severity'].upper()}]** {signal['description']}\n"

    state_db.save_analysis(
        database_id=state["database_id"],
        agent="observer",
        analysis_type="metrics_collection",
        result_json=result_json,
        result_markdown=markdown_report,
    )

    # Save signals to the signals table
    for signal in state["signals"]:
        state_db.create_signal(
            database_id=state["database_id"],
            signal_type=signal["signal_type"],
            severity=signal["severity"],
            description=signal["description"],
            details=signal["details"],
        )

    state_db.log("observer", "INFO",
                "Observation complete and saved",
                database_id=state["database_id"])

    return state


def should_continue(state: ObserverState) -> str:
    """Determine if we should continue or end due to error."""
    if state.get("error"):
        return "error"
    return "continue"


def create_observer_graph():
    """Create the Observer agent workflow graph."""
    workflow = StateGraph(ObserverState)

    # Add nodes
    workflow.add_node("collect_query_metrics", collect_query_metrics)
    workflow.add_node("collect_table_metrics", collect_table_metrics)
    workflow.add_node("collect_index_metrics", collect_index_metrics)
    workflow.add_node("load_previous_metrics", load_previous_metrics)
    workflow.add_node("analyze_metrics_with_llm", analyze_metrics_with_llm)
    workflow.add_node("detect_signals", detect_signals)
    workflow.add_node("save_results", save_results)

    # Set entry point
    workflow.set_entry_point("collect_query_metrics")

    # Add edges
    workflow.add_conditional_edges(
        "collect_query_metrics",
        should_continue,
        {"continue": "collect_table_metrics", "error": END}
    )
    workflow.add_edge("collect_table_metrics", "collect_index_metrics")
    workflow.add_edge("collect_index_metrics", "load_previous_metrics")
    workflow.add_edge("load_previous_metrics", "analyze_metrics_with_llm")
    workflow.add_edge("analyze_metrics_with_llm", "detect_signals")
    workflow.add_edge("detect_signals", "save_results")
    workflow.add_edge("save_results", END)

    return workflow.compile()


async def run_observer_agent(database_id: int) -> Dict[str, Any]:
    """
    Run the Observer agent on a database.

    Args:
        database_id: ID of the database in the state DB

    Returns:
        Observation results including signals detected
    """
    state_db.log("observer", "INFO", f"Starting observation for database {database_id}")

    # Create initial state
    initial_state: ObserverState = {
        "database_id": database_id,
        "query_metrics": [],
        "table_metrics": [],
        "index_metrics": [],
        "previous_metrics": None,
        "signals": [],
        "llm_analysis": None,
        "error": None,
    }

    # Create and run the graph
    graph = create_observer_graph()
    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        return {"error": final_state["error"]}

    return {
        "status": "success",
        "queries_analyzed": len(final_state["query_metrics"]),
        "tables_analyzed": len(final_state["table_metrics"]),
        "indexes_analyzed": len(final_state["index_metrics"]),
        "signals_detected": len(final_state["signals"]),
        "signals": final_state["signals"],
    }
