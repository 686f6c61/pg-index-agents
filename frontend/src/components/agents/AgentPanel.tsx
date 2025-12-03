/**
 * PG Index Agents - Componente AgentPanel
 * https://github.com/686f6c61/pg-index-agents
 *
 * Panel de control principal para ejecutar los agentes de analisis.
 * Permite ejecutar agentes individualmente o en secuencia completa,
 * con visualizacion del progreso en tiempo real.
 *
 * Agentes disponibles:
 *   - Explorer: Analisis inicial de estructura y anomalias
 *   - Observer: Monitoreo continuo y deteccion de senales
 *   - Architect: Generacion de propuestas de indices con IA
 *   - Gardener: Analisis de salud y tareas de mantenimiento
 *   - Partitioner: Recomendaciones de particionamiento (read-only)
 *
 * Funcionalidades:
 *   - Ejecucion individual de cada agente
 *   - Ejecucion secuencial de todos los agentes ("Run All")
 *   - Barra de progreso durante ejecucion
 *   - Visualizacion de pipeline con estados
 *   - Modal con informacion tecnica detallada de cada agente
 *   - Polling de jobs para actualizar estado en tiempo real
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState, useCallback } from 'react';
import {
  Compass,
  Eye,
  Building2,
  Flower2,
  Grid3X3,
  Play,
  PlayCircle,
  StopCircle,
  RefreshCw,
  CheckCircle,
  XCircle,
  Circle,
  ArrowRight,
  Info,
  X,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { api, Job } from '@/lib/api';

/** Props del componente AgentPanel */
interface AgentPanelProps {
  databaseId: number;
  onAnalysisComplete?: () => void;
}

type AgentState = 'pending' | 'running' | 'success' | 'error';

interface AgentStatus {
  state: AgentState;
  result: string | null;
}

interface AgentTechnicalInfo {
  overview: string;
  workflow: string[];
  dataCollected: string[];
  output: string[];
  technicalDetails: string;
}

