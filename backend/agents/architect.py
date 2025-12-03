"""
PG Index Agents - Agente Architect
https://github.com/686f6c61/pg-index-agents

El agente Architect analiza senales del Observer y genera propuestas concretas
de indices con justificaciones detalladas. Es el agente que propone cambios
a la estructura de indices.

Funciones principales:
1. Recibir senales del Observer (queries lentas, scans secuenciales)
2. Analizar queries problematicas (EXPLAIN, patrones de filtrado)
3. Evaluar indices existentes en las tablas involucradas
4. Proponer mejoras especificas (CREATE INDEX, DROP INDEX)
5. Estimar impacto y generar justificaciones comprensibles

El Architect utiliza el modelo de lenguaje para generar propuestas SQL
sintacticamente correctas y justificaciones que explican el razonamiento
detras de cada recomendacion.

Las propuestas generadas requieren aprobacion manual por defecto (nivel
de autonomia "assisted"). El SQL generado usa CONCURRENTLY cuando es
posible para evitar bloqueos.

Autor: 686f6c61
Licencia: MIT
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
import re
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text
import json

from core.database import db_manager
from core.state import state_db
from core.llm import get_llm_for_proposals


class IndexProposal(TypedDict):
    """A proposed index improvement."""
    proposal_type: str  # create_index, drop_index, rewrite_query, analyze_table
    table: str
    sql_command: str
    justification: str
    estimated_impact: Dict[str, Any]
    confidence: float  # 0-1


class ArchitectState(TypedDict):
    """State for the Architect agent workflow."""
    database_id: int
    signal: Dict[str, Any]
    query_analysis: Optional[Dict[str, Any]]
    existing_indexes: List[Dict[str, Any]]
    table_columns: List[Dict[str, Any]]
    proposals: List[IndexProposal]
    llm_analysis: Optional[str]
    error: Optional[str]


def analyze_query(state: ArchitectState) -> ArchitectState:
    """Analyze the problematic query from the signal."""
    if state.get("error"):
        return state

    signal = state["signal"]

    # Only analyze query-related signals
    if signal["signal_type"] not in ("high_impact_query", "query_degradation", "high_sequential_scans"):
        return {**state, "query_analysis": None}

    query_sample = signal.get("details", {}).get("query_sample", "")

    if not query_sample:
        return {**state, "query_analysis": None}

    # Parse query structure
    analysis = {
        "original_query": query_sample,
        "tables": [],
        "where_columns": [],
        "join_columns": [],
        "order_columns": [],
        "group_columns": [],
        "select_columns": [],
    }

    query_lower = query_sample.lower()

    # Extract tables (simple regex approach)
    from_match = re.findall(r'\bfrom\s+([a-z_][a-z0-9_]*)', query_lower)
    join_match = re.findall(r'\bjoin\s+([a-z_][a-z0-9_]*)', query_lower)
    analysis["tables"] = list(set(from_match + join_match))

    # Extract WHERE columns
    where_match = re.findall(r'where\s+.*?([a-z_][a-z0-9_]*)\s*[=<>]', query_lower)
    and_match = re.findall(r'\band\s+([a-z_][a-z0-9_]*)\s*[=<>]', query_lower)
    analysis["where_columns"] = list(set(where_match + and_match))

    # Extract JOIN columns
    on_match = re.findall(r'\bon\s+[a-z_\.]+\.([a-z_][a-z0-9_]*)\s*=', query_lower)
    analysis["join_columns"] = list(set(on_match))

    # Extract ORDER BY columns
    order_match = re.findall(r'order\s+by\s+([a-z_][a-z0-9_,\s]+)', query_lower)
    if order_match:
        order_cols = re.findall(r'([a-z_][a-z0-9_]*)', order_match[0])
        analysis["order_columns"] = order_cols

    # Extract GROUP BY columns
    group_match = re.findall(r'group\s+by\s+([a-z_][a-z0-9_,\s]+)', query_lower)
    if group_match:
        group_cols = re.findall(r'([a-z_][a-z0-9_]*)', group_match[0])
        analysis["group_columns"] = group_cols

    state_db.log("architect", "INFO",
                f"Analyzed query: {len(analysis['tables'])} tables, {len(analysis['where_columns'])} where columns",
                database_id=state["database_id"])

    return {**state, "query_analysis": analysis}


def get_existing_indexes(state: ArchitectState) -> ArchitectState:
    """Get existing indexes for the affected tables."""
    if state.get("error"):
        return state

    tables = []
    if state["query_analysis"]:
        tables = state["query_analysis"]["tables"]
    elif state["signal"].get("table"):
        tables = [state["signal"]["table"]]

    if not tables:
        return {**state, "existing_indexes": []}

    try:
        with db_manager.read_connection() as conn:
            # Use parameterized query to prevent SQL injection
            placeholders = ", ".join([f":table_{i}" for i in range(len(tables))])
            params = {f"table_{i}": t for i, t in enumerate(tables)}
            result = conn.execute(text(f"""
                SELECT
                    i.relname as index_name,
                    t.relname as table_name,
                    array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) as columns,
                    ix.indisunique as is_unique,
                    ix.indisprimary as is_primary,
                    pg_get_indexdef(ix.indexrelid) as definition,
                    pg_relation_size(i.oid) as size_bytes
                FROM pg_index ix
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE n.nspname = 'public'
                AND t.relname IN ({placeholders})
                GROUP BY i.relname, t.relname, ix.indisunique, ix.indisprimary, ix.indexrelid, i.oid
                ORDER BY t.relname, i.relname
            """), params)

            indexes = []
            for row in result:
                indexes.append({
                    "index_name": row[0],
                    "table_name": row[1],
                    "columns": row[2],
                    "is_unique": row[3],
                    "is_primary": row[4],
                    "definition": row[5],
                    "size_bytes": row[6],
                })

            return {**state, "existing_indexes": indexes}

    except Exception as e:
        state_db.log("architect", "ERROR", f"Failed to get existing indexes: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "existing_indexes": []}


def get_table_columns(state: ArchitectState) -> ArchitectState:
    """Get column information for affected tables."""
    if state.get("error"):
        return state

    tables = []
    if state["query_analysis"]:
        tables = state["query_analysis"]["tables"]
    elif state["signal"].get("table"):
        tables = [state["signal"]["table"]]

    if not tables:
        return {**state, "table_columns": []}

    try:
        with db_manager.read_connection() as conn:
            # Use parameterized query to prevent SQL injection
            placeholders = ", ".join([f":table_{i}" for i in range(len(tables))])
            params = {f"table_{i}": t for i, t in enumerate(tables)}
            result = conn.execute(text(f"""
                SELECT
                    c.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    s.n_distinct,
                    s.null_frac
                FROM information_schema.columns c
                LEFT JOIN pg_stats s ON s.tablename = c.table_name AND s.attname = c.column_name
                WHERE c.table_schema = 'public'
                AND c.table_name IN ({placeholders})
                ORDER BY c.table_name, c.ordinal_position
            """), params)

            columns = []
            for row in result:
                columns.append({
                    "table_name": row[0],
                    "column_name": row[1],
                    "data_type": row[2],
                    "is_nullable": row[3] == "YES",
                    "n_distinct": row[4],
                    "null_frac": row[5],
                })

            return {**state, "table_columns": columns}

    except Exception as e:
        state_db.log("architect", "ERROR", f"Failed to get table columns: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "table_columns": []}


def should_skip_llm_analysis(signal: Dict[str, Any], existing_indexes: List[Dict[str, Any]]) -> bool:
    """Check if we should skip LLM analysis for this signal (optimization)."""
    if signal.get("signal_type") == "unused_index":
        details = signal.get("details", {})
        index_name = details.get("index_name", "")

        # Skip if it's a primary key - no need to analyze
        if index_name.endswith('_pkey') or 'primary' in index_name.lower():
            return True

        # Check in existing_indexes
        for idx in existing_indexes:
            if idx.get("index_name") == index_name and idx.get("is_primary"):
                return True

    return False


def analyze_with_llm(state: ArchitectState) -> ArchitectState:
    """Use LLM to analyze the signal and generate intelligent recommendations."""
    if state.get("error"):
        return state

    signal = state["signal"]
    existing_indexes = state["existing_indexes"]

    # Optimization: skip LLM for primary keys
    if should_skip_llm_analysis(signal, existing_indexes):
        state_db.log("architect", "INFO",
                    f"Skipping LLM analysis for primary key index",
                    database_id=state["database_id"])
        return {**state, "llm_analysis": None}

    try:
        llm = get_llm_for_proposals()
        signal = state["signal"]
        analysis = state["query_analysis"]
        existing_indexes = state["existing_indexes"]
        columns = state["table_columns"]

        # Build context for the LLM
        indexes_info = []
        for idx in existing_indexes:
            indexes_info.append(f"  - {idx['index_name']} ON ({', '.join(idx['columns'])})")

        columns_info = []
        for col in columns[:20]:  # Limit to avoid token overflow
            cardinality = f"cardinality={col['n_distinct']}" if col['n_distinct'] else ""
            columns_info.append(f"  - {col['table_name']}.{col['column_name']} ({col['data_type']}) {cardinality}")

        prompt = f"""Analiza este problema de rendimiento en PostgreSQL y genera recomendaciones específicas.

