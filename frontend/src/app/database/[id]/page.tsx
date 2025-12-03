/**
 * PG Index Agents - Pagina de detalle de base de datos
 * https://github.com/686f6c61/pg-index-agents
 *
 * Vista principal de una base de datos registrada. Muestra los resultados
 * de los agentes, permite ejecutar nuevos analisis, y gestionar propuestas.
 *
 * Pestanas disponibles:
 *   - Overview: Resumen con metricas, plan de trabajo y anomalias destacadas
 *   - Tables: Clasificacion y estadisticas de todas las tablas
 *   - Anomalies: Lista completa de anomalias detectadas
 *   - Dependencies: Grafo interactivo de relaciones entre tablas
 *   - Signals: Senales de rendimiento del Observer
 *   - Proposals: Propuestas de indices del Architect (aprobar/rechazar)
 *   - Maintenance: Tareas de mantenimiento del Gardener
 *   - Partitioning: Recomendaciones del Partitioner
 *   - Settings: Configuracion de nivel de autonomia
 *   - Report: Informe completo con resumen ejecutivo IA
 *
 * Funcionalidades:
 *   - Ejecucion de agentes desde AgentPanel
 *   - Descarga de informes en TXT/Markdown
 *   - Limpieza de todos los resultados
 *   - Visualizacion de progreso de analisis en curso
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  RefreshCw,
  Play,
  Download,
  AlertCircle,
  Clock,
  Database as DatabaseIcon,
  Trash2,
  FileText,
  FileCode,
  Grid3X3,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { SummaryStats } from '@/components/analysis/SummaryStats';
import { TableClassifications } from '@/components/analysis/TableClassifications';
import { AnomaliesList } from '@/components/analysis/AnomaliesList';
import { DependencyGraph } from '@/components/analysis/DependencyGraph';
import { WorkPlan } from '@/components/analysis/WorkPlan';
import { AgentPanel } from '@/components/agents/AgentPanel';
import { SignalsList } from '@/components/agents/SignalsList';
import { ProposalsList } from '@/components/agents/ProposalsList';
import { MaintenanceTasks } from '@/components/agents/MaintenanceTasks';
import { AutonomySettings } from '@/components/agents/AutonomySettings';
import { ReportTab } from '@/components/reports/ReportTab';
import { api, Database, Analysis, Signal, Proposal, MaintenanceTask } from '@/lib/api';
import { formatDate } from '@/lib/utils';

/** Tipo union de las pestanas disponibles */
type Tab = 'overview' | 'tables' | 'anomalies' | 'graph' | 'signals' | 'proposals' | 'maintenance' | 'partitioning' | 'settings' | 'report';

interface PartitionAnalysis {
  large_tables: Array<{
    table_name: string;
    size_human: string;
    row_count: number;
  }>;
  partition_candidates: Array<{
    table_name: string;
    size_human: string;
    row_count: number;
    recommended_strategy: string;
    recommendation_confidence: number;
  }>;
  recommendations: Array<{
    table_name: string;
    partition_key: string;
    partition_type: string;
    partition_interval?: string;
    estimated_partitions: number;
    benefits: string[];
    risks: string[];
    sql_commands: string[];
    confidence: number;
  }>;
  existing_partitions: Array<{
    table_name: string;
    strategy: string;
    columns: string[];
    partition_count: number;
  }>;
}

