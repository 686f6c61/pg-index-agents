"""
PG Index Agents - Agente Explorer
https://github.com/686f6c61/pg-index-agents

El agente Explorer realiza el analisis inicial de una base de datos PostgreSQL.
Es el primer agente que se ejecuta y proporciona el contexto necesario para
que los demas agentes puedan operar.

Funciones principales:
1. Extraer metadatos (tablas, columnas, indices, constraints)
2. Construir grafo de dependencias desde foreign keys y convenciones de nombres
3. Clasificar tablas por tipo (central, log, catalogo, transaccional)
4. Detectar anomalias estructurales (indices faltantes, redundantes)
5. Generar plan de trabajo priorizado para otros agentes

El Explorer utiliza LangGraph para orquestar su flujo de trabajo en pasos
secuenciales. Cada paso actualiza el estado compartido y puede invocar
al modelo de lenguaje para analisis mas profundos.

Autor: 686f6c61
Licencia: MIT
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import json
import re

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_llm_for_analysis
from core.state import state_db
from services.metadata import metadata_extractor


# State definition for the Explorer agent
class ExplorerState(TypedDict):
    """State for the Explorer agent workflow."""
    database_id: int
    schema: str
    metadata: Dict[str, Any]
    dependency_graph: Dict[str, Any]
    table_classifications: Dict[str, Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    llm_insights: Optional[str]
    work_plan: Dict[str, Any]
    markdown_report: str
    error: Optional[str]


def extract_metadata(state: ExplorerState) -> ExplorerState:
    """Extract metadata from the target database."""
    try:
        metadata = metadata_extractor.get_full_snapshot(state["schema"])
        state_db.log(
            "explorer", "INFO",
            f"Extracted metadata: {len(metadata['tables'])} tables, {len(metadata['indexes'])} indexes",
            database_id=state["database_id"]
        )
        return {**state, "metadata": metadata}
    except Exception as e:
        state_db.log("explorer", "ERROR", f"Failed to extract metadata: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def build_dependency_graph(state: ExplorerState) -> ExplorerState:
    """Build a dependency graph from foreign keys and inferred relationships."""
    if state.get("error"):
        return state

    metadata = state["metadata"]
    graph = {
        "nodes": {},  # table_name -> {references: [], referenced_by: [], inferred: []}
        "edges": [],  # {from, to, type, column}
    }

    # Initialize nodes for all tables
    for table in metadata["tables"]:
        graph["nodes"][table["name"]] = {
            "references": [],      # Tables this table references
            "referenced_by": [],   # Tables that reference this table
            "inferred": [],        # Inferred relationships
        }

    # Add explicit foreign key relationships
    for fk in metadata["foreign_keys"]:
        from_table = fk["from_table"]
        to_table = fk["to_table"]

        if from_table in graph["nodes"] and to_table in graph["nodes"]:
            graph["nodes"][from_table]["references"].append(to_table)
            graph["nodes"][to_table]["referenced_by"].append(from_table)
            graph["edges"].append({
                "from": from_table,
                "to": to_table,
                "type": "foreign_key",
                "column": fk["from_column"]
            })

    # Infer relationships from naming conventions (e.g., user_id -> users)
    table_names = set(graph["nodes"].keys())

    for table in metadata["tables"]:
        for column in table["columns"]:
            col_name = column["name"].lower()

            # Pattern: *_id might reference a table
            if col_name.endswith("_id") and col_name != "id":
                # Extract potential table name
                potential_table = col_name[:-3]  # Remove _id

                # Try various pluralization patterns
                candidates = [
                    potential_table,
                    potential_table + "s",
                    potential_table + "es",
                    potential_table.rstrip("y") + "ies" if potential_table.endswith("y") else None,
                ]

                for candidate in candidates:
                    if candidate and candidate in table_names:
                        # Check if this relationship isn't already explicit
                        existing = any(
                            e["from"] == table["name"] and e["to"] == candidate
                            for e in graph["edges"]
                        )
                        if not existing and table["name"] != candidate:
                            graph["nodes"][table["name"]]["inferred"].append(candidate)
                            graph["edges"].append({
                                "from": table["name"],
                                "to": candidate,
                                "type": "inferred",
                                "column": column["name"]
                            })
                            break

    state_db.log(
        "explorer", "INFO",
        f"Built dependency graph: {len(graph['edges'])} relationships",
        database_id=state["database_id"]
    )

    return {**state, "dependency_graph": graph}


def classify_tables(state: ExplorerState) -> ExplorerState:
    """Classify tables based on their characteristics."""
    if state.get("error"):
        return state

    metadata = state["metadata"]
    graph = state["dependency_graph"]
    classifications = {}

    # Get table statistics
    stats_by_table = {s["table_name"]: s for s in metadata["table_statistics"]}

    for table in metadata["tables"]:
        table_name = table["name"]
        stats = stats_by_table.get(table_name, {})
        node = graph["nodes"].get(table_name, {})

        classification = {
            "name": table_name,
            "type": "unknown",
            "criticality": "medium",
            "characteristics": [],
            "row_count": stats.get("row_count", 0),
            "total_size_bytes": stats.get("total_size_bytes", 0),
        }

        # Count relationships
        ref_count = len(node.get("references", [])) + len(node.get("inferred", []))
        refby_count = len(node.get("referenced_by", []))

        # Classification rules
        # Central tables: Many tables reference them
        if refby_count >= 3:
            classification["type"] = "central"
            classification["criticality"] = "high"
            classification["characteristics"].append(f"Referenced by {refby_count} tables")

        # Log tables: Large, timestamp columns, few references
        elif any(c["name"].lower() in ("created_at", "timestamp", "logged_at", "date")
                for c in table["columns"]):
            if stats.get("row_count", 0) > 10000 and refby_count == 0:
                classification["type"] = "log"
                classification["criticality"] = "low"
                classification["characteristics"].append("Has timestamp column, large, no references")

        # Catalog/lookup tables: Small, rarely changes
        elif stats.get("row_count", 0) < 1000 and refby_count > 0:
            classification["type"] = "catalog"
            classification["criticality"] = "low"
            classification["characteristics"].append("Small lookup table")

        # Junction/bridge tables: References 2+ tables, no content columns
        elif ref_count >= 2 and len(table["columns"]) <= 4:
            classification["type"] = "junction"
            classification["criticality"] = "medium"
            classification["characteristics"].append("Many-to-many relationship table")

        # Transactional: Has timestamps, moderate size, some references
        elif any(c["name"].lower() in ("created_at", "updated_at", "modified_at")
                for c in table["columns"]):
            classification["type"] = "transactional"
            classification["criticality"] = "high"
            classification["characteristics"].append("Transactional data")

        # Default to data table
        else:
            classification["type"] = "data"

        # Add column count
        classification["column_count"] = len(table["columns"])

        # Add index count
        index_count = len([i for i in metadata["indexes"] if i["table_name"] == table_name])
        classification["index_count"] = index_count

        classifications[table_name] = classification

    state_db.log(
        "explorer", "INFO",
        f"Classified {len(classifications)} tables",
        database_id=state["database_id"]
    )

    return {**state, "table_classifications": classifications}


def detect_anomalies(state: ExplorerState) -> ExplorerState:
    """Detect structural anomalies in the database."""
    if state.get("error"):
        return state

    metadata = state["metadata"]
    classifications = state["table_classifications"]
    anomalies = []

    # Build index lookup
    indexes_by_table = {}
    for idx in metadata["indexes"]:
        table = idx["table_name"]
        if table not in indexes_by_table:
            indexes_by_table[table] = []
        indexes_by_table[table].append(idx)

    for table in metadata["tables"]:
        table_name = table["name"]
        table_indexes = indexes_by_table.get(table_name, [])
        classification = classifications.get(table_name, {})
        row_count = classification.get("row_count", 0)

        # Anomaly 1: Large tables with only primary key index
        non_pk_indexes = [i for i in table_indexes if not i["is_primary"]]
        if row_count > 10000 and len(non_pk_indexes) == 0:
            anomalies.append({
                "type": "missing_secondary_index",
                "severity": "high",
                "table": table_name,
                "description": f"Large table ({row_count:,} rows) has no secondary indexes",
                "recommendation": "Consider adding indexes on frequently queried columns"
            })

        # Anomaly 2: Common filter columns without indexes
        common_filter_patterns = ["status", "type", "state", "created_at", "updated_at",
                                  "user_id", "owner_id", "parent_id", "category"]

        indexed_columns = set()
        for idx in table_indexes:
            indexed_columns.update(idx["columns"])

        for col in table["columns"]:
            col_lower = col["name"].lower()
            # Check if column matches common filter patterns
            if any(pattern in col_lower for pattern in common_filter_patterns):
                if col["name"] not in indexed_columns:
                    anomalies.append({
                        "type": "missing_filter_index",
                        "severity": "medium",
                        "table": table_name,
                        "column": col["name"],
                        "description": f"Column '{col['name']}' is commonly used for filtering but has no index",
                        "recommendation": f"CREATE INDEX idx_{table_name}_{col['name']} ON {table_name}({col['name']})"
                    })

        # Anomaly 3: Redundant indexes (one is prefix of another)
        for i, idx1 in enumerate(table_indexes):
            for idx2 in table_indexes[i+1:]:
                cols1 = idx1["columns"]
                cols2 = idx2["columns"]

                # Check if one is prefix of another
                if cols1[:len(cols2)] == cols2:
                    anomalies.append({
                        "type": "redundant_index",
                        "severity": "low",
                        "table": table_name,
                        "indexes": [idx1["name"], idx2["name"]],
                        "description": f"Index '{idx2['name']}' is a prefix of '{idx1['name']}'",
                        "recommendation": f"Consider dropping '{idx2['name']}' as '{idx1['name']}' covers its use cases"
                    })
                elif cols2[:len(cols1)] == cols1:
                    anomalies.append({
                        "type": "redundant_index",
                        "severity": "low",
                        "table": table_name,
                        "indexes": [idx1["name"], idx2["name"]],
                        "description": f"Index '{idx1['name']}' is a prefix of '{idx2['name']}'",
                        "recommendation": f"Consider dropping '{idx1['name']}' as '{idx2['name']}' covers its use cases"
                    })

        # Anomaly 4: Unused indexes (from statistics)
        for idx_stat in metadata["index_statistics"]:
            if idx_stat["table_name"] == table_name:
                if idx_stat["idx_scan"] == 0:
                    # Find the index
                    idx = next((i for i in table_indexes if i["name"] == idx_stat["index_name"]), None)
                    if idx and not idx["is_primary"]:
                        anomalies.append({
                            "type": "unused_index",
                            "severity": "low",
                            "table": table_name,
                            "index": idx_stat["index_name"],
                            "description": f"Index '{idx_stat['index_name']}' has never been used (0 scans)",
                            "recommendation": f"Consider dropping if not needed: DROP INDEX {idx_stat['index_name']}"
                        })

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    anomalies.sort(key=lambda x: severity_order.get(x["severity"], 3))

    state_db.log(
        "explorer", "INFO",
        f"Detected {len(anomalies)} anomalies",
        database_id=state["database_id"]
    )

    return {**state, "anomalies": anomalies}


def analyze_with_llm(state: ExplorerState) -> ExplorerState:
    """Use LLM to generate a complete human-readable explanation of the database."""
    if state.get("error"):
        return state

    try:
        llm = get_llm_for_analysis()

        # Prepare context for the LLM
        metadata = state["metadata"]
        classifications = state["table_classifications"]
        anomalies = state["anomalies"]
        graph = state["dependency_graph"]

        # Create a summary for the LLM
        tables_summary = []
        for name, info in sorted(classifications.items(), key=lambda x: x[1]['row_count'], reverse=True)[:15]:
            tables_summary.append(
                f"- {name}: tipo={info['type']}, {info['row_count']:,} filas, "
                f"{info['index_count']} índices, criticidad={info['criticality']}"
            )

        anomalies_by_severity = {"high": [], "medium": [], "low": []}
        for a in anomalies:
            anomalies_by_severity[a["severity"]].append(
                f"- {a['table']}: {a['description']}"
            )

        relationships = [
            f"- {e['from']} → {e['to']} (via {e['column']}, {e['type']})"
            for e in graph["edges"][:15]
        ]

        unused_indexes = [a for a in anomalies if a["type"] == "unused_index"]
        missing_indexes = [a for a in anomalies if a["type"] in ("missing_filter_index", "missing_secondary_index")]

        prompt = f"""Eres un DBA experto explicando el estado de una base de datos PostgreSQL a un equipo de desarrollo.