const agentTechnicalInfo: Record<string, AgentTechnicalInfo> = {
  explorer: {
    overview: 'El Explorer es el agente de reconocimiento inicial que realiza un análisis exhaustivo de la estructura de la base de datos. Utiliza consultas a los catálogos del sistema de PostgreSQL para construir un mapa completo del esquema.',
    workflow: [
      'Extrae metadatos de pg_catalog y information_schema',
      'Clasifica tablas por tipo (transaccional, catálogo, log, staging)',
      'Calcula criticidad basada en referencias FK y tamaño',
      'Construye grafo de dependencias entre tablas',
      'Detecta anomalías estructurales y de diseño',
      'Genera plan de trabajo para otros agentes',
    ],
    dataCollected: [
      'pg_stat_user_tables: estadísticas de uso de tablas',
      'pg_stat_user_indexes: estadísticas de índices',
      'pg_class, pg_attribute: estructura de columnas',
      'pg_constraint: claves foráneas y restricciones',
      'pg_indexes: definiciones de índices',
    ],
    output: [
      'Clasificación de tablas con nivel de criticidad',
      'Grafo de dependencias (FK e inferidas)',
      'Lista de anomalías detectadas con severidad',
      'Plan de trabajo priorizado para Observer/Architect/Gardener',
    ],
    technicalDetails: 'Utiliza LangGraph para orquestar el flujo de análisis. Las anomalías detectadas incluyen: tablas sin PK, índices duplicados, columnas sin FK que parecen referencias, tablas grandes sin índices, y más.',
  },
  observer: {
    overview: 'El Observer monitoriza continuamente el rendimiento de la base de datos, recopilando métricas en tiempo real y detectando señales que indican problemas potenciales o oportunidades de optimización.',
    workflow: [
      'Recopila métricas de pg_stat_statements',
      'Analiza patrones de consultas lentas',
      'Detecta escaneos secuenciales costosos',
      'Identifica índices no utilizados',
      'Monitoriza bloqueos y contención',
      'Genera señales priorizadas para el Architect',
    ],
    dataCollected: [
      'pg_stat_statements: consultas ejecutadas con tiempos',
      'pg_stat_user_tables: seq_scan, idx_scan counts',
      'pg_stat_activity: consultas activas y bloqueos',
      'pg_locks: información de bloqueos',
      'pg_stat_bgwriter: estadísticas de I/O',
    ],
    output: [
      'Señales de tipo slow_query, missing_index, unused_index',
      'Métricas agregadas por tabla e índice',
      'Ranking de consultas por tiempo total',
      'Alertas de bloqueos y deadlocks',
    ],
    technicalDetails: 'Requiere pg_stat_statements habilitado. Los umbrales de detección son configurables. Las señales se almacenan con severidad (high/medium/low) y se envían al Architect para generar propuestas.',
  },
  architect: {
    overview: 'El Architect analiza las señales del Observer y diseña soluciones de indexación óptimas. Utiliza IA (Claude) para generar propuestas de índices con justificaciones técnicas detalladas.',
    workflow: [
      'Procesa señales pendientes del Observer',
      'Analiza patrones WHERE/JOIN/ORDER BY',
      'Evalúa selectividad de columnas',
      'Propone índices B-tree, Hash, GIN, GiST según el caso',
      'Calcula impacto estimado en rendimiento',
      'Genera DDL con CONCURRENTLY cuando aplica',
    ],
    dataCollected: [
      'Señales de missing_index del Observer',
      'pg_stats: estadísticas de distribución de datos',
      'Patrones de consultas de pg_stat_statements',
      'Índices existentes para evitar duplicados',
    ],
    output: [
      'Propuestas de CREATE INDEX con justificación',
      'Estimación de mejora en tiempo de consulta',
      'DDL listo para ejecutar (requiere aprobación)',
      'Análisis de trade-offs (espacio vs velocidad)',
    ],
    technicalDetails: 'Usa Claude para análisis semántico de consultas. Considera índices parciales, covering indexes, y expresiones. Las propuestas pasan por aprobación manual antes de ejecutarse.',
  },
  gardener: {
    overview: 'El Gardener mantiene la salud de los índices existentes, identificando bloat, índices fragmentados, y planificando tareas de mantenimiento como REINDEX y VACUUM.',
    workflow: [
      'Analiza bloat de índices usando pgstattuple',
      'Identifica índices con baja utilización',
      'Detecta índices inválidos o corruptos',
      'Planifica ventanas de mantenimiento',
      'Genera comandos REINDEX CONCURRENTLY',
      'Monitoriza progreso de operaciones',
    ],
    dataCollected: [
      'pgstattuple: ratio de bloat real',
      'pg_stat_user_indexes: uso de índices',
      'pg_index: estado de validez',
      'pg_class: tamaño físico de índices',
    ],
    output: [
      'Lista de índices que necesitan REINDEX',
      'Recomendaciones de VACUUM ANALYZE',
      'Índices candidatos a eliminación',
      'Plan de mantenimiento priorizado',
    ],
    technicalDetails: 'El bloat se calcula comparando tamaño real vs estimado. Umbral por defecto: >20% bloat. Usa REINDEX CONCURRENTLY para evitar bloqueos en producción.',
  },
  partitioner: {
    overview: 'El Partitioner analiza tablas grandes y recomienda estrategias de particionamiento para mejorar el rendimiento de consultas y facilitar el mantenimiento de datos históricos.',
    workflow: [
      'Identifica tablas > 100K filas o > 50MB',
      'Analiza columnas candidatas (timestamps, enums)',
      'Evalúa patrones de consulta en pg_stat_statements',
      'Detecta particiones existentes',
      'Genera recomendaciones RANGE/LIST/HASH',
      'Crea plan de migración con SQL',
    ],
    dataCollected: [
      'pg_class: tamaño de tablas',
      'pg_stats: distribución de valores por columna',
      'pg_stat_statements: patrones WHERE comunes',
      'pg_inherits: jerarquía de particiones existentes',
      'pg_partitioned_table: configuración de particiones',
    ],
    output: [
      'Candidatos a particionamiento con score',
      'Tipo de partición recomendado (RANGE/LIST/HASH)',
      'Clave de partición óptima',
      'DDL de migración paso a paso',
      'Análisis de beneficios y riesgos',
    ],
    technicalDetails: 'Opera en modo solo lectura. El scoring considera: tamaño, patrón de acceso, cardinalidad de columnas, y presencia en cláusulas WHERE. Soporta particionamiento nativo de PostgreSQL 10+.',
  },
};

