/**
 * PG Index Agents - Componente DatabaseCard
 * https://github.com/686f6c61/pg-index-agents
 *
 * Tarjeta que muestra informacion resumida de una base de datos registrada.
 * Se utiliza en el listado principal de bases de datos y enlaza a la pagina
 * de detalle donde se puede ejecutar el analisis completo.
 *
 * Informacion mostrada:
 *   - Nombre y nombre de la base de datos PostgreSQL
 *   - Estado de conexion (active/inactive)
 *   - Fecha del ultimo analisis o indicador de "nunca analizada"
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import Link from 'next/link';
import { Database, Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Database as DatabaseType } from '@/lib/api';
import { formatDate } from '@/lib/utils';

/** Props del componente DatabaseCard */
interface DatabaseCardProps {
  database: DatabaseType;
}

export function DatabaseCard({ database }: DatabaseCardProps) {
  const statusVariant = database.status === 'active' ? 'success' : 'warning';

  return (
    <Link href={`/database/${database.id}`}>
      <Card className="hover:border-[var(--primary)] transition-colors cursor-pointer">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[var(--primary)]/10 rounded-lg">
              <Database className="h-6 w-6 text-[var(--primary)]" />
            </div>
            <div>
              <h3 className="font-semibold text-[var(--card-foreground)]">
                {database.name}
              </h3>
              <p className="text-sm text-[var(--muted-foreground)]">
                {database.database_name}
              </p>
            </div>
          </div>
          <Badge variant={statusVariant}>{database.status}</Badge>
        </div>

        <div className="mt-4 pt-4 border-t border-[var(--border)]">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-1 text-[var(--muted-foreground)]">
              <Clock className="h-4 w-4" />
              <span>
                {database.last_analysis
                  ? `Analyzed ${formatDate(database.last_analysis)}`
                  : 'Never analyzed'}
              </span>
            </div>
            {database.last_analysis ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
            )}
          </div>
        </div>
      </Card>
    </Link>
  );
}