Tu objetivo es que CUALQUIER persona (técnica o no) entienda qué está pasando y qué hay que hacer.

BASE DE DATOS ANALIZADA
Nombre: {metadata['database_size']['database_name']}
Tamaño total: {metadata['database_size']['size_human']}
Total tablas: {len(metadata['tables'])}
Total índices: {len(metadata['indexes'])}
Foreign Keys explícitas: {len(metadata['foreign_keys'])}
Relaciones inferidas: {len([e for e in graph['edges'] if e['type'] == 'inferred'])}

TABLAS PRINCIPALES (por tamaño)
{chr(10).join(tables_summary)}

RELACIONES DETECTADAS
{chr(10).join(relationships) if relationships else "No se detectaron relaciones"}

PROBLEMAS DETECTADOS
Alta severidad ({len(anomalies_by_severity['high'])}):
{chr(10).join(anomalies_by_severity['high']) if anomalies_by_severity['high'] else "Ninguno"}

Media severidad ({len(anomalies_by_severity['medium'])}):
{chr(10).join(anomalies_by_severity['medium'][:5]) if anomalies_by_severity['medium'] else "Ninguno"}

Baja severidad ({len(anomalies_by_severity['low'])}):
{len(anomalies_by_severity['low'])} problemas menores (principalmente índices no utilizados)