const agents = [
  {
    id: 'explorer',
    name: 'Explorer',
    description: 'Initial analysis, table classification, anomaly detection',
    icon: Compass,
    color: 'text-blue-500',
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-300 dark:border-blue-700',
  },
  {
    id: 'observer',
    name: 'Observer',
    description: 'Continuous monitoring, metrics collection, signal detection',
    icon: Eye,
    color: 'text-green-500',
    bg: 'bg-green-50 dark:bg-green-900/20',
    borderColor: 'border-green-300 dark:border-green-700',
  },
  {
    id: 'architect',
    name: 'Architect',
    description: 'Query analysis, index proposals with justifications',
    icon: Building2,
    color: 'text-purple-500',
    bg: 'bg-purple-50 dark:bg-purple-900/20',
    borderColor: 'border-purple-300 dark:border-purple-700',
  },
  {
    id: 'gardener',
    name: 'Gardener',
    description: 'Index health monitoring, maintenance scheduling',
    icon: Flower2,
    color: 'text-orange-500',
    bg: 'bg-orange-50 dark:bg-orange-900/20',
    borderColor: 'border-orange-300 dark:border-orange-700',
  },
  {
    id: 'partitioner',
    name: 'Partitioner',
    description: 'Table partitioning analysis and recommendations (read-only)',
    icon: Grid3X3,
    color: 'text-cyan-500',
    bg: 'bg-cyan-50 dark:bg-cyan-900/20',
    borderColor: 'border-cyan-300 dark:border-cyan-700',
  },
];

interface AgentInfoModalProps {
  agent: typeof agents[0];
  info: AgentTechnicalInfo;
  onClose: () => void;
}

