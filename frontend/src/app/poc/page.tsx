/**
 * PG Index Agents - Pagina PoC (Proof of Concept)
 * https://github.com/686f6c61/pg-index-agents
 *
 * Documentacion de la prueba de concepto que explica la hipotesis,
 * los agentes disponibles, la base de datos de prueba, la arquitectura
 * tecnica, y los hallazgos del sistema.
 *
 * Secciones:
 *   - Hipotesis: Objetivo del sistema multi-agente con IA
 *   - Base de datos de prueba: Stack Exchange DBA dataset
 *   - Sistema de agentes: Descripcion de los 5 agentes
 *   - Hallazgos: Anomalias detectadas y propuestas generadas
 *   - Arquitectura tecnica: Stack tecnologico y niveles de autonomia
 *
 * Esta pagina sirve como documentacion interna y landing page
 * para explicar el proposito del proyecto.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import {
  Compass,
  Eye,
  PenTool,
  Wrench,
  Grid3X3,
  Database,
  Target,
  Lightbulb,
  ArrowRight,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  GitBranch
} from 'lucide-react';

/** Pagina de documentacion del Proof of Concept */
export default function PoCPage() {
  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Hero Section */}
      <div className="text-center space-y-4 py-8">
        <h1 className="text-4xl font-bold text-[var(--foreground)]">
          PG Index Agents
        </h1>
        <p className="text-xl text-[var(--muted-foreground)] max-w-2xl mx-auto">
          Sistema de agentes inteligentes para analisis y optimizacion automatica de indices en PostgreSQL
        </p>
      </div>

      {/* Hypothesis Section */}
      <Card className="border-[var(--primary)]/20 bg-[var(--primary)]/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-6 w-6 text-[var(--primary)]" />
            Hipotesis
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--foreground)]">
            La gestion de indices en bases de datos PostgreSQL es un proceso complejo que tradicionalmente
            requiere expertise de DBAs especializados. Nuestra hipotesis es que un sistema multi-agente
            con capacidades de IA puede:
          </p>
          <ul className="space-y-2">
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span>Analizar automaticamente la estructura y patrones de uso de una base de datos</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span>Detectar anomalias y oportunidades de optimizacion de indices</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span>Generar propuestas de indices con justificaciones claras</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span>Mantener la salud de los indices existentes de forma proactiva</span>
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Database Used */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-6 w-6" />
            Base de Datos de Prueba
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--foreground)]">
            Para validar nuestra hipotesis, utilizamos el dump publico de <strong>Stack Exchange - DBA</strong>,
            la comunidad de preguntas y respuestas sobre administracion de bases de datos.
          </p>

          <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <p className="text-sm text-[var(--foreground)]">
              <strong>Descarga:</strong>{' '}
              <a
                href="https://archive.org/details/stackexchange"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--primary)] hover:underline"
              >
                Stack Exchange Data Dump - Archive.org
              </a>
            </p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              Dataset: dba.stackexchange.com - Disponible en formato XML, convertido a PostgreSQL
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <div className="p-4 rounded-lg bg-[var(--muted)] text-center">
              <div className="text-2xl font-bold text-[var(--primary)]">8</div>
              <div className="text-sm text-[var(--muted-foreground)]">Tablas</div>
            </div>
            <div className="p-4 rounded-lg bg-[var(--muted)] text-center">
              <div className="text-2xl font-bold text-[var(--primary)]">500K+</div>
              <div className="text-sm text-[var(--muted-foreground)]">Registros</div>
            </div>
            <div className="p-4 rounded-lg bg-[var(--muted)] text-center">
              <div className="text-2xl font-bold text-[var(--primary)]">6</div>
              <div className="text-sm text-[var(--muted-foreground)]">Foreign Keys</div>
            </div>
            <div className="p-4 rounded-lg bg-[var(--muted)] text-center">
              <div className="text-2xl font-bold text-[var(--primary)]">~200MB</div>
              <div className="text-sm text-[var(--muted-foreground)]">Tamano</div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-[var(--muted)] mt-4">
            <h4 className="font-medium mb-2">Tablas principales:</h4>
            <div className="flex flex-wrap gap-2 text-sm">
              {['posts', 'users', 'comments', 'votes', 'badges', 'tags', 'posthistory', 'postlinks'].map((table) => (
                <span key={table} className="px-2 py-1 rounded bg-[var(--background)] border border-[var(--border)]">
                  {table}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Agents Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-6 w-6" />
            Sistema de Agentes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[var(--muted-foreground)] mb-6">
            El sistema esta compuesto por 5 agentes especializados que trabajan en conjunto:
          </p>

          <div className="space-y-6">
            {/* Explorer Agent */}
            <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-lg bg-blue-500/10">
                  <Compass className="h-6 w-6 text-blue-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-lg text-[var(--foreground)]">Explorer Agent</h3>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Analiza la estructura de la base de datos, clasifica tablas por criticidad y
                    detecta anomalias como indices duplicados, unused indexes y missing indexes.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-500">Metadata extraction</span>
                    <span className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-500">Dependency graph</span>
                    <span className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-500">Anomaly detection</span>
                    <span className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-500">LLM analysis</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Observer Agent */}
            <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-lg bg-purple-500/10">
                  <Eye className="h-6 w-6 text-purple-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-lg text-[var(--foreground)]">Observer Agent</h3>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Monitorea metricas de rendimiento en tiempo real, analiza patrones de queries
                    y genera senales cuando detecta problemas potenciales.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-purple-500/10 text-purple-500">pg_stat_statements</span>
                    <span className="text-xs px-2 py-1 rounded bg-purple-500/10 text-purple-500">Query analysis</span>
                    <span className="text-xs px-2 py-1 rounded bg-purple-500/10 text-purple-500">Signal detection</span>
                    <span className="text-xs px-2 py-1 rounded bg-purple-500/10 text-purple-500">Trend analysis</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Architect Agent */}
            <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-lg bg-orange-500/10">
                  <PenTool className="h-6 w-6 text-orange-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-lg text-[var(--foreground)]">Architect Agent</h3>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Procesa las senales detectadas y genera propuestas concretas de indices
                    con justificaciones detalladas y estimaciones de impacto.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-500">Index proposals</span>
                    <span className="text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-500">SQL generation</span>
                    <span className="text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-500">Impact estimation</span>
                    <span className="text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-500">CONCURRENTLY support</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Gardener Agent */}
            <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-lg bg-green-500/10">
                  <Wrench className="h-6 w-6 text-green-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-lg text-[var(--foreground)]">Gardener Agent</h3>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Mantiene la salud de los indices existentes, detecta bloat, programa
                    tareas de mantenimiento y genera recomendaciones priorizadas.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-500">Bloat detection</span>
                    <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-500">REINDEX tasks</span>
                    <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-500">VACUUM scheduling</span>
                    <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-500">Health monitoring</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Partitioner Agent */}
            <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--card)]">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-lg bg-cyan-500/10">
                  <Grid3X3 className="h-6 w-6 text-cyan-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-lg text-[var(--foreground)]">Partitioner Agent</h3>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Analiza tablas grandes para recomendar estrategias de particionamiento.
                    Opera en modo solo lectura, generando informes detallados sin ejecutar cambios.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-500">Large table analysis</span>
                    <span className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-500">Partition key detection</span>
                    <span className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-500">Query pattern validation</span>
                    <span className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-500">Migration plan generation</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Agent Flow */}
          <div className="mt-8 p-4 rounded-lg bg-[var(--muted)]">
            <h4 className="font-medium mb-4 text-center">Flujo de trabajo</h4>
            <div className="flex items-center justify-center flex-wrap gap-2">
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-blue-500/10 text-blue-500">
                <Compass className="h-4 w-4" />
                <span className="text-sm font-medium">Explorer</span>
              </div>
              <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)]" />
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-purple-500/10 text-purple-500">
                <Eye className="h-4 w-4" />
                <span className="text-sm font-medium">Observer</span>
              </div>
              <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)]" />
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-orange-500/10 text-orange-500">
                <PenTool className="h-4 w-4" />
                <span className="text-sm font-medium">Architect</span>
              </div>
              <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)]" />
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-green-500/10 text-green-500">
                <Wrench className="h-4 w-4" />
                <span className="text-sm font-medium">Gardener</span>
              </div>
              <ArrowRight className="h-4 w-4 text-[var(--muted-foreground)]" />
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-cyan-500/10 text-cyan-500">
                <Grid3X3 className="h-4 w-4" />
                <span className="text-sm font-medium">Partitioner</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Findings Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-6 w-6" />
            Hallazgos
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--muted-foreground)]">
            Durante el analisis de la base de datos Stack Exchange DBA, el sistema detecto:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                <h4 className="font-medium text-yellow-500">Anomalias detectadas</h4>
              </div>
              <ul className="space-y-1 text-sm text-[var(--foreground)]">
                <li>- Indices potencialmente duplicados</li>
                <li>- Indices con bajo uso (unused indexes)</li>
                <li>- Tablas grandes sin indices adecuados</li>
                <li>- Foreign keys sin indices de soporte</li>
              </ul>
            </div>

            <div className="p-4 rounded-lg border border-green-500/20 bg-green-500/5">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <h4 className="font-medium text-green-500">Propuestas generadas</h4>
              </div>
              <ul className="space-y-1 text-sm text-[var(--foreground)]">
                <li>- CREATE INDEX CONCURRENTLY para tablas criticas</li>
                <li>- Indices compuestos para queries frecuentes</li>
                <li>- REINDEX para indices con bloat</li>
                <li>- VACUUM ANALYZE recomendados</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Architecture Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-6 w-6" />
            Arquitectura Tecnica
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium mb-3">Backend</h4>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  FastAPI (Python 3.11+)
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  LangGraph para orquestacion de agentes
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  SQLAlchemy para conexion PostgreSQL
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  SQLite para estado interno
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  OpenRouter para LLM (Kimi K2)
                </li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium mb-3">Frontend</h4>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  Next.js 15 (App Router)
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  TypeScript
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  Tailwind CSS
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  Lucide React icons
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                  React Flow para grafos
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-lg bg-[var(--muted)]">
            <h4 className="font-medium mb-2">Niveles de Autonomia</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div className="p-2 rounded bg-[var(--background)] border border-[var(--border)]">
                <span className="font-medium">Observacion</span>
                <p className="text-xs text-[var(--muted-foreground)]">Solo observa e informa</p>
              </div>
              <div className="p-2 rounded bg-[var(--background)] border border-[var(--border)]">
                <span className="font-medium">Asistido</span>
                <p className="text-xs text-[var(--muted-foreground)]">Propone, requiere aprobacion</p>
              </div>
              <div className="p-2 rounded bg-[var(--background)] border border-[var(--border)]">
                <span className="font-medium">Confianza</span>
                <p className="text-xs text-[var(--muted-foreground)]">Auto-ejecuta bajo riesgo</p>
              </div>
              <div className="p-2 rounded bg-[var(--background)] border border-[var(--border)]">
                <span className="font-medium">Autonomo</span>
                <p className="text-xs text-[var(--muted-foreground)]">Ejecuta todo automaticamente</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-center py-8 text-sm text-[var(--muted-foreground)]">
        <p>PG Index Agents - Proof of Concept</p>
        <p className="mt-1">Desarrollado con LangGraph + FastAPI + Next.js</p>
      </div>
    </div>
  );
}
