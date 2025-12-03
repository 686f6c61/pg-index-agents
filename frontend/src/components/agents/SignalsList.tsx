/**
 * PG Index Agents - Componente SignalsList
 * https://github.com/686f6c61/pg-index-agents
 *
 * Lista de senales de rendimiento detectadas por el agente Observer.
 * Las senales representan problemas en tiempo real identificados
 * mediante el analisis de pg_stat_statements y otras estadisticas.
 *
 * Tipos de senales:
 *   - slow_query: Consultas lentas que superan umbrales de tiempo
 *   - missing_index: Escaneos secuenciales en tablas grandes
 *   - unused_index: Indices que consumen espacio sin ser utilizados
 *   - lock_contention: Bloqueos frecuentes entre transacciones
 *
 * Cada senal incluye:
 *   - Severidad y tipo de senal
 *   - Estado (pending, addressed)
 *   - Timestamp de deteccion
 *   - Detalles JSON expandibles
 *   - Explicacion IA bajo demanda
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { AlertTriangle, AlertCircle, Info, Clock } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { AIExplanation } from '@/components/ui/AIExplanation';
import { Signal } from '@/lib/api';
import { formatDate } from '@/lib/utils';

/** Props del componente SignalsList */
interface SignalsListProps {
  signals: Signal[];
  databaseId: number;
}

const severityConfig = {
  high: {
    icon: AlertTriangle,
    color: 'text-red-500',
    bg: 'bg-red-50 dark:bg-red-900/20',
    badge: 'destructive' as const,
  },
  medium: {
    icon: AlertCircle,
    color: 'text-yellow-500',
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    badge: 'warning' as const,
  },
  low: {
    icon: Info,
    color: 'text-blue-500',
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    badge: 'secondary' as const,
  },
};

export function SignalsList({ signals, databaseId }: SignalsListProps) {
  if (signals.length === 0) {
    return (
      <Card className="text-center py-8">
        <Info className="h-12 w-12 mx-auto text-[var(--muted-foreground)] mb-3" />
        <p className="text-[var(--muted-foreground)]">No signals detected</p>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          Run the Observer agent to detect performance signals
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-[var(--card-foreground)]">
        Signals ({signals.length})
      </h3>
      {signals.map((signal) => {
        const config = severityConfig[signal.severity as keyof typeof severityConfig] || severityConfig.low;
        const Icon = config.icon;

        const borderColorClass = config.badge === 'destructive' ? 'border-l-red-500' :
                                 config.badge === 'warning' ? 'border-l-yellow-500' : 'border-l-blue-500';
        return (
          <Card key={signal.id} className={`${config.bg} border-l-4 ${borderColorClass}`}>
            <div className="flex items-start gap-3">
              <Icon className={`h-5 w-5 ${config.color} mt-0.5 flex-shrink-0`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={config.badge}>{signal.severity}</Badge>
                  <Badge variant="secondary">{signal.signal_type}</Badge>
                  <Badge variant={signal.status === 'pending' ? 'warning' : 'success'}>
                    {signal.status}
                  </Badge>
                </div>
                <p className="text-sm text-[var(--card-foreground)]">{signal.description}</p>
                <div className="flex items-center gap-1 mt-2 text-xs text-[var(--muted-foreground)]">
                  <Clock className="h-3 w-3" />
                  <span>{formatDate(signal.detected_at)}</span>
                </div>
                {signal.details_json && (
                  <details className="mt-2">
                    <summary className="text-xs text-[var(--muted-foreground)] cursor-pointer hover:text-[var(--foreground)]">
                      View details
                    </summary>
                    <pre className="mt-1 text-xs bg-[var(--secondary)] p-2 rounded overflow-auto max-h-40">
                      {JSON.stringify(signal.details_json, null, 2)}
                    </pre>
                  </details>
                )}
                <AIExplanation
                  type="signal"
                  data={signal}
                  databaseId={databaseId}
                />
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