export default function DatabaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const databaseId = params.id ? Number(params.id) : null;

  const [database, setDatabase] = useState<Database | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [maintenanceTasks, setMaintenanceTasks] = useState<MaintenanceTask[]>([]);
  const [partitionAnalysis, setPartitionAnalysis] = useState<PartitionAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const fetchData = useCallback(async () => {
    if (!databaseId) return;

    setLoading(true);
    setError(null);
    try {
      // Always fetch database first
      const dbData = await api.getDatabase(databaseId);
      setDatabase(dbData);

      // Fetch analysis data (may not exist)
      const [analysisData, signalsData, proposalsData] = await Promise.all([
        api.getAnalysis(databaseId, 'explorer').catch(() => null),
        api.getSignals(databaseId).catch(() => []),
        api.getProposals(databaseId).catch(() => []),
      ]);

      if (analysisData && 'result_json' in analysisData) {
        setAnalysis(analysisData as Analysis);
      } else {
        setAnalysis(null);
      }
      setSignals(Array.isArray(signalsData) ? signalsData : []);
      setProposals(Array.isArray(proposalsData) ? proposalsData : []);

      // Fetch gardener analysis for maintenance tasks
      const gardenerAnalysis = await api.getAnalysis(databaseId, 'gardener').catch(() => null);
      if (gardenerAnalysis && 'result_json' in gardenerAnalysis) {
        const result = gardenerAnalysis as { result_json: { maintenance_tasks?: MaintenanceTask[] } };
        setMaintenanceTasks(result.result_json?.maintenance_tasks || []);
      }

      // Fetch partitioner analysis
      const partitionerAnalysis = await api.getAnalysis(databaseId, 'partitioner').catch(() => null);
      if (partitionerAnalysis && 'result_json' in partitionerAnalysis) {
        const result = partitionerAnalysis as unknown as { result_json: PartitionAnalysis };
        setPartitionAnalysis(result.result_json || null);
      } else {
        setPartitionAnalysis(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [databaseId]);

  const runAnalysis = async () => {
    if (!databaseId) return;
    setAnalyzing(true);
    setError(null);
    try {
      // Use background job with polling
      const { job_id } = await api.runExplorerBackground(databaseId);

      // Poll for job completion
      const pollInterval = 1000;
      const maxAttempts = 600; // 10 minutes max

      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const job = await api.getJob(job_id);

        if (job.status === 'completed') {
          break;
        }
        if (job.status === 'failed') {
          throw new Error(job.error || 'Analysis failed');
        }
        if (job.status === 'cancelled') {
          throw new Error('Analysis cancelled');
        }

        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }

      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const clearResults = async () => {
    if (!databaseId) return;
    setClearing(true);
    setError(null);
    try {
      await api.clearResults(databaseId);
      setAnalysis(null);
      setSignals([]);
      setProposals([]);
      setMaintenanceTasks([]);
      setPartitionAnalysis(null);
      setShowClearDialog(false);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear results');
    } finally {
      setClearing(false);
    }
  };

  const downloadReportMarkdown = () => {
    if (!analysis?.result_markdown) return;
    const blob = new Blob([analysis.result_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${database?.name || 'database'}-analysis.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadReportTxt = () => {
    if (!analysis?.result_markdown) return;
    const blob = new Blob([analysis.result_markdown], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${database?.name || 'database'}-analysis.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (databaseId) {
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [databaseId]);

  // Show loader only while actively loading with a valid databaseId
  if (loading && databaseId) {
    return (
      <div className="flex items-center justify-center py-24">
        <RefreshCw className="h-8 w-8 animate-spin text-[var(--primary)]" />
      </div>
    );
  }

  // Invalid database ID
  if (!databaseId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <AlertCircle className="h-12 w-12 text-[var(--destructive)]" />
        <p className="text-[var(--muted-foreground)]">Invalid database ID</p>
        <Button onClick={() => router.push('/')} variant="secondary">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Databases
        </Button>
      </div>
    );
  }

  if (error && !database) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <AlertCircle className="h-12 w-12 text-[var(--destructive)]" />
        <p className="text-[var(--muted-foreground)]">{error}</p>
        <Button onClick={() => router.push('/')} variant="secondary">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Databases
        </Button>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'tables', label: 'Tables' },
    { key: 'anomalies', label: 'Anomalies', count: analysis?.result_json.anomalies.length },
    { key: 'graph', label: 'Dependencies' },
    { key: 'signals', label: 'Signals', count: signals.length },
    { key: 'proposals', label: 'Proposals', count: proposals.length },
    { key: 'maintenance', label: 'Maintenance', count: maintenanceTasks.length },
    { key: 'partitioning', label: 'Partitioning', count: partitionAnalysis?.recommendations?.length },
    { key: 'settings', label: 'Settings' },
    { key: 'report', label: 'Informe' },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.push('/')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-[var(--primary)]/10 rounded-lg">
              <DatabaseIcon className="h-8 w-8 text-[var(--primary)]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[var(--foreground)]">
                {database?.name}
              </h1>
              <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                <span>{database?.database_name}</span>
                <Badge variant={database?.status === 'active' ? 'success' : 'warning'}>
                  {database?.status}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {analysis && (
            <>
              <Button variant="secondary" onClick={downloadReportTxt}>
                <FileText className="h-4 w-4 mr-2" />
                TXT
              </Button>
              <Button variant="secondary" onClick={downloadReportMarkdown}>
                <FileCode className="h-4 w-4 mr-2" />
                Markdown
              </Button>
              <Button
                variant="secondary"
                onClick={() => setShowClearDialog(true)}
                className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Limpiar
              </Button>
            </>
          )}
          <Button onClick={runAnalysis} loading={analyzing}>
            <Play className="h-4 w-4 mr-2" />
            {analysis ? 'Re-analizar' : 'Analizar'}
          </Button>
        </div>
      </div>

      {/* Last analysis info */}
      {analysis && (
        <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] mb-6">
          <Clock className="h-4 w-4" />
          <span>Last analyzed: {formatDate(analysis.created_at)}</span>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <Card className="mb-6 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </Card>
      )}

      {/* No analysis state */}
      {!analysis && !analyzing && (
        <div className="space-y-6">
          <AgentPanel databaseId={databaseId} onAnalysisComplete={fetchData} />
          <Card className="text-center py-12">
            <DatabaseIcon className="h-16 w-16 mx-auto text-[var(--muted-foreground)] mb-4" />
            <h2 className="text-xl font-semibold text-[var(--card-foreground)] mb-2">
              No Analysis Yet
            </h2>
            <p className="text-[var(--muted-foreground)] mb-4">
              Use the Explorer agent above to analyze this database
            </p>
          </Card>
        </div>
      )}

      {/* Analysis content */}
      {analysis && (
        <>
          {/* Summary stats */}
          <div className="mb-6">
            <SummaryStats analysis={analysis} />
          </div>

          {/* Tabs */}
          <div className="border-b border-[var(--border)] mb-6">
            <nav className="flex gap-6">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`pb-3 text-sm font-medium transition-colors relative flex items-center gap-2 ${
                    activeTab === tab.key
                      ? 'text-[var(--primary)]'
                      : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                  }`}
                >
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className="text-xs bg-[var(--muted)] px-1.5 py-0.5 rounded-full">
                      {tab.count}
                    </span>
                  )}
                  {activeTab === tab.key && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />
                  )}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab content */}
          <div>
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <AgentPanel databaseId={databaseId} onAnalysisComplete={fetchData} />
                <WorkPlan workPlan={analysis.result_json.work_plan} />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <AnomaliesList anomalies={analysis.result_json.anomalies.slice(0, 5)} databaseId={databaseId} />
                  <DependencyGraph
                    graph={analysis.result_json.dependency_graph}
                    classifications={analysis.result_json.table_classifications}
                  />
                </div>
              </div>
            )}

            {activeTab === 'tables' && (
              <TableClassifications
                classifications={analysis.result_json.table_classifications}
              />
            )}

            {activeTab === 'anomalies' && (
              <AnomaliesList anomalies={analysis.result_json.anomalies} databaseId={databaseId} />
            )}

            {activeTab === 'graph' && (
              <DependencyGraph
                graph={analysis.result_json.dependency_graph}
                classifications={analysis.result_json.table_classifications}
              />
            )}

            {activeTab === 'signals' && (
              <SignalsList signals={signals} databaseId={databaseId} />
            )}

            {activeTab === 'proposals' && (
              <ProposalsList proposals={proposals} onUpdate={fetchData} />
            )}

            {activeTab === 'maintenance' && (
              <MaintenanceTasks tasks={maintenanceTasks} databaseId={databaseId} />
            )}

            {activeTab === 'partitioning' && (
              <div className="space-y-6">
                {!partitionAnalysis ? (
                  <Card className="text-center py-12">
                    <Grid3X3 className="h-16 w-16 mx-auto text-[var(--muted-foreground)] mb-4" />
                    <h2 className="text-xl font-semibold text-[var(--card-foreground)] mb-2">
                      Sin Analisis de Particionamiento
                    </h2>
                    <p className="text-[var(--muted-foreground)] mb-4">
                      Ejecuta el agente Partitioner para analizar oportunidades de particionamiento
                    </p>
                  </Card>
                ) : (
                  <>
                    {/* Summary Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <Card className="text-center">
                        <div className="text-3xl font-bold text-[var(--primary)]">
                          {partitionAnalysis.large_tables?.length || 0}
                        </div>
                        <div className="text-sm text-[var(--muted-foreground)]">Tablas Grandes</div>
                      </Card>
                      <Card className="text-center">
                        <div className="text-3xl font-bold text-cyan-500">
                          {partitionAnalysis.partition_candidates?.length || 0}
                        </div>
                        <div className="text-sm text-[var(--muted-foreground)]">Candidatas</div>
                      </Card>
                      <Card className="text-center">
                        <div className="text-3xl font-bold text-green-500">
                          {partitionAnalysis.recommendations?.length || 0}
                        </div>
                        <div className="text-sm text-[var(--muted-foreground)]">Recomendaciones</div>
                      </Card>
                      <Card className="text-center">
                        <div className="text-3xl font-bold text-purple-500">
                          {partitionAnalysis.existing_partitions?.length || 0}
                        </div>
                        <div className="text-sm text-[var(--muted-foreground)]">Ya Particionadas</div>
                      </Card>
                    </div>

                    {/* Existing Partitions */}
                    {partitionAnalysis.existing_partitions?.length > 0 && (
                      <Card>
                        <h3 className="text-lg font-semibold mb-4">Tablas Ya Particionadas</h3>
                        <div className="space-y-2">
                          {partitionAnalysis.existing_partitions.map((p, i) => (
                            <div key={i} className="p-3 bg-[var(--secondary)] rounded-lg flex items-center justify-between">
                              <div>
                                <span className="font-medium">{p.table_name}</span>
                                <span className="text-sm text-[var(--muted-foreground)] ml-2">
                                  {p.strategy.toUpperCase()} por {p.columns?.join(', ')}
                                </span>
                              </div>
                              <Badge variant="info">{p.partition_count} particiones</Badge>
                            </div>
                          ))}
                        </div>
                      </Card>
                    )}

                    {/* Recommendations */}
                    {partitionAnalysis.recommendations?.length > 0 && (
                      <Card>
                        <h3 className="text-lg font-semibold mb-4">Recomendaciones de Particionamiento</h3>
                        <div className="space-y-4">
                          {partitionAnalysis.recommendations.map((rec, i) => (
                            <div key={i} className="border border-[var(--border)] rounded-lg p-4">
                              <div className="flex items-start justify-between mb-3">
                                <div>
                                  <h4 className="font-bold text-lg">{rec.table_name}</h4>
                                  <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                                    <span>Partition key: <strong>{rec.partition_key}</strong></span>
                                    <Badge variant={rec.partition_type === 'range' ? 'success' : rec.partition_type === 'list' ? 'info' : 'warning'}>
                                      {rec.partition_type.toUpperCase()}
                                    </Badge>
                                    {rec.partition_interval && (
                                      <span>({rec.partition_interval})</span>
                                    )}
                                  </div>
                                </div>
                                <div className="text-right">
                                  <div className="text-sm text-[var(--muted-foreground)]">Confianza</div>
                                  <div className={`font-bold ${rec.confidence >= 0.7 ? 'text-green-500' : rec.confidence >= 0.5 ? 'text-yellow-500' : 'text-red-500'}`}>
                                    {Math.round(rec.confidence * 100)}%
                                  </div>
                                </div>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                <div>
                                  <h5 className="font-medium text-green-600 mb-2">Beneficios</h5>
                                  <ul className="text-sm space-y-1">
                                    {rec.benefits?.slice(0, 3).map((b, j) => (
                                      <li key={j} className="flex items-start gap-2">
                                        <span className="text-green-500">+</span>
                                        <span>{b}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                                <div>
                                  <h5 className="font-medium text-red-600 mb-2">Riesgos</h5>
                                  <ul className="text-sm space-y-1">
                                    {rec.risks?.slice(0, 3).map((r, j) => (
                                      <li key={j} className="flex items-start gap-2">
                                        <span className="text-red-500">-</span>
                                        <span>{r}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>

                              {rec.sql_commands?.length > 0 && (
                                <div>
                                  <h5 className="font-medium mb-2">Comandos SQL</h5>
                                  <pre className="text-xs bg-[var(--secondary)] p-3 rounded overflow-x-auto">
                                    {rec.sql_commands.join('\n')}
                                  </pre>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </Card>
                    )}

                    {/* Large Tables */}
                    {partitionAnalysis.large_tables?.length > 0 && (
                      <Card>
                        <h3 className="text-lg font-semibold mb-4">Tablas Grandes Analizadas</h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-[var(--border)]">
                                <th className="text-left py-2 px-3">Tabla</th>
                                <th className="text-right py-2 px-3">Tamano</th>
                                <th className="text-right py-2 px-3">Filas</th>
                              </tr>
                            </thead>
                            <tbody>
                              {partitionAnalysis.large_tables.map((t, i) => (
                                <tr key={i} className="border-b border-[var(--border)]">
                                  <td className="py-2 px-3 font-medium">{t.table_name}</td>
                                  <td className="py-2 px-3 text-right">{t.size_human}</td>
                                  <td className="py-2 px-3 text-right">{t.row_count?.toLocaleString()}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </Card>
                    )}
                  </>
                )}
              </div>
            )}

            {activeTab === 'settings' && (
              <AutonomySettings databaseId={databaseId} />
            )}

            {activeTab === 'report' && (
              <ReportTab
                analysis={analysis}
                signals={signals}
                proposals={proposals}
                maintenanceTasks={maintenanceTasks}
                databaseId={databaseId}
                databaseName={database?.name || 'database'}
              />
            )}
          </div>
        </>
      )}

      {/* Clear Results Dialog */}
      <Dialog
        open={showClearDialog}
        onClose={() => setShowClearDialog(false)}
        title="Clear All Results"
        description="This will permanently delete all analysis results, signals, proposals, and logs for this database. This action cannot be undone."
        confirmText="Clear All"
        cancelText="Cancel"
        onConfirm={clearResults}
        variant="danger"
        loading={clearing}
      />
    </div>
  );
}
