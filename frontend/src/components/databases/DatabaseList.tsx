/**
 * PG Index Agents - Componente DatabaseList
 * https://github.com/686f6c61/pg-index-agents
 *
 * Lista de bases de datos registradas en el sistema. Muestra todas las
 * bases de datos en un grid responsive de tarjetas y permite agregar
 * nuevas bases de datos.
 *
 * Funcionalidades:
 *   - Carga automatica de bases de datos al montar
 *   - Indicador de carga y manejo de errores
 *   - Boton de refresh para actualizar la lista
 *   - Estado vacio con call-to-action para agregar primera BD
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useEffect, useState } from 'react';
import { Plus, RefreshCw, AlertCircle } from 'lucide-react';
import { DatabaseCard } from './DatabaseCard';
import { Button } from '@/components/ui/Button';
import { api, Database } from '@/lib/api';

/** Componente que renderiza la lista de bases de datos */
export function DatabaseList() {
  const [databases, setDatabases] = useState<Database[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDatabases = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listDatabases();
      setDatabases(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch databases');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatabases();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-8 w-8 animate-spin text-[var(--primary)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <AlertCircle className="h-12 w-12 text-[var(--destructive)]" />
        <p className="text-[var(--muted-foreground)]">{error}</p>
        <Button onClick={fetchDatabases} variant="secondary">
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[var(--foreground)]">Databases</h2>
          <p className="text-[var(--muted-foreground)]">
            {databases.length} database{databases.length !== 1 ? 's' : ''} connected
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={fetchDatabases}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Database
          </Button>
        </div>
      </div>

      {databases.length === 0 ? (
        <div className="text-center py-12 bg-[var(--card)] border border-[var(--border)] rounded-lg">
          <p className="text-[var(--muted-foreground)] mb-4">
            No databases connected yet
          </p>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add your first database
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {databases.map((db) => (
            <DatabaseCard key={db.id} database={db} />
          ))}
        </div>
      )}
    </div>
  );
}
