/**
 * PG Index Agents - Componente AnomaliesList
 * https://github.com/686f6c61/pg-index-agents
 *
 * Lista expandible de anomalias detectadas por el agente Explorer. Las
 * anomalias representan problemas estructurales o de diseno en los indices
 * y tablas de la base de datos.
 *
 * Tipos de anomalias soportados:
 *   - missing_secondary_index: Tabla sin indice en columna de FK
 *   - missing_filter_index: Consultas filtran por columnas sin indice
 *   - redundant_index: Indice cubierto por otro indice existente
 *   - unused_index: Indice que no se utiliza en consultas
 *
 * Cada anomalia incluye:
 *   - Severidad (high, medium, low)
 *   - Tabla afectada
 *   - Descripcion del problema
 *   - Recomendacion SQL
 *   - Opcion de obtener explicacion IA detallada
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { AIExplanation } from '@/components/ui/AIExplanation';
import { Anomaly } from '@/lib/api';
import { getSeverityColor } from '@/lib/utils';

/** Props del componente AnomaliesList */
interface AnomaliesListProps {
  anomalies: Anomaly[];
  databaseId: number;
}

export function AnomaliesList({ anomalies, databaseId }: AnomaliesListProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const high = anomalies.filter((a) => a.severity === 'high');
  const medium = anomalies.filter((a) => a.severity === 'medium');
  const low = anomalies.filter((a) => a.severity === 'low');

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'high':
        return <AlertTriangle className="h-5 w-5 text-red-500" />;
      case 'medium':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
      default:
        return <Info className="h-5 w-5 text-blue-500" />;
    }
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      missing_secondary_index: 'Missing Index',
      missing_filter_index: 'Missing Filter Index',
      redundant_index: 'Redundant Index',
      unused_index: 'Unused Index',
    };
    return labels[type] || type;
  };

  const renderAnomalyGroup = (title: string, items: Anomaly[], variant: 'danger' | 'warning' | 'info') => {
    if (items.length === 0) return null;

    return (
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <h4 className="font-semibold text-[var(--card-foreground)]">{title}</h4>
          <Badge variant={variant}>{items.length}</Badge>
        </div>
        <div className="space-y-2">
          {items.map((anomaly, index) => {
            const globalIndex = anomalies.indexOf(anomaly);
            const isExpanded = expandedIndex === globalIndex;

            return (
              <div
                key={index}
                className="border border-[var(--border)] rounded-lg overflow-hidden"
              >
                <button
                  className="w-full p-3 flex items-center justify-between bg-[var(--card)] hover:bg-[var(--secondary)] transition-colors"
                  onClick={() => setExpandedIndex(isExpanded ? null : globalIndex)}
                >
                  <div className="flex items-center gap-3">
                    {getSeverityIcon(anomaly.severity)}
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[var(--card-foreground)]">
                          {anomaly.table}
                        </span>
                        <Badge variant="default" size="sm">
                          {getTypeLabel(anomaly.type)}
                        </Badge>
                      </div>
                      <p className="text-sm text-[var(--muted-foreground)] line-clamp-1">
                        {anomaly.description}
                      </p>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="h-5 w-5 text-[var(--muted-foreground)]" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-[var(--muted-foreground)]" />
                  )}
                </button>

                {isExpanded && (
                  <div className="p-4 bg-[var(--secondary)] border-t border-[var(--border)]">
                    <p className="text-sm text-[var(--card-foreground)] mb-3">
                      {anomaly.description}
                    </p>
                    {anomaly.recommendation && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">
                          Recommendation:
                        </p>
                        <code className="block p-2 bg-[var(--card)] rounded text-sm font-mono text-[var(--primary)] overflow-x-auto">
                          {anomaly.recommendation}
                        </code>
                      </div>
                    )}
                    <AIExplanation
                      type="anomaly"
                      data={anomaly}
                      databaseId={databaseId}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Detected Anomalies</CardTitle>
        <p className="text-sm text-[var(--muted-foreground)]">
          {anomalies.length} issue{anomalies.length !== 1 ? 's' : ''} found
        </p>
      </CardHeader>
      <CardContent>
        {anomalies.length === 0 ? (
          <div className="text-center py-8 text-[var(--muted-foreground)]">
            No anomalies detected
          </div>
        ) : (
          <>
            {renderAnomalyGroup('High Severity', high, 'danger')}
            {renderAnomalyGroup('Medium Severity', medium, 'warning')}
            {renderAnomalyGroup('Low Severity', low, 'info')}
          </>
        )}
      </CardContent>
    </Card>
  );
}