## Señal Detectada
- **Tipo**: {signal.get('signal_type')}
- **Severidad**: {signal.get('severity')}
- **Descripción**: {signal.get('description')}
- **Tabla afectada**: {signal.get('table', 'N/A')}

## Detalles del Problema
```json
{json.dumps(signal.get('details', {}), indent=2)}
```

## Query Analizado
{analysis.get('original_query', 'No disponible') if analysis else 'No disponible'}

## Columnas usadas en WHERE
{', '.join(analysis.get('where_columns', [])) if analysis else 'N/A'}

## Columnas usadas en JOIN
{', '.join(analysis.get('join_columns', [])) if analysis else 'N/A'}

## Índices Existentes
{chr(10).join(indexes_info) if indexes_info else 'Ninguno'}

## Columnas de las Tablas
{chr(10).join(columns_info) if columns_info else 'No disponible'}

## Tu Tarea
1. **Diagnóstico**: Explica en lenguaje natural por qué este query es lento o problemático
2. **Causa raíz**: Identifica la causa principal del problema de rendimiento
3. **Solución recomendada**: Proporciona el comando SQL exacto para crear el índice óptimo
4. **Justificación técnica**: Explica por qué esta solución funcionará y qué mejora se espera
5. **Consideraciones**: Menciona impacto en escrituras, espacio, y cuándo NO aplicar esta solución

