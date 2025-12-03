"""
PG Index Agents - Agente Partitioner
https://github.com/686f6c61/pg-index-agents

El agente Partitioner analiza tablas grandes y recomienda estrategias de
particionamiento. Opera exclusivamente en modo observacion debido a la
naturaleza de alto riesgo de las operaciones de particionamiento.

Funciones principales:
1. Analizar tablas grandes como candidatas a particionamiento
2. Detectar columnas adecuadas para partition keys (timestamps, enums)
3. Analizar patrones de queries para validar la seleccion de partition key
4. Generar recomendaciones de particionamiento con planes de migracion
5. Operar siempre en modo solo lectura (nunca ejecuta cambios)

El Partitioner considera multiples factores para sus recomendaciones:
- Tamano de tabla (minimo 100K filas o 50MB)
- Cardinalidad de columnas candidatas
- Patrones de acceso detectados por el Observer
- Distribucion de datos en columnas temporales

Tipos de particionamiento soportados:
- RANGE: Para datos temporales (fecha, timestamp)
- LIST: Para enumeraciones de baja cardinalidad
- HASH: Para distribucion uniforme

Autor: 686f6c61
Licencia: MIT
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import text

from core.database import db_manager
from core.state import state_db
from core.llm import get_llm_for_analysis


# Minimum row count to consider a table for partitioning
MIN_ROWS_FOR_PARTITIONING = 100_000  # 100k rows
# Minimum table size in bytes (50MB)
MIN_SIZE_FOR_PARTITIONING = 50 * 1024 * 1024


class PartitionCandidate(TypedDict):
    """A table that is a candidate for partitioning."""
    table_name: str
    row_count: int
    size_bytes: int
    size_human: str
    partition_columns: List[Dict[str, Any]]
    recommended_strategy: Optional[str]
    recommendation_confidence: float


class PartitionRecommendation(TypedDict):
    """A detailed partitioning recommendation."""
    table_name: str
    partition_key: str
    partition_type: str  # range, list, hash
    partition_interval: Optional[str]  # monthly, yearly, etc.
    estimated_partitions: int
    benefits: List[str]
    risks: List[str]
    migration_steps: List[str]
    sql_commands: List[str]
    confidence: float


class PartitionerState(TypedDict):
    """State for the Partitioner agent workflow."""
    database_id: int
    schema: str
    large_tables: List[Dict[str, Any]]
    partition_candidates: List[PartitionCandidate]
    query_patterns: Dict[str, List[Dict[str, Any]]]
    existing_partitions: List[Dict[str, Any]]
    recommendations: List[PartitionRecommendation]
    llm_analysis: Optional[str]
    markdown_report: str
    error: Optional[str]


def find_large_tables(state: PartitionerState) -> PartitionerState:
    """Find tables that are large enough to benefit from partitioning."""
    if state.get("error"):
        return state

    try:
        with db_manager.read_connection() as conn:
            result = conn.execute(text("""
                SELECT
                    t.relname AS table_name,
                    pg_total_relation_size(t.oid) AS total_size_bytes,
                    pg_size_pretty(pg_total_relation_size(t.oid)) AS size_human,
                    s.n_live_tup AS row_count,
                    s.seq_scan AS sequential_scans,
                    s.idx_scan AS index_scans,
                    s.n_tup_ins AS inserts,
                    s.n_tup_upd AS updates,
                    s.n_tup_del AS deletes
                FROM pg_class t
                JOIN pg_namespace n ON n.oid = t.relnamespace
                LEFT JOIN pg_stat_user_tables s ON s.relid = t.oid
                WHERE n.nspname = :schema
                AND t.relkind = 'r'  -- Regular tables only
                AND pg_total_relation_size(t.oid) > :min_size
                ORDER BY pg_total_relation_size(t.oid) DESC
                LIMIT 20
            """), {"schema": state["schema"], "min_size": MIN_SIZE_FOR_PARTITIONING})

            large_tables = []
            for row in result:
                large_tables.append({
                    "table_name": row[0],
                    "total_size_bytes": row[1],
                    "size_human": row[2],
                    "row_count": row[3] or 0,
                    "sequential_scans": row[4] or 0,
                    "index_scans": row[5] or 0,
                    "inserts": row[6] or 0,
                    "updates": row[7] or 0,
                    "deletes": row[8] or 0,
                })

            state_db.log(
                "partitioner", "INFO",
                f"Found {len(large_tables)} large tables for partitioning analysis",
                database_id=state["database_id"]
            )

            return {**state, "large_tables": large_tables}

    except Exception as e:
        state_db.log("partitioner", "ERROR", f"Failed to find large tables: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def analyze_partition_columns(state: PartitionerState) -> PartitionerState:
    """Analyze columns that could serve as partition keys."""
    if state.get("error"):
        return state

    large_tables = state["large_tables"]
    if not large_tables:
        return {**state, "partition_candidates": []}

    candidates = []

    try:
        with db_manager.read_connection() as conn:
            for table_info in large_tables:
                table_name = table_info["table_name"]

                # Get columns with statistics
                result = conn.execute(text("""
                    SELECT
                        a.attname AS column_name,
                        pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                        s.n_distinct,
                        s.null_frac,
                        s.most_common_vals::text,
                        s.correlation
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_stats s ON s.tablename = c.relname
                        AND s.attname = a.attname
                        AND s.schemaname = n.nspname
                    WHERE n.nspname = :schema
                    AND c.relname = :table_name
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                    ORDER BY a.attnum
                """), {"schema": state["schema"], "table_name": table_name})

                partition_columns = []
                for row in result:
                    col_name = row[0]
                    data_type = row[1]
                    n_distinct = row[2]
                    null_frac = row[3]
                    most_common = row[4]
                    correlation = row[5]

                    score = 0
                    reasons = []
                    partition_type = None
                    interval = None

                    # Timestamp/date columns - excellent for RANGE partitioning
                    if any(t in data_type.lower() for t in ['timestamp', 'date']):
                        score += 80
                        reasons.append("Columna temporal ideal para particion por rango")
                        partition_type = "range"

                        # Check naming patterns
                        if any(p in col_name.lower() for p in ['created', 'inserted', 'logged', 'timestamp']):
                            score += 15
                            reasons.append("Nombre sugiere datos de insercion cronologica")
                            interval = "monthly"
                        elif any(p in col_name.lower() for p in ['updated', 'modified']):
                            score += 5
                            reasons.append("Columna de actualizacion (menos ideal)")

                    # Low cardinality columns - good for LIST partitioning
                    elif n_distinct and 2 <= n_distinct <= 20:
                        score += 60
                        reasons.append(f"Baja cardinalidad ({int(n_distinct)} valores distintos)")
                        partition_type = "list"

                        if any(p in col_name.lower() for p in ['status', 'type', 'state', 'category', 'region']):
                            score += 20
                            reasons.append("Nombre sugiere categorias fijas")

                    # Integer columns with good distribution - possible for HASH
                    elif 'integer' in data_type.lower() or 'bigint' in data_type.lower():
                        if col_name.lower().endswith('_id') and col_name.lower() != 'id':
                            score += 30
                            reasons.append("Columna FK puede distribuir por HASH")
                            partition_type = "hash"

                    # Penalize columns with high nulls
                    if null_frac and null_frac > 0.3:
                        score -= 20
                        reasons.append(f"Alto porcentaje de NULLs ({null_frac*100:.0f}%)")

                    # Only include columns with positive scores
                    if score > 0:
                        partition_columns.append({
                            "column_name": col_name,
                            "data_type": data_type,
                            "score": score,
                            "reasons": reasons,
                            "suggested_type": partition_type,
                            "suggested_interval": interval,
                            "n_distinct": n_distinct,
                            "null_fraction": null_frac,
                        })

                # Sort by score
                partition_columns.sort(key=lambda x: x["score"], reverse=True)

                if partition_columns:
                    best_col = partition_columns[0]
                    candidates.append({
                        "table_name": table_name,
                        "row_count": table_info["row_count"],
                        "size_bytes": table_info["total_size_bytes"],
                        "size_human": table_info["size_human"],
                        "partition_columns": partition_columns[:5],  # Top 5
                        "recommended_strategy": best_col["suggested_type"],
                        "recommendation_confidence": min(best_col["score"] / 100, 1.0),
                    })

        state_db.log(
            "partitioner", "INFO",
            f"Found {len(candidates)} partition candidates",
            database_id=state["database_id"]
        )

        return {**state, "partition_candidates": candidates}

    except Exception as e:
        state_db.log("partitioner", "ERROR", f"Failed to analyze partition columns: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "error": str(e)}


def analyze_query_patterns(state: PartitionerState) -> PartitionerState:
    """Analyze query patterns to validate partition key selection."""
    if state.get("error"):
        return state

    candidates = state["partition_candidates"]
    if not candidates:
        return {**state, "query_patterns": {}}

    query_patterns = {}

    try:
        with db_manager.read_connection() as conn:
            # Check if pg_stat_statements is available
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                )
            """))
            has_pg_stat = result.scalar()

            if has_pg_stat:
                for candidate in candidates:
                    table_name = candidate["table_name"]

                    # Get queries that reference this table
                    result = conn.execute(text("""
                        SELECT
                            query,
                            calls,
                            mean_exec_time,
                            total_exec_time
                        FROM pg_stat_statements
                        WHERE query ILIKE :pattern
                        AND calls > 10
                        ORDER BY total_exec_time DESC
                        LIMIT 10
                    """), {"pattern": f"%{table_name}%"})

                    patterns = []
                    for row in result:
                        query = row[0]

                        # Extract WHERE columns
                        where_columns = []
                        query_lower = query.lower()

                        for col in candidate["partition_columns"]:
                            col_name = col["column_name"].lower()
                            # Check if column appears in WHERE clause
                            if f" {col_name} " in query_lower or f".{col_name}" in query_lower:
                                if " where " in query_lower and col_name in query_lower.split(" where ")[1]:
                                    where_columns.append(col_name)

                        patterns.append({
                            "query_sample": query[:200],
                            "calls": row[1],
                            "mean_time_ms": row[2],
                            "total_time_ms": row[3],
                            "uses_partition_column": where_columns,
                        })

                    query_patterns[table_name] = patterns

                state_db.log(
                    "partitioner", "INFO",
                    f"Analyzed query patterns for {len(query_patterns)} tables",
                    database_id=state["database_id"]
                )
            else:
                state_db.log(
                    "partitioner", "WARNING",
                    "pg_stat_statements not available - skipping query pattern analysis",
                    database_id=state["database_id"]
                )

        return {**state, "query_patterns": query_patterns}

    except Exception as e:
        state_db.log("partitioner", "WARNING", f"Query pattern analysis failed: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "query_patterns": {}}


def check_existing_partitions(state: PartitionerState) -> PartitionerState:
    """Check for existing partitioned tables."""
    if state.get("error"):
        return state

    try:
        with db_manager.read_connection() as conn:
            result = conn.execute(text("""
                SELECT
                    c.relname AS table_name,
                    CASE p.partstrat
                        WHEN 'r' THEN 'range'
                        WHEN 'l' THEN 'list'
                        WHEN 'h' THEN 'hash'
                    END AS partition_strategy,
                    array_agg(a.attname) AS partition_columns,
                    (SELECT count(*)
                     FROM pg_inherits i
                     WHERE i.inhparent = c.oid) AS partition_count
                FROM pg_partitioned_table p
                JOIN pg_class c ON c.oid = p.partrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(p.partattrs)
                WHERE n.nspname = :schema
                GROUP BY c.relname, p.partstrat, c.oid
            """), {"schema": state["schema"]})

            existing = []
            for row in result:
                existing.append({
                    "table_name": row[0],
                    "strategy": row[1],
                    "columns": row[2],
                    "partition_count": row[3],
                })

            state_db.log(
                "partitioner", "INFO",
                f"Found {len(existing)} existing partitioned tables",
                database_id=state["database_id"]
            )

            return {**state, "existing_partitions": existing}

    except Exception as e:
        state_db.log("partitioner", "WARNING", f"Failed to check existing partitions: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "existing_partitions": []}


def generate_recommendations(state: PartitionerState) -> PartitionerState:
    """Generate detailed partitioning recommendations."""
    if state.get("error"):
        return state

    candidates = state["partition_candidates"]
    query_patterns = state["query_patterns"]
    existing = {p["table_name"] for p in state["existing_partitions"]}

    recommendations = []

    for candidate in candidates:
        table_name = candidate["table_name"]

        # Skip already partitioned tables
        if table_name in existing:
            continue

        # Skip low confidence candidates
        if candidate["recommendation_confidence"] < 0.5:
            continue

        best_col = candidate["partition_columns"][0]
        partition_type = best_col["suggested_type"]
        partition_col = best_col["column_name"]

        # Validate with query patterns
        patterns = query_patterns.get(table_name, [])
        queries_use_column = sum(
            1 for p in patterns
            if partition_col.lower() in [c.lower() for c in p.get("uses_partition_column", [])]
        )

        confidence = candidate["recommendation_confidence"]
        if patterns and queries_use_column > 0:
            confidence = min(confidence + 0.2, 1.0)
        elif patterns and queries_use_column == 0:
            confidence = max(confidence - 0.3, 0.3)

        benefits = []
        risks = []
        migration_steps = []
        sql_commands = []
        estimated_partitions = 0

        if partition_type == "range" and best_col["suggested_interval"] == "monthly":
            benefits = [
                "Partition pruning eliminara particiones completas en consultas con filtro de fecha",
                "Las consultas que filtran por rango de fechas seran significativamente mas rapidas",
                "Facilita el archivado de datos antiguos (detach partition)",
                "VACUUM y mantenimiento pueden ejecutarse por particion",
            ]
            risks = [
                "Requiere migracion de datos existentes",
                "Consultas sin filtro de fecha escanearan todas las particiones",
                "Necesita proceso automatizado para crear particiones futuras",
                "Foreign keys hacia esta tabla requieren ajustes",
            ]
            estimated_partitions = 24  # 2 years of monthly partitions

            migration_steps = [
                "1. Crear backup completo de la tabla",
                "2. Crear nueva tabla particionada con el mismo esquema",
                "3. Crear particiones para el rango de datos existente",
                "4. Migrar datos usando INSERT...SELECT con batching",
                "5. Verificar integridad de datos",
                "6. Renombrar tablas (swap atomico)",
                "7. Actualizar foreign keys si existen",
                "8. Configurar creacion automatica de particiones futuras",
            ]

            sql_commands = [
                f"-- Crear tabla particionada",
                f"CREATE TABLE {table_name}_partitioned (",
                f"    LIKE {table_name} INCLUDING ALL",
                f") PARTITION BY RANGE ({partition_col});",
                f"",
                f"-- Crear particion para mes actual",
                f"CREATE TABLE {table_name}_y2024m01 PARTITION OF {table_name}_partitioned",
                f"    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');",
                f"",
                f"-- Migrar datos (ejecutar en lotes)",
                f"INSERT INTO {table_name}_partitioned SELECT * FROM {table_name};",
                f"",
                f"-- Swap atomico",
                f"ALTER TABLE {table_name} RENAME TO {table_name}_old;",
                f"ALTER TABLE {table_name}_partitioned RENAME TO {table_name};",
            ]

        elif partition_type == "list":
            n_values = int(best_col.get("n_distinct", 5))
            benefits = [
                f"Partition pruning para consultas con filtro en '{partition_col}'",
                "Cada particion contendra un subconjunto logico de datos",
                "Facilita el mantenimiento por categoria/tipo",
            ]
            risks = [
                "Nuevos valores requieren crear nuevas particiones",
                "Distribucion desigual si algunos valores tienen mas datos",
            ]
            estimated_partitions = n_values

            migration_steps = [
                "1. Identificar todos los valores distintos actuales",
                "2. Crear tabla particionada",
                "3. Crear particion para cada valor",
                "4. Crear particion DEFAULT para valores futuros",
                "5. Migrar datos y hacer swap",
            ]

            sql_commands = [
                f"CREATE TABLE {table_name}_partitioned (",
                f"    LIKE {table_name} INCLUDING ALL",
                f") PARTITION BY LIST ({partition_col});",
                f"",
                f"-- Crear particion por cada valor",
                f"CREATE TABLE {table_name}_value1 PARTITION OF {table_name}_partitioned",
                f"    FOR VALUES IN ('value1');",
                f"",
                f"-- Particion default para nuevos valores",
                f"CREATE TABLE {table_name}_default PARTITION OF {table_name}_partitioned",
                f"    DEFAULT;",
            ]

        elif partition_type == "hash":
            benefits = [
                "Distribucion uniforme de datos entre particiones",
                "Ideal para tablas con patrones de acceso uniformes",
                "Paralelismo en consultas que escanean toda la tabla",
            ]
            risks = [
                "No permite partition pruning eficiente",
                "Solo util si el patron de acceso es uniforme",
                "Numero de particiones fijo (potencia de 2 recomendado)",
            ]
            estimated_partitions = 8

            sql_commands = [
                f"CREATE TABLE {table_name}_partitioned (",
                f"    LIKE {table_name} INCLUDING ALL",
                f") PARTITION BY HASH ({partition_col});",
                f"",
                f"-- Crear 8 particiones",
                f"CREATE TABLE {table_name}_p0 PARTITION OF {table_name}_partitioned",
                f"    FOR VALUES WITH (MODULUS 8, REMAINDER 0);",
                f"-- ... repetir para particiones 1-7",
            ]

        recommendations.append({
            "table_name": table_name,
            "partition_key": partition_col,
            "partition_type": partition_type,
            "partition_interval": best_col.get("suggested_interval"),
            "estimated_partitions": estimated_partitions,
            "benefits": benefits,
            "risks": risks,
            "migration_steps": migration_steps,
            "sql_commands": sql_commands,
            "confidence": confidence,
            "query_validation": {
                "queries_analyzed": len(patterns),
                "queries_using_partition_key": queries_use_column,
            },
        })

    # Sort by confidence
    recommendations.sort(key=lambda x: x["confidence"], reverse=True)

    state_db.log(
        "partitioner", "INFO",
        f"Generated {len(recommendations)} partition recommendations",
        database_id=state["database_id"]
    )

    return {**state, "recommendations": recommendations}


def analyze_with_llm(state: PartitionerState) -> PartitionerState:
    """Use LLM to generate a comprehensive partitioning analysis."""
    if state.get("error"):
        return state

    recommendations = state["recommendations"]
    if not recommendations:
        return {**state, "llm_analysis": None}

    try:
        llm = get_llm_for_analysis()

        # Build context
        tables_info = []
        for rec in recommendations[:5]:  # Top 5
            tables_info.append(f"""
Tabla: {rec['table_name']}
- Columna de particion recomendada: {rec['partition_key']}
- Tipo de particion: {rec['partition_type']}
- Confianza: {rec['confidence']*100:.0f}%
- Beneficios esperados: {', '.join(rec['benefits'][:2])}
- Riesgos: {', '.join(rec['risks'][:2])}
""")

        existing_info = []
        for p in state["existing_partitions"][:5]:
            existing_info.append(f"- {p['table_name']}: {p['strategy']} por {', '.join(p['columns'])} ({p['partition_count']} particiones)")

        prompt = f"""Analiza las siguientes recomendaciones de particionamiento para una base de datos PostgreSQL.

TABLAS GRANDES ANALIZADAS: {len(state['large_tables'])}
CANDIDATAS PARA PARTICIONAMIENTO: {len(state['partition_candidates'])}
TABLAS YA PARTICIONADAS: {len(state['existing_partitions'])}

TABLAS YA PARTICIONADAS:
{chr(10).join(existing_info) if existing_info else 'Ninguna'}

RECOMENDACIONES PRINCIPALES:
{chr(10).join(tables_info)}

TU TAREA:
1. EVALUACION GENERAL: Evalua si esta base de datos se beneficiaria del particionamiento
2. PRIORIDADES: Indica que tabla deberia particionarse primero y por que
3. ADVERTENCIAS: Menciona casos donde el particionamiento NO seria beneficioso
4. PLAN DE IMPLEMENTACION: Sugiere un orden y enfoque para implementar estas recomendaciones
5. CONSIDERACIONES DE PRODUCCION: Indica precauciones para ejecutar en produccion

IMPORTANTE:
- NO uses emojis
- NO uses formato markdown
- Escribe en parrafos claros
- Usa MAYUSCULAS para titulos de seccion
- Se especifico y practico en las recomendaciones"""

        response = llm.invoke([
            SystemMessage(content="""Eres un DBA experto en PostgreSQL especializado en particionamiento de tablas.
Tienes amplia experiencia migrando tablas a esquemas particionados en produccion sin downtime.
Siempre priorizas la seguridad de los datos y explicas los riesgos claramente.

REGLAS DE FORMATO:
- NUNCA uses emojis
- NO uses formato markdown
- Escribe en parrafos claros
- Usa MAYUSCULAS para titulos"""),
            HumanMessage(content=prompt)
        ])

        state_db.log(
            "partitioner", "INFO",
            f"LLM analysis complete: {len(response.content)} chars",
            database_id=state["database_id"]
        )

        return {**state, "llm_analysis": response.content}

    except Exception as e:
        state_db.log("partitioner", "WARNING", f"LLM analysis failed: {str(e)}",
                    database_id=state["database_id"])
        return {**state, "llm_analysis": None}


def generate_report(state: PartitionerState) -> PartitionerState:
    """Generate a comprehensive plain text report."""
    if state.get("error"):
        return state

    lines = []
    lines.append("=" * 60)
    lines.append("ANALISIS DE PARTICIONAMIENTO")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Summary
    lines.append("RESUMEN")
    lines.append("-" * 30)
    lines.append(f"  Tablas grandes analizadas: {len(state['large_tables'])}")
    lines.append(f"  Candidatas para particionamiento: {len(state['partition_candidates'])}")
    lines.append(f"  Recomendaciones generadas: {len(state['recommendations'])}")
    lines.append(f"  Tablas ya particionadas: {len(state['existing_partitions'])}")
    lines.append("")

    # LLM Analysis first
    if state.get("llm_analysis"):
        lines.append("-" * 60)
        lines.append("")
        lines.append(state["llm_analysis"])
        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    # Existing partitions
    if state["existing_partitions"]:
        lines.append("TABLAS YA PARTICIONADAS")
        lines.append("-" * 30)
        for p in state["existing_partitions"]:
            lines.append(f"  {p['table_name']}")
            lines.append(f"    Estrategia: {p['strategy']}")
            lines.append(f"    Columnas: {', '.join(p['columns'])}")
            lines.append(f"    Particiones: {p['partition_count']}")
            lines.append("")

    # Recommendations
    lines.append("RECOMENDACIONES DE PARTICIONAMIENTO")
    lines.append("-" * 30)
    lines.append("")

    if state["recommendations"]:
        for i, rec in enumerate(state["recommendations"], 1):
            lines.append(f"  {i}. {rec['table_name'].upper()}")
            lines.append("  " + "-" * 25)
            lines.append(f"    Columna de particion: {rec['partition_key']}")
            lines.append(f"    Tipo: {rec['partition_type'].upper()}")
            if rec.get("partition_interval"):
                lines.append(f"    Intervalo: {rec['partition_interval']}")
            lines.append(f"    Particiones estimadas: {rec['estimated_partitions']}")
            lines.append(f"    Confianza: {rec['confidence']*100:.0f}%")

            if rec.get("query_validation"):
                qv = rec["query_validation"]
                lines.append(f"    Validacion de queries: {qv['queries_using_partition_key']}/{qv['queries_analyzed']} usan la columna")

            lines.append("")
            lines.append("    BENEFICIOS:")
            for benefit in rec["benefits"]:
                lines.append(f"      - {benefit}")

            lines.append("")
            lines.append("    RIESGOS:")
            for risk in rec["risks"]:
                lines.append(f"      - {risk}")

            lines.append("")
            lines.append("    PASOS DE MIGRACION:")
            for step in rec["migration_steps"]:
                lines.append(f"      {step}")

            lines.append("")
            lines.append("    COMANDOS SQL:")
            for cmd in rec["sql_commands"]:
                lines.append(f"      {cmd}")

            lines.append("")
            lines.append("")
    else:
        lines.append("  No se encontraron tablas candidatas para particionamiento.")
        lines.append("  Posibles razones:")
        lines.append("    - Las tablas no son suficientemente grandes (< 50MB)")
        lines.append("    - No hay columnas adecuadas para partition key")
        lines.append("    - Las tablas ya estan particionadas")
        lines.append("")

    # Large tables analyzed
    lines.append("TABLAS GRANDES ANALIZADAS")
    lines.append("-" * 30)
    for table in state["large_tables"][:10]:
        lines.append(f"  {table['table_name']}: {table['size_human']}, {table['row_count']:,} filas")
        lines.append(f"    Seq scans: {table['sequential_scans']:,}, Idx scans: {table['index_scans']:,}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("FIN DEL REPORTE")
    lines.append("=" * 60)

    report = "\n".join(lines)
    return {**state, "markdown_report": report}


def save_results(state: PartitionerState) -> PartitionerState:
    """Save analysis results to the database."""
    if state.get("error"):
        return state

    result_json = {
        "large_tables": state["large_tables"],
        "partition_candidates": state["partition_candidates"],
        "existing_partitions": state["existing_partitions"],
        "recommendations": state["recommendations"],
        "query_patterns_analyzed": len(state["query_patterns"]),
    }

    state_db.save_analysis(
        database_id=state["database_id"],
        agent="partitioner",
        analysis_type="partition_analysis",
        result_json=result_json,
        result_markdown=state["markdown_report"]
    )

    state_db.log(
        "partitioner", "INFO",
        f"Analysis complete: {len(state['recommendations'])} recommendations saved",
        database_id=state["database_id"]
    )

    return state


def should_continue(state: PartitionerState) -> str:
    """Determine if we should continue or end due to error."""
    if state.get("error"):
        return "error"
    return "continue"


def create_partitioner_graph():
    """Create the Partitioner agent workflow graph."""
    workflow = StateGraph(PartitionerState)

    # Add nodes
    workflow.add_node("find_large_tables", find_large_tables)
    workflow.add_node("analyze_partition_columns", analyze_partition_columns)
    workflow.add_node("analyze_query_patterns", analyze_query_patterns)
    workflow.add_node("check_existing_partitions", check_existing_partitions)
    workflow.add_node("generate_recommendations", generate_recommendations)
    workflow.add_node("analyze_with_llm", analyze_with_llm)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("save_results", save_results)

    # Set entry point
    workflow.set_entry_point("find_large_tables")

    # Add edges
    workflow.add_conditional_edges(
        "find_large_tables",
        should_continue,
        {"continue": "analyze_partition_columns", "error": END}
    )
    workflow.add_edge("analyze_partition_columns", "analyze_query_patterns")
    workflow.add_edge("analyze_query_patterns", "check_existing_partitions")
    workflow.add_edge("check_existing_partitions", "generate_recommendations")
    workflow.add_edge("generate_recommendations", "analyze_with_llm")
    workflow.add_edge("analyze_with_llm", "generate_report")
    workflow.add_edge("generate_report", "save_results")
    workflow.add_edge("save_results", END)

    return workflow.compile()


async def run_partitioner_agent(database_id: int, schema: str = "public") -> Dict[str, Any]:
    """
    Run the Partitioner agent on a database.

    Args:
        database_id: ID of the database in the state DB
        schema: PostgreSQL schema to analyze (default: public)

    Returns:
        Analysis results including partition recommendations
    """
    state_db.log("partitioner", "INFO", f"Starting partition analysis for database {database_id}")

    # Create initial state
    initial_state: PartitionerState = {
        "database_id": database_id,
        "schema": schema,
        "large_tables": [],
        "partition_candidates": [],
        "query_patterns": {},
        "existing_partitions": [],
        "recommendations": [],
        "llm_analysis": None,
        "markdown_report": "",
        "error": None,
    }

    # Create and run the graph
    graph = create_partitioner_graph()
    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        return {"error": final_state["error"]}

    return {
        "status": "success",
        "large_tables_analyzed": len(final_state["large_tables"]),
        "partition_candidates": len(final_state["partition_candidates"]),
        "recommendations_count": len(final_state["recommendations"]),
        "existing_partitions": len(final_state["existing_partitions"]),
        "markdown_report": final_state["markdown_report"],
    }
