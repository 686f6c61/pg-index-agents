"""
PG Index Agents - Servicio de explicaciones con IA
https://github.com/686f6c61/pg-index-agents

Este modulo genera explicaciones tecnicas detalladas utilizando modelos de
lenguaje a traves de OpenRouter. Las explicaciones estan orientadas a DBAs
y desarrolladores, proporcionando contexto y recomendaciones accionables.

El servicio soporta explicaciones para:
- Anomalias detectadas (indices duplicados, no usados, faltantes)
- Senales de rendimiento (queries lentas, bloqueos, bloat)
- Propuestas de indices (justificaciones, impacto esperado)
- Tareas de mantenimiento (REINDEX, VACUUM, ANALYZE)

Todas las explicaciones se generan en castellano y siguen una estructura
consistente que incluye: descripcion del problema, impacto, metodo de
deteccion, solucion recomendada y consideraciones adicionales.

Autor: 686f6c61
Licencia: MIT
"""

from typing import Dict, Any, Optional
from core.llm import get_llm_for_analysis


async def explain_anomaly(anomaly: Dict[str, Any], db_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a technical explanation for a detected anomaly.

    Args:
        anomaly: The anomaly data (type, severity, table, description, etc.)
        db_context: Optional database context for more relevant explanations

    Returns:
        Detailed technical explanation in Spanish
    """
    llm = get_llm_for_analysis()

    context_str = ""
    if db_context:
        context_str = f"""
Contexto de la base de datos:
- Nombre: {db_context.get('name', 'N/A')}
- Tablas: {db_context.get('tables_count', 'N/A')}
- Índices: {db_context.get('indexes_count', 'N/A')}
"""

    prompt = f"""Eres un experto DBA de PostgreSQL. Analiza la siguiente anomalía detectada y proporciona una explicación técnica detallada en español.

{context_str}

Anomalía detectada:
- Tipo: {anomaly.get('type', 'unknown')}
- Severidad: {anomaly.get('severity', 'unknown')}
- Tabla: {anomaly.get('table', 'unknown')}
- Columna: {anomaly.get('column', 'N/A')}
- Índice: {anomaly.get('index', 'N/A')}
- Descripción: {anomaly.get('description', 'N/A')}
- Recomendación actual: {anomaly.get('recommendation', 'N/A')}

Proporciona una explicación técnica que incluya:

1. **¿Qué significa esta anomalía?**
   Explica en términos técnicos qué está ocurriendo.

2. **¿Por qué es un problema?**
   Describe el impacto en rendimiento, espacio o mantenibilidad.

3. **¿Cómo se detectó?**
   Explica brevemente qué métricas o análisis revelaron este problema.

4. **Solución recomendada**
   Proporciona pasos concretos para resolver el problema, incluyendo SQL si aplica.

5. **Consideraciones adicionales**
   Menciona riesgos, tiempo de ejecución estimado, o precauciones.

Responde de forma clara y estructurada, orientada a un DBA o desarrollador."""

    response = await llm.ainvoke(prompt)
    return response.content


async def explain_signal(signal: Dict[str, Any], db_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a technical explanation for a detected signal.

    Args:
        signal: The signal data (type, severity, description, details, etc.)
        db_context: Optional database context

    Returns:
        Detailed technical explanation in Spanish
    """
    llm = get_llm_for_analysis()

    context_str = ""
    if db_context:
        context_str = f"""
Contexto de la base de datos:
- Nombre: {db_context.get('name', 'N/A')}
"""

    details_str = ""
    if signal.get('details_json'):
        import json
        try:
            details_str = f"\nDetalles técnicos:\n{json.dumps(signal['details_json'], indent=2, ensure_ascii=False)}"
        except:
            details_str = f"\nDetalles: {signal['details_json']}"

    prompt = f"""Eres un experto DBA de PostgreSQL especializado en optimización de rendimiento. Analiza la siguiente señal de monitoreo y proporciona una explicación técnica detallada en español.

{context_str}

Señal detectada:
- Tipo: {signal.get('signal_type', 'unknown')}
- Severidad: {signal.get('severity', 'unknown')}
- Estado: {signal.get('status', 'unknown')}
- Descripción: {signal.get('description', 'N/A')}
- Detectado: {signal.get('detected_at', 'N/A')}
{details_str}

Proporciona una explicación técnica que incluya:

1. **¿Qué indica esta señal?**
   Explica qué patrón de comportamiento se ha detectado.

2. **Impacto en el sistema**
   Describe cómo afecta esto al rendimiento de la base de datos.

3. **Causa probable**
   Analiza las posibles causas raíz basándote en los detalles.

4. **Acciones recomendadas**
   Lista las acciones concretas para abordar esta señal.

5. **Métricas a monitorear**
   Indica qué métricas vigilar para confirmar la mejora.

Responde de forma clara y estructurada."""

    response = await llm.ainvoke(prompt)
    return response.content


async def explain_maintenance_task(task: Dict[str, Any], db_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a technical explanation for a maintenance task.

    Args:
        task: The maintenance task data (type, table, index, reason, sql, etc.)
        db_context: Optional database context

    Returns:
        Detailed technical explanation in Spanish
    """
    llm = get_llm_for_analysis()

    context_str = ""
    if db_context:
        context_str = f"""
Contexto de la base de datos:
- Nombre: {db_context.get('name', 'N/A')}
"""

    prompt = f"""Eres un experto DBA de PostgreSQL especializado en mantenimiento de bases de datos. Analiza la siguiente tarea de mantenimiento y proporciona una explicación técnica detallada en español.

{context_str}

Tarea de mantenimiento:
- Tipo: {task.get('task_type', 'unknown')}
- Tabla: {task.get('table_name', 'N/A')}
- Índice: {task.get('index_name', 'N/A')}
- Prioridad: {task.get('priority', 'unknown')}
- Razón: {task.get('reason', 'N/A')}
- Duración estimada: {task.get('estimated_duration', 'N/A')}
- Comando SQL: {task.get('sql_command', 'N/A')}

Proporciona una explicación técnica que incluya:

1. **¿Por qué es necesaria esta tarea?**
   Explica el problema subyacente que requiere esta acción.

2. **¿Qué hace exactamente el comando?**
   Describe paso a paso qué ocurre cuando se ejecuta.

3. **Impacto durante la ejecución**
   - ¿Bloquea la tabla?
   - ¿Consume muchos recursos?
   - ¿Es seguro en producción?

4. **Mejor momento para ejecutar**
   Recomienda cuándo es mejor realizar esta tarea.

5. **Verificación post-ejecución**
   Indica cómo confirmar que la tarea se completó correctamente.

6. **Alternativas**
   Si existen, menciona otras formas de lograr el mismo resultado.

Responde de forma clara y estructurada."""

    response = await llm.ainvoke(prompt)
    return response.content


async def explain_proposal(proposal: Dict[str, Any], db_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a technical explanation for an index proposal.

    Args:
        proposal: The proposal data (type, sql, justification, impact, etc.)
        db_context: Optional database context

    Returns:
        Detailed technical explanation in Spanish
    """
    llm = get_llm_for_analysis()

    context_str = ""
    if db_context:
        context_str = f"""
Contexto de la base de datos:
- Nombre: {db_context.get('name', 'N/A')}
"""

    impact_str = ""
    if proposal.get('estimated_impact_json'):
        import json
        try:
            if isinstance(proposal['estimated_impact_json'], str):
                impact = json.loads(proposal['estimated_impact_json'])
            else:
                impact = proposal['estimated_impact_json']
            impact_str = f"\nImpacto estimado:\n{json.dumps(impact, indent=2, ensure_ascii=False)}"
        except:
            impact_str = f"\nImpacto: {proposal['estimated_impact_json']}"

    prompt = f"""Eres un experto DBA de PostgreSQL especializado en optimización de índices. Analiza la siguiente propuesta de índice y proporciona una explicación técnica detallada en español.

{context_str}

Propuesta de índice:
- Tipo: {proposal.get('proposal_type', 'unknown')}
- Estado: {proposal.get('status', 'unknown')}
- SQL: {proposal.get('sql_command', 'N/A')}
- Justificación original: {proposal.get('justification', 'N/A')}
{impact_str}

Proporciona una explicación técnica que incluya:

1. **Análisis del índice propuesto**
   - ¿Qué tipo de índice es? (B-tree, Hash, GIN, GiST, etc.)
   - ¿Qué columnas cubre?
   - ¿Es un índice parcial o con expresión?

2. **Beneficios esperados**
   - ¿Qué consultas se beneficiarán?
   - ¿Cuánto puede mejorar el rendimiento?

3. **Costos y trade-offs**
   - Espacio en disco adicional
   - Impacto en operaciones INSERT/UPDATE/DELETE
   - Tiempo de creación

4. **Recomendación de ejecución**
   - ¿Usar CONCURRENTLY?
   - ¿Mejor momento para crear?
   - ¿Precauciones necesarias?

5. **Verificación post-creación**
   - Cómo confirmar que el índice se usa
   - Consultas para validar el impacto

6. **Alternativas consideradas**
   - ¿Hay otras opciones de índice?
   - ¿Covering index vs índice simple?

Responde de forma clara y estructurada."""

    response = await llm.ainvoke(prompt)
    return response.content


async def generate_executive_summary(
    anomalies: list,
    signals: list,
    proposals: list,
    maintenance_tasks: list,
    db_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate an executive summary of the database analysis.

    Args:
        anomalies: List of detected anomalies
        signals: List of detected signals
        proposals: List of index proposals
        maintenance_tasks: List of maintenance tasks
        db_context: Database context

    Returns:
        Executive summary in Spanish
    """
    llm = get_llm_for_analysis()

    # Count by severity
    high_anomalies = len([a for a in anomalies if a.get('severity') == 'high'])
    medium_anomalies = len([a for a in anomalies if a.get('severity') == 'medium'])
    low_anomalies = len([a for a in anomalies if a.get('severity') == 'low'])

    high_signals = len([s for s in signals if s.get('severity') == 'high'])
    pending_proposals = len([p for p in proposals if p.get('status') == 'pending'])

    high_maintenance = len([t for t in maintenance_tasks if t.get('priority') == 'high'])

    context_str = ""
    if db_context:
        context_str = f"""
Base de datos: {db_context.get('name', 'N/A')}
Host: {db_context.get('host', 'localhost')}
"""

    prompt = f"""Eres un consultor experto en bases de datos PostgreSQL. Genera un resumen ejecutivo del estado de la base de datos basándote en el análisis realizado.

{context_str}

Estadísticas del análisis:
- Anomalías totales: {len(anomalies)} (Alta: {high_anomalies}, Media: {medium_anomalies}, Baja: {low_anomalies})
- Señales detectadas: {len(signals)} (Alta severidad: {high_signals})
- Propuestas de índices pendientes: {pending_proposals}
- Tareas de mantenimiento: {len(maintenance_tasks)} (Alta prioridad: {high_maintenance})

Tipos de anomalías encontradas:
{', '.join(set(a.get('type', 'unknown') for a in anomalies[:10])) if anomalies else 'Ninguna'}

Tipos de señales:
{', '.join(set(s.get('signal_type', 'unknown') for s in signals[:10])) if signals else 'Ninguna'}

Genera un resumen ejecutivo en español que incluya:

1. **Estado General de la Base de Datos**
   Una evaluación global (Crítico/Necesita Atención/Saludable).

2. **Hallazgos Principales**
   Los 3-5 problemas más importantes a abordar.

3. **Prioridades Recomendadas**
   Qué acciones tomar primero y por qué.

4. **Riesgos Identificados**
   Problemas que podrían escalar si no se atienden.

5. **Próximos Pasos**
   Plan de acción recomendado.

El resumen debe ser conciso pero informativo, orientado a tomadores de decisiones técnicas."""

    response = await llm.ainvoke(prompt)
    return response.content
