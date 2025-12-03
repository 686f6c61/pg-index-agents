"""
PG Index Agents - Servicio de extraccion de metadatos de PostgreSQL
https://github.com/686f6c61/pg-index-agents

Este modulo extrae metadatos estructurales de bases de datos PostgreSQL para
su analisis por los agentes. Utiliza las vistas de information_schema y los
catalogos del sistema (pg_catalog) para obtener informacion detallada sobre
tablas, columnas, indices, foreign keys y estadisticas.

La extraccion esta optimizada para evitar problemas de rendimiento N+1,
obteniendo todos los datos necesarios con un numero minimo de queries.

Metadatos extraidos:
- Estructura de tablas y columnas
- Definiciones de indices (B-tree, GIN, GiST, etc.)
- Relaciones de foreign keys
- Estadisticas de uso de tablas e indices
- Configuracion relevante de PostgreSQL
- Disponibilidad de pg_stat_statements

Autor: 686f6c61
Licencia: MIT
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import text
from core.database import db_manager


class MetadataExtractor:
    """
    Extractor de metadatos de bases de datos PostgreSQL.

    Esta clase proporciona metodos para obtener un snapshot completo de la
    estructura de una base de datos PostgreSQL. Los datos extraidos son
    utilizados por el agente Explorer para analizar la estructura y detectar
    anomalias.

    La extraccion se realiza en modo solo lectura y no modifica ningun dato
    en la base de datos objetivo.

    Attributes:
        db: Gestor de conexiones a base de datos.
    """

    def __init__(self):
        """Inicializa el extractor con el gestor de base de datos global."""
        self.db = db_manager

    def get_full_snapshot(self, schema: str = "public") -> Dict[str, Any]:
        """
        Extract complete metadata snapshot from a PostgreSQL database.

        Returns a dictionary with:
        - tables: List of tables with columns, types, constraints
        - indexes: List of indexes with details
        - foreign_keys: List of FK relationships
        - statistics: Table and index statistics
        - settings: Relevant PostgreSQL settings
        """
        with self.db.read_connection() as conn:
            snapshot = {
                "schema": schema,
                "tables": self._get_tables(conn, schema),
                "indexes": self._get_indexes(conn, schema),
                "foreign_keys": self._get_foreign_keys(conn, schema),
                "table_statistics": self._get_table_statistics(conn, schema),
                "index_statistics": self._get_index_statistics(conn, schema),
                "database_size": self._get_database_size(conn),
                "settings": self._get_relevant_settings(conn),
                "pg_stat_statements_available": self._check_pg_stat_statements(conn)
            }
            return snapshot

    def _get_tables(self, conn, schema: str) -> List[Dict]:
        """Get all tables with their columns - optimized to avoid N+1 queries."""
        # Get tables
        tables_query = text("""
            SELECT
                t.table_name,
                t.table_type,
                pg_catalog.obj_description(
                    (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass, 'pg_class'
                ) as table_comment
            FROM information_schema.tables t
            WHERE t.table_schema = :schema
            AND t.table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY t.table_name
        """)

        tables_result = conn.execute(tables_query, {"schema": schema})

        # Build table dict first
        tables_dict = {}
        for row in tables_result:
            table_name = row[0]
            tables_dict[table_name] = {
                "name": table_name,
                "type": row[1],
                "comment": row[2],
                "columns": [],
                "constraints": []
            }

        if not tables_dict:
            return []

        # Get ALL columns in a single query (fix N+1)
        all_columns = self._get_all_columns(conn, schema)
        for col in all_columns:
            table_name = col.pop("table_name")
            if table_name in tables_dict:
                tables_dict[table_name]["columns"].append(col)

        # Get ALL constraints in a single query (fix N+1)
        all_constraints = self._get_all_constraints(conn, schema)
        for table_name, constraints in all_constraints.items():
            if table_name in tables_dict:
                tables_dict[table_name]["constraints"] = constraints

        return list(tables_dict.values())

    def _get_all_columns(self, conn, schema: str) -> List[Dict]:
        """Get all columns for all tables in a single query."""
        query = text("""
            SELECT
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale
            FROM information_schema.columns c
            WHERE c.table_schema = :schema
            ORDER BY c.table_name, c.ordinal_position
        """)

        result = conn.execute(query, {"schema": schema})
        columns = []

        for row in result:
            columns.append({
                "table_name": row[0],
                "name": row[1],
                "data_type": row[2],
                "is_nullable": row[3] == "YES",
                "default": row[4],
                "max_length": row[5],
                "numeric_precision": row[6],
                "numeric_scale": row[7],
                "comment": None  # Skip individual column comments for performance
            })

        return columns

    def _get_all_constraints(self, conn, schema: str) -> Dict[str, List[Dict]]:
        """Get all constraints for all tables in a single query."""
        query = text("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.table_schema = :schema
            ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
        """)

        result = conn.execute(query, {"schema": schema})

        # Group by table, then by constraint
        tables_constraints: Dict[str, Dict[str, Dict]] = {}

        for row in result:
            table_name = row[0]
            constraint_name = row[1]

            if table_name not in tables_constraints:
                tables_constraints[table_name] = {}

            if constraint_name not in tables_constraints[table_name]:
                tables_constraints[table_name][constraint_name] = {
                    "name": constraint_name,
                    "type": row[2],
                    "columns": []
                }
            tables_constraints[table_name][constraint_name]["columns"].append(row[3])

        # Convert to final format
        return {
            table: list(constraints.values())
            for table, constraints in tables_constraints.items()
        }

    def _get_indexes(self, conn, schema: str) -> List[Dict]:
        """Get all indexes in the schema."""
        query = text("""
            SELECT
                i.relname as index_name,
                t.relname as table_name,
                ix.indisunique as is_unique,
                ix.indisprimary as is_primary,
                array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) as columns,
                pg_get_indexdef(ix.indexrelid) as index_definition,
                pg_relation_size(i.oid) as index_size_bytes
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE n.nspname = :schema
            GROUP BY i.relname, t.relname, ix.indisunique, ix.indisprimary,
                     ix.indexrelid, i.oid
            ORDER BY t.relname, i.relname
        """)

        result = conn.execute(query, {"schema": schema})
        indexes = []

        for row in result:
            indexes.append({
                "name": row[0],
                "table_name": row[1],
                "is_unique": row[2],
                "is_primary": row[3],
                "columns": row[4],
                "definition": row[5],
                "size_bytes": row[6]
            })

        return indexes

    def _get_foreign_keys(self, conn, schema: str) -> List[Dict]:
        """Get all foreign key relationships."""
        query = text("""
            SELECT
                tc.constraint_name,
                tc.table_name as from_table,
                kcu.column_name as from_column,
                ccu.table_name as to_table,
                ccu.column_name as to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = :schema
            ORDER BY tc.table_name, kcu.column_name
        """)

        result = conn.execute(query, {"schema": schema})
        foreign_keys = []

        for row in result:
            foreign_keys.append({
                "constraint_name": row[0],
                "from_table": row[1],
                "from_column": row[2],
                "to_table": row[3],
                "to_column": row[4]
            })

        return foreign_keys

    def _get_table_statistics(self, conn, schema: str) -> List[Dict]:
        """Get statistics for all tables."""
        query = text("""
            SELECT
                schemaname,
                relname as table_name,
                n_live_tup as row_count,
                n_dead_tup as dead_rows,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                seq_scan,
                seq_tup_read,
                idx_scan,
                idx_tup_fetch,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes,
                pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) as total_size_bytes,
                pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) as table_size_bytes
            FROM pg_stat_user_tables
            WHERE schemaname = :schema
            ORDER BY n_live_tup DESC
        """)

        result = conn.execute(query, {"schema": schema})
        stats = []

        for row in result:
            stats.append({
                "schema": row[0],
                "table_name": row[1],
                "row_count": row[2],
                "dead_rows": row[3],
                "last_vacuum": str(row[4]) if row[4] else None,
                "last_autovacuum": str(row[5]) if row[5] else None,
                "last_analyze": str(row[6]) if row[6] else None,
                "last_autoanalyze": str(row[7]) if row[7] else None,
                "seq_scan": row[8],
                "seq_tup_read": row[9],
                "idx_scan": row[10],
                "idx_tup_fetch": row[11],
                "inserts": row[12],
                "updates": row[13],
                "deletes": row[14],
                "total_size_bytes": row[15],
                "table_size_bytes": row[16]
            })

        return stats

    def _get_index_statistics(self, conn, schema: str) -> List[Dict]:
        """Get statistics for all indexes."""
        query = text("""
            SELECT
                schemaname,
                relname as table_name,
                indexrelname as index_name,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch,
                pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(indexrelname)) as index_size_bytes
            FROM pg_stat_user_indexes
            WHERE schemaname = :schema
            ORDER BY idx_scan DESC
        """)

        result = conn.execute(query, {"schema": schema})
        stats = []

        for row in result:
            stats.append({
                "schema": row[0],
                "table_name": row[1],
                "index_name": row[2],
                "idx_scan": row[3],
                "idx_tup_read": row[4],
                "idx_tup_fetch": row[5],
                "index_size_bytes": row[6]
            })

        return stats

    def _get_database_size(self, conn) -> Dict:
        """Get database size information."""
        query = text("""
            SELECT
                pg_database_size(current_database()) as database_size_bytes,
                current_database() as database_name
        """)

        result = conn.execute(query)
        row = result.fetchone()

        return {
            "database_name": row[1],
            "size_bytes": row[0],
            "size_human": self._bytes_to_human(row[0])
        }

    def _get_relevant_settings(self, conn) -> Dict:
        """Get PostgreSQL settings relevant to performance."""
        query = text("""
            SELECT name, setting, unit, short_desc
            FROM pg_settings
            WHERE name IN (
                'shared_buffers', 'effective_cache_size', 'work_mem',
                'maintenance_work_mem', 'random_page_cost', 'seq_page_cost',
                'default_statistics_target', 'max_connections',
                'autovacuum', 'track_counts', 'track_activities'
            )
            ORDER BY name
        """)

        result = conn.execute(query)
        settings = {}

        for row in result:
            settings[row[0]] = {
                "value": row[1],
                "unit": row[2],
                "description": row[3]
            }

        return settings

    def _check_pg_stat_statements(self, conn) -> bool:
        """Check if pg_stat_statements extension is available."""
        query = text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
            )
        """)

        result = conn.execute(query)
        return result.scalar()

    def get_query_statistics(self, limit: int = 100) -> List[Dict]:
        """Get query statistics from pg_stat_statements if available."""
        with self.db.read_connection() as conn:
            if not self._check_pg_stat_statements(conn):
                return []

            query = text("""
                SELECT
                    queryid,
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows,
                    shared_blks_hit,
                    shared_blks_read,
                    temp_blks_written
                FROM pg_stat_statements
                ORDER BY total_exec_time DESC
                LIMIT :limit
            """)

            result = conn.execute(query, {"limit": limit})
            stats = []

            for row in result:
                stats.append({
                    "query_id": str(row[0]),
                    "query": row[1],
                    "calls": row[2],
                    "total_exec_time_ms": row[3],
                    "mean_exec_time_ms": row[4],
                    "rows": row[5],
                    "shared_blks_hit": row[6],
                    "shared_blks_read": row[7],
                    "temp_blks_written": row[8]
                })

            return stats

    @staticmethod
    def _bytes_to_human(size_bytes: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"


# Global instance
metadata_extractor = MetadataExtractor()
