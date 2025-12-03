/**
 * PG Index Agents - Componente ReportTab
 * https://github.com/686f6c61/pg-index-agents
 *
 * Vista de informe completo que consolida todos los resultados de los
 * agentes en un formato estructurado y exportable. Incluye resumen
 * ejecutivo generado por IA y secciones expandibles.
 *
 * Secciones del informe:
 *   - Resumen ejecutivo IA: Sintesis generada con Claude
 *   - Anomalias detectadas: Del agente Explorer
 *   - Senales de rendimiento: Del agente Observer
 *   - Propuestas de indices: Del agente Architect
 *   - Tareas de mantenimiento: Del agente Gardener
 *   - Informe original markdown: Del analisis Explorer
 *
 * Funcionalidades:
 *   - Estadisticas rapidas en cards superiores
 *   - Secciones colapsables para navegacion facil
 *   - Descarga en formato TXT o Markdown
 *   - Regeneracion del resumen ejecutivo
 *   - Explicacion IA para cada elemento individual
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState, useEffect } from 'react';
import { FileText, FileCode, Sparkles, RefreshCw, AlertTriangle, AlertCircle, Wrench, Database, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { AIExplanation } from '@/components/ui/AIExplanation';
import { api, Analysis, Signal, Proposal, MaintenanceTask, Anomaly } from '@/lib/api';

/** Props del componente ReportTab */
interface ReportTabProps {
  analysis: Analysis;
  signals: Signal[];
  proposals: Proposal[];
  maintenanceTasks: MaintenanceTask[];
  databaseId: number;
  databaseName: string;
}