function AgentInfoModal({ agent, info, onClose }: AgentInfoModalProps) {
  const Icon = agent.icon;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-[var(--card)] rounded-xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`${agent.bg} p-4 border-b border-[var(--border)]`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full bg-white/80 dark:bg-black/20 flex items-center justify-center`}>
                <Icon className={`h-5 w-5 ${agent.color}`} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-[var(--card-foreground)]">{agent.name}</h2>
                <p className="text-sm text-[var(--muted-foreground)]">{agent.description}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-black/10 dark:hover:bg-white/10 rounded-full transition-colors"
            >
              <X className="h-5 w-5 text-[var(--muted-foreground)]" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto max-h-[calc(85vh-100px)]">
          {/* Overview */}
          <div className="mb-5">
            <p className="text-sm text-[var(--card-foreground)] leading-relaxed">
              {info.overview}
            </p>
          </div>

          {/* Workflow */}
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-[var(--card-foreground)] mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]"></span>
              Flujo de trabajo
            </h3>
            <ol className="space-y-1.5 ml-4">
              {info.workflow.map((step, i) => (
                <li key={i} className="text-sm text-[var(--muted-foreground)] flex items-start gap-2">
                  <span className="text-[var(--primary)] font-mono text-xs mt-0.5">{i + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>

          {/* Data Collected */}
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-[var(--card-foreground)] mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
              Datos recopilados
            </h3>
            <ul className="space-y-1 ml-4">
              {info.dataCollected.map((data, i) => (
                <li key={i} className="text-sm text-[var(--muted-foreground)] flex items-start gap-2">
                  <code className="text-xs bg-[var(--secondary)] px-1 py-0.5 rounded font-mono">
                    {data.split(':')[0]}
                  </code>
                  <span className="text-xs">{data.includes(':') ? data.split(':')[1] : ''}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Output */}
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-[var(--card-foreground)] mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
              Output generado
            </h3>
            <ul className="space-y-1 ml-4">
              {info.output.map((out, i) => (
                <li key={i} className="text-sm text-[var(--muted-foreground)] flex items-start gap-2">
                  <span className="text-purple-500">-</span>
                  {out}
                </li>
              ))}
            </ul>
          </div>

          {/* Technical Details */}
          <div className="p-3 bg-[var(--secondary)]/50 rounded-lg border border-[var(--border)]">
            <h3 className="text-sm font-semibold text-[var(--card-foreground)] mb-1.5 flex items-center gap-2">
              <Info className="h-4 w-4 text-[var(--muted-foreground)]" />
              Detalles técnicos
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
              {info.technicalDetails}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AgentPanel({ databaseId, onAnalysisComplete }: AgentPanelProps) {
  const [agentStatus, setAgentStatus] = useState<Record<string, AgentStatus>>({});
  const [runningAll, setRunningAll] = useState(false);
  const [currentStep, setCurrentStep] = useState<number>(-1);
  const [shouldStop, setShouldStop] = useState(false);
  const [selectedAgentInfo, setSelectedAgentInfo] = useState<string | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  const updateAgentStatus = (agentId: string, state: AgentState, result: string | null = null) => {
    setAgentStatus(prev => ({
      ...prev,
      [agentId]: { state, result },
    }));
  };

  // Poll job status until completion
  const pollJobStatus = useCallback(async (jobId: string, agentId: string): Promise<string> => {
    const pollInterval = 1000; // 1 second
    const maxAttempts = 600; // 10 minutes max

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const job = await api.getJob(jobId);

      if (job.status === 'completed') {
        // Extract result summary from job
        if (job.result_json) {
          const result = job.result_json as Record<string, unknown>;
          switch (agentId) {
            case 'explorer':
              return `${result.anomalies_count || 0} anomalies found`;
            case 'observer':
              return `${result.metrics_collected || 0} metrics, ${result.signals_detected || 0} signals`;
            case 'architect':
              return `${result.proposals_created || 0} proposals created`;
            case 'gardener':
              return `${result.indexes_checked || 0} indexes, ${result.tasks_count || 0} tasks`;
            case 'partitioner':
              return `${result.recommendations_count || 0} recommendations`;
            default:
              return 'Completed';
          }
        }
        return 'Completed';
      }

      if (job.status === 'failed') {
        throw new Error(job.error || 'Job failed');
      }

      if (job.status === 'cancelled') {
        throw new Error('Job cancelled');
      }

      // Wait before next poll
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }

    throw new Error('Job timed out');
  }, []);

  // Start agent job and return job ID
  const startAgentJob = async (agentId: string): Promise<string> => {
    let response: { job_id: string };
    switch (agentId) {
      case 'explorer':
        response = await api.runExplorerBackground(databaseId);
        break;
      case 'observer':
        response = await api.runObserverBackground(databaseId);
        break;
      case 'architect':
        response = await api.runArchitectBackground(databaseId);
        break;
      case 'gardener':
        response = await api.runGardenerBackground(databaseId);
        break;
      case 'partitioner':
        response = await api.runPartitionerBackground(databaseId);
        break;
      default:
        throw new Error(`Unknown agent: ${agentId}`);
    }
    return response.job_id;
  };

  const runAgent = async (agentId: string) => {
    updateAgentStatus(agentId, 'running');

    try {
      const jobId = await startAgentJob(agentId);
      setCurrentJobId(jobId);
      const result = await pollJobStatus(jobId, agentId);
      updateAgentStatus(agentId, 'success', result);
      onAnalysisComplete?.();
    } catch (error) {
      updateAgentStatus(agentId, 'error', error instanceof Error ? error.message : 'Failed');
    } finally {
      setCurrentJobId(null);
    }
  };

  const stopAnalysis = async () => {
    setShouldStop(true);
    // Cancel current job if running
    if (currentJobId) {
      try {
        await api.cancelJob(currentJobId);
      } catch {
        // Ignore cancel errors
      }
    }
  };

  const runAllAgentsSequentially = async () => {
    setRunningAll(true);
    setCurrentStep(0);
    setShouldStop(false);

    // Reset all statuses to pending
    const initialStatus: Record<string, AgentStatus> = {};
    agents.forEach(agent => {
      initialStatus[agent.id] = { state: 'pending', result: null };
    });
    setAgentStatus(initialStatus);

    // Run agents sequentially with visual feedback
    for (let i = 0; i < agents.length; i++) {
      // Check if should stop before starting next agent
      if (shouldStop) {
        // Mark remaining agents as stopped
        for (let j = i; j < agents.length; j++) {
          updateAgentStatus(agents[j].id, 'error', 'Stopped by user');
        }
        break;
      }

      const agent = agents[i];
      setCurrentStep(i);
      updateAgentStatus(agent.id, 'running');

      try {
        const jobId = await startAgentJob(agent.id);
        setCurrentJobId(jobId);
        const result = await pollJobStatus(jobId, agent.id);
        updateAgentStatus(agent.id, 'success', result);
      } catch (error) {
        updateAgentStatus(agent.id, 'error', error instanceof Error ? error.message : 'Failed');
        // Continue with next agent even if one fails
      } finally {
        setCurrentJobId(null);
      }
    }

    setCurrentStep(-1);
    setRunningAll(false);
    setShouldStop(false);
    onAnalysisComplete?.();
  };

  const anyRunning = Object.values(agentStatus).some(s => s.state === 'running') || runningAll;

  // Calculate progress
  const completedCount = Object.values(agentStatus).filter(s => s.state === 'success' || s.state === 'error').length;
  const progressPercent = runningAll ? ((completedCount + 0.5) / agents.length) * 100 : 0;

  // Get status icon for an agent
  const getStatusIcon = (agentId: string, index: number) => {
    const status = agentStatus[agentId];
    if (!status || status.state === 'pending') {
      return <Circle className="h-5 w-5 text-gray-300" />;
    }
    if (status.state === 'running') {
      return <RefreshCw className="h-5 w-5 animate-spin text-blue-500" />;
    }
    if (status.state === 'success') {
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    }
    return <XCircle className="h-5 w-5 text-red-500" />;
  };

  const selectedAgent = selectedAgentInfo ? agents.find(a => a.id === selectedAgentInfo) : null;

  return (
    <>
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-[var(--card-foreground)]">
            Agents
          </h3>
          <div className="flex gap-2">
            {runningAll && (
              <Button
                onClick={stopAnalysis}
                variant="destructive"
                size="sm"
              >
                <StopCircle className="h-4 w-4 mr-2" />
                Stop
              </Button>
            )}
            <Button
              onClick={runAllAgentsSequentially}
              loading={runningAll}
              disabled={anyRunning}
              size="sm"
            >
              <PlayCircle className="h-4 w-4 mr-2" />
              Run All
            </Button>
          </div>
        </div>

        {/* Progress bar when running */}
        {runningAll && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-[var(--muted-foreground)]">
                Step {currentStep + 1} of {agents.length}
              </span>
              <span className="font-medium text-[var(--primary)]">
                {agents[currentStep]?.name} running...
              </span>
            </div>
            <div className="h-2 bg-[var(--muted)] rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--primary)] transition-all duration-500 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Sequential Pipeline View when running all */}
        {runningAll && (
          <div className="mb-4 p-4 bg-[var(--secondary)]/50 rounded-lg border border-[var(--border)]">
            <div className="flex items-center justify-between gap-2">
              {agents.map((agent, index) => {
                const Icon = agent.icon;
                const status = agentStatus[agent.id];
                const isActive = currentStep === index;
                const isCompleted = status?.state === 'success' || status?.state === 'error';
                const isPending = !status || status.state === 'pending';

                return (
                  <div key={agent.id} className="flex items-center flex-1">
                    <div className={`
                      flex flex-col items-center p-3 rounded-lg flex-1 transition-all duration-300
                      ${isActive ? 'bg-[var(--primary)]/10 ring-2 ring-[var(--primary)] scale-105' : ''}
                      ${isCompleted ? 'bg-green-50 dark:bg-green-900/20' : ''}
                      ${isPending ? 'opacity-50' : ''}
                    `}>
                      <div className={`
                        w-10 h-10 rounded-full flex items-center justify-center mb-2
                        ${isActive ? 'bg-[var(--primary)] text-white animate-pulse' : ''}
                        ${isCompleted && status?.state === 'success' ? 'bg-green-500 text-white' : ''}
                        ${isCompleted && status?.state === 'error' ? 'bg-red-500 text-white' : ''}
                        ${isPending ? 'bg-gray-200 dark:bg-gray-700' : ''}
                      `}>
                        {isActive ? (
                          <RefreshCw className="h-5 w-5 animate-spin" />
                        ) : isCompleted ? (
                          status?.state === 'success' ? <CheckCircle className="h-5 w-5" /> : <XCircle className="h-5 w-5" />
                        ) : (
                          <Icon className="h-5 w-5 text-gray-400" />
                        )}
                      </div>
                      <span className={`text-xs font-medium text-center ${isActive ? 'text-[var(--primary)]' : 'text-[var(--muted-foreground)]'}`}>
                        {agent.name}
                      </span>
                      {isActive && (
                        <span className="text-[10px] text-[var(--primary)] mt-1 animate-pulse">
                          Analyzing...
                        </span>
                      )}
                      {isCompleted && status?.result && (
                        <span className={`text-[10px] mt-1 text-center ${status.state === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                          {status.result}
                        </span>
                      )}
                    </div>
                    {index < agents.length - 1 && (
                      <ArrowRight className={`h-5 w-5 mx-1 flex-shrink-0 ${
                        index < currentStep ? 'text-green-500' : 'text-gray-300'
                      }`} />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Current step description */}
            {currentStep >= 0 && (
              <div className="mt-4 p-3 bg-[var(--primary)]/5 rounded border-l-4 border-[var(--primary)]">
                <div className="flex items-center gap-2 mb-1">
                  {(() => {
                    const Icon = agents[currentStep].icon;
                    return <Icon className={`h-4 w-4 ${agents[currentStep].color}`} />;
                  })()}
                  <span className="font-medium text-sm">{agents[currentStep].name}</span>
                </div>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {agents[currentStep].description}
                </p>
                {currentStep < agents.length - 1 && (
                  <p className="text-xs text-[var(--muted-foreground)] mt-2">
                    <span className="font-medium">Next:</span> {agents[currentStep + 1].name} - {agents[currentStep + 1].description}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Agent cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {agents.map((agent, index) => {
            const Icon = agent.icon;
            const status = agentStatus[agent.id];
            const isActive = runningAll && currentStep === index;

            return (
              <div
                key={agent.id}
                className={`
                  p-3 rounded-lg border transition-all duration-300
                  ${agent.bg}
                  ${isActive ? `ring-2 ring-[var(--primary)] ${agent.borderColor}` : 'border-[var(--border)]'}
                  ${runningAll && currentStep > index && status?.state === 'success' ? 'opacity-75' : ''}
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`
                      w-8 h-8 rounded-full flex items-center justify-center
                      ${isActive ? 'bg-[var(--primary)] animate-pulse' : ''}
                      ${status?.state === 'success' ? 'bg-green-100 dark:bg-green-900/30' : ''}
                      ${status?.state === 'error' ? 'bg-red-100 dark:bg-red-900/30' : ''}
                    `}>
                      {status?.state === 'running' ? (
                        <RefreshCw className={`h-4 w-4 animate-spin ${isActive ? 'text-white' : agent.color}`} />
                      ) : status?.state === 'success' ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : status?.state === 'error' ? (
                        <XCircle className="h-4 w-4 text-red-500" />
                      ) : (
                        <Icon className={`h-4 w-4 ${agent.color}`} />
                      )}
                    </div>
                    <div>
                      <span className="font-medium text-[var(--card-foreground)]">
                        {agent.name}
                      </span>
                      {runningAll && (
                        <span className="ml-2 text-xs text-[var(--muted-foreground)]">
                          (Step {index + 1})
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setSelectedAgentInfo(agent.id)}
                      className="h-7 w-7 p-0 flex items-center justify-center rounded-md hover:bg-black/5 dark:hover:bg-white/10 transition-colors"
                      title="Ver información técnica"
                    >
                      <Info className="h-4 w-4 text-[var(--muted-foreground)] hover:text-[var(--primary)]" />
                    </button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => runAgent(agent.id)}
                      disabled={anyRunning}
                      className="h-7 w-7 p-0"
                    >
                      {status?.state === 'running' ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-[var(--muted-foreground)] mt-1 ml-10">
                  {agent.description}
                </p>
                {status?.result && (
                  <div className="mt-2 ml-10 flex items-center gap-2">
                    {status.state === 'success' ? (
                      <CheckCircle className="h-3 w-3 text-green-500" />
                    ) : (
                      <XCircle className="h-3 w-3 text-red-500" />
                    )}
                    <span className={`text-xs ${status.state === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {status.result}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Info Modal */}
      {selectedAgent && agentTechnicalInfo[selectedAgent.id] && (
        <AgentInfoModal
          agent={selectedAgent}
          info={agentTechnicalInfo[selectedAgent.id]}
          onClose={() => setSelectedAgentInfo(null)}
        />
      )}
    </>
  );
}
