/**
 * PG Index Agents - Pagina de actividad
 * https://github.com/686f6c61/pg-index-agents
 *
 * Panel de monitoreo de trabajos en background y logs del sistema.
 * Muestra el estado de los agentes ejecutandose, permite cancelar
 * jobs activos, y consultar el historial de operaciones.
 *
 * Funcionalidades:
 *   - Lista de jobs con filtros (all, running, completed, failed)
 *   - Auto-refresh cada 5 segundos (configurable)
 *   - Indicadores de progreso para jobs en ejecucion
 *   - Panel de logs con colores por nivel (INFO, WARNING, ERROR)
 *   - Cancelacion de jobs desde la interfaz
 *
 * Los jobs representan ejecuciones de agentes y se almacenan en
 * la base de datos SQLite de estado interno.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, Job, LogEntry, Database } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  RefreshCw,
  AlertTriangle,
  Search,
  Compass,
  Eye,
  PenTool,
  Wrench,
  Play
} from 'lucide-react';

const AGENT_ICONS: Record<string, React.ReactNode> = {
  explorer: <Compass className="h-4 w-4" />,
  observer: <Eye className="h-4 w-4" />,
  architect: <PenTool className="h-4 w-4" />,
  gardener: <Wrench className="h-4 w-4" />,
  all: <Play className="h-4 w-4" />,
};

const AGENT_LABELS: Record<string, string> = {
  explorer: 'Explorer',
  observer: 'Observer',
  architect: 'Architect',
  gardener: 'Gardener',
  all: 'Full Analysis',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  running: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  completed: 'bg-green-500/10 text-green-500 border-green-500/20',
  failed: 'bg-red-500/10 text-red-500 border-red-500/20',
  cancelled: 'bg-gray-500/10 text-gray-500 border-gray-500/20',
};

const LOG_LEVEL_COLORS: Record<string, string> = {
  INFO: 'text-blue-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-gray-400',
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(startStr: string | null, endStr: string | null): string {
  if (!startStr) return '-';
  const start = new Date(startStr);
  const end = endStr ? new Date(endStr) : new Date();
  const diffMs = end.getTime() - start.getTime();
  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

export default function ActivityPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [databases, setDatabases] = useState<Database[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'running' | 'completed' | 'failed'>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [jobsData, logsData, dbsData] = await Promise.all([
        api.listJobs(undefined, filter === 'all' ? undefined : filter),
        api.getLogs(undefined, undefined, 50),
        api.listDatabases(),
      ]);
      setJobs(jobsData);
      setLogs(logsData);
      setDatabases(dbsData);
    } catch (error) {
      console.error('Error fetching activity data:', error);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchData();

    // Auto-refresh every 5 seconds if enabled
    let interval: NodeJS.Timeout | null = null;
    if (autoRefresh) {
      interval = setInterval(fetchData, 5000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchData, autoRefresh]);

  const getDatabaseName = (dbId: number | null): string => {
    if (!dbId) return 'System';
    const db = databases.find((d) => d.id === dbId);
    return db?.name || `DB ${dbId}`;
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      await api.cancelJob(jobId);
      fetchData();
    } catch (error) {
      console.error('Error cancelling job:', error);
    }
  };

  const runningJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Activity</h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            Monitor background jobs and system logs
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </Button>
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* Running Jobs Summary */}
      {runningJobs.length > 0 && (
        <Card padding="none" className="border-blue-500/20 bg-blue-500/5">
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
              <span className="font-medium text-blue-500">
                {runningJobs.length} job{runningJobs.length !== 1 ? 's' : ''} running
              </span>
              <div className="flex-1 flex items-center gap-2 flex-wrap">
                {runningJobs.map((job) => (
                  <Badge key={job.id} className={STATUS_COLORS[job.status]}>
                    {AGENT_ICONS[job.agent]}
                    <span className="ml-1">{AGENT_LABELS[job.agent] || job.agent}</span>
                    {job.current_step && (
                      <span className="ml-1 opacity-70">- {job.current_step}</span>
                    )}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Jobs Panel */}
        <Card padding="none">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Background Jobs
              </CardTitle>
              <div className="flex gap-1">
                {(['all', 'running', 'completed', 'failed'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      filter === f
                        ? 'bg-[var(--primary)] text-white'
                        : 'bg-[var(--muted)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]'
                    }`}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loading && jobs.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-[var(--muted-foreground)]" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-8 text-[var(--muted-foreground)]">
                <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No jobs found</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    className="p-3 rounded-lg bg-[var(--muted)] border border-[var(--border)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="p-1.5 rounded bg-[var(--background)]">
                          {AGENT_ICONS[job.agent] || <Clock className="h-4 w-4" />}
                        </div>
                        <div>
                          <div className="font-medium text-sm">
                            {AGENT_LABELS[job.agent] || job.agent}
                          </div>
                          <div className="text-xs text-[var(--muted-foreground)]">
                            {getDatabaseName(job.database_id)}
                          </div>
                        </div>
                      </div>
                      <Badge className={STATUS_COLORS[job.status]}>
                        {job.status === 'running' && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                        {job.status === 'completed' && <CheckCircle className="h-3 w-3 mr-1" />}
                        {job.status === 'failed' && <XCircle className="h-3 w-3 mr-1" />}
                        {job.status === 'cancelled' && <XCircle className="h-3 w-3 mr-1" />}
                        {job.status === 'pending' && <Clock className="h-3 w-3 mr-1" />}
                        {job.status}
                      </Badge>
                    </div>

                    {job.status === 'running' && job.current_step && (
                      <div className="mt-2">
                        <div className="text-xs text-[var(--muted-foreground)] mb-1">
                          Step: {job.current_step}
                        </div>
                        <div className="h-1.5 bg-[var(--background)] rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 transition-all duration-300"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {job.error && (
                      <div className="mt-2 p-2 rounded bg-red-500/10 border border-red-500/20">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                          <span className="text-xs text-red-400">{job.error}</span>
                        </div>
                      </div>
                    )}

                    <div className="mt-2 flex items-center justify-between text-xs text-[var(--muted-foreground)]">
                      <span>Started: {formatDate(job.started_at || job.created_at)}</span>
                      <span>
                        Duration: {formatDuration(job.started_at || job.created_at, job.completed_at)}
                      </span>
                    </div>

                    {(job.status === 'running' || job.status === 'pending') && (
                      <div className="mt-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full text-xs"
                          onClick={() => handleCancelJob(job.id)}
                        >
                          <XCircle className="h-3 w-3 mr-1" />
                          Cancel
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Logs Panel */}
        <Card padding="none">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              System Logs
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading && logs.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-[var(--muted-foreground)]" />
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-8 text-[var(--muted-foreground)]">
                <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No logs found</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[500px] overflow-y-auto font-mono text-xs">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className="p-2 rounded bg-[var(--muted)] border border-[var(--border)]"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-[var(--muted-foreground)] shrink-0">
                        {formatDate(log.created_at).split(' ')[1]}
                      </span>
                      <span className={`font-bold shrink-0 ${LOG_LEVEL_COLORS[log.level] || 'text-gray-400'}`}>
                        [{log.level}]
                      </span>
                      <span className="text-[var(--primary)] shrink-0">{log.agent}</span>
                      <span className="text-[var(--foreground)] break-all">{log.message}</span>
                    </div>
                    {log.database_id && (
                      <div className="mt-1 text-[var(--muted-foreground)]">
                        Database: {getDatabaseName(log.database_id)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