Índices no utilizados: {len(unused_indexes)}
Índices faltantes detectados: {len(missing_indexes)}

---

TU TAREA: Genera un informe COMPLETO y EXPLICATIVO en texto plano.

IMPORTANTE:
- NO uses emojis bajo ninguna circunstancia
- NO uses formato markdown (no ##, no **, no -, no ```)
- Escribe en párrafos claros y bien estructurados
- Usa MAYÚSCULAS para los títulos de sección
- Usa sangrías y espacios en blanco para organizar el contenido
- Cada sección debe tener un párrafo introductorio que explique de qué trata

El informe debe incluir las siguientes secciones:

RESUMEN EJECUTIVO
Escribe 2-3 párrafos que respondan: ¿Qué tipo de base de datos es esta? (e-commerce, foro, logs, etc.), ¿Está en buen estado general o hay problemas urgentes?, ¿Qué debería hacer el equipo primero?

EXPLICACIÓN DE LA ESTRUCTURA
Empieza con un párrafo introductorio explicando cómo está organizada la base de datos. Luego describe las tablas principales y su propósito probable. Explica las relaciones entre tablas de forma simple. Menciona si hay tablas que parecen no usarse o estar mal diseñadas.

PROBLEMAS ENCONTRADOS Y SOLUCIONES
Empieza explicando cuántos problemas se encontraron y su distribución por severidad. Para CADA problema importante incluye: una explicación de QUÉ es el problema en términos simples, POR QUÉ es un problema (impacto en rendimiento), la solución EXACTA (comando SQL entre corchetes), y una explicación de QUÉ hace ese comando y si es seguro ejecutarlo.

PLAN DE ACCIÓN PASO A PASO
Introduce esta sección explicando la estrategia recomendada. Luego enumera los pasos que debe seguir el equipo, en orden de prioridad, explicando el porqué de cada uno.

ADVERTENCIAS Y CONSIDERACIONES
Explica los riesgos potenciales al hacer estos cambios. Indica qué hay que tener en cuenta antes de ejecutar los comandos. Recomienda cuándo es mejor hacer estos cambios (horario de bajo tráfico).

Usa un tono profesional pero accesible. Explica la jerga técnica cuando la uses."""

        state_db.log(
            "explorer", "INFO",
            "Calling LLM for comprehensive database explanation...",
            database_id=state["database_id"]
        )

        response = llm.invoke([
            SystemMessage(content="""Eres un DBA senior de PostgreSQL con 15 años de experiencia.
Tu especialidad es explicar conceptos técnicos complejos de forma clara y accionable.
Siempre das comandos SQL exactos y explicas los riesgos de cada acción.
Tu objetivo es que después de leer tu informe, el equipo sepa EXACTAMENTE qué hacer.

REGLAS DE FORMATO ESTRICTAS:
- NUNCA uses emojis
- NUNCA uses formato markdown como ##, **, -, ```, etc.
- Escribe títulos en MAYÚSCULAS sin ningún símbolo
- Usa párrafos completos y bien desarrollados
- Los comandos SQL van entre corchetes: [SELECT * FROM tabla]
- Separa secciones con líneas en blanco"""),
            HumanMessage(content=prompt)
        ])

        state_db.log(
            "explorer", "INFO",
            f"LLM comprehensive analysis complete: {len(response.content)} chars",
            database_id=state["database_id"]
        )

        state["llm_insights"] = response.content
        return state

    except Exception as e:
        state_db.log(
            "explorer", "WARNING",
            f"LLM analysis failed (continuing without): {str(e)}",
            database_id=state["database_id"]
        )
        state["llm_insights"] = None
        return state


def generate_work_plan(state: ExplorerState) -> ExplorerState:
    """Generate a prioritized work plan for other agents."""
    if state.get("error"):
        return state

    classifications = state["table_classifications"]
    anomalies = state["anomalies"]

    work_plan = {
        "observer_priorities": [],
        "architect_tasks": [],
        "gardener_tasks": [],
        "llm_recommendations": state.get("llm_insights", ""),
        "summary": {}
    }

    # Observer priorities: Focus on high-criticality tables
    high_crit_tables = [
        {"table": name, "reason": "High criticality " + info["type"]}
        for name, info in classifications.items()
        if info["criticality"] == "high"
    ]
    work_plan["observer_priorities"] = high_crit_tables[:10]  # Top 10

    # Architect tasks: Based on anomalies
    for anomaly in anomalies:
        if anomaly["severity"] in ("high", "medium"):
            work_plan["architect_tasks"].append({
                "type": anomaly["type"],
                "table": anomaly["table"],
                "description": anomaly["description"],
                "recommendation": anomaly.get("recommendation", "")
            })

    # Gardener tasks: Unused indexes to review, potential maintenance
    for anomaly in anomalies:
        if anomaly["type"] in ("unused_index", "redundant_index"):
            work_plan["gardener_tasks"].append({
                "type": anomaly["type"],
                "table": anomaly["table"],
                "index": anomaly.get("index") or anomaly.get("indexes", [None])[0],
                "action": "review_for_removal"
            })

    # Summary statistics
    work_plan["summary"] = {
        "total_tables": len(classifications),
        "high_criticality_tables": len([c for c in classifications.values() if c["criticality"] == "high"]),
        "total_anomalies": len(anomalies),
        "high_severity_anomalies": len([a for a in anomalies if a["severity"] == "high"]),
        "medium_severity_anomalies": len([a for a in anomalies if a["severity"] == "medium"]),
    }

    return {**state, "work_plan": work_plan}


def generate_report(state: ExplorerState) -> ExplorerState:
    """Generate a human-readable plain text report with AI analysis first."""
    if state.get("error"):
        return state

    metadata = state["metadata"]
    classifications = state["table_classifications"]
    anomalies = state["anomalies"]
    work_plan = state["work_plan"]
    graph = state["dependency_graph"]

    # Build plain text report - AI ANALYSIS FIRST
    lines = []
    lines.append("=" * 60)
    lines.append("ANALISIS DE BASE DE DATOS")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Base de datos: {metadata['database_size']['database_name']}")
    lines.append(f"Tamaño: {metadata['database_size']['size_human']}")
    lines.append("")

    # AI Analysis FIRST - This is the main content
    if state.get("llm_insights"):
        lines.append("-" * 60)
        lines.append("")
        lines.append(state["llm_insights"])
        lines.append("")
        lines.append("-" * 60)

    # Technical Details Section
    lines.append("")
    lines.append("=" * 60)
    lines.append("DATOS TECNICOS DETALLADOS")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Esta seccion contiene los datos tecnicos completos extraidos")
    lines.append("durante el analisis automatizado de la base de datos.")
    lines.append("")

    # Summary stats
    lines.append("ESTADISTICAS GENERALES")
    lines.append("-" * 30)
    lines.append(f"  Tablas: {len(metadata['tables'])}")
    lines.append(f"  Indices: {len(metadata['indexes'])}")
    lines.append(f"  Foreign Keys: {len(metadata['foreign_keys'])}")
    lines.append(f"  Relaciones inferidas: {len([e for e in graph['edges'] if e['type'] == 'inferred'])}")
    lines.append("")

    # Table Classifications
    by_type = {}
    for name, info in classifications.items():
        t = info["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(info)

    lines.append("CLASIFICACION DE TABLAS")
    lines.append("-" * 30)
    lines.append("")
    lines.append("Las tablas han sido clasificadas automaticamente segun sus")
    lines.append("caracteristicas, relaciones y patrones de uso detectados.")
    lines.append("")

    for table_type, tables in sorted(by_type.items()):
        lines.append(f"  {table_type.upper()} ({len(tables)} tablas)")
        lines.append("  " + "-" * 25)
        for t in sorted(tables, key=lambda x: x["row_count"], reverse=True)[:10]:
            size = metadata_extractor._bytes_to_human(t["total_size_bytes"])
            lines.append(f"    {t['name']}: {t['row_count']:,} filas, {size}, {t['index_count']} indices")
        lines.append("")

    # Anomalies details
    lines.append("LISTA COMPLETA DE ANOMALIAS")
    lines.append("-" * 30)
    lines.append("")
    lines.append("Las anomalias son problemas estructurales detectados que")
    lines.append("pueden afectar el rendimiento o la integridad de la base de datos.")
    lines.append("")

    if anomalies:
        high = [a for a in anomalies if a["severity"] == "high"]
        medium = [a for a in anomalies if a["severity"] == "medium"]
        low = [a for a in anomalies if a["severity"] == "low"]

        if high:
            lines.append("  ALTA SEVERIDAD")
            lines.append("  " + "-" * 20)
            for a in high:
                lines.append(f"    Tabla: {a['table']}")
                lines.append(f"    Problema: {a['description']}")
                if a.get("recommendation"):
                    lines.append(f"    Solucion: [{a['recommendation']}]")
                lines.append("")

        if medium:
            lines.append("  MEDIA SEVERIDAD")
            lines.append("  " + "-" * 20)
            for a in medium:
                lines.append(f"    Tabla: {a['table']}")
                lines.append(f"    Problema: {a['description']}")
                lines.append("")

        if low:
            lines.append(f"  BAJA SEVERIDAD ({len(low)} problemas)")
            lines.append("  " + "-" * 20)
            for a in low[:10]:
                lines.append(f"    {a['table']}: {a['description']}")
            if len(low) > 10:
                lines.append(f"    ... y {len(low) - 10} mas")
            lines.append("")
    else:
        lines.append("  No se detectaron anomalias.")
        lines.append("")

    # PostgreSQL Settings
    lines.append("CONFIGURACION DE POSTGRESQL")
    lines.append("-" * 30)
    lines.append("")
    lines.append("Parametros de configuracion relevantes para el rendimiento.")
    lines.append("")
    for name, info in metadata["settings"].items():
        val = f"{info['value']} {info['unit'] or ''}".strip()
        lines.append(f"  {name}: {val}")
        if info['description']:
            lines.append(f"    ({info['description'][:60]}...)")
    lines.append("")

    lines.append("=" * 60)
    lines.append("FIN DEL REPORTE")
    lines.append("=" * 60)

    report_text = "\n".join(lines)
    return {**state, "markdown_report": report_text}


def save_results(state: ExplorerState) -> ExplorerState:
    """Save analysis results to the state database."""
    if state.get("error"):
        return state

    # Prepare JSON result
    result_json = {
        "metadata_summary": {
            "tables": len(state["metadata"]["tables"]),
            "indexes": len(state["metadata"]["indexes"]),
            "foreign_keys": len(state["metadata"]["foreign_keys"]),
            "database_size": state["metadata"]["database_size"],
        },
        "dependency_graph": state["dependency_graph"],
        "table_classifications": state["table_classifications"],
        "anomalies": state["anomalies"],
        "work_plan": state["work_plan"],
    }

    # Save to database
    state_db.save_analysis(
        database_id=state["database_id"],
        agent="explorer",
        analysis_type="full_analysis",
        result_json=result_json,
        result_markdown=state["markdown_report"]
    )

    state_db.log(
        "explorer", "INFO",
        "Analysis complete and saved",
        database_id=state["database_id"]
    )

    return state


def should_continue(state: ExplorerState) -> str:
    """Determine if we should continue or end due to error."""
    if state.get("error"):
        return "error"
    return "continue"


# Build the LangGraph workflow
def create_explorer_graph():
    """Create the Explorer agent workflow graph."""
    workflow = StateGraph(ExplorerState)

    # Add nodes
    workflow.add_node("extract_metadata", extract_metadata)
    workflow.add_node("build_dependency_graph", build_dependency_graph)
    workflow.add_node("classify_tables", classify_tables)
    workflow.add_node("detect_anomalies", detect_anomalies)
    workflow.add_node("analyze_with_llm", analyze_with_llm)
    workflow.add_node("generate_work_plan", generate_work_plan)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("save_results", save_results)

    # Set entry point
    workflow.set_entry_point("extract_metadata")

    # Add edges
    workflow.add_conditional_edges(
        "extract_metadata",
        should_continue,
        {"continue": "build_dependency_graph", "error": END}
    )
    workflow.add_edge("build_dependency_graph", "classify_tables")
    workflow.add_edge("classify_tables", "detect_anomalies")
    workflow.add_edge("detect_anomalies", "analyze_with_llm")
    workflow.add_edge("analyze_with_llm", "generate_work_plan")
    workflow.add_edge("generate_work_plan", "generate_report")
    workflow.add_edge("generate_report", "save_results")
    workflow.add_edge("save_results", END)

    return workflow.compile()


# Main function to run the explorer
async def run_explorer_agent(database_id: int, schema: str = "public") -> Dict[str, Any]:
    """
    Run the Explorer agent on a database.

    Args:
        database_id: ID of the database in the state DB
        schema: PostgreSQL schema to analyze (default: public)

    Returns:
        Analysis results including classifications, anomalies, and work plan
    """
    state_db.log("explorer", "INFO", f"Starting analysis for database {database_id}")

    # Create initial state
    initial_state: ExplorerState = {
        "database_id": database_id,
        "schema": schema,
        "metadata": {},
        "dependency_graph": {},
        "table_classifications": {},
        "anomalies": [],
        "llm_insights": None,
        "work_plan": {},
        "markdown_report": "",
        "error": None,
    }

    # Create and run the graph
    graph = create_explorer_graph()
    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        return {"error": final_state["error"]}

    return {
        "status": "success",
        "summary": final_state["work_plan"]["summary"],
        "anomalies_count": len(final_state["anomalies"]),
        "high_severity_count": len([a for a in final_state["anomalies"] if a["severity"] == "high"]),
        "markdown_report": final_state["markdown_report"],
    }