Responde de forma clara y estructurada, pensando que el lector puede no ser un DBA experto."""

        state_db.log("architect", "INFO",
                    "Calling LLM for intelligent analysis...",
                    database_id=state["database_id"])

        response = llm.invoke([
            SystemMessage(content="""Eres un DBA experto en PostgreSQL con años de experiencia optimizando bases de datos.
Tu rol es analizar problemas de rendimiento y proponer soluciones concretas con justificaciones claras.
Siempre explicas el "por qué" detrás de tus recomendaciones para que otros puedan aprender.
Generas comandos SQL seguros usando CONCURRENTLY cuando es posible.

REGLAS DE FORMATO ESTRICTAS:
- NUNCA uses emojis bajo ninguna circunstancia
- NO uses formato markdown como ##, **, -, ```
- Escribe en parrafos claros y bien estructurados
- Usa MAYUSCULAS para titulos de seccion
- Los comandos SQL van entre corchetes: [SELECT * FROM tabla]"""),
            HumanMessage(content=prompt)
        ])

        state_db.log("architect", "INFO",
                    f"LLM analysis complete: {len(response.content)} chars",
                    database_id=state["database_id"])

        return {**state, "llm_analysis": response.content}

    except Exception as e:
        state_db.log("architect", "WARNING",
                    f"LLM analysis failed (continuing with heuristics): {str(e)}",
                    database_id=state["database_id"])
        return {**state, "llm_analysis": None}


def generate_proposals(state: ArchitectState) -> ArchitectState:
    """Generate index proposals based on analysis."""
    if state.get("error"):
        return state

    proposals: List[IndexProposal] = []
    signal = state["signal"]
    analysis = state["query_analysis"]
    existing_indexes = state["existing_indexes"]
    columns = state["table_columns"]
    llm_analysis = state.get("llm_analysis", "")

    # Get columns by table
    columns_by_table = {}
    for col in columns:
        if col["table_name"] not in columns_by_table:
            columns_by_table[col["table_name"]] = []
        columns_by_table[col["table_name"]].append(col)

    # Get existing indexed columns by table
    indexed_columns_by_table = {}
    for idx in existing_indexes:
        table = idx["table_name"]
        if table not in indexed_columns_by_table:
            indexed_columns_by_table[table] = set()
        indexed_columns_by_table[table].update(idx["columns"])

    # Strategy 1: Create index for WHERE columns not indexed
    if analysis and analysis["where_columns"]:
        for table in analysis["tables"]:
            indexed = indexed_columns_by_table.get(table, set())
            table_cols = {c["column_name"] for c in columns_by_table.get(table, [])}

            for where_col in analysis["where_columns"]:
                # Check if column exists in table and is not indexed
                if where_col in table_cols and where_col not in indexed:
                    # Check column cardinality
                    col_info = next(
                        (c for c in columns_by_table.get(table, []) if c["column_name"] == where_col),
                        None
                    )

                    # Skip low cardinality columns (boolean-like)
                    if col_info and col_info["n_distinct"] and -1 < col_info["n_distinct"] < 10:
                        continue

                    index_name = f"idx_{table}_{where_col}"

                    proposals.append({
                        "proposal_type": "create_index",
                        "table": table,
                        "sql_command": f"CREATE INDEX CONCURRENTLY {index_name} ON {table}({where_col})",
                        "justification": f"Column '{where_col}' is used in WHERE clause but has no index. "
                                        f"Creating an index will allow PostgreSQL to quickly locate matching rows "
                                        f"instead of scanning the entire table.",
                        "estimated_impact": {
                            "read_improvement": "high",
                            "write_overhead": "low",
                            "space_overhead": "low",
                        },
                        "confidence": 0.8,
                    })

    # Strategy 2: Composite index for multiple WHERE columns
    if analysis and len(analysis["where_columns"]) > 1:
        for table in analysis["tables"]:
            table_cols = {c["column_name"] for c in columns_by_table.get(table, [])}
            relevant_cols = [c for c in analysis["where_columns"] if c in table_cols]

            if len(relevant_cols) >= 2:
                # Check if a composite index already exists
                existing_composite = False
                for idx in existing_indexes:
                    if idx["table_name"] == table:
                        if all(c in idx["columns"] for c in relevant_cols[:2]):
                            existing_composite = True
                            break

                if not existing_composite:
                    # Order columns by cardinality (higher first)
                    col_order = sorted(
                        relevant_cols[:3],  # Max 3 columns
                        key=lambda c: abs(next(
                            (col["n_distinct"] or 0 for col in columns_by_table.get(table, [])
                             if col["column_name"] == c), 0
                        )),
                        reverse=True
                    )

                    cols_str = ", ".join(col_order)
                    index_name = f"idx_{table}_{'_'.join(col_order[:2])}"

                    proposals.append({
                        "proposal_type": "create_index",
                        "table": table,
                        "sql_command": f"CREATE INDEX CONCURRENTLY {index_name} ON {table}({cols_str})",
                        "justification": f"Query filters on multiple columns ({', '.join(col_order)}). "
                                        f"A composite index can satisfy the entire WHERE clause in a single index scan, "
                                        f"which is more efficient than using multiple single-column indexes.",
                        "estimated_impact": {
                            "read_improvement": "very_high",
                            "write_overhead": "medium",
                            "space_overhead": "medium",
                        },
                        "confidence": 0.85,
                    })

    # Strategy 3: Suggest ANALYZE for high sequential scans
    if signal["signal_type"] == "high_sequential_scans":
        table = signal.get("table")
        if table:
            proposals.append({
                "proposal_type": "analyze_table",
                "table": table,
                "sql_command": f"ANALYZE {table}",
                "justification": f"Table '{table}' has high sequential scan ratio. "
                                f"Running ANALYZE updates table statistics, which may help the query planner "
                                f"choose better execution plans including index usage.",
                "estimated_impact": {
                    "read_improvement": "medium",
                    "write_overhead": "none",
                    "space_overhead": "none",
                },
                "confidence": 0.6,
            })

    # Strategy 4: Suggest dropping unused indexes
    if signal["signal_type"] == "unused_index":
        details = signal.get("details", {})
        index_name = details.get("index_name")
        table = details.get("table_name") or signal.get("table")
        size_bytes = details.get("size_bytes", 0)

        if index_name:
            # Check if it's a primary key by querying existing_indexes
            # OR by checking if name contains 'pkey' pattern
            is_primary = any(
                idx.get("is_primary") for idx in existing_indexes
                if idx.get("index_name") == index_name
            )
            # Also check common PostgreSQL primary key naming convention
            if not is_primary:
                is_primary = index_name.endswith('_pkey') or 'primary' in index_name.lower()

            if not is_primary:
                size_mb = size_bytes / 1024 / 1024 if size_bytes else 0
                proposals.append({
                    "proposal_type": "drop_index",
                    "table": table or "unknown",
                    "sql_command": f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}",
                    "justification": f"El índice '{index_name}' nunca ha sido utilizado (0 escaneos) pero consume "
                                    f"{size_mb:.1f}MB de almacenamiento y ralentiza las operaciones de escritura. "
                                    f"Eliminarlo mejorará el rendimiento de INSERT/UPDATE/DELETE en esta tabla.",
                    "estimated_impact": {
                        "read_improvement": "none",
                        "write_improvement": "medium",
                        "space_savings": size_bytes,
                    },
                    "confidence": 0.75,
                })
            else:
                state_db.log("architect", "INFO",
                            f"Skipping primary key index: {index_name}",
                            database_id=state["database_id"])

    # Add LLM analysis to all proposals if available
    if llm_analysis:
        for proposal in proposals:
            proposal["justification"] += f"\n\n**Análisis Detallado (IA):**\n{llm_analysis}"

    state_db.log("architect", "INFO",
                f"Generated {len(proposals)} proposals",
                database_id=state["database_id"])

    return {**state, "proposals": proposals}


def save_proposals(state: ArchitectState) -> ArchitectState:
    """Save proposals to the database."""
    if state.get("error"):
        return state

    for proposal in state["proposals"]:
        state_db.create_proposal(
            database_id=state["database_id"],
            proposal_type=proposal["proposal_type"],
            sql_command=proposal["sql_command"],
            justification=proposal["justification"],
            estimated_impact=proposal["estimated_impact"],
            signal_id=state["signal"].get("id"),
        )

    # Mark the signal as processed
    signal_id = state["signal"].get("id")
    if signal_id:
        state_db.mark_signal_processed(signal_id)

    state_db.log("architect", "INFO",
                f"Saved {len(state['proposals'])} proposals for signal {signal_id}",
                database_id=state["database_id"])

    return state


def should_continue(state: ArchitectState) -> str:
    """Determine if we should continue or end due to error."""
    if state.get("error"):
        return "error"
    return "continue"


def create_architect_graph():
    """Create the Architect agent workflow graph."""
    workflow = StateGraph(ArchitectState)

    # Add nodes
    workflow.add_node("analyze_query", analyze_query)
    workflow.add_node("get_existing_indexes", get_existing_indexes)
    workflow.add_node("get_table_columns", get_table_columns)
    workflow.add_node("analyze_with_llm", analyze_with_llm)
    workflow.add_node("generate_proposals", generate_proposals)
    workflow.add_node("save_proposals", save_proposals)

    # Set entry point
    workflow.set_entry_point("analyze_query")

    # Add edges
    workflow.add_conditional_edges(
        "analyze_query",
        should_continue,
        {"continue": "get_existing_indexes", "error": END}
    )
    workflow.add_edge("get_existing_indexes", "get_table_columns")
    workflow.add_edge("get_table_columns", "analyze_with_llm")
    workflow.add_edge("analyze_with_llm", "generate_proposals")
    workflow.add_edge("generate_proposals", "save_proposals")
    workflow.add_edge("save_proposals", END)

    return workflow.compile()


async def run_architect_agent(database_id: int, signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the Architect agent on a specific signal.

    Args:
        database_id: ID of the database in the state DB
        signal: The signal to analyze

    Returns:
        Analysis results including proposals
    """
    state_db.log("architect", "INFO",
                f"Starting analysis for signal: {signal.get('signal_type')}",
                database_id=database_id)

    # Create initial state
    initial_state: ArchitectState = {
        "database_id": database_id,
        "signal": signal,
        "query_analysis": None,
        "existing_indexes": [],
        "table_columns": [],
        "proposals": [],
        "llm_analysis": None,
        "error": None,
    }

    # Create and run the graph
    graph = create_architect_graph()
    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        return {"error": final_state["error"]}

    return {
        "status": "success",
        "signal_type": signal.get("signal_type"),
        "proposals": final_state["proposals"],
        "proposals_count": len(final_state["proposals"]),
        "llm_analysis": final_state.get("llm_analysis"),
    }


