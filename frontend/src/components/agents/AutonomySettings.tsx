/**
 * PG Index Agents - Componente AutonomySettings
 * https://github.com/686f6c61/pg-index-agents
 *
 * Panel de configuracion del nivel de autonomia de los agentes.
 * Controla cuantas acciones pueden ejecutar los agentes sin
 * requerir aprobacion humana.
 *
 * Niveles de autonomia:
 *   - observation: Solo analiza e informa, sin modificaciones
 *   - assisted: Propone acciones que requieren aprobacion manual
 *   - trust: Ejecuta acciones de bajo riesgo automaticamente
 *   - autonomous: Control total sin aprobacion (solo desarrollo)
 *
 * Acciones por nivel:
 *   - observation: Ninguna ejecucion de SQL
 *   - assisted: Todo requiere aprobacion
 *   - trust: CREATE INDEX CONCURRENTLY y ANALYZE automaticos
 *   - autonomous: DROP INDEX, REINDEX, etc. sin aprobacion
 *
 * La configuracion se persiste en el backend y puede ser global
 * o especifica por base de datos.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState, useEffect } from 'react';
import { Shield, Eye, UserCheck, Zap, Bot, RefreshCw } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { api, AutonomyLevel } from '@/lib/api';

/** Props del componente AutonomySettings */
interface AutonomySettingsProps {
  databaseId?: number;
  onLevelChange?: (level: AutonomyLevel) => void;
}

const autonomyLevels: {
  level: AutonomyLevel;
  name: string;
  description: string;
  details: string;
  icon: typeof Eye;
  color: string;
  riskLevel: string;
}[] = [
  {
    level: 'observation',
    name: 'Observacion',
    description: 'Solo observa e informa. No ejecuta acciones.',
    details: 'Los agentes analizan la base de datos y generan informes, pero no realizan ninguna modificacion. Ideal para auditorias y evaluaciones iniciales.',
    icon: Eye,
    color: 'text-blue-500',
    riskLevel: 'Seguro',
  },
  {
    level: 'assisted',
    name: 'Asistido',
    description: 'Propone acciones, pero requiere aprobacion humana.',
    details: 'Los agentes generan propuestas de indices y mantenimiento que deben ser aprobadas manualmente antes de ejecutarse. Recomendado para produccion.',
    icon: UserCheck,
    color: 'text-green-500',
    riskLevel: 'Riesgo Bajo',
  },
  {
    level: 'trust',
    name: 'Confianza',
    description: 'Ejecuta acciones de bajo riesgo automaticamente.',
    details: 'Ejecuta automaticamente ANALYZE y CREATE INDEX CONCURRENTLY. Las operaciones de alto riesgo (DROP INDEX, REINDEX) requieren aprobacion.',
    icon: Zap,
    color: 'text-yellow-500',
    riskLevel: 'Riesgo Medio',
  },
  {
    level: 'autonomous',
    name: 'Autonomo',
    description: 'Ejecuta todas las acciones sin aprobacion.',
    details: 'Los agentes tienen control total para crear, eliminar y reindexar. Solo usar en entornos de desarrollo o con supervision activa.',
    icon: Bot,
    color: 'text-red-500',
    riskLevel: 'Riesgo Alto',
  },
];

export function AutonomySettings({ databaseId, onLevelChange }: AutonomySettingsProps) {
  const [currentLevel, setCurrentLevel] = useState<AutonomyLevel>('assisted');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchConfig = async () => {
      setLoading(true);
      try {
        const config = await api.getAutonomyConfig(databaseId);
        setCurrentLevel(config.level);
      } catch (error) {
        console.error('Failed to fetch autonomy config:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, [databaseId]);

  const handleLevelChange = async (level: AutonomyLevel) => {
    setSaving(true);
    try {
      await api.setAutonomyLevel(level, databaseId);
      setCurrentLevel(level);
      onLevelChange?.(level);
    } catch (error) {
      console.error('Failed to set autonomy level:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="flex items-center justify-center py-8">
        <RefreshCw className="h-6 w-6 animate-spin text-[var(--primary)]" />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <Shield className="h-5 w-5 text-[var(--primary)]" />
        <h3 className="text-lg font-semibold text-[var(--card-foreground)]">
          Nivel de Autonomia
        </h3>
      </div>

      <p className="text-sm text-[var(--muted-foreground)] mb-4">
        Controla cuanta autonomia tienen los agentes al ejecutar acciones sobre la base de datos.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {autonomyLevels.map((item) => {
          const Icon = item.icon;
          const isSelected = currentLevel === item.level;

          return (
            <button
              key={item.level}
              onClick={() => handleLevelChange(item.level)}
              disabled={saving}
              className={`
                p-4 rounded-lg border-2 text-left transition-all
                ${isSelected
                  ? 'border-[var(--primary)] bg-[var(--primary)]/5'
                  : 'border-[var(--border)] hover:border-[var(--muted-foreground)]'
                }
                ${saving ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              `}
            >
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${isSelected ? 'bg-[var(--primary)]/10' : 'bg-[var(--secondary)]'}`}>
                  <Icon className={`h-5 w-5 ${isSelected ? 'text-[var(--primary)]' : item.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[var(--card-foreground)]">
                      {item.name}
                    </span>
                    {isSelected && (
                      <Badge variant="success" size="sm">Activo</Badge>
                    )}
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)] mt-1">
                    {item.description}
                  </p>
                  {isSelected && (
                    <p className="text-xs text-[var(--foreground)] mt-2 p-2 bg-[var(--secondary)] rounded">
                      {item.details}
                    </p>
                  )}
                  <Badge
                    variant={
                      item.riskLevel === 'Seguro' ? 'info' :
                      item.riskLevel === 'Riesgo Bajo' ? 'success' :
                      item.riskLevel === 'Riesgo Medio' ? 'warning' : 'danger'
                    }
                    size="sm"
                    className="mt-2"
                  >
                    {item.riskLevel}
                  </Badge>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-4 p-3 bg-[var(--secondary)] rounded-lg">
        <p className="text-xs text-[var(--muted-foreground)]">
          <strong>Nota:</strong> Los niveles de autonomia mas altos permiten a los agentes ejecutar
          operaciones en la base de datos sin aprobacion. Usar con precaucion en entornos de produccion.
        </p>
      </div>
    </Card>
  );
}