export function ReportTab({
  analysis,
  signals,
  proposals,
  maintenanceTasks,
  databaseId,
  databaseName,
}: ReportTabProps) {
  const [executiveSummary, setExecutiveSummary] = useState<string | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [errorSummary, setErrorSummary] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    summary: true,
    anomalies: true,
    signals: true,
    proposals: true,
    maintenance: true,
    original: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const generateSummary = async (isAutomatic = false) => {
    // Don't auto-generate if already loading or already have a summary
    if (isAutomatic && (loadingSummary || executiveSummary)) return;
    setLoadingSummary(true);
    setErrorSummary(null);
    try {
      const result = await api.generateReportSummary(databaseId);
      setExecutiveSummary(result.summary);
    } catch (err) {
      setErrorSummary(err instanceof Error ? err.message : 'Error al generar resumen');
    } finally {
      setLoadingSummary(false);
    }
  };

  const downloadReportMarkdown = () => {
    if (!analysis?.result_markdown) return;
    const blob = new Blob([analysis.result_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${databaseName}-analysis.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadReportTxt = () => {
    if (!analysis?.result_markdown) return;
    const blob = new Blob([analysis.result_markdown], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${databaseName}-analysis.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Auto-generate executive summary on mount
  useEffect(() => {
    generateSummary(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [databaseId]);

  const anomalies = analysis.result_json.anomalies || [];
  const highAnomalies = anomalies.filter(a => a.severity === 'high');
  const mediumAnomalies = anomalies.filter(a => a.severity === 'medium');
  const lowAnomalies = anomalies.filter(a => a.severity === 'low');

  const highSignals = signals.filter(s => s.severity === 'high');
  const pendingProposals = proposals.filter(p => p.status === 'pending');
  const highMaintenanceTasks = maintenanceTasks.filter(t => t.priority === 'high');

  return (
    <div className="space-y-6">
      {/* Header with download buttons */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-[var(--card-foreground)]">
          Informe Completo del Analisis
        </h2>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={downloadReportTxt}>
            <FileText className="h-4 w-4 mr-2" />
            TXT
          </Button>
          <Button variant="secondary" size="sm" onClick={downloadReportMarkdown}>
            <FileCode className="h-4 w-4 mr-2" />
            Markdown
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center p-4">
          <div className="text-2xl font-bold text-red-500">{highAnomalies.length}</div>
          <div className="text-xs text-[var(--muted-foreground)]">Anomalias Criticas</div>
        </Card>
        <Card className="text-center p-4">
          <div className="text-2xl font-bold text-yellow-500">{highSignals.length}</div>
          <div className="text-xs text-[var(--muted-foreground)]">Senales Alta Sev.</div>
        </Card>
        <Card className="text-center p-4">
          <div className="text-2xl font-bold text-blue-500">{pendingProposals.length}</div>
          <div className="text-xs text-[var(--muted-foreground)]">Propuestas Pendientes</div>
        </Card>
        <Card className="text-center p-4">
          <div className="text-2xl font-bold text-orange-500">{highMaintenanceTasks.length}</div>
          <div className="text-xs text-[var(--muted-foreground)]">Mant. Urgente</div>
        </Card>
      </div>

      {/* Executive Summary Section */}
      <Card>
        <button
          onClick={() => toggleSection('summary')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--secondary)] transition-colors rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <Sparkles className="h-5 w-5 text-purple-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[var(--card-foreground)]">Resumen Ejecutivo IA</h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                Analisis generado con inteligencia artificial
              </p>
            </div>
          </div>
          {expandedSections.summary ? (
            <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
          ) : (
            <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
          )}
        </button>

        {expandedSections.summary && (
          <div className="p-4 border-t border-[var(--border)]">
            {loadingSummary && (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-8 w-8 animate-spin text-purple-500 mr-3" />
                <span className="text-[var(--muted-foreground)]">
                  Generando resumen ejecutivo con IA...
                </span>
              </div>
            )}

            {errorSummary && !loadingSummary && (
              <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg">
                {errorSummary}
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => generateSummary(false)}
                  className="mt-2"
                >
                  Reintentar
                </Button>
              </div>
            )}

            {executiveSummary && !loadingSummary && (
              <>
                <div className="prose prose-sm dark:prose-invert max-w-none bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 p-4 rounded-lg">
                  <ReactMarkdown
                    components={{
                      h1: ({children}) => <h1 className="text-lg font-bold text-[var(--primary)] mt-4 mb-2 first:mt-0">{children}</h1>,
                      h2: ({children}) => <h2 className="text-base font-bold text-[var(--primary)] mt-4 mb-2">{children}</h2>,
                      h3: ({children}) => <h3 className="text-sm font-bold text-[var(--primary)] mt-3 mb-1">{children}</h3>,
                      p: ({children}) => <p className="mb-2 text-sm leading-relaxed text-[var(--card-foreground)]">{children}</p>,
                      ul: ({children}) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
                      li: ({children}) => <li className="text-sm text-[var(--card-foreground)]">{children}</li>,
                      code: ({children}) => <code className="bg-[var(--secondary)] px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                      pre: ({children}) => <pre className="bg-[var(--secondary)] p-3 rounded-lg my-2 overflow-x-auto">{children}</pre>,
                      strong: ({children}) => <strong className="font-semibold text-[var(--primary)]">{children}</strong>,
                    }}
                  >
                    {executiveSummary}
                  </ReactMarkdown>
                </div>
                <div className="mt-3 flex justify-end">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setExecutiveSummary(null);
                      generateSummary(false);
                    }}
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Regenerar Resumen
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </Card>

      {/* Anomalies Section */}
      <Card>
        <button
          onClick={() => toggleSection('anomalies')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--secondary)] transition-colors rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
              <AlertTriangle className="h-5 w-5 text-red-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[var(--card-foreground)]">
                Anomalias Detectadas
              </h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                {anomalies.length} anomalias ({highAnomalies.length} altas, {mediumAnomalies.length} medias, {lowAnomalies.length} bajas)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {highAnomalies.length > 0 && <Badge variant="destructive">{highAnomalies.length}</Badge>}
            {expandedSections.anomalies ? (
              <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
            ) : (
              <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
            )}
          </div>
        </button>

        {expandedSections.anomalies && (
          <div className="p-4 border-t border-[var(--border)] space-y-3 max-h-[500px] overflow-y-auto">
            {anomalies.map((anomaly, index) => (
              <AnomalyItem key={index} anomaly={anomaly} databaseId={databaseId} />
            ))}
          </div>
        )}
      </Card>

      {/* Signals Section */}
      <Card>
        <button
          onClick={() => toggleSection('signals')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--secondary)] transition-colors rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
              <AlertCircle className="h-5 w-5 text-yellow-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[var(--card-foreground)]">
                Senales de Rendimiento
              </h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                {signals.length} senales detectadas
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {highSignals.length > 0 && <Badge variant="warning">{highSignals.length}</Badge>}
            {expandedSections.signals ? (
              <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
            ) : (
              <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
            )}
          </div>
        </button>

        {expandedSections.signals && (
          <div className="p-4 border-t border-[var(--border)] space-y-3 max-h-[500px] overflow-y-auto">
            {signals.length === 0 ? (
              <p className="text-center text-[var(--muted-foreground)] py-4">
                No hay senales detectadas. Ejecuta el agente Observer para detectar senales.
              </p>
            ) : (
              signals.map((signal) => (
                <SignalItem key={signal.id} signal={signal} databaseId={databaseId} />
              ))
            )}
          </div>
        )}
      </Card>

      {/* Proposals Section */}
      <Card>
        <button
          onClick={() => toggleSection('proposals')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--secondary)] transition-colors rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <Database className="h-5 w-5 text-blue-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[var(--card-foreground)]">
                Propuestas de Indices
              </h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                {proposals.length} propuestas ({pendingProposals.length} pendientes)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {pendingProposals.length > 0 && <Badge variant="info">{pendingProposals.length}</Badge>}
            {expandedSections.proposals ? (
              <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
            ) : (
              <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
            )}
          </div>
        </button>

        {expandedSections.proposals && (
          <div className="p-4 border-t border-[var(--border)] space-y-3 max-h-[500px] overflow-y-auto">
            {proposals.length === 0 ? (
              <p className="text-center text-[var(--muted-foreground)] py-4">
                No hay propuestas de indices. Ejecuta el agente Architect para generar propuestas.
              </p>
            ) : (
              proposals.map((proposal) => (
                <ProposalItem key={proposal.id} proposal={proposal} databaseId={databaseId} />
              ))
            )}
          </div>
        )}
      </Card>

      {/* Maintenance Section */}
      <Card>
        <button
          onClick={() => toggleSection('maintenance')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--secondary)] transition-colors rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <Wrench className="h-5 w-5 text-orange-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[var(--card-foreground)]">
                Tareas de Mantenimiento
              </h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                {maintenanceTasks.length} tareas ({highMaintenanceTasks.length} urgentes)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {highMaintenanceTasks.length > 0 && <Badge variant="destructive">{highMaintenanceTasks.length}</Badge>}
            {expandedSections.maintenance ? (
              <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
            ) : (
              <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
            )}
          </div>
        </button>

        {expandedSections.maintenance && (
          <div className="p-4 border-t border-[var(--border)] space-y-3 max-h-[500px] overflow-y-auto">
            {maintenanceTasks.length === 0 ? (
              <p className="text-center text-[var(--muted-foreground)] py-4">
                No hay tareas de mantenimiento. Ejecuta el agente Gardener para detectar tareas.
              </p>
            ) : (
              maintenanceTasks.map((task, index) => (
                <MaintenanceItem key={index} task={task} databaseId={databaseId} />
              ))
            )}
          </div>
        )}
      </Card>

      {/* Original Report Section */}
      <Card>
        <button
          onClick={() => toggleSection('original')}
          className="w-full flex items-center justify-between p-4 hover:bg-[var(--secondary)] transition-colors rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gray-100 dark:bg-gray-900/30 rounded-lg">
              <FileText className="h-5 w-5 text-gray-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[var(--card-foreground)]">
                Informe Original del Explorer
              </h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                Informe markdown generado por el agente Explorer
              </p>
            </div>
          </div>
          {expandedSections.original ? (
            <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
          ) : (
            <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
          )}
        </button>

        {expandedSections.original && (
          <div className="p-4 border-t border-[var(--border)] overflow-auto max-h-[70vh]">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown
                components={{
                  h1: ({children}) => <h1 className="text-xl font-bold text-[var(--primary)] mt-6 mb-3 first:mt-0 border-b pb-2">{children}</h1>,
                  h2: ({children}) => <h2 className="text-lg font-bold text-[var(--primary)] mt-5 mb-2">{children}</h2>,
                  h3: ({children}) => <h3 className="text-base font-bold text-[var(--primary)] mt-4 mb-2">{children}</h3>,
                  h4: ({children}) => <h4 className="text-sm font-bold text-[var(--primary)] mt-3 mb-1">{children}</h4>,
                  p: ({children}) => <p className="mb-3 text-sm leading-relaxed text-[var(--card-foreground)]">{children}</p>,
                  ul: ({children}) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                  ol: ({children}) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
                  li: ({children}) => <li className="text-sm text-[var(--card-foreground)]">{children}</li>,
                  code: ({children, className}) => {
                    const isBlock = className?.includes('language-');
                    return isBlock
                      ? <code className="block bg-[var(--secondary)] p-3 rounded text-xs font-mono my-2 overflow-x-auto">{children}</code>
                      : <code className="bg-[var(--secondary)] px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>;
                  },
                  pre: ({children}) => <pre className="bg-[var(--secondary)] p-4 rounded-lg my-3 overflow-x-auto text-xs">{children}</pre>,
                  strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                  table: ({children}) => <table className="w-full border-collapse my-3 text-sm">{children}</table>,
                  thead: ({children}) => <thead className="bg-[var(--secondary)]">{children}</thead>,
                  th: ({children}) => <th className="border border-[var(--border)] px-3 py-2 text-left font-medium">{children}</th>,
                  td: ({children}) => <td className="border border-[var(--border)] px-3 py-2">{children}</td>,
                  hr: () => <hr className="my-4 border-[var(--border)]" />,
                  blockquote: ({children}) => <blockquote className="border-l-4 border-[var(--primary)] pl-4 italic my-3 text-[var(--muted-foreground)]">{children}</blockquote>,
                }}
              >
                {analysis.result_markdown}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

// Sub-components for each item type
function AnomalyItem({ anomaly, databaseId }: { anomaly: Anomaly; databaseId: number }) {
  const [expanded, setExpanded] = useState(false);
  const severityColors = {
    high: 'border-l-red-500 bg-red-50 dark:bg-red-900/10',
    medium: 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10',
    low: 'border-l-blue-500 bg-blue-50 dark:bg-blue-900/10',
  };

  return (
    <div className={`border-l-4 rounded-lg p-3 ${severityColors[anomaly.severity]}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-[var(--card-foreground)]">{anomaly.table}</span>
            <Badge variant={anomaly.severity === 'high' ? 'destructive' : anomaly.severity === 'medium' ? 'warning' : 'secondary'} size="sm">
              {anomaly.severity}
            </Badge>
            <Badge variant="default" size="sm">{anomaly.type}</Badge>
          </div>
          <p className="text-sm text-[var(--muted-foreground)]">{anomaly.description}</p>
          {anomaly.recommendation && (
            <code className="block mt-2 p-2 bg-[var(--card)] rounded text-xs font-mono overflow-x-auto">
              {anomaly.recommendation}
            </code>
          )}
        </div>
      </div>
      <AIExplanation type="anomaly" data={anomaly} databaseId={databaseId} />
    </div>
  );
}

function SignalItem({ signal, databaseId }: { signal: Signal; databaseId: number }) {
  const severityColors = {
    high: 'border-l-red-500 bg-red-50 dark:bg-red-900/10',
    medium: 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10',
    low: 'border-l-blue-500 bg-blue-50 dark:bg-blue-900/10',
  };

  return (
    <div className={`border-l-4 rounded-lg p-3 ${severityColors[signal.severity as keyof typeof severityColors] || severityColors.low}`}>
      <div className="flex items-center gap-2 mb-1">
        <Badge variant={signal.severity === 'high' ? 'destructive' : signal.severity === 'medium' ? 'warning' : 'secondary'} size="sm">
          {signal.severity}
        </Badge>
        <Badge variant="default" size="sm">{signal.signal_type}</Badge>
        <Badge variant={signal.status === 'pending' ? 'warning' : 'success'} size="sm">
          {signal.status}
        </Badge>
      </div>
      <p className="text-sm text-[var(--card-foreground)]">{signal.description}</p>
      <AIExplanation type="signal" data={signal} databaseId={databaseId} />
    </div>
  );
}

function ProposalItem({ proposal, databaseId }: { proposal: Proposal; databaseId: number }) {
  return (
    <div className="border-l-4 border-l-blue-500 bg-blue-50 dark:bg-blue-900/10 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        <Badge variant={proposal.status === 'pending' ? 'warning' : proposal.status === 'approved' ? 'success' : 'secondary'} size="sm">
          {proposal.status}
        </Badge>
        <Badge variant="default" size="sm">{proposal.proposal_type}</Badge>
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none text-[var(--muted-foreground)] mb-2">
        <ReactMarkdown
          components={{
            h1: ({children}) => <h1 className="text-base font-bold text-[var(--primary)] mt-3 mb-2">{children}</h1>,
            h2: ({children}) => <h2 className="text-sm font-bold text-[var(--primary)] mt-3 mb-1">{children}</h2>,
            h3: ({children}) => <h3 className="text-sm font-semibold text-[var(--primary)] mt-2 mb-1">{children}</h3>,
            p: ({children}) => <p className="mb-2 text-sm leading-relaxed">{children}</p>,
            ul: ({children}) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
            ol: ({children}) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
            li: ({children}) => <li className="text-sm">{children}</li>,
            code: ({children, className}) => {
              const isBlock = className?.includes('language-');
              return isBlock
                ? <code className="block bg-[var(--secondary)] p-2 rounded text-xs font-mono my-2 overflow-x-auto">{children}</code>
                : <code className="bg-[var(--secondary)] px-1 py-0.5 rounded text-xs font-mono">{children}</code>;
            },
            pre: ({children}) => <pre className="bg-[var(--secondary)] p-3 rounded-lg my-2 overflow-x-auto">{children}</pre>,
            strong: ({children}) => <strong className="font-semibold text-[var(--primary)]">{children}</strong>,
          }}
        >
          {proposal.justification}
        </ReactMarkdown>
      </div>
      <code className="block p-2 bg-[var(--card)] rounded text-xs font-mono overflow-x-auto">
        {proposal.sql_command}
      </code>
      <AIExplanation type="proposal" data={proposal} databaseId={databaseId} />
    </div>
  );
}

function MaintenanceItem({ task, databaseId }: { task: MaintenanceTask; databaseId: number }) {
  const priorityColors = {
    high: 'border-l-red-500 bg-red-50 dark:bg-red-900/10',
    medium: 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10',
    low: 'border-l-blue-500 bg-blue-50 dark:bg-blue-900/10',
  };

  return (
    <div className={`border-l-4 rounded-lg p-3 ${priorityColors[task.priority]}`}>
      <div className="flex items-center gap-2 mb-1">
        <Badge variant={task.priority === 'high' ? 'destructive' : task.priority === 'medium' ? 'warning' : 'secondary'} size="sm">
          {task.priority}
        </Badge>
        <Badge variant="default" size="sm">{task.task_type}</Badge>
        <span className="text-sm font-medium text-[var(--card-foreground)]">
          {task.index_name || task.table_name}
        </span>
      </div>
      <p className="text-sm text-[var(--muted-foreground)] mb-2">{task.reason}</p>
      <code className="block p-2 bg-[var(--card)] rounded text-xs font-mono overflow-x-auto">
        {task.sql_command}
      </code>
      <p className="text-xs text-[var(--muted-foreground)] mt-2">
        Duracion estimada: {task.estimated_duration}
      </p>
      <AIExplanation type="maintenance" data={task} databaseId={databaseId} />
    </div>
  );
}