async def process_pending_signals(database_id: int) -> Dict[str, Any]:
    """
    Process all pending signals for a database.

    Args:
        database_id: ID of the database

    Returns:
        Summary of processed signals and proposals
    """
    signals = state_db.get_pending_signals(database_id)
    total_proposals = 0
    processed_signals = 0
    all_proposals = []
    all_llm_analyses = []

    state_db.log("architect", "INFO",
                f"Processing {len(signals)} pending signals",
                database_id=database_id)

    for signal in signals:
        result = await run_architect_agent(database_id, signal)
        if result.get("status") == "success":
            total_proposals += result.get("proposals_count", 0)
            processed_signals += 1
            all_proposals.extend(result.get("proposals", []))
            if result.get("llm_analysis"):
                all_llm_analyses.append({
                    "signal_type": signal.get("signal_type"),
                    "description": signal.get("description"),
                    "analysis": result.get("llm_analysis")
                })

    # Generate summary report
    if total_proposals > 0 or processed_signals > 0:
        markdown_report = generate_architect_report(
            processed_signals, total_proposals, all_proposals, all_llm_analyses
        )

        # Save analysis
        result_json = {
            "signals_processed": processed_signals,
            "total_proposals": total_proposals,
            "proposals": all_proposals,
            "analyses": all_llm_analyses,
            "processed_at": datetime.now().isoformat(),
        }

        state_db.save_analysis(
            database_id=database_id,
            agent="architect",
            analysis_type="signal_processing",
            result_json=result_json,
            result_markdown=markdown_report,
        )

    return {
        "status": "success",
        "signals_processed": processed_signals,
        "total_proposals": total_proposals,
    }


