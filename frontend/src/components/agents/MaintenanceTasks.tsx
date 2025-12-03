/**
 * PG Index Agents - Componente MaintenanceTasks
 * https://github.com/686f6c61/pg-index-agents
 *
 * Lista de tareas de mantenimiento generadas por el agente Gardener.
 * Estas tareas representan operaciones necesarias para mantener
 * la salud de los indices existentes.
 *
 * Tipos de tareas:
 *   - reindex: Indices con bloat excesivo que necesitan reconstruirse
 *   - vacuum: Tablas que requieren VACUUM ANALYZE
 *   - review_index: Indices a revisar manualmente por bajo uso
 *
 * Cada tarea incluye:
 *   - Prioridad (high, medium, low)
 *   - Indice o tabla afectada
 *   - Razon de la recomendacion
 *   - Comando SQL con boton de copiar
 *   - Duracion estimada de la operacion
 *   - Explicacion IA bajo demanda
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState } from 'react';
import { Wrench, AlertTriangle, Clock, Copy, Check, Database } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { AIExplanation } from '@/components/ui/AIExplanation';
import { MaintenanceTask } from '@/lib/api';

/** Props del componente MaintenanceTasks */
interface MaintenanceTasksProps {
  tasks: MaintenanceTask[];
  databaseId: number;
}

const priorityConfig = {
  high: {
    color: 'text-red-500',
    bg: 'bg-red-50 dark:bg-red-900/20',
    badge: 'destructive' as const,
  },
  medium: {
    color: 'text-yellow-500',
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    badge: 'warning' as const,
  },
  low: {
    color: 'text-blue-500',
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    badge: 'secondary' as const,
  },
};

const taskTypeIcons: Record<string, typeof Wrench> = {
  reindex: Wrench,
  vacuum: Database,
  review_index: AlertTriangle,
};

export function MaintenanceTasks({ tasks, databaseId }: MaintenanceTasksProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyToClipboard = async (sql: string, index: number) => {
    await navigator.clipboard.writeText(sql);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  if (tasks.length === 0) {
    return (
      <Card className="text-center py-8">
        <Wrench className="h-12 w-12 mx-auto text-[var(--muted-foreground)] mb-3" />
        <p className="text-[var(--muted-foreground)]">No maintenance tasks needed</p>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          All indexes are healthy
        </p>
      </Card>
    );
  }

  const highPriority = tasks.filter(t => t.priority === 'high');
  const mediumPriority = tasks.filter(t => t.priority === 'medium');
  const lowPriority = tasks.filter(t => t.priority === 'low');

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--card-foreground)]">
          Maintenance Tasks ({tasks.length})
        </h3>
        <div className="flex items-center gap-2">
          {highPriority.length > 0 && (
            <Badge variant="destructive">{highPriority.length} high</Badge>
          )}
          {mediumPriority.length > 0 && (
            <Badge variant="warning">{mediumPriority.length} medium</Badge>
          )}
          {lowPriority.length > 0 && (
            <Badge variant="secondary">{lowPriority.length} low</Badge>
          )}
        </div>
      </div>

      {tasks.map((task, index) => {
        const config = priorityConfig[task.priority] || priorityConfig.low;
        const Icon = taskTypeIcons[task.task_type] || Wrench;

        return (
          <Card key={index} className={`${config.bg}`}>
            <div className="flex items-start gap-3">
              <Icon className={`h-5 w-5 ${config.color} mt-0.5 flex-shrink-0`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={config.badge}>{task.priority}</Badge>
                  <Badge variant="secondary">{task.task_type}</Badge>
                  <span className="text-sm font-medium text-[var(--card-foreground)]">
                    {task.index_name || task.table_name}
                  </span>
                </div>

                <p className="text-sm text-[var(--muted-foreground)] mb-3">
                  {task.reason}
                </p>

                <div className="relative">
                  <pre className="text-xs bg-[var(--background)] p-2 rounded overflow-x-auto font-mono">
                    {task.sql_command}
                  </pre>
                  <button
                    onClick={() => copyToClipboard(task.sql_command, index)}
                    className="absolute top-1 right-1 p-1 bg-[var(--secondary)] rounded hover:bg-[var(--muted)] transition-colors"
                    title="Copy SQL"
                  >
                    {copiedIndex === index ? (
                      <Check className="h-3 w-3 text-green-500" />
                    ) : (
                      <Copy className="h-3 w-3 text-[var(--muted-foreground)]" />
                    )}
                  </button>
                </div>

                <div className="flex items-center gap-1 mt-2 text-xs text-[var(--muted-foreground)]">
                  <Clock className="h-3 w-3" />
                  <span>Duration: {task.estimated_duration}</span>
                </div>

                <AIExplanation
                  type="maintenance"
                  data={task}
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
