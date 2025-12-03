/**
 * PG Index Agents - Componente ProposalsList
 * https://github.com/686f6c61/pg-index-agents
 *
 * Lista de propuestas de indices generadas por el agente Architect.
 * Cada propuesta incluye justificacion detallada generada con IA,
 * comando SQL, y controles para aprobar o rechazar.
 *
 * Tipos de propuestas:
 *   - create_index: Creacion de nuevo indice
 *   - drop_index: Eliminacion de indice redundante o no usado
 *   - analyze_table: Actualizacion de estadisticas
 *
 * Estados de propuestas:
 *   - pending: Pendiente de revision humana
 *   - approved: Aprobada y ejecutada
 *   - rejected: Rechazada por el usuario
 *   - executed: Ejecutada exitosamente
 *
 * Funcionalidades:
 *   - Justificacion Markdown con formato enriquecido
 *   - Impacto estimado (mejora de rendimiento, espacio)
 *   - Copiar SQL al portapapeles
 *   - Expandir/colapsar analisis detallado
 *   - Aprobar ejecuta el comando automaticamente
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState, useMemo, useCallback, memo } from 'react';
import { FileCode, CheckCircle, XCircle, Clock, Zap, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Proposal, api } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';

/** Props del componente ProposalsList */
interface ProposalsListProps {
  proposals: Proposal[];
  onUpdate?: () => void;
}

// Helper to safely parse estimated_impact_json
function parseEstimatedImpact(impact: any): Record<string, string> | null {
  if (!impact) return null;

  // If it's already an object, use it
  if (typeof impact === 'object' && !Array.isArray(impact)) {
    return impact;
  }

  // If it's a string, try to parse it
  if (typeof impact === 'string') {
    try {
      return JSON.parse(impact);
    } catch {
      return null;
    }
  }

  return null;
}

// Format impact value for display
function formatImpactValue(key: string, value: any): string {
  if (key === 'space_savings' && typeof value === 'number') {
    const mb = value / 1024 / 1024;
    return `${mb.toFixed(1)} MB`;
  }
  if (typeof value === 'string') {
    return value.replace(/_/g, ' ');
  }
  return String(value);
}

// Get badge variant based on impact type
function getImpactVariant(key: string, value: any): 'success' | 'warning' | 'secondary' | 'destructive' {
  const val = String(value).toLowerCase();
  if (val === 'high' || val === 'very_high') return 'success';
  if (val === 'medium') return 'warning';
  if (val === 'none' || val === 'low') return 'secondary';
  return 'secondary';
}

// Extract short justification (first sentence or paragraph)
function getShortJustification(justification: string): string {
  // Find the first line break or analysis section
  const analysisStart = justification.indexOf('**Analisis');
  const analysisStartAlt = justification.indexOf('ANALISIS');
  const splitPoint = analysisStart > 0 ? analysisStart : (analysisStartAlt > 0 ? analysisStartAlt : -1);

  if (splitPoint > 0) {
    return justification.substring(0, splitPoint).trim();
  }

  // Otherwise return first ~200 chars
  if (justification.length > 200) {
    return justification.substring(0, 200) + '...';
  }
  return justification;
}

// Check if there's detailed analysis
function hasDetailedAnalysis(justification: string): boolean {
  return justification.includes('**Analisis') ||
         justification.includes('ANALISIS') ||
         justification.length > 300;
}

