/**
 * PG Index Agents - Componente DependencyGraph
 * https://github.com/686f6c61/pg-index-agents
 *
 * Visualizacion SVG del grafo de dependencias entre tablas. Muestra las
 * relaciones de foreign keys y las inferidas por convencion de nombres
 * en un layout circular interactivo.
 *
 * Caracteristicas:
 *   - Layout circular con tablas criticas mas cerca del centro
 *   - Colores por tipo de tabla (central, log, catalog, etc.)
 *   - Lineas solidas para FKs, punteadas para relaciones inferidas
 *   - Seleccion de nodos para ver conexiones destacadas
 *   - Panel lateral con detalles de referencias
 *
 * La visualizacion es generada en el cliente usando SVG nativo
 * sin dependencias externas de graficos.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DependencyGraph as DependencyGraphType, TableClassification } from '@/lib/api';
import { getTableTypeColor } from '@/lib/utils';

/** Props del componente DependencyGraph */
interface DependencyGraphProps {
  graph: DependencyGraphType;
  classifications: Record<string, TableClassification>;
}

interface NodePosition {
  x: number;
  y: number;
  table: string;
  type: string;
}

export function DependencyGraph({ graph, classifications }: DependencyGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 400 });
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    if (containerRef.current) {
      const { width } = containerRef.current.getBoundingClientRect();
      setDimensions({ width: Math.max(width, 600), height: 400 });
    }
  }, []);

  // Simple force-directed-like layout
  const tables = Object.keys(graph.nodes);
  const nodePositions: NodePosition[] = [];

  // Calculate positions in a circular layout with some adjustments
  const centerX = dimensions.width / 2;
  const centerY = dimensions.height / 2;
  const radius = Math.min(dimensions.width, dimensions.height) * 0.35;

  tables.forEach((table, index) => {
    const angle = (2 * Math.PI * index) / tables.length - Math.PI / 2;
    const classification = classifications[table];

    // Central tables closer to center
    const distanceFactor = classification?.criticality === 'high' ? 0.6 : 1;

    nodePositions.push({
      x: centerX + radius * distanceFactor * Math.cos(angle),
      y: centerY + radius * distanceFactor * Math.sin(angle),
      table,
      type: classification?.type || 'data',
    });
  });

  const getNodePosition = (tableName: string) =>
    nodePositions.find((n) => n.table === tableName);

  const getNodeColor = (type: string) => {
    const colors: Record<string, string> = {
      central: '#8b5cf6',
      log: '#6b7280',
      catalog: '#22c55e',
      junction: '#3b82f6',
      transactional: '#f97316',
      data: '#64748b',
    };
    return colors[type] || colors.data;
  };

  const selectedNodeInfo = selectedNode ? graph.nodes[selectedNode] : null;

  return (
    <Card padding="none">
      <div className="p-4 border-b border-[var(--border)]">
        <CardHeader className="p-0 pb-2">
          <CardTitle>Dependency Graph</CardTitle>
          <p className="text-sm text-[var(--muted-foreground)]">
            {tables.length} tables, {graph.edges.length} relationships
          </p>
        </CardHeader>
        <div className="flex gap-4 mt-4 flex-wrap">
          <div className="flex items-center gap-2 text-sm">
            <div className="w-3 h-0.5 bg-blue-500"></div>
            <span className="text-[var(--muted-foreground)]">Foreign Key</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <div className="w-3 h-0.5 bg-orange-400 border-dashed border-t-2 border-orange-400"></div>
            <span className="text-[var(--muted-foreground)]">Inferred</span>
          </div>
        </div>
      </div>

      <div className="flex">
        <div ref={containerRef} className="flex-1 overflow-auto">
          <svg
            width={dimensions.width}
            height={dimensions.height}
            className="bg-[var(--secondary)]"
          >
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#64748b" />
              </marker>
              <marker
                id="arrowhead-inferred"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#f97316" />
              </marker>
            </defs>

            {/* Draw edges */}
            {graph.edges.map((edge, index) => {
              const from = getNodePosition(edge.from);
              const to = getNodePosition(edge.to);
              if (!from || !to) return null;

              const isInferred = edge.type === 'inferred';
              const isHighlighted =
                selectedNode === edge.from || selectedNode === edge.to;

              return (
                <line
                  key={index}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={isInferred ? '#f97316' : '#3b82f6'}
                  strokeWidth={isHighlighted ? 2 : 1}
                  strokeDasharray={isInferred ? '5,5' : undefined}
                  opacity={selectedNode && !isHighlighted ? 0.2 : 0.6}
                  markerEnd={isInferred ? 'url(#arrowhead-inferred)' : 'url(#arrowhead)'}
                />
              );
            })}

            {/* Draw nodes */}
            {nodePositions.map((node) => {
              const isSelected = selectedNode === node.table;
              const isConnected =
                selectedNode &&
                (graph.nodes[selectedNode]?.references.includes(node.table) ||
                  graph.nodes[selectedNode]?.referenced_by.includes(node.table) ||
                  graph.nodes[selectedNode]?.inferred.includes(node.table) ||
                  graph.nodes[node.table]?.references.includes(selectedNode) ||
                  graph.nodes[node.table]?.referenced_by.includes(selectedNode) ||
                  graph.nodes[node.table]?.inferred.includes(selectedNode));

              const opacity = selectedNode && !isSelected && !isConnected ? 0.3 : 1;

              return (
                <g
                  key={node.table}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={() => setSelectedNode(isSelected ? null : node.table)}
                  className="cursor-pointer"
                  opacity={opacity}
                >
                  <circle
                    r={isSelected ? 28 : 24}
                    fill={getNodeColor(node.type)}
                    stroke={isSelected ? '#fff' : 'transparent'}
                    strokeWidth={2}
                    className="transition-all duration-200"
                  />
                  <text
                    textAnchor="middle"
                    dy="0.3em"
                    fill="white"
                    fontSize="10"
                    fontWeight="500"
                    className="pointer-events-none"
                  >
                    {node.table.length > 10
                      ? node.table.substring(0, 8) + '...'
                      : node.table}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Side panel for selected node */}
        {selectedNodeInfo && (
          <div className="w-64 border-l border-[var(--border)] p-4 bg-[var(--card)]">
            <h4 className="font-semibold text-[var(--card-foreground)] mb-2">
              {selectedNode}
            </h4>
            <Badge className={getTableTypeColor(classifications[selectedNode!]?.type || 'data')}>
              {classifications[selectedNode!]?.type || 'data'}
            </Badge>

            {selectedNodeInfo.references.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">
                  References ({selectedNodeInfo.references.length})
                </p>
                <ul className="text-sm space-y-1">
                  {selectedNodeInfo.references.map((ref) => (
                    <li key={ref} className="text-[var(--card-foreground)]">
                      → {ref}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selectedNodeInfo.referenced_by.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">
                  Referenced by ({selectedNodeInfo.referenced_by.length})
                </p>
                <ul className="text-sm space-y-1">
                  {selectedNodeInfo.referenced_by.map((ref) => (
                    <li key={ref} className="text-[var(--card-foreground)]">
                      ← {ref}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selectedNodeInfo.inferred.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-[var(--muted-foreground)] mb-1">
                  Inferred ({selectedNodeInfo.inferred.length})
                </p>
                <ul className="text-sm space-y-1">
                  {selectedNodeInfo.inferred.map((ref) => (
                    <li key={ref} className="text-orange-500">
                      ⤳ {ref}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
