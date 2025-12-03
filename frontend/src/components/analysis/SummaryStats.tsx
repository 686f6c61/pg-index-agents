/**
 * PG Index Agents - Componente SummaryStats
 * https://github.com/686f6c61/pg-index-agents
 *
 * Panel de metricas resumidas del analisis Explorer. Muestra los
 * indicadores clave en tarjetas compactas para una vision rapida
 * del estado de la base de datos.
 *
 * Metricas mostradas:
 *   - Tamano de la base de datos (humanizado)
 *   - Numero de tablas
 *   - Numero de indices
 *   - Numero de foreign keys
 *   - Total de anomalias (con color segun severidad)
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { Database, Table, Key, AlertTriangle, HardDrive } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Analysis } from '@/lib/api';

/** Props del componente SummaryStats */
interface SummaryStatsProps {
  analysis: Analysis;
}

export function SummaryStats({ analysis }: SummaryStatsProps) {
  const { metadata_summary, work_plan } = analysis.result_json;

  const stats = [
    {
      label: 'Database Size',
      value: metadata_summary.database_size.size_human,
      icon: HardDrive,
      color: 'text-blue-500',
      bg: 'bg-blue-100 dark:bg-blue-900/30',
    },
    {
      label: 'Tables',
      value: metadata_summary.tables,
      icon: Table,
      color: 'text-purple-500',
      bg: 'bg-purple-100 dark:bg-purple-900/30',
    },
    {
      label: 'Indexes',
      value: metadata_summary.indexes,
      icon: Key,
      color: 'text-green-500',
      bg: 'bg-green-100 dark:bg-green-900/30',
    },
    {
      label: 'Foreign Keys',
      value: metadata_summary.foreign_keys,
      icon: Database,
      color: 'text-orange-500',
      bg: 'bg-orange-100 dark:bg-orange-900/30',
    },
    {
      label: 'Anomalies',
      value: work_plan.summary.total_anomalies,
      icon: AlertTriangle,
      color: work_plan.summary.high_severity_anomalies > 0 ? 'text-red-500' : 'text-yellow-500',
      bg: work_plan.summary.high_severity_anomalies > 0
        ? 'bg-red-100 dark:bg-red-900/30'
        : 'bg-yellow-100 dark:bg-yellow-900/30',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {stats.map((stat) => (
        <Card key={stat.label} className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${stat.bg}`}>
            <stat.icon className={`h-5 w-5 ${stat.color}`} />
          </div>
          <div>
            <p className="text-2xl font-bold text-[var(--card-foreground)]">
              {stat.value}
            </p>
            <p className="text-xs text-[var(--muted-foreground)]">{stat.label}</p>
          </div>
        </Card>
      ))}
    </div>
  );
}