export function ProposalsList({ proposals, onUpdate }: ProposalsListProps) {
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [loading, setLoading] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const copyToClipboard = async (sql: string, id: number) => {
    await navigator.clipboard.writeText(sql);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleApprove = async (proposalId: number) => {
    setLoading(proposalId);
    try {
      await api.approveProposal(proposalId);
      onUpdate?.();
    } catch (error) {
      console.error('Failed to approve proposal:', error);
    } finally {
      setLoading(null);
    }
  };

  const handleReject = async (proposalId: number) => {
    setLoading(proposalId);
    try {
      await api.rejectProposal(proposalId);
      onUpdate?.();
    } catch (error) {
      console.error('Failed to reject proposal:', error);
    } finally {
      setLoading(null);
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (proposals.length === 0) {
    return (
      <Card className="text-center py-8">
        <FileCode className="h-12 w-12 mx-auto text-[var(--muted-foreground)] mb-3" />
        <p className="text-[var(--muted-foreground)]">No hay propuestas pendientes</p>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          Ejecuta el agente Architect para generar propuestas de indices
        </p>
      </Card>
    );
  }

  // Get human-readable proposal type
  const getProposalTypeLabel = (type: string) => {
    switch (type) {
      case 'drop_index': return 'Eliminar Indice';
      case 'create_index': return 'Crear Indice';
      case 'analyze_table': return 'Analizar Tabla';
      default: return type.replace(/_/g, ' ');
    }
  };

  // Get human-readable status
  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending': return 'Pendiente';
      case 'approved': return 'Aprobada';
      case 'rejected': return 'Rechazada';
      case 'executed': return 'Ejecutada';
      default: return status;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--card-foreground)]">
          Propuestas de Indices ({proposals.length})
        </h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Aprobar ejecuta el comando SQL. Rechazar descarta la propuesta.
        </p>
      </div>

      {proposals.map((proposal) => {
        const impact = parseEstimatedImpact(proposal.estimated_impact_json);
        const isExpanded = expandedId === proposal.id;
        const showExpandButton = hasDetailedAnalysis(proposal.justification);
        const shortJustification = getShortJustification(proposal.justification);

        return (
          <Card key={proposal.id} className="overflow-hidden">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="secondary">{getProposalTypeLabel(proposal.proposal_type)}</Badge>
                <Badge
                  variant={
                    proposal.status === 'pending'
                      ? 'warning'
                      : proposal.status === 'approved'
                      ? 'success'
                      : 'destructive'
                  }
                >
                  {getStatusLabel(proposal.status)}
                </Badge>
              </div>
              <div className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
                <Clock className="h-3 w-3" />
                <span>{formatDate(proposal.created_at)}</span>
              </div>
            </div>

            {/* Justification */}
            <div className="mb-3">
              <div className="prose prose-sm dark:prose-invert max-w-none text-[var(--card-foreground)]">
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
                    blockquote: ({children}) => <blockquote className="border-l-4 border-purple-400 pl-3 italic my-2 text-sm">{children}</blockquote>,
                  }}
                >
                  {isExpanded ? proposal.justification : shortJustification}
                </ReactMarkdown>
              </div>
              {showExpandButton && (
                <button
                  onClick={() => toggleExpand(proposal.id)}
                  className="mt-2 flex items-center gap-1 text-xs text-[var(--primary)] hover:underline"
                >
                  {isExpanded ? (
                    <>
                      <ChevronUp className="h-3 w-3" />
                      Ocultar analisis detallado
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-3 w-3" />
                      Ver analisis detallado
                    </>
                  )}
                </button>
              )}
            </div>

            {/* SQL Command */}
            <div className="relative">
              <pre className="text-xs bg-[var(--secondary)] p-3 rounded-lg overflow-x-auto font-mono">
                {proposal.sql_command}
              </pre>
              <button
                onClick={() => copyToClipboard(proposal.sql_command, proposal.id)}
                className="absolute top-2 right-2 p-1.5 bg-[var(--background)] rounded hover:bg-[var(--muted)] transition-colors"
                title="Copiar SQL"
              >
                {copiedId === proposal.id ? (
                  <Check className="h-4 w-4 text-green-500" />
                ) : (
                  <Copy className="h-4 w-4 text-[var(--muted-foreground)]" />
                )}
              </button>
            </div>

            {/* Estimated Impact - properly parsed */}
            {impact && (
              <div className="mt-3 p-3 bg-[var(--secondary)]/50 rounded-lg">
                <div className="flex items-center gap-2 mb-2 text-sm font-medium">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  <span>Impacto Estimado</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(impact).map(([key, value]) => {
                    const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    const displayValue = formatImpactValue(key, value);
                    return (
                      <div key={key} className="flex items-center gap-1">
                        <span className="text-xs text-[var(--muted-foreground)]">{label}:</span>
                        <Badge variant={getImpactVariant(key, value)} className="text-xs">
                          {displayValue}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Actions */}
            {proposal.status === 'pending' && (
              <div className="mt-4 flex items-center gap-2 pt-3 border-t border-[var(--border)]">
                <Button
                  size="sm"
                  onClick={() => handleApprove(proposal.id)}
                  loading={loading === proposal.id}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <CheckCircle className="h-4 w-4 mr-1" />
                  Aprobar (Ejecutar)
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleReject(proposal.id)}
                  loading={loading === proposal.id}
                >
                  <XCircle className="h-4 w-4 mr-1" />
                  Rechazar
                </Button>
                <span className="text-xs text-[var(--muted-foreground)] ml-2">
                  Al aprobar, el comando SQL se ejecutara automaticamente.
                </span>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
