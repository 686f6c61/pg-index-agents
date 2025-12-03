/**
 * PG Index Agents - Componente TableClassifications
 * https://github.com/686f6c61/pg-index-agents
 *
 * Tabla interactiva con la clasificacion de todas las tablas analizadas.
 * Permite ordenar por cualquier columna y filtrar por tipo de tabla.
 *
 * Columnas mostradas:
 *   - Nombre de tabla
 *   - Tipo (central, log, catalog, junction, transactional, data)
 *   - Numero de filas
 *   - Tamano en disco
 *   - Numero de columnas
 *   - Numero de indices
 *   - Criticidad (high, medium, low)
 *
 * La clasificacion se genera mediante IA en el agente Explorer y refleja
 * el rol funcional de cada tabla en el esquema de la base de datos.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState } from 'react';
import { Table, ArrowUpDown, Database } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { TableClassification } from '@/lib/api';
import { formatBytes, formatNumber, getTableTypeColor, getCriticalityColor } from '@/lib/utils';

/** Props del componente TableClassifications */
interface TableClassificationsProps {
  classifications: Record<string, TableClassification>;
}

type SortKey = 'name' | 'row_count' | 'total_size_bytes' | 'type' | 'criticality';
type SortOrder = 'asc' | 'desc';

export function TableClassifications({ classifications }: TableClassificationsProps) {
  const [sortKey, setSortKey] = useState<SortKey>('row_count');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [filterType, setFilterType] = useState<string>('all');

  const tables = Object.values(classifications);
  const types = ['all', ...new Set(tables.map((t) => t.type))];

  const filteredTables = tables.filter(
    (t) => filterType === 'all' || t.type === filterType
  );

  const sortedTables = [...filteredTables].sort((a, b) => {
    let comparison = 0;
    switch (sortKey) {
      case 'name':
        comparison = a.name.localeCompare(b.name);
        break;
      case 'row_count':
        comparison = a.row_count - b.row_count;
        break;
      case 'total_size_bytes':
        comparison = a.total_size_bytes - b.total_size_bytes;
        break;
      case 'type':
        comparison = a.type.localeCompare(b.type);
        break;
      case 'criticality':
        const order = { high: 0, medium: 1, low: 2 };
        comparison = (order[a.criticality as keyof typeof order] || 3) -
                     (order[b.criticality as keyof typeof order] || 3);
        break;
    }
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  const SortHeader = ({ label, sortKeyName }: { label: string; sortKeyName: SortKey }) => (
    <th
      className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider cursor-pointer hover:text-[var(--foreground)] transition-colors"
      onClick={() => handleSort(sortKeyName)}
    >
      <div className="flex items-center gap-1">
        {label}
        <ArrowUpDown className={`h-3 w-3 ${sortKey === sortKeyName ? 'text-[var(--primary)]' : ''}`} />
      </div>
    </th>
  );

  return (
    <Card padding="none">
      <div className="p-4 border-b border-[var(--border)]">
        <CardHeader className="p-0 pb-2">
          <CardTitle>Table Classifications</CardTitle>
          <p className="text-sm text-[var(--muted-foreground)]">
            {tables.length} tables analyzed
          </p>
        </CardHeader>
        <div className="flex gap-2 mt-4 flex-wrap">
          {types.map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1 text-sm rounded-full transition-colors ${
                filterType === type
                  ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                  : 'bg-[var(--secondary)] text-[var(--secondary-foreground)] hover:bg-[var(--accent)]'
              }`}
            >
              {type === 'all' ? 'All' : type}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-[var(--secondary)]">
            <tr>
              <SortHeader label="Table" sortKeyName="name" />
              <SortHeader label="Type" sortKeyName="type" />
              <SortHeader label="Rows" sortKeyName="row_count" />
              <SortHeader label="Size" sortKeyName="total_size_bytes" />
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Columns
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">
                Indexes
              </th>
              <SortHeader label="Criticality" sortKeyName="criticality" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {sortedTables.map((table) => (
              <tr key={table.name} className="hover:bg-[var(--secondary)] transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-[var(--muted-foreground)]" />
                    <span className="font-medium text-[var(--card-foreground)]">
                      {table.name}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <Badge className={getTableTypeColor(table.type)}>{table.type}</Badge>
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] font-mono text-sm">
                  {formatNumber(table.row_count)}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] font-mono text-sm">
                  {formatBytes(table.total_size_bytes)}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] text-sm">
                  {table.column_count}
                </td>
                <td className="px-4 py-3 text-[var(--muted-foreground)] text-sm">
                  {table.index_count}
                </td>
                <td className="px-4 py-3">
                  <span className={`font-medium ${getCriticalityColor(table.criticality)}`}>
                    {table.criticality}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