def generate_architect_report(
    processed_signals: int,
    total_proposals: int,
    proposals: List[Dict],
    analyses: List[Dict]
) -> str:
    """Generate a human-readable markdown report."""
    report = f"""# Architect Analysis Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- **Signals Processed:** {processed_signals}
- **Proposals Generated:** {total_proposals}

## Propuestas de Optimización

"""
    if proposals:
        for i, prop in enumerate(proposals[:10], 1):
            report += f"""### {i}. {prop.get('proposal_type', 'N/A').replace('_', ' ').title()}

**Tabla:** {prop.get('table', 'N/A')}

**Comando SQL:**
```sql
{prop.get('sql_command', 'N/A')}
```

**Justificación:**
{prop.get('justification', 'Sin justificación')}

**Impacto Estimado:**
- Mejora en lecturas: {prop.get('estimated_impact', {}).get('read_improvement', 'N/A')}
- Mejora en escrituras: {prop.get('estimated_impact', {}).get('write_improvement', 'N/A')}
- Confianza: {prop.get('confidence', 0) * 100:.0f}%

---

"""
    else:
        report += "*No se generaron propuestas. Los índices existentes pueden ser claves primarias o ya están optimizados.*\n\n"

    if analyses:
        report += "## Análisis Detallado por IA\n\n"
        for analysis in analyses[:5]:
            report += f"""### Señal: {analysis.get('signal_type', 'N/A')}
{analysis.get('description', '')}

{analysis.get('analysis', 'Sin análisis disponible')}

---

"""

    return report
