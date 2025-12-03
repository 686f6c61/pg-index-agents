/**
 * PG Index Agents - Componente WorkPlan
 * https://github.com/686f6c61/pg-index-agents
 *
 * Visualiza el plan de trabajo generado por el agente Explorer. Muestra
 * tres columnas con las tareas priorizadas para cada agente subsiguiente.
 *
 * Secciones:
 *   - Observer priorities: Tablas de alta criticidad que deben monitorearse
 *   - Architect tasks: Anomalias que requieren creacion de indices
 *   - Gardener tasks: Indices que necesitan mantenimiento o eliminacion
 *
 * Este componente sirve como resumen ejecutivo de las acciones recomendadas
 * tras el analisis inicial de la base de datos.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { Eye, Wrench, Leaf, ChevronRight } from 'lucide-react';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { WorkPlan as WorkPlanType } from '@/lib/api';

/** Props del componente WorkPlan */
interface WorkPlanProps {
  workPlan: WorkPlanType;
}

export function WorkPlan({ workPlan }: WorkPlanProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Observer Priorities */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
            <Eye className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold text-[var(--card-foreground)]">Observer</h3>
            <p className="text-xs text-[var(--muted-foreground)]">Monitor priorities</p>
          </div>
        </div>

        {workPlan.observer_priorities.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">No high-priority tables</p>
        ) : (
          <ul className="space-y-2">
            {workPlan.observer_priorities.slice(0, 5).map((item, index) => (
              <li
                key={index}
                className="flex items-center gap-2 p-2 bg-[var(--secondary)] rounded-lg text-sm"
              >
                <ChevronRight className="h-4 w-4 text-[var(--muted-foreground)]" />
                <span className="font-medium text-[var(--card-foreground)]">{item.table}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Architect Tasks */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <Wrench className="h-5 w-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold text-[var(--card-foreground)]">Architect</h3>
            <p className="text-xs text-[var(--muted-foreground)]">Index improvements</p>
          </div>
          <Badge variant="warning" className="ml-auto">
            {workPlan.architect_tasks.length}
          </Badge>
        </div>

        {workPlan.architect_tasks.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">No index improvements needed</p>
        ) : (
          <ul className="space-y-2">
            {workPlan.architect_tasks.slice(0, 5).map((task, index) => (
              <li
                key={index}
                className="p-2 bg-[var(--secondary)] rounded-lg text-sm"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-[var(--card-foreground)]">{task.table}</span>
                  <Badge size="sm">{task.type.replace(/_/g, ' ')}</Badge>
                </div>
                <p className="text-xs text-[var(--muted-foreground)] line-clamp-2">
                  {task.description}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Gardener Tasks */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
            <Leaf className="h-5 w-5 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <h3 className="font-semibold text-[var(--card-foreground)]">Gardener</h3>
            <p className="text-xs text-[var(--muted-foreground)]">Maintenance tasks</p>
          </div>
          <Badge variant="info" className="ml-auto">
            {workPlan.gardener_tasks.length}
          </Badge>
        </div>

        {workPlan.gardener_tasks.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">No maintenance needed</p>
        ) : (
          <ul className="space-y-2">
            {workPlan.gardener_tasks.slice(0, 5).map((task, index) => (
              <li
                key={index}
                className="p-2 bg-[var(--secondary)] rounded-lg text-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-[var(--card-foreground)]">{task.index}</span>
                  <Badge size="sm" variant={task.type === 'unused_index' ? 'warning' : 'default'}>
                    {task.type.replace(/_/g, ' ')}
                  </Badge>
                </div>
                <p className="text-xs text-[var(--muted-foreground)]">
                  on {task.table}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
